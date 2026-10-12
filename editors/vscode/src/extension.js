const vscode = require('vscode');
const { runCli } = require('./runner');
const { parseReport, location, within } = require('./report');
const { Scheduler } = require('./scheduler');

function activate(context) {
  const output = vscode.window.createOutputChannel('skillsaw');
  const folders = new Map();
  const config = (folder) => vscode.workspace.getConfiguration('skillsaw', folder.uri);
  const bounded = (value, fallback, min, max) =>
    Number.isInteger(value) ? Math.min(max, Math.max(min, value)) : fallback;
  const severity = {
    error: vscode.DiagnosticSeverity.Error,
    warning: vscode.DiagnosticSeverity.Warning,
    info: vscode.DiagnosticSeverity.Information,
  };
  const scheduler = new Scheduler(
    async (options) => {
      if (!vscode.workspace.isTrusted)
        throw new Error('Trust the workspace before running skillsaw.');
      const result = await runCli(options);
      if (result.stderr) output.appendLine(`[${options.cwd}] ${result.stderr}`);
      try {
        return { ...result, report: parseReport(result.stdout) };
      } catch (error) {
        output.appendLine(
          `[${options.cwd}] stdout (first 4000 characters): ${result.stdout.slice(0, 4000)}`,
        );
        throw error;
      }
    },
    (key, { code, report }) => {
      const state = folders.get(key);
      if (!state) return;
      const dirty = new Set(
        vscode.workspace.textDocuments
          .filter((doc) => doc.isDirty)
          .map((doc) => doc.uri.toString()),
      );
      const grouped = new Map();
      for (const finding of report.violations) {
        const target = location(state.folder.uri.fsPath, finding);
        const uri = vscode.Uri.file(target.file);
        if (dirty.has(uri.toString())) continue;
        const diagnostic = new vscode.Diagnostic(
          new vscode.Range(target.line, 0, target.line, 0),
          target.message,
          severity[finding.severity],
        );
        diagnostic.code = finding.rule_id;
        diagnostic.source = 'skillsaw';
        const item = grouped.get(uri.toString()) ?? [uri, []];
        item[1].push(diagnostic);
        grouped.set(uri.toString(), item);
      }
      state.diagnostics.clear();
      state.diagnostics.set([...grouped.values()]);
      state.error = null;
      output.appendLine(
        `[${state.folder.name}] exit ${code}; ${report.violations.length} findings (skillsaw ${report.version}).`,
      );
    },
    (key, error) => {
      const state = folders.get(key);
      if (!state) return;
      state.diagnostics.clear();
      output.appendLine(`[${state.folder.name}] ${error.message}`);
      if (state.error !== error.message) {
        state.error = error.message;
        void vscode.window
          .showErrorMessage(`skillsaw (${state.folder.name}): ${error.message}`, 'Show Output')
          .then((choice) => {
            if (choice === 'Show Output') output.show();
          });
      }
    },
  );

  function invalidate(state) {
    scheduler.invalidate(state.folder.uri.toString());
    state.diagnostics.clear();
  }
  function request(state, explicit = false) {
    invalidate(state);
    if (!vscode.workspace.isTrusted) return;
    const settings = config(state.folder);
    if (!explicit && !settings.get('runOnSave', true)) return;
    scheduler.request(
      state.folder.uri.toString(),
      {
        executable: settings.get('executable', 'skillsaw'),
        cwd: state.folder.uri.fsPath,
        timeoutMs: bounded(settings.get('timeoutMs'), 30000, 1000, 300000),
      },
      explicit ? 0 : bounded(settings.get('debounceMs'), 600, 100, 10000),
    );
  }
  function affected(uris, callback) {
    for (const state of folders.values()) {
      if (uris.some((uri) => uri.scheme === 'file' && within(state.folder.uri.fsPath, uri.fsPath)))
        callback(state);
    }
  }
  function syncFolders() {
    const current = new Map(
      (vscode.workspace.workspaceFolders ?? [])
        .filter((folder) => folder.uri.scheme === 'file')
        .map((folder) => [folder.uri.toString(), folder]),
    );
    for (const [key, state] of folders) {
      if (!current.has(key)) {
        invalidate(state);
        state.diagnostics.dispose();
        folders.delete(key);
      }
    }
    for (const [key, folder] of current) {
      if (!folders.has(key)) {
        const state = {
          folder,
          diagnostics: vscode.languages.createDiagnosticCollection('skillsaw'),
          error: null,
        };
        folders.set(key, state);
        request(state);
      }
    }
  }
  context.subscriptions.push(
    output,
    scheduler,
    {
      dispose() {
        for (const state of folders.values()) state.diagnostics.dispose();
        folders.clear();
      },
    },
    vscode.commands.registerCommand('skillsaw.showOutput', () => output.show()),
    vscode.commands.registerCommand('skillsaw.lint', () => {
      if (!vscode.workspace.isTrusted) {
        void vscode.window.showWarningMessage('Trust the workspace before running skillsaw.');
        return;
      }
      if (!folders.size) {
        void vscode.window.showWarningMessage(
          'Open a folder on the extension host filesystem to lint with skillsaw.',
        );
        return;
      }
      for (const state of folders.values()) request(state, true);
    }),
    vscode.workspace.onDidSaveTextDocument((doc) => affected([doc.uri], request)),
    vscode.workspace.onDidChangeTextDocument((event) => {
      if (event.contentChanges.length) affected([event.document.uri], invalidate);
    }),
    vscode.workspace.onDidCloseTextDocument((doc) => affected([doc.uri], request)),
    vscode.workspace.onDidCreateFiles((event) => affected(event.files, request)),
    vscode.workspace.onDidDeleteFiles((event) => affected(event.files, request)),
    vscode.workspace.onDidRenameFiles((event) =>
      affected(
        event.files.flatMap((file) => [file.oldUri, file.newUri]),
        request,
      ),
    ),
    vscode.workspace.onDidChangeWorkspaceFolders(syncFolders),
    vscode.workspace.onDidGrantWorkspaceTrust(() => {
      for (const state of folders.values()) request(state);
    }),
    vscode.workspace.onDidChangeConfiguration((event) => {
      for (const state of folders.values())
        if (event.affectsConfiguration('skillsaw', state.folder.uri)) request(state);
    }),
  );
  syncFolders();
}

module.exports = { activate };

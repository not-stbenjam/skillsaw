const { test } = require('node:test');
const assert = require('node:assert/strict');
const Module = require('node:module');
const path = require('node:path');
const fs = require('node:fs/promises');
const os = require('node:os');
const { setTimeout: delay } = require('node:timers/promises');

async function until(predicate) {
  const deadline = Date.now() + 3000;
  while (!predicate()) {
    assert(Date.now() < deadline, 'expected extension event');
    await delay(10);
  }
}

function harness(t, trusted = true, roots = ['one', 'two']) {
  const events = {},
    commands = {},
    runs = [],
    errors = [],
    logs = [],
    collections = [];
  const uri = (file) => ({
    scheme: 'file',
    fsPath: path.resolve(file),
    toString() {
      return this.fsPath;
    },
  });
  const folder = (name) => ({ name, uri: uri(name) });
  const settings = new Map();
  const register = (key) => (callback) => {
    events[key] = callback;
    return { dispose() {} };
  };
  const workspace = {
    isTrusted: trusted,
    workspaceFolders: roots.map(folder),
    textDocuments: [],
    getConfiguration: (_, resource) => ({
      get: (key, fallback) =>
        settings.get(resource.toString())?.[key] ?? (key === 'debounceMs' ? 100 : fallback),
    }),
  };
  for (const name of [
    'onDidOpenTextDocument',
    'onDidSaveTextDocument',
    'onDidChangeTextDocument',
    'onDidCloseTextDocument',
    'onDidCreateFiles',
    'onDidDeleteFiles',
    'onDidRenameFiles',
    'onDidChangeWorkspaceFolders',
    'onDidGrantWorkspaceTrust',
    'onDidChangeConfiguration',
  ])
    workspace[name] = register(name);
  const vscode = {
    workspace,
    Uri: { file: uri },
    DiagnosticSeverity: { Error: 0, Warning: 1, Information: 2 },
    Range: class {
      constructor(line) {
        this.start = { line };
      }
    },
    Diagnostic: class {
      constructor(range, message, severity) {
        Object.assign(this, { range, message, severity });
      }
    },
    commands: {
      registerCommand(name, callback) {
        commands[name] = callback;
        return { dispose() {} };
      },
    },
    window: {
      createOutputChannel: () => ({
        appendLine: (line) => logs.push(line),
        show() {},
        dispose() {},
      }),
      showErrorMessage: async (message) => {
        errors.push(message);
      },
      showWarningMessage: async (message) => {
        errors.push(message);
      },
    },
    languages: {
      createDiagnosticCollection() {
        const collection = {
          entries: [],
          updates: 0,
          clear() {
            this.entries = [];
          },
          set(entries) {
            this.entries = entries;
            this.updates++;
          },
          dispose() {
            this.clear();
            this.disposed = true;
          },
        };
        collections.push(collection);
        return collection;
      },
    },
  };
  const original = Module._load;
  const extensionPath = require.resolve('../src/extension');
  delete require.cache[extensionPath];
  Module._load = function (name, ...args) {
    if (name === 'vscode') return vscode;
    if (name === './runner')
      return {
        runCli: (options) =>
          new Promise((resolve, reject) => runs.push({ ...options, resolve, reject })),
      };
    return original.call(this, name, ...args);
  };
  let activate;
  try {
    ({ activate } = require(extensionPath));
  } finally {
    Module._load = original;
  }
  const context = { subscriptions: [] };
  activate(context);
  t.after(() => {
    for (const sub of context.subscriptions) sub.dispose();
    delete require.cache[extensionPath];
  });
  const complete = (index, violations = []) =>
    runs[index].resolve({
      code: violations.length ? 1 : 0,
      stderr: '',
      stdout: JSON.stringify({
        version: '0.21.1',
        stats: {},
        summary: { errors: violations.length, warnings: 0, info: 0 },
        violations,
      }),
    });
  return {
    events,
    commands,
    runs,
    errors,
    logs,
    collections,
    workspace,
    settings,
    uri,
    folder,
    complete,
  };
}
const finding = {
  rule_id: 'agentskill-name',
  severity: 'error',
  message: 'Use kebab-case.',
  file_path: 'skills/release-notes/SKILL.md',
  line: 2,
};

test('trust blocks activation, save, configuration and command paths until granted', async (t) => {
  const h = harness(t, false);
  h.events.onDidSaveTextDocument({ uri: h.uri('one/SKILL.md') });
  h.events.onDidChangeTextDocument({
    document: { uri: h.uri('one/SKILL.md'), isDirty: false },
    contentChanges: [{}],
  });
  h.events.onDidChangeConfiguration({ affectsConfiguration: () => true });
  h.commands['skillsaw.lint']();
  await delay(150);
  assert.equal(h.runs.length, 0);
  assert.match(h.errors[0], /Trust/);
  h.workspace.isTrusted = true;
  h.events.onDidGrantWorkspaceTrust();
  await delay(150);
  assert.equal(h.runs.length, 1);
});

test('collections replace old results independently and errors clear stale findings', async (t) => {
  const h = harness(t);
  await delay(150);
  h.complete(0, [finding]);
  await until(() => h.runs.length === 2);
  h.complete(1, [finding]);
  await until(() => h.collections[1].entries.length === 1);
  assert.equal(h.collections[0].entries[0][1][0].code, 'agentskill-name');
  h.events.onDidSaveTextDocument({ uri: h.uri('one/arbitrary.extension') });
  assert.equal(h.collections[0].entries.length, 0);
  assert.equal(h.collections[1].entries.length, 1);
  await delay(150);
  h.complete(2);
  await delay(0);
  assert.equal(h.collections[0].entries.length, 0);
  h.events.onDidSaveTextDocument({ uri: h.uri('two/.skillsaw.yaml') });
  await delay(150);
  h.runs[3].resolve({ code: 1, stdout: 'bad report', stderr: 'bad config' });
  await delay(0);
  assert.equal(h.collections[1].entries.length, 0);
  assert.match(h.errors[0], /Invalid skillsaw JSON/);
  assert(h.logs.some((entry) => entry.includes('bad config')));
  assert(h.logs.some((entry) => entry.includes('bad report')));
});

test('edits, settings and removal invalidate in-flight results; folder add starts its own run', async (t) => {
  const h = harness(t);
  await delay(150);
  h.events.onDidChangeTextDocument({
    document: { uri: h.uri('one/SKILL.md'), isDirty: true },
    contentChanges: [{}],
  });
  assert.equal(h.runs[0].signal.aborted, true);
  h.complete(0, [finding]);
  await until(() => h.runs.length === 2);
  assert.equal(h.collections[0].entries.length, 0);
  h.settings.set(h.uri('two').toString(), { executable: 'changed-skillsaw', runOnSave: false });
  h.events.onDidChangeConfiguration({
    affectsConfiguration: (_, uri) => uri.toString() === h.uri('two').toString(),
  });
  assert.equal(h.runs[1].signal.aborted, true);
  h.complete(1, [finding]);
  await delay(0);
  h.workspace.workspaceFolders = [h.workspace.workspaceFolders[0], h.folder('three')];
  h.events.onDidChangeWorkspaceFolders();
  assert.equal(h.collections[1].disposed, true);
  await delay(150);
  assert.equal(h.runs[2].cwd, path.resolve('three'));
  h.complete(2);
  await delay(0);
});

test('manual runs suppress diagnostics for dirty buffers and use per-folder executable settings', async (t) => {
  const h = harness(t);
  h.settings.set(h.uri('one').toString(), { executable: '/custom/skillsaw', runOnSave: false });
  h.settings.set(h.uri('two').toString(), { runOnSave: false });
  h.events.onDidChangeConfiguration({ affectsConfiguration: () => true });
  h.workspace.textDocuments = [{ uri: h.uri('one/skills/release-notes/SKILL.md'), isDirty: true }];
  h.commands['skillsaw.lint']();
  await delay(10);
  assert.equal(h.runs[0].executable, '/custom/skillsaw');
  h.complete(0, [finding]);
  await until(() => h.runs.length === 2);
  assert.equal(h.collections[0].entries.length, 0);
  h.workspace.workspaceFolders = [h.workspace.workspaceFolders[0]];
  h.events.onDidChangeWorkspaceFolders();
  assert.equal(h.runs[1].signal.aborted, true);
  h.complete(1, [finding]);
  await delay(0);
  assert.equal(h.collections[1].entries.length, 0);
});

test('a clean disk reload replaces a pending save without linting dirty buffers', async (t) => {
  const h = harness(t, true, ['one']);
  const doc = { uri: h.uri('one/skills/release-notes/SKILL.md'), isDirty: false };
  await until(() => h.runs.length === 1);
  h.complete(0, [finding]);
  await until(() => h.collections[0].entries.length === 1);
  h.events.onDidSaveTextDocument(doc);
  await until(() => h.runs.length === 2);
  h.events.onDidChangeTextDocument({ document: doc, contentChanges: [{}] });
  assert(h.runs[1].signal.aborted, 'discard the report started before the reload');
  h.complete(1, [finding]);
  await until(() => h.runs.length === 3);
  h.complete(2, [finding]);
  await until(() => h.collections[0].entries.length === 1);

  doc.isDirty = true;
  h.events.onDidChangeTextDocument({ document: doc, contentChanges: [{}] });
  assert.equal(h.collections[0].entries.length, 0);
  await delay(150);
  assert.equal(h.runs.length, 3, 'dirty-buffer changes must not start lint');
  h.settings.set(h.uri('one').toString(), { runOnSave: false });
  doc.isDirty = false;
  h.events.onDidChangeTextDocument({ document: doc, contentChanges: [{}] });
  await delay(150);
  assert.equal(h.runs.length, 3, 'command-only mode must not lint disk reloads');
});

test('clean tab closes preserve pending and published command-only diagnostics', async (t) => {
  const h = harness(t, true, ['one']);
  h.settings.set(h.uri('one').toString(), { runOnSave: false });
  h.events.onDidChangeConfiguration({ affectsConfiguration: () => true });
  const doc = { uri: h.uri('one/skills/release-notes/SKILL.md'), isDirty: false };
  h.workspace.textDocuments = [doc];
  h.commands['skillsaw.lint']();
  await until(() => h.runs.length === 1);
  h.workspace.textDocuments = [];
  h.events.onDidCloseTextDocument(doc);
  assert.equal(h.runs[0].signal.aborted, false, 'closing a clean tab must not cancel manual lint');
  h.complete(0, [finding]);
  await until(() => h.collections[0].entries.length === 1);
  h.workspace.textDocuments = [doc];
  h.events.onDidOpenTextDocument(doc);
  h.workspace.textDocuments = [];
  h.events.onDidCloseTextDocument(doc);
  await delay(150);
  assert.equal(h.collections[0].entries.length, 1, 'manual findings survive clean tab navigation');
  assert.equal(h.runs.length, 1, 'command-only mode must not queue a replacement');

  h.settings.set(h.uri('one').toString(), { runOnSave: true });
  h.events.onDidCloseTextDocument(doc);
  assert.equal(h.collections[0].entries.length, 0, 'automatic mode still refreshes on close');
  await until(() => h.runs.length === 2);
  h.complete(1);
});

test('cached manual reports stay invalidated after file, settings and folder changes', async (t) => {
  const h = harness(t, true, ['one']);
  h.settings.set(h.uri('one').toString(), { runOnSave: false });
  h.events.onDidChangeConfiguration({ affectsConfiguration: () => true });
  const doc = { uri: h.uri('one/skills/release-notes/SKILL.md'), isDirty: false };
  h.workspace.textDocuments = [doc];
  const changes = [
    () => h.events.onDidSaveTextDocument(doc),
    () => h.events.onDidDeleteFiles({ files: [doc.uri] }),
    () => h.events.onDidChangeConfiguration({ affectsConfiguration: () => true }),
    () => {
      h.workspace.workspaceFolders = [];
      h.events.onDidChangeWorkspaceFolders();
    },
  ];
  for (const change of changes) {
    const index = h.runs.length;
    h.commands['skillsaw.lint']();
    await until(() => h.runs.length === index + 1);
    h.complete(index, [finding]);
    await until(() => h.collections[0].entries.length === 1);
    h.events.onDidOpenTextDocument(doc);
    change();
    h.workspace.textDocuments = [];
    h.events.onDidCloseTextDocument(doc);
    await delay(50);
    assert.equal(h.collections[0].entries.length, 0, 'cancel the mapping in progress');
    h.workspace.textDocuments = [doc];
    h.events.onDidOpenTextDocument(doc);
    await delay(50);
    assert.equal(h.collections[0].entries.length, 0, 'discard the invalidated cached report');
    assert.equal(h.runs.length, index + 1, 'only the explicit command runs lint');
  }
  assert(h.collections[0].disposed);
});

test(
  'command-only findings follow newly opened aliases without another CLI run',
  { skip: process.platform === 'win32' },
  async (t) => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'skillsaw manual aliases '));
    t.after(() => fs.rm(root, { recursive: true, force: true }));
    await fs.mkdir(path.join(root, 'skills/release-notes'), { recursive: true });
    await fs.writeFile(path.join(root, finding.file_path), 'name: Release_Notes\n');
    await fs.mkdir(path.join(root, '.agents'));
    await fs.symlink('../skills', path.join(root, '.agents/skills'));
    const h = harness(t, true, [root]);
    h.settings.set(h.uri(root).toString(), { runOnSave: false });
    h.events.onDidChangeConfiguration({ affectsConfiguration: () => true });
    const canonical = { uri: h.uri(path.join(root, finding.file_path)), isDirty: false };
    const alias = {
      uri: h.uri(path.join(root, '.agents/skills/release-notes/SKILL.md')),
      isDirty: false,
    };
    const has = (doc) =>
      h.collections[0].entries.some(([uri]) => uri.toString() === doc.uri.toString());
    h.commands['skillsaw.lint']();
    await until(() => h.runs.length === 1);
    h.complete(0, [finding]);
    await until(() => has(canonical));

    h.workspace.textDocuments = [alias];
    h.events.onDidOpenTextDocument(alias);
    await until(() => has(alias));
    h.workspace.textDocuments = [alias, canonical];
    h.events.onDidOpenTextDocument(canonical);
    await until(() => has(alias) && has(canonical));
    assert.equal(h.runs.length, 1, 'opening aliases only remaps the cached manual report');

    // A lookup already in flight must not republish after a subsequent edit.
    h.events.onDidOpenTextDocument(alias);
    alias.isDirty = true;
    h.events.onDidChangeTextDocument({ document: alias, contentChanges: [{}] });
    await delay(150);
    assert.equal(h.collections[0].entries.length, 0);
    alias.isDirty = false;
    h.events.onDidOpenTextDocument(alias);
    await delay(150);
    assert.equal(h.collections[0].entries.length, 0, 'invalidated reports cannot be remapped');
    assert.equal(h.runs.length, 1);
  },
);

test(
  'symlink aliases receive findings and closing the dirty copy restores the others',
  { skip: process.platform === 'win32' },
  async (t) => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'skillsaw documents '));
    t.after(() => fs.rm(root, { recursive: true, force: true }));
    await fs.mkdir(path.join(root, 'skills/release-notes'), { recursive: true });
    await fs.writeFile(path.join(root, finding.file_path), 'name: Release_Notes\n');
    await fs.mkdir(path.join(root, '.agents'));
    await fs.symlink('../skills', path.join(root, '.agents/skills'));
    const h = harness(t, true, [root]);
    const canonical = { uri: h.uri(path.join(root, finding.file_path)), isDirty: false };
    const alias = {
      uri: h.uri(path.join(root, '.agents/skills/release-notes/SKILL.md')),
      isDirty: false,
    };
    h.workspace.textDocuments = [canonical, alias];
    h.events.onDidOpenTextDocument(alias);
    await until(() => h.runs.length === 1);
    h.complete(0, [finding]);
    await until(() => h.collections[0].entries.length === 2);
    assert.deepEqual(
      h.collections[0].entries.map(([uri]) => uri.toString()).sort(),
      [canonical.uri.toString(), alias.uri.toString()].sort(),
    );
    h.settings.set(h.uri(root).toString(), { runOnSave: false });
    h.events.onDidChangeConfiguration({ affectsConfiguration: () => true });
    alias.isDirty = true;
    h.events.onDidChangeTextDocument({ document: alias, contentChanges: [{}] });
    assert.equal(h.collections[0].entries.length, 0);
    h.commands['skillsaw.lint']();
    await until(() => h.runs.length === 2);
    h.complete(1, [finding]);
    await until(() => h.collections[0].updates === 2);
    assert.equal(h.collections[0].entries.length, 0);
    h.workspace.textDocuments = [alias];
    h.events.onDidCloseTextDocument(canonical);
    await until(() => h.collections[0].updates === 3);
    assert.equal(
      h.collections[0].entries.length,
      0,
      'a remaining dirty alias still suppresses findings',
    );
    h.workspace.textDocuments = [canonical, alias];
    h.events.onDidOpenTextDocument(canonical);
    await until(() => h.collections[0].updates === 4);
    assert.equal(h.collections[0].entries.length, 0);
    // The host removes a closed document before firing onDidCloseTextDocument.
    // The disk report remains valid when that removal has no content change.
    h.workspace.textDocuments = [canonical];
    h.events.onDidCloseTextDocument(alias);
    await until(() => h.collections[0].entries.length === 1);
    assert.equal(h.collections[0].entries[0][0].toString(), canonical.uri.toString());
    assert.equal(h.runs.length, 2, 'closing the dirty alias only remaps the cached report');
  },
);

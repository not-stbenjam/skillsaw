// Runs inside the real VS Code extension host, against the installed CLI.
const assert = require('node:assert/strict');
const vscode = require('vscode');

async function until(predicate, message) {
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    if (predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  assert.fail(message);
}
const diagnostics = (uri) =>
  vscode.languages.getDiagnostics(uri).filter((item) => item.source === 'skillsaw');

async function replace(doc, before, after, save = true) {
  const text = doc.getText();
  const index = text.indexOf(before);
  assert.notEqual(index, -1);
  const edit = new vscode.WorkspaceEdit();
  edit.replace(
    doc.uri,
    new vscode.Range(doc.positionAt(index), doc.positionAt(index + before.length)),
    after,
  );
  assert.equal(await vscode.workspace.applyEdit(edit), true);
  if (save) assert.equal(await doc.save(), true);
}

async function run() {
  const extension = vscode.extensions.getExtension('stbenjam.skillsaw');
  assert(extension, 'pilot installed in the extension host');
  await extension.activate();
  const [one, two] = vscode.workspace.workspaceFolders;
  const skill = (folder) => vscode.Uri.joinPath(folder.uri, 'skills/release-notes/SKILL.md');
  const doc1 = await vscode.workspace.openTextDocument(skill(one));
  const doc2 = await vscode.workspace.openTextDocument(skill(two));
  await replace(doc1, 'name: release-notes', 'name: Release_Notes');
  await replace(doc2, 'name: release-notes', 'name: Release_Notes');
  await until(
    () => diagnostics(doc1.uri).length > 0 && diagnostics(doc2.uri).length > 0,
    'save diagnostics in both workspace folders',
  );
  const name = diagnostics(doc1.uri).find((item) => item.code === 'agentskill-name');
  assert(name);
  assert.equal(name.range.start.line, 1);
  assert.equal(name.severity, vscode.DiagnosticSeverity.Error);
  await replace(doc1, 'name: Release_Notes', 'name: release-notes', false);
  await until(
    () => diagnostics(doc1.uri).length === 0,
    'clear diagnostics while a buffer is dirty',
  );
  assert(diagnostics(doc2.uri).length > 0, 'other workspace remains intact');
  await doc1.save();
  const config = await vscode.workspace.openTextDocument(
    vscode.Uri.joinPath(two.uri, '.skillsaw.yaml'),
  );
  await replace(
    config,
    'fail-on: warning',
    'fail-on: warning\nrules:\n  agentskill-name:\n    severity: info',
  );
  await until(
    () =>
      diagnostics(doc2.uri).some(
        (item) =>
          item.code === 'agentskill-name' &&
          item.severity === vscode.DiagnosticSeverity.Information,
      ),
    'saved root configuration changes diagnostics',
  );
  await vscode.workspace
    .getConfiguration('skillsaw', two.uri)
    .update('runOnSave', false, vscode.ConfigurationTarget.WorkspaceFolder);
  await replace(doc2, 'name: Release_Notes', 'name: release-notes');
  await replace(doc2, 'name: release-notes', 'name: Release_Notes');
  await vscode.commands.executeCommand('skillsaw.lint');
  await until(
    () => diagnostics(doc2.uri).length > 0,
    'explicit command runs with runOnSave disabled',
  );
  const deletion = new vscode.WorkspaceEdit();
  deletion.deleteFile(doc2.uri);
  assert.equal(await vscode.workspace.applyEdit(deletion), true);
  await until(() => diagnostics(doc2.uri).length === 0, 'deleted files clear diagnostics');
  console.log(
    'skillsaw extension-host smoke passed: multi-root saves, mappings, config, dirty buffers, command and deletion.',
  );
}

module.exports = { run };

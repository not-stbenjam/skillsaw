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
  const doc1 = await vscode.workspace.openTextDocument(
    vscode.Uri.joinPath(one.uri, '.agents/skills/release-notes/SKILL.md'),
  );
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
  const canonical = await vscode.workspace.openTextDocument(skill(one));
  await until(
    () => diagnostics(doc1.uri).length > 0 && diagnostics(canonical.uri).length > 0,
    'opening another alias maps findings to both open documents',
  );
  await replace(doc1, 'name: Release_Notes', 'name: release-notes', false);
  await until(
    () => diagnostics(doc1.uri).length === 0 && diagnostics(canonical.uri).length === 0,
    'clear diagnostics while a buffer is dirty',
  );
  assert(diagnostics(doc2.uri).length > 0, 'other workspace remains intact');
  await vscode.commands.executeCommand('skillsaw.lint');
  // The global queue processes the first root before the second. A fresh
  // second-root finding proves the dirty-buffer report has also completed.
  await until(() => diagnostics(doc2.uri).length > 0, 'explicit multi-root run completed');
  assert(doc1.isDirty);
  assert.equal(diagnostics(doc1.uri).length, 0);
  assert.equal(diagnostics(canonical.uri).length, 0);
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
  const checklist = vscode.Uri.joinPath(one.uri, 'skills/release-notes/references/checklist.md');
  const moved = vscode.Uri.joinPath(one.uri, 'skills/release-notes/references/moved.md');
  const referenceBroken = () =>
    diagnostics(doc1.uri).some((item) => item.code === 'content-broken-internal-reference');
  const rename = new vscode.WorkspaceEdit();
  rename.renameFile(checklist, moved);
  assert.equal(await vscode.workspace.applyEdit(rename), true);
  await until(referenceBroken, 'rename triggers new findings on a surviving document');
  const restoreName = new vscode.WorkspaceEdit();
  restoreName.renameFile(moved, checklist);
  assert.equal(await vscode.workspace.applyEdit(restoreName), true);
  await until(() => !referenceBroken(), 'restoring the filename clears the finding');
  const checklistText = Buffer.from(await vscode.workspace.fs.readFile(checklist)).toString();
  const removeReference = new vscode.WorkspaceEdit();
  removeReference.deleteFile(checklist);
  assert.equal(await vscode.workspace.applyEdit(removeReference), true);
  await until(referenceBroken, 'deletion triggers new findings on a surviving document');
  const restoreReference = new vscode.WorkspaceEdit();
  restoreReference.createFile(checklist);
  restoreReference.insert(checklist, new vscode.Position(0, 0), checklistText);
  assert.equal(await vscode.workspace.applyEdit(restoreReference), true);
  assert.equal(await (await vscode.workspace.openTextDocument(checklist)).save(), true);
  const newDir = vscode.Uri.joinPath(one.uri, 'skills/new-skill');
  await vscode.workspace.fs.createDirectory(newDir);
  const newSkill = vscode.Uri.joinPath(newDir, 'SKILL.md');
  const create = new vscode.WorkspaceEdit();
  create.createFile(newSkill);
  assert.equal(await vscode.workspace.applyEdit(create), true);
  await until(
    () => diagnostics(newSkill).length > 0,
    'creation discovers an invalid new skill without the explicit command',
  );
  const newDoc = await vscode.workspace.openTextDocument(newSkill);
  const write = new vscode.WorkspaceEdit();
  write.insert(
    newSkill,
    new vscode.Position(0, 0),
    doc1.getText().replace('name: release-notes', 'name: Release_Notes'),
  );
  assert.equal(await vscode.workspace.applyEdit(write), true);
  assert.equal(await newDoc.save(), true);
  await until(
    () => diagnostics(newSkill).some((item) => item.code === 'agentskill-name'),
    'saved new skill uses the existing engine rules',
  );
  assert.equal(referenceBroken(), false, 'restoring the checklist clears its finding');
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
    'skillsaw extension-host smoke passed: multi-root saves, aliases, dirty buffers, config, command, create, rename and delete.',
  );
}

module.exports = { run };

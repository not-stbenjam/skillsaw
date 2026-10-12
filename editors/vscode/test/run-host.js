const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { runTests } = require('@vscode/test-electron');

async function main() {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'skillsaw-vscode-'));
  try {
    const fixture = path.resolve(__dirname, '../../../examples/editor-onboarding');
    for (const name of ['publisher one', 'publisher two'])
      await fs.cp(fixture, path.join(temp, name), { recursive: true });
    const first = path.join(temp, 'publisher one');
    await fs.mkdir(path.join(first, '.agents'));
    await fs.symlink(
      path.join(first, 'skills'),
      path.join(first, '.agents/skills'),
      process.platform === 'win32' ? 'junction' : 'dir',
    );
    const workspace = path.join(temp, 'publisher.code-workspace');
    const executable =
      process.env.SKILLSAW_CLI ||
      path.resolve(
        __dirname,
        '../../../.venv',
        process.platform === 'win32' ? 'Scripts/skillsaw.exe' : 'bin/skillsaw',
      );
    await fs.writeFile(
      workspace,
      JSON.stringify({
        folders: [{ path: 'publisher one' }, { path: 'publisher two' }],
        settings: {
          'skillsaw.executable': executable,
          'skillsaw.debounceMs': 100,
          'files.enableTrash': false,
        },
      }),
    );
    await runTests({
      version: '1.96.4',
      extensionDevelopmentPath: path.resolve(__dirname, '..'),
      extensionTestsPath: path.resolve(__dirname, 'host.js'),
      launchArgs: [
        workspace,
        '--disable-workspace-trust',
        '--skip-welcome',
        '--skip-release-notes',
        '--disable-gpu',
        '--no-sandbox',
        '--user-data-dir',
        path.join(temp, 'user'),
        '--extensions-dir',
        path.join(temp, 'extensions'),
      ],
    });
  } finally {
    await fs.rm(temp, { recursive: true, force: true });
  }
}
main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

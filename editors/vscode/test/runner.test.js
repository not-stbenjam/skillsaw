const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { runCli, LINT_ARGS } = require('../src/runner');

async function fake(t, body) {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'skillsaw process ; '));
  t.after(() => fs.rm(dir, { recursive: true, force: true }));
  const executable = path.join(dir, 'fake cli');
  await fs.writeFile(executable, `#!${process.execPath}\n${body}`, { mode: 0o755 });
  return { cwd: dir, executable, timeoutMs: 2000, signal: new AbortController().signal };
}

test('missing executable and invalid executable settings are meaningful failures', async () => {
  const options = {
    executable: 'skillsaw-absent-6f8ce',
    cwd: os.tmpdir(),
    timeoutMs: 1000,
    signal: new AbortController().signal,
  };
  await assert.rejects(runCli(options), /Cannot find skillsaw executable/);
  await assert.rejects(runCli({ ...options, executable: '' }), /Set skillsaw.executable/);
});

// These fake entry points need POSIX shebang support. On Windows the pilot
// invokes the skillsaw.exe installed by pip instead.
test(
  'fixed argv and cwd survive spaces and shell metacharacters; exit 1 is a result',
  { skip: process.platform === 'win32' },
  async (t) => {
    const options = await fake(
      t,
      'console.log(JSON.stringify({argv:process.argv.slice(2),cwd:process.cwd()})); process.stderr.write("notice"); process.exitCode=1;',
    );
    const result = await runCli(options);
    assert.equal(result.code, 1);
    assert.deepEqual(JSON.parse(result.stdout), { argv: LINT_ARGS, cwd: options.cwd });
    assert.equal(result.stderr, 'notice');
  },
);

test(
  'usage errors, output limits, timeouts, signals and cancellation reject',
  { skip: process.platform === 'win32' },
  async (t) => {
    await assert.rejects(
      runCli(await fake(t, 'process.stderr.write("bad argument"); process.exitCode=2;')),
      /exit 2.*bad argument/,
    );
    await assert.rejects(
      runCli({ ...(await fake(t, 'process.stdout.write("x".repeat(4000));')), maxBytes: 100 }),
      /output exceeded/,
    );
    await assert.rejects(
      runCli({ ...(await fake(t, 'setInterval(()=>{},1000);')), timeoutMs: 100 }),
      /exceeded 100 ms/,
    );
    await assert.rejects(runCli(await fake(t, 'process.kill(process.pid,"SIGTERM");')), /SIGTERM/);
    const controller = new AbortController();
    const options = await fake(t, 'process.on("SIGTERM",()=>{}); setInterval(()=>{},1000);');
    const pending = runCli({ ...options, signal: controller.signal });
    setTimeout(() => controller.abort(), 150);
    await assert.rejects(pending, /cancelled/);
    await assert.rejects(runCli({ ...options, signal: controller.signal }), /cancelled/);
  },
);

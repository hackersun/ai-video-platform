import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { pathToFileURL } from 'node:url';

import * as runner from './run-isolated-production-os.mjs';

const {
  assertSafeTempDatabaseUrl,
  buildIsolatedEnvironment,
  buildIsolatedPlaywrightEnvironment,
  resolvePlaywrightCachePath,
} = runner;

const runnerModuleUrl = pathToFileURL(path.resolve('scripts/run-isolated-production-os.mjs')).href;

async function waitForFile(filePath, timeoutMs = 2_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try { return await readFile(filePath, 'utf8'); } catch { /* not ready */ }
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  throw new Error(`timed out waiting for ${filePath}`);
}

async function runLifecycleCase({ mode, signals = [], cleanupFails = false }) {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), 'runner-lifecycle-'));
  const configPath = path.join(tempDir, 'tsconfig.json');
  const readyPath = path.join(tempDir, 'ready');
  const grandchildPidPath = path.join(tempDir, 'grandchild.pid');
  const childPath = path.join(tempDir, 'child.mjs');
  const harnessPath = path.join(tempDir, 'harness.mjs');
  const original = Buffer.from('{\n  "include": [".next-playwright/types/**/*.ts"]\n}\n');
  await writeFile(configPath, original);
  await writeFile(childPath, `
    import { appendFileSync, writeFileSync } from 'node:fs';
    import { spawn } from 'node:child_process';
    const [mode, configPath, readyPath, grandchildPidPath] = process.argv.slice(2);
    appendFileSync(configPath, 'child-mutation\\n');
    if (mode === 'failure') process.exit(7);
    if (mode === 'normal') process.exit(0);
    process.on('SIGTERM', () => {});
    process.on('SIGINT', () => {});
    const code = \`const fs=require('node:fs');process.on('SIGTERM',()=>{});process.on('SIGINT',()=>{});setInterval(()=>fs.appendFileSync(process.argv[1],'grandchild-mutation\\\\n'),10)\`;
    const grandchild = spawn(process.execPath, ['-e', code, configPath], { stdio: 'ignore' });
    writeFileSync(grandchildPidPath, String(grandchild.pid));
    writeFileSync(readyPath, 'ready');
    setInterval(() => appendFileSync(configPath, 'child-mutation\\n'), 10);
  `);
  await writeFile(harnessPath, `
    import { runRestorableCommand } from ${JSON.stringify(runnerModuleUrl)};
    const [configPath, childPath, mode, readyPath, grandchildPidPath, cleanupFails] = process.argv.slice(2);
    try {
      await runRestorableCommand({
        filePath: configPath,
        command: process.execPath,
        args: [childPath, mode, configPath, readyPath, grandchildPidPath],
        terminationTimeoutMs: 1_000,
        cleanup: async () => { if (cleanupFails === '1') throw new Error('synthetic cleanup failure'); },
      });
    } catch (error) {
      console.error(error instanceof Error ? error.message : error);
      process.exitCode = Number.isInteger(error?.exitCode) ? error.exitCode : 1;
    }
  `);

  const child = spawn(process.execPath, [harnessPath, configPath, childPath, mode, readyPath, grandchildPidPath, cleanupFails ? '1' : '0'], {
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let stderr = '';
  child.stderr.on('data', (chunk) => { stderr += chunk; });
  if (signals.length) {
    await waitForFile(readyPath);
    for (const signal of signals) child.kill(signal);
  }
  const [code, signal] = await new Promise((resolve) => child.once('exit', (exitCode, exitSignal) => resolve([exitCode, exitSignal])));
  await new Promise((resolve) => setTimeout(resolve, 150));
  const restored = await readFile(configPath);
  let grandchildPid = null;
  try { grandchildPid = Number(await readFile(grandchildPidPath, 'utf8')); } catch { /* no grandchild */ }
  const result = { code, signal, stderr, original, restored, grandchildPid };
  await rm(tempDir, { recursive: true, force: true });
  return result;
}

test('isolated runner rejects non-temp databases', () => {
  assert.throws(
    () => assertSafeTempDatabaseUrl('sqlite+aiosqlite:////Users/example/ai_video.db'),
    /under \/tmp/,
  );
});

test('isolated runner creates independent ports, cache and output paths', () => {
  const env = buildIsolatedEnvironment({
    tempDir: '/tmp/production-os-test-run',
    backendPort: 49111,
    frontendPort: 49112,
  });

  assert.equal(env.DATABASE_URL, 'sqlite+aiosqlite:////tmp/production-os-test-run/production-os.db');
  assert.equal(env.E2E_REQUIRE_ISOLATED_DB, 'true');
  assert.equal(env.NEXT_PUBLIC_API_URL, 'http://127.0.0.1:49111/api/v1');
  assert.equal(env.PLAYWRIGHT_PORT, '49112');
  assert.equal(env.PLAYWRIGHT_REUSE_EXISTING_SERVER, '0');
  assert.equal(env.PLAYWRIGHT_DIST_DIR, '.next-playwright-production-os-test-run');
  assert.equal(env.PLAYWRIGHT_OUTPUT_DIR, '/tmp/production-os-test-run/test-results');
});

test('isolated runner rejects the platform temp directory when it is outside /tmp', () => {
  assert.throws(
    () => buildIsolatedEnvironment({
      tempDir: '/private/var/folders/platform-temp/production-os',
      backendPort: 49111,
      frontendPort: 49112,
    }),
    /under \/tmp/,
  );
});

test('frontend-only suites receive a unique no-reuse Playwright environment', () => {
  assert.deepEqual(
    buildIsolatedPlaywrightEnvironment('/tmp/frontend-suite-123', 49113),
    {
      PLAYWRIGHT_PORT: '49113',
      PLAYWRIGHT_REUSE_EXISTING_SERVER: '0',
      PLAYWRIGHT_DIST_DIR: '.next-playwright-frontend-suite-123',
      PLAYWRIGHT_OUTPUT_DIR: '/tmp/frontend-suite-123/test-results',
    },
  );
});

test('Playwright cache cleanup resolves only a safe frontend child basename', () => {
  assert.equal(
    resolvePlaywrightCachePath('/workspace/frontend', '.next-playwright-run_123'),
    '/workspace/frontend/.next-playwright-run_123',
  );
  assert.throws(
    () => resolvePlaywrightCachePath('/workspace/frontend', '../outside'),
    /safe project-relative basename/,
  );
  assert.throws(
    () => resolvePlaywrightCachePath('/workspace/frontend', '/tmp/outside'),
    /safe project-relative basename/,
  );
});

test('runner exports a shared restorable command lifecycle', () => {
  assert.equal(typeof runner.runRestorableCommand, 'function');
});

test('restores exact bytes after normal exit and child failure while preserving exit codes', async () => {
  const normal = await runLifecycleCase({ mode: 'normal' });
  assert.equal(normal.code, 0);
  assert.deepEqual(normal.restored, normal.original);
  const failure = await runLifecycleCase({ mode: 'failure' });
  assert.equal(failure.code, 7);
  assert.deepEqual(failure.restored, failure.original);
});

test('SIGINT and SIGTERM restore bytes and preserve conventional exit codes', async () => {
  const interrupted = await runLifecycleCase({ mode: 'linger', signals: ['SIGINT'] });
  assert.equal(interrupted.code, 130, interrupted.stderr);
  assert.deepEqual(interrupted.restored, interrupted.original);
  const terminated = await runLifecycleCase({ mode: 'linger', signals: ['SIGTERM'] });
  assert.equal(terminated.code, 143, terminated.stderr);
  assert.deepEqual(terminated.restored, terminated.original);
});

test('repeated concurrent signals await one cleanup promise', async () => {
  const result = await runLifecycleCase({ mode: 'linger', signals: ['SIGINT', 'SIGTERM', 'SIGINT'] });
  assert.equal(result.code, 130, result.stderr);
  assert.deepEqual(result.restored, result.original);
});

test('cleanup failure restores bytes and exits nonzero', async () => {
  const result = await runLifecycleCase({ mode: 'normal', cleanupFails: true });
  assert.equal(result.code, 1);
  assert.match(result.stderr, /synthetic cleanup failure/);
  assert.deepEqual(result.restored, result.original);
});

test('kills a TERM-ignoring grandchild before final restoration', async () => {
  const result = await runLifecycleCase({ mode: 'linger', signals: ['SIGTERM'] });
  assert.equal(result.code, 143, result.stderr);
  assert.deepEqual(result.restored, result.original);
  assert.ok(result.grandchildPid);
  assert.throws(() => process.kill(result.grandchildPid, 0), /ESRCH/);
});

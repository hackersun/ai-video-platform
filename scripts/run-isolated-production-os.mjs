import { createHash } from 'node:crypto';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import net from 'node:net';
import path from 'node:path';
import { execFile, spawn } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath, pathToFileURL } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const execFileAsync = promisify(execFile);

function checksum(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

export async function snapshotFile(filePath) {
  const bytes = await readFile(filePath);
  return { bytes, checksum: checksum(bytes) };
}

export async function restoreFileSnapshot(filePath, snapshot) {
  await writeFile(filePath, snapshot.bytes);
  const restoredChecksum = checksum(await readFile(filePath));
  if (restoredChecksum !== snapshot.checksum) {
    throw new Error(`failed to restore ${filePath}: checksum mismatch`);
  }
  return restoredChecksum;
}

function signalExitCode(signal) {
  return signal === 'SIGINT' ? 130 : 143;
}

async function processGroupMembers(processGroupId) {
  if (!processGroupId) return [];
  const { stdout } = await execFileAsync('ps', ['-axo', 'pid=,pgid=,stat=,command=']);
  return stdout.split('\n').map((line) => line.trim()).filter((line) => {
    const [, pgid, status = ''] = line.split(/\s+/);
    return Number(pgid) === processGroupId && !status.startsWith('Z');
  });
}

async function processGroupAlive(processGroupId) {
  return (await processGroupMembers(processGroupId)).length > 0;
}

async function waitUntil(predicate, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await predicate()) return true;
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  return predicate();
}

export function spawnManagedProcess(command, args, options = {}) {
  const detached = process.platform !== 'win32';
  const child = spawn(command, args, { stdio: 'inherit', detached, ...options });
  child.processGroupId = detached ? child.pid : null;
  child.completion = new Promise((resolve, reject) => {
    child.once('error', reject);
    child.once('close', (code, signal) => resolve({ code, signal }));
  });
  return child;
}

export async function terminateManagedProcess(child, timeoutMs = 5_000) {
  if (!child) return;
  const signalTree = (signal) => {
    try {
      if (child.processGroupId) process.kill(-child.processGroupId, signal);
      else if (child.exitCode === null) child.kill(signal);
    } catch (error) {
      if (error?.code !== 'ESRCH') throw error;
    }
  };
  const treeAlive = async () => child.processGroupId
    ? processGroupAlive(child.processGroupId)
    : child.exitCode === null;
  if (await treeAlive()) signalTree('SIGTERM');
  if (!(await waitUntil(() => !treeAlive(), timeoutMs))) {
    signalTree('SIGKILL');
    await Promise.race([
      child.completion,
      new Promise((resolve) => setTimeout(resolve, timeoutMs)),
    ]);
    if (!(await waitUntil(() => !treeAlive(), timeoutMs))) {
      const members = child.processGroupId ? await processGroupMembers(child.processGroupId) : [];
      if (members.length) {
        throw new Error(`process group ${child.processGroupId || child.pid} did not exit after SIGKILL: ${members.join(' | ')}`);
      }
    }
  }
  await child.completion;
}

export function createRunnerLifecycle({ filePath, snapshot, processes, cleanup, terminationTimeoutMs = 5_000 }) {
  let cleanupPromise;
  let signalPromise;
  const handlers = new Map();
  const requestCleanup = () => {
    if (!cleanupPromise) {
      cleanupPromise = (async () => {
        const errors = [];
        for (const child of [...processes].reverse()) {
          try { await terminateManagedProcess(child, terminationTimeoutMs); } catch (error) { errors.push(error); }
        }
        try { await cleanup?.(); } catch (error) { errors.push(error); }
        try { await restoreFileSnapshot(filePath, snapshot); } catch (error) { errors.push(error); }
        if (errors.length) throw new AggregateError(errors, errors.map((error) => error?.message || String(error)).join('; '));
      })();
    }
    return cleanupPromise;
  };
  const removeSignalHandlers = () => {
    for (const [signal, handler] of handlers) process.off(signal, handler);
  };
  for (const [signal, exitCode] of [['SIGINT', 130], ['SIGTERM', 143]]) {
    const handler = () => {
      if (!signalPromise) {
        signalPromise = requestCleanup()
          .then(() => exitCode)
          .catch((error) => {
            console.error(error instanceof Error ? error.message : error);
            return 1;
          })
          .then((code) => {
            removeSignalHandlers();
            process.exit(code);
          });
      }
    };
    handlers.set(signal, handler);
    process.on(signal, handler);
  }
  return {
    requestCleanup,
    async finish() {
      try {
        await requestCleanup();
      } finally {
        removeSignalHandlers();
      }
    },
  };
}

export async function runRestorableCommand({
  filePath,
  command,
  args = [],
  cwd,
  env,
  cleanup,
  terminationTimeoutMs = 5_000,
}) {
  const snapshot = await snapshotFile(filePath);
  const processes = [];
  const lifecycle = createRunnerLifecycle({ filePath, snapshot, processes, cleanup, terminationTimeoutMs });
  let commandError;
  try {
    const child = spawnManagedProcess(command, args, { cwd, env });
    processes.push(child);
    const result = await child.completion;
    if (result.code !== 0) {
      commandError = new Error(`${command} exited with ${result.code ?? result.signal}`);
      commandError.exitCode = result.code ?? 1;
    }
  } catch (error) {
    commandError = error;
  }
  try {
    await lifecycle.finish();
  } catch (cleanupError) {
    throw cleanupError;
  }
  if (commandError) throw commandError;
}

export function assertSafeTempDatabaseUrl(databaseUrl) {
  const prefix = 'sqlite+aiosqlite:////tmp/';
  if (!databaseUrl.startsWith(prefix) || !databaseUrl.endsWith('.db')) {
    throw new Error('isolated production-os database must be a SQLite .db under /tmp/');
  }
}

export function buildIsolatedPlaywrightEnvironment(tempDir, frontendPort) {
  if (!path.resolve(tempDir).startsWith('/tmp/')) {
    throw new Error('isolated Playwright temp directory must be under /tmp/');
  }
  const runId = path.basename(tempDir);
  return {
    PLAYWRIGHT_PORT: String(frontendPort),
    PLAYWRIGHT_REUSE_EXISTING_SERVER: '0',
    PLAYWRIGHT_DIST_DIR: `.next-playwright-${runId}`,
    PLAYWRIGHT_OUTPUT_DIR: path.join(tempDir, 'test-results'),
  };
}

export function resolvePlaywrightCachePath(frontendRoot, distDir) {
  if (
    path.basename(distDir) !== distDir
    || !/^\.next-playwright-[A-Za-z0-9_-]+$/.test(distDir)
  ) {
    throw new Error('Playwright distDir must be a safe project-relative basename');
  }
  const root = path.resolve(frontendRoot);
  const target = path.resolve(root, distDir);
  if (path.dirname(target) !== root) {
    throw new Error('Playwright cache cleanup target escaped the frontend root');
  }
  return target;
}

export function buildIsolatedEnvironment({ tempDir, backendPort, frontendPort }) {
  if (!path.resolve(tempDir).startsWith('/tmp/')) {
    throw new Error('isolated production-os temp directory must be under /tmp/');
  }
  const databaseUrl = `sqlite+aiosqlite:////tmp/${path.relative('/tmp', tempDir)}/production-os.db`;
  assertSafeTempDatabaseUrl(databaseUrl);
  return {
    DATABASE_URL: databaseUrl,
    E2E_REQUIRE_ISOLATED_DB: 'true',
    DEV_MODE: 'true',
    NEXT_PUBLIC_API_URL: `http://127.0.0.1:${backendPort}/api/v1`,
    ...buildIsolatedPlaywrightEnvironment(tempDir, frontendPort),
    PRODUCTION_OS_REAL_BACKEND: '1',
  };
}

async function allocatePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      const port = typeof address === 'object' && address ? address.port : 0;
      server.close((error) => error ? reject(error) : resolve(port));
    });
  });
}

async function run(command, args, processes, options = {}) {
  const child = spawnManagedProcess(command, args, options);
  processes.push(child);
  const result = await child.completion;
  if (result.code !== 0) {
    const error = new Error(`${command} exited with ${result.code ?? result.signal}`);
    error.exitCode = result.code ?? 1;
    throw error;
  }
  return child;
}

async function waitForHealth(url, child, timeoutMs = 30_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error(`isolated backend exited with ${child.exitCode}`);
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // Backend is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error(`isolated backend did not become healthy at ${url}`);
}

export async function main() {
  const tempDir = await mkdtemp('/tmp/ai-video-production-os-');
  const backendPort = await allocatePort();
  const frontendPort = await allocatePort();
  const isolated = buildIsolatedEnvironment({ tempDir, backendPort, frontendPort });
  const env = { ...process.env, ...isolated };
  const frontendRoot = path.join(repoRoot, 'frontend');
  const cachePath = resolvePlaywrightCachePath(frontendRoot, isolated.PLAYWRIGHT_DIST_DIR);
  const tsconfigPath = path.join(frontendRoot, 'tsconfig.json');
  const tsconfigSnapshot = await snapshotFile(tsconfigPath);
  const processes = [];
  let backend;
  const lifecycle = createRunnerLifecycle({
    filePath: tsconfigPath,
    snapshot: tsconfigSnapshot,
    processes,
    cleanup: async () => {
      await rm(cachePath, { recursive: true, force: true });
      await rm(tempDir, { recursive: true, force: true });
    },
  });
  try {
    await run('python3', ['init_db.py'], processes, { cwd: path.join(repoRoot, 'backend'), env });
    backend = spawnManagedProcess(
      'python3',
      ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', String(backendPort)],
      { cwd: path.join(repoRoot, 'backend'), env, stdio: 'inherit' },
    );
    processes.push(backend);
    await waitForHealth(`http://127.0.0.1:${backendPort}/health`, backend);
    await run('npm', ['run', 'e2e:production-os:real:direct'], processes, {
      cwd: frontendRoot,
      env,
    });
  } finally {
    await lifecycle.finish();
  }
}

const invokedPath = process.argv[1] ? pathToFileURL(path.resolve(process.argv[1])).href : '';
if (import.meta.url === invokedPath) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  });
}

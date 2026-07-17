import { mkdtemp, rm } from 'node:fs/promises';
import net from 'node:net';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  buildIsolatedPlaywrightEnvironment,
  createRunnerLifecycle,
  resolvePlaywrightCachePath,
  spawnManagedProcess,
  snapshotFile,
} from './run-isolated-production-os.mjs';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

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

async function main() {
  const args = process.argv.slice(2);
  if (!args.length) throw new Error('provide Playwright test arguments');
  const tempDir = await mkdtemp('/tmp/ai-video-frontend-e2e-');
  const frontendPort = await allocatePort();
  const env = {
    ...process.env,
    ...buildIsolatedPlaywrightEnvironment(tempDir, frontendPort),
  };
  const frontendRoot = path.join(repoRoot, 'frontend');
  const cachePath = resolvePlaywrightCachePath(frontendRoot, env.PLAYWRIGHT_DIST_DIR);
  const tsconfigPath = path.join(frontendRoot, 'tsconfig.json');
  const tsconfigSnapshot = await snapshotFile(tsconfigPath);
  let passed = false;
  const processes = [];
  const lifecycle = createRunnerLifecycle({
    filePath: tsconfigPath,
    snapshot: tsconfigSnapshot,
    processes,
    cleanup: async () => {
      await rm(cachePath, { recursive: true, force: true });
      if (passed) await rm(tempDir, { recursive: true, force: true });
    },
  });
  try {
    const executable = path.join(frontendRoot, 'node_modules', '.bin', 'playwright');
    const child = spawnManagedProcess(executable, ['test', ...args], { cwd: frontendRoot, env, stdio: 'inherit' });
    processes.push(child);
    const result = await child.completion;
    if (result.code !== 0) throw new Error(`Playwright exited with ${result.code ?? result.signal}; artifacts retained at ${tempDir}`);
    passed = true;
  } finally {
    await lifecycle.finish();
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});

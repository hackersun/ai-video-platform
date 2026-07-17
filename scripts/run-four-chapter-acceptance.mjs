import { createHash, randomUUID } from 'node:crypto';
import { execFile, spawn } from 'node:child_process';
import { access, mkdir, readFile, rm, stat } from 'node:fs/promises';
import net from 'node:net';
import path from 'node:path';
import { promisify } from 'node:util';
import { fileURLToPath, pathToFileURL } from 'node:url';

import {
  createRunnerLifecycle,
  resolvePlaywrightCachePath,
  snapshotFile,
  spawnManagedProcess,
} from './run-isolated-production-os.mjs';

const execFileAsync = promisify(execFile);
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const backendRoot = path.join(repoRoot, 'backend');
const frontendRoot = path.join(repoRoot, 'frontend');
const isolatedDbPath = '/tmp/ai-video-platform-four-chapter.db';
const protectedTables = ['users', 'novels', 'chapters', 'llm_configs', 'series_production_runs', 'media_generation_jobs'];
const liveConfigIds = Object.freeze([
  '18e068a4-200b-4f17-9ffa-c8b1ee108caa',
  '5f20af31-3cda-48e3-a6eb-fc766ba14549',
  'sunqy-volcano-seed-tts-2-0',
  '980cb5db-0281-4835-9486-a739fcb35d98',
]);
const liveStorageConfigId = '0e8091db-0d9c-4e12-9ae7-7ff26e42f03c';

export function parseLiveCanaryOptions(source = process.env) {
  if (source.PRODUCTION_OS_LIVE !== '1') return { enabled: false };
  if (source.PRODUCTION_OS_LIVE_REQUIRED !== '1') throw new Error('PRODUCTION_OS_LIVE_REQUIRED=1 is required');
  const budget = Number(source.PRODUCTION_OS_LIVE_MAX_RMB);
  if (!Number.isFinite(budget) || budget !== 10) throw new Error('Wave 1 budget must be exactly RMB 10');
  const anchorCount = Number(source.PRODUCTION_OS_LIVE_ANCHOR_COUNT);
  if (anchorCount !== 2) throw new Error('Wave 2 is disabled; Wave 1 requires exactly 2 anchors');
  const sourceDb = path.resolve(source.FOUR_CHAPTER_LIVE_SOURCE_DB || '');
  if (!sourceDb.startsWith('/tmp/') || !/\.(?:db|sqlite|sqlite3)$/i.test(sourceDb)) {
    throw new Error('FOUR_CHAPTER_LIVE_SOURCE_DB must be an explicit /tmp source DB copy');
  }
  const sourceUserId = String(source.FOUR_CHAPTER_LIVE_SOURCE_USER_ID || '').trim();
  if (!sourceUserId) throw new Error('FOUR_CHAPTER_LIVE_SOURCE_USER_ID is required');
  return {
    enabled: true,
    sourceDb,
    sourceUserId,
    targetDb: isolatedDbPath,
    maxRmb: '10.00',
    anchorCount,
    configIds: [...liveConfigIds],
    storageConfigId: liveStorageConfigId,
    serverBudgetEnvironment: {
      LIVE_CANARY_MAX_RMB: '10.00',
      LIVE_CANARY_IMAGE_ESTIMATE_RMB: '1.00',
      LIVE_CANARY_TTS_ESTIMATE_RMB: '0.50',
      LIVE_CANARY_VIDEO_ESTIMATE_RMB: '3.50',
    },
  };
}

export function buildFourChapterEnvironment(databasePath = isolatedDbPath, canaryUserId = `four-chapter-canary-${randomUUID()}`) {
  if (path.resolve(databasePath) !== isolatedDbPath) throw new Error(`four-chapter database must be ${isolatedDbPath}`);
  const outputDir = process.env.FOUR_CHAPTER_OUTPUT_DIR || `/tmp/ai-video-platform-four-chapter-output-${randomUUID()}`;
  return {
    DATABASE_URL: `sqlite+aiosqlite:////${databasePath.replace(/^\//, '')}`,
    E2E_REQUIRE_ISOLATED_DB: 'true',
    DEV_MODE: 'true',
    NEXT_PUBLIC_API_URL: 'http://127.0.0.1:8000/api/v1',
    PLAYWRIGHT_PORT: '3100',
    PLAYWRIGHT_REUSE_EXISTING_SERVER: '0',
    PLAYWRIGHT_DIST_DIR: `.next-playwright-four-chapter-${randomUUID()}`,
    PLAYWRIGHT_OUTPUT_DIR: outputDir,
    FOUR_CHAPTER_CANARY_USER_ID: canaryUserId,
    FOUR_CHAPTER_DETERMINISTIC: '1',
    DETERMINISTIC_PROVIDER_FAKE: '1',
    DETERMINISTIC_REFERENCE_URL: 'http://127.0.0.1:18081/valid-composite.png',
    LIVE_CANARY_MAX_RMB: '10.00',
    LIVE_CANARY_IMAGE_ESTIMATE_RMB: '0.10',
    LIVE_CANARY_TTS_ESTIMATE_RMB: '0.05',
    LIVE_CANARY_VIDEO_ESTIMATE_RMB: '0.20',
    FOUR_CHAPTER_E2E_MANIFEST: path.join(outputDir, 'browser-lineage.json'),
    FOUR_CHAPTER_FAILURE_EVIDENCE: path.join(outputDir, 'failure-evidence.json'),
    LIVE_EVIDENCE_CONTRACT: 'model-execution-evidence-v1',
  };
}

export function formatPhaseStatus(label, status) {
  const labels = { passed: '通过', failed: '失败', unavailable: '无法运行' };
  if (!(status in labels)) throw new Error(`unknown phase status: ${status}`);
  return `${label}：${labels[status]}`;
}

export function compareDatabaseSnapshots(before, after) {
  if (JSON.stringify(before) !== JSON.stringify(after)) {
    throw new Error(`development database changed: before=${JSON.stringify(before)} after=${JSON.stringify(after)}`);
  }
}

export function compareTrackedBaseline(before, after) {
  if (before.bytesChecksum !== after.bytesChecksum || before.diffChecksum !== after.diffChecksum) {
    throw new Error(`tracked baseline changed: before=${JSON.stringify(before)} after=${JSON.stringify(after)}`);
  }
}

async function trackedBaseline(filePath) {
  const bytes = await readFile(filePath);
  const { stdout } = await execFileAsync('git', ['diff', '--', path.relative(repoRoot, filePath)], { cwd: repoRoot, encoding: 'buffer' });
  const digest = (value) => createHash('sha256').update(value).digest('hex');
  return { bytesChecksum: digest(bytes), diffChecksum: digest(stdout), dirty: stdout.length > 0 };
}

async function databaseSnapshot(databasePath) {
  const resolved = path.resolve(databasePath);
  try {
    await access(resolved);
  } catch {
    return { path: resolved, exists: false, size: 0, counts: {} };
  }
  const info = await stat(resolved);
  const code = [
    'import json, sqlite3, sys',
    'p=sys.argv[1]',
    `wanted=${JSON.stringify(protectedTables)}`,
    "db=sqlite3.connect('file:' + p + '?mode=ro', uri=True)",
    "existing={r[0] for r in db.execute(\"select name from sqlite_master where type='table'\")}",
    'counts={name: db.execute(f\'select count(*) from "{name}"\').fetchone()[0] for name in wanted if name in existing}',
    'db.close()',
    'print(json.dumps(counts, sort_keys=True))',
  ].join(';');
  const { stdout } = await execFileAsync('python3', ['-c', code, resolved]);
  return { path: resolved, exists: true, size: info.size, counts: JSON.parse(stdout) };
}

async function portAvailable(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once('error', () => resolve(false));
    server.listen(port, '127.0.0.1', () => server.close(() => resolve(true)));
  });
}

export function isRepositoryBackendProcess(processInfo, expectedBackendRoot = backendRoot) {
  return processInfo.cwd === expectedBackendRoot
    && /(?:^|\s|\/)uvicorn\s+main:app(?:\s|$)/.test(processInfo.command)
    && /--port\s+8000(?:\s|$)/.test(processInfo.command);
}

export function isRepositoryNextProcess(processInfo, expectedFrontendRoot = frontendRoot) {
  return processInfo.cwd === expectedFrontendRoot
    && /(?:^|\s|\/)next(?:\/dist\/bin\/next)?\s+dev(?:\s|$)/.test(processInfo.command)
    && /-p\s+(?:3000|3100)(?:\s|$)/.test(processInfo.command);
}

async function suspendRepositoryBackend() {
  let stdout;
  try {
    ({ stdout } = await execFileAsync('lsof', ['-tiTCP:8000', '-sTCP:LISTEN']));
  } catch (error) {
    if (error?.code === 1) return null;
    throw error;
  }
  const candidates = [...new Set(stdout.trim().split(/\s+/).filter(Boolean).map(Number))];
  const matching = [];
  for (const pid of candidates) {
    const [{ stdout: processInfo }, { stdout: cwdInfo }] = await Promise.all([
      execFileAsync('ps', ['-o', 'pid=,ppid=,command=', '-p', String(pid)]),
      execFileAsync('lsof', ['-a', '-p', String(pid), '-d', 'cwd', '-Fn']),
    ]);
    const cwd = cwdInfo.split('\n').find((line) => line.startsWith('n'))?.slice(1);
    if (isRepositoryBackendProcess({ cwd, command: processInfo })) {
      const [ownPid, parentPid] = processInfo.trim().split(/\s+/, 2).map(Number);
      matching.push({ pid: ownPid, parentPid });
    }
  }
  if (!matching.length) return null;
  const matchingIds = new Set(matching.map((item) => item.pid));
  const root = matching.find((item) => !matchingIds.has(item.parentPid)) || matching[0];
  process.kill(root.pid, 'SIGTERM');
  const deadline = Date.now() + 10_000;
  while (Date.now() < deadline && !(await portAvailable(8000))) {
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  if (!(await portAvailable(8000))) throw new Error(`repository backend PID ${root.pid} did not release port 8000`);
  return { pid: root.pid, command: path.join(backendRoot, 'venv/bin/uvicorn'), args: ['main:app', '--reload', '--port', '8000'], cwd: backendRoot };
}

async function restoreRepositoryBackend(suspended) {
  if (!suspended) return;
  const child = spawn(suspended.command, suspended.args, { cwd: suspended.cwd, detached: true, stdio: 'ignore' });
  child.unref();
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    try { if ((await fetch('http://127.0.0.1:8000/health')).ok) return; } catch { /* restarting */ }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error('repository backend was suspended for acceptance but could not be restored');
}

async function waitForHealth(url, child, timeoutMs = 45_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error(`backend exited with ${child.exitCode}`);
    try { if ((await fetch(url)).ok) return; } catch { /* starting */ }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error(`backend health timeout: ${url}`);
}

async function runPhase(label, command, args, options, processes) {
  let child;
  try {
    child = spawnManagedProcess(command, args, options);
    processes.push(child);
    const result = await child.completion;
    if (result.code !== 0) {
      console.error(formatPhaseStatus(label, 'failed'));
      const error = new Error(`${label} exited with ${result.code ?? result.signal}`);
      error.exitCode = result.code ?? 1;
      throw error;
    }
    console.log(formatPhaseStatus(label, 'passed'));
  } catch (error) {
    if (error?.code === 'ENOENT') console.error(formatPhaseStatus(label, 'unavailable'));
    throw error;
  }
}

async function captureLiveFailureEvidence(env, userId) {
  try {
    await access(isolatedDbPath);
  } catch {
    return false;
  }
  const { stdout } = await execFileAsync('python3', [
    'scripts/export_live_canary_failure_evidence.py',
    '--database', isolatedDbPath,
    '--user-id', userId,
    '--output', env.FOUR_CHAPTER_FAILURE_EVIDENCE,
  ], { cwd: backendRoot, env });
  console.log(`实模失败恢复证据：${stdout.trim()}`);
  return true;
}

export async function main() {
  const live = parseLiveCanaryOptions();
  const envValues = buildFourChapterEnvironment(isolatedDbPath,
    live.enabled ? `four-chapter-live-${randomUUID()}` : undefined);
  const env = {
    ...process.env, ...envValues,
    ...(live.enabled ? {
      ...live.serverBudgetEnvironment,
      FOUR_CHAPTER_DETERMINISTIC: '0',
      DETERMINISTIC_PROVIDER_FAKE: '0',
      PRODUCTION_OS_LIVE_REQUIRED: '1',
      PRODUCTION_OS_LIVE_MAX_RMB: live.maxRmb,
      PRODUCTION_OS_LIVE_ANCHOR_COUNT: String(live.anchorCount),
    } : {}),
  };
  if (live.enabled && env.DETERMINISTIC_PROVIDER_FAKE !== '0') throw new Error('live runner refused deterministic provider fake');
  if (live.enabled) console.log('实模 provider fake：已关闭');
  const devDbPath = path.join(backendRoot, 'ai_video.db');
  let beforeDb = await databaseSnapshot(devDbPath);
  console.log(`开发数据库（只读保护）前：${JSON.stringify(beforeDb)}`);
  const tsconfigPath = path.join(frontendRoot, 'tsconfig.json');
  const tsconfigSnapshot = await snapshotFile(tsconfigPath);
  const trackedBefore = await trackedBaseline(tsconfigPath);
  console.log(`tsconfig 执行前基线：${JSON.stringify(trackedBefore)}`);
  const cachePath = resolvePlaywrightCachePath(frontendRoot, envValues.PLAYWRIGHT_DIST_DIR);
  const processes = [];
  let suspendedBackend = null;
  await rm(isolatedDbPath, { force: true });
  await mkdir(envValues.PLAYWRIGHT_OUTPUT_DIR, { recursive: true, mode: 0o700 });
  const lifecycle = createRunnerLifecycle({
    filePath: tsconfigPath,
    snapshot: tsconfigSnapshot,
    processes,
    cleanup: async () => {
      await rm(cachePath, { recursive: true, force: true });
      await rm(isolatedDbPath, { force: true });
      // Keep repository-external redacted logs and lineage manifests for audit.
    },
  });

  try {
    if (!(await portAvailable(8000))) suspendedBackend = await suspendRepositoryBackend();
    if (suspendedBackend) {
      beforeDb = await databaseSnapshot(devDbPath);
      console.log(`开发数据库（停止本仓库后端后的只读基线）：${JSON.stringify(beforeDb)}`);
    }
    if (!(await portAvailable(8000)) || !(await portAvailable(3100))) {
      console.error(formatPhaseStatus('固定端口预检', 'unavailable'));
      throw new Error('backend 8000 or frontend 3100 is already in use');
    }
    console.log(formatPhaseStatus('固定端口预检', 'passed'));
    if (!(await portAvailable(18081))) throw new Error('deterministic reference fixture port 18081 is already in use');
    const referenceServer = spawnManagedProcess('python3', ['scripts/serve_deterministic_reference.py', '--port', '18081'], { cwd: backendRoot, env, stdio: 'inherit' });
    processes.push(referenceServer);
    await waitForHealth(env.DETERMINISTIC_REFERENCE_URL, referenceServer);
    console.log(formatPhaseStatus('确定性复合参考图服务', 'passed'));

    await runPhase('后端聚焦测试', 'python3', ['-m', 'pytest', '-q',
      'tests/test_series_run_orchestrator.py', 'tests/test_series_run_preflight.py',
      'tests/test_anchor_shot_service.py', 'tests/test_series_anchor_quality.py',
      'tests/test_live_canary_budget.py', 'tests/test_prepare_isolated_live_model_configs.py',
      'tests/test_deterministic_provider_fake.py'],
    { cwd: backendRoot, env: { ...env, DETERMINISTIC_PROVIDER_FAKE: '0' }, stdio: 'inherit' }, processes);

    await rm(isolatedDbPath, { force: true });
    if (live.enabled) {
      await runPhase('实模配置隔离暂存', 'python3', [
        'scripts/prepare_isolated_live_model_configs.py',
        '--source-db', live.sourceDb, '--target-db', live.targetDb,
        '--source-user-id', live.sourceUserId, '--target-user-id', envValues.FOUR_CHAPTER_CANARY_USER_ID,
        '--config-id', ...live.configIds,
        '--storage-config-id', live.storageConfigId,
      ], { cwd: backendRoot, env, stdio: 'inherit' }, processes);
    } else {
      await runPhase('独立数据库初始化', 'python3', ['init_db.py'], { cwd: backendRoot, env, stdio: 'inherit' }, processes);
    }
    const backend = spawnManagedProcess('python3', ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8000'], {
      cwd: backendRoot, env, stdio: 'inherit',
    });
    processes.push(backend);
    try {
      await waitForHealth('http://127.0.0.1:8000/health', backend);
      console.log(formatPhaseStatus('独立后端启动', 'passed'));
    } catch (error) {
      console.error(formatPhaseStatus('独立后端启动', 'failed'));
      throw error;
    }

    await runPhase('前端类型检查', 'npm', ['run', 'typecheck'], { cwd: frontendRoot, env, stdio: 'inherit' }, processes);
    await runPhase('前端构建', 'npm', ['run', 'build'], {
      cwd: frontendRoot, env: { ...env, NEXT_DIST_DIR: '.next-four-chapter-verify' }, stdio: 'inherit',
    }, processes);
    await rm(path.join(frontendRoot, '.next-four-chapter-verify'), { recursive: true, force: true });
    await runPhase(live.enabled ? '浏览器四章实模 Wave 1 验收' : '浏览器四章验收', path.join(frontendRoot, 'node_modules', '.bin', 'playwright'),
      ['test', live.enabled ? 'e2e/four-chapter-live-canary.spec.ts' : 'e2e/four-chapter-series-run.spec.ts', '--project=chromium', '--workers=1'],
      { cwd: frontendRoot, env, stdio: 'inherit' }, processes);
    if (!live.enabled) {
      await runPhase('SQLite 真实血缘审计', 'python3', [
        'scripts/audit_four_chapter_acceptance.py', '--database', isolatedDbPath,
        '--manifest', envValues.FOUR_CHAPTER_E2E_MANIFEST,
      ], { cwd: backendRoot, env, stdio: 'inherit' }, processes);
    }
  } catch (error) {
    if (live.enabled) {
      try {
        await captureLiveFailureEvidence(env, envValues.FOUR_CHAPTER_CANARY_USER_ID);
      } catch (evidenceError) {
        console.error(`实模失败恢复证据：失败 (${evidenceError?.name || 'Error'})`);
      }
    }
    throw error;
  } finally {
    const finalizationErrors = [];
    try { await lifecycle.finish(); } catch (error) { finalizationErrors.push(error); }
    try {
      const afterDb = await databaseSnapshot(devDbPath);
      console.log(`开发数据库（只读保护）后：${JSON.stringify(afterDb)}`);
      compareDatabaseSnapshots(beforeDb, afterDb);
      const restored = await readFile(tsconfigPath);
      if (!restored.equals(tsconfigSnapshot.bytes)) throw new Error('frontend/tsconfig.json changed');
      const trackedAfter = await trackedBaseline(tsconfigPath);
      compareTrackedBaseline(trackedBefore, trackedAfter);
      console.log(`tsconfig 执行后基线：${JSON.stringify(trackedAfter)}`);
      console.log(formatPhaseStatus('开发数据库与 tsconfig 保护', 'passed'));
    } catch (error) {
      console.error(formatPhaseStatus('开发数据库与 tsconfig 保护', 'failed'));
      finalizationErrors.push(error);
    }
    try {
      await restoreRepositoryBackend(suspendedBackend);
      if (suspendedBackend) console.log(formatPhaseStatus('原开发后端恢复', 'passed'));
    } catch (error) {
      console.error(formatPhaseStatus('原开发后端恢复', 'failed'));
      finalizationErrors.push(error);
    }
    if (finalizationErrors.length) throw new AggregateError(finalizationErrors, finalizationErrors.map((error) => error?.message || String(error)).join('; '));
  }
}

const invokedPath = process.argv[1] ? pathToFileURL(path.resolve(process.argv[1])).href : '';
if (import.meta.url === invokedPath) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = Number.isInteger(error?.exitCode) ? error.exitCode : 1;
  });
}

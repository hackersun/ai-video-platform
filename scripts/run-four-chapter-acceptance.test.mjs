import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildFourChapterEnvironment,
  compareDatabaseSnapshots,
  compareTrackedBaseline,
  formatPhaseStatus,
  isRepositoryBackendProcess,
  isRepositoryNextProcess,
  parseLiveCanaryOptions,
} from './run-four-chapter-acceptance.mjs';
import {
  isRecoverableReadonlyPreflight,
  stableChapterSnapshot,
} from '../frontend/e2e/helpers/four-chapter-sync.mjs';
import { formatSafeApiErrorDetail } from '../frontend/src/lib/safe-api-error.mjs';

test('safe API conflict formatting exposes only validated hashes', () => {
  const hash = 'a'.repeat(64);
  assert.equal(formatSafeApiErrorDetail({ code: 'blocked', message: 'review', conflict_fields: [
    { category: 'identity_attribute', field: 'visual_dna', value_hashes: [hash] },
  ]}, 'HTTP 409'), `blocked · review · identity_attribute/visual_dna=${hash}`);
  const serialized = formatSafeApiErrorDetail({ code: 'blocked', conflict_fields: [
    { category: 'identity_relation', field: 'relations', value_hashes: ['ally'] },
  ]}, 'HTTP 409');
  assert.equal(serialized, 'blocked');
  assert.doesNotMatch(serialized, /ally|enemy|沈砚/);
});

test('chapter synchronization requires exact count, unique ids, and expected titles', () => {
  assert.deepEqual(stableChapterSnapshot([
    { id: 'c2', title: '第二章' }, { id: 'c1', title: '第一章' },
  ], ['第一章', '第二章']), [
    { id: 'c1', title: '第一章' }, { id: 'c2', title: '第二章' },
  ]);
  assert.equal(stableChapterSnapshot([{ id: 'c1', title: '第一章' }], ['第一章', '第二章']), null);
  assert.equal(stableChapterSnapshot([{ id: 'same', title: '第一章' }, { id: 'same', title: '第二章' }], ['第一章', '第二章']), null);
});

test('only readonly preflight StaleDataError is classified as recoverable', () => {
  assert.equal(isRecoverableReadonlyPreflight(500, { detail: 'StaleDataError expected to update 1 row(s); 0 were matched' }), true);
  assert.equal(isRecoverableReadonlyPreflight(409, { detail: 'expected to update 1 row(s); 0 were matched' }), false);
  assert.equal(isRecoverableReadonlyPreflight(500, { detail: 'unrelated failure' }), false);
});

test('four chapter environment is fixed, isolated, external, and deterministic', () => {
  const env = buildFourChapterEnvironment('/tmp/ai-video-platform-four-chapter.db', 'canary-123');
  assert.equal(env.DATABASE_URL, 'sqlite+aiosqlite:////tmp/ai-video-platform-four-chapter.db');
  assert.equal(env.E2E_REQUIRE_ISOLATED_DB, 'true');
  assert.equal(env.NEXT_PUBLIC_API_URL, 'http://127.0.0.1:8000/api/v1');
  assert.equal(env.PLAYWRIGHT_PORT, '3100');
  assert.equal(env.PLAYWRIGHT_REUSE_EXISTING_SERVER, '0');
  assert.equal(env.FOUR_CHAPTER_CANARY_USER_ID, 'canary-123');
  assert.equal(env.FOUR_CHAPTER_DETERMINISTIC, '1');
  assert.equal(env.DETERMINISTIC_REFERENCE_URL, 'http://127.0.0.1:18081/valid-composite.png');
  assert.match(env.PLAYWRIGHT_OUTPUT_DIR, /^\/tmp\/ai-video-platform-four-chapter-output-/);
  assert.equal(env.FOUR_CHAPTER_FAILURE_EVIDENCE, `${env.PLAYWRIGHT_OUTPUT_DIR}/failure-evidence.json`);
});

test('only repository Next dev processes are eligible for stale frontend cleanup', () => {
  const root = '/workspace/ai-video-platform/frontend';
  assert.equal(isRepositoryNextProcess({ cwd: root, command: 'node /workspace/ai-video-platform/frontend/node_modules/next/dist/bin/next dev -p 3000 -p 3100' }, root), true);
  assert.equal(isRepositoryNextProcess({ cwd: '/foreign/frontend', command: 'next dev -p 3100' }, root), false);
  assert.equal(isRepositoryNextProcess({ cwd: root, command: 'next start -p 3100' }, root), false);
});

test('database comparison rejects path, size, or protected-row drift', () => {
  const before = { path: '/repo/backend/ai_video.db', exists: true, size: 42, counts: { users: 2, novels: 3 } };
  assert.doesNotThrow(() => compareDatabaseSnapshots(before, structuredClone(before)));
  assert.throws(() => compareDatabaseSnapshots(before, { ...before, size: 43 }), /development database changed/);
  assert.throws(() => compareDatabaseSnapshots(before, { ...before, counts: { ...before.counts, users: 3 } }), /development database changed/);
});

test('tracked dirty baseline is allowed but no new diff drift is allowed', () => {
  const baseline = { bytesChecksum: 'abc', diffChecksum: 'dirty-1' };
  assert.doesNotThrow(() => compareTrackedBaseline(baseline, { ...baseline }));
  assert.throws(() => compareTrackedBaseline(baseline, { ...baseline, diffChecksum: 'dirty-2' }), /tracked baseline changed/);
});

test('phase status has only the mandated Chinese vocabulary', () => {
  assert.equal(formatPhaseStatus('后端聚焦测试', 'passed'), '后端聚焦测试：通过');
  assert.equal(formatPhaseStatus('前端构建', 'failed'), '前端构建：失败');
  assert.equal(formatPhaseStatus('浏览器验收', 'unavailable'), '浏览器验收：无法运行');
  assert.throws(() => formatPhaseStatus('x', 'unknown'), /unknown phase status/);
});

test('only this repository uvicorn command is eligible for temporary suspension', () => {
  const backendRoot = '/workspace/ai-video-platform/backend';
  assert.equal(isRepositoryBackendProcess({ cwd: backendRoot, command: 'venv/bin/uvicorn main:app --reload --port 8000' }, backendRoot), true);
  assert.equal(isRepositoryBackendProcess({ cwd: '/another/repo/backend', command: 'uvicorn main:app --port 8000' }, backendRoot), false);
  assert.equal(isRepositoryBackendProcess({ cwd: backendRoot, command: 'python unrelated.py --port 8000' }, backendRoot), false);
  assert.equal(isRepositoryBackendProcess({ cwd: backendRoot, command: 'uvicorn main:app --port 9000' }, backendRoot), false);
});

test('live Wave 1 options are explicit, fixed, isolated, and server-authoritative', () => {
  const options = parseLiveCanaryOptions({
    PRODUCTION_OS_LIVE: '1',
    PRODUCTION_OS_LIVE_REQUIRED: '1',
    PRODUCTION_OS_LIVE_MAX_RMB: '10',
    PRODUCTION_OS_LIVE_ANCHOR_COUNT: '2',
    FOUR_CHAPTER_LIVE_SOURCE_DB: '/tmp/source-live.db',
    FOUR_CHAPTER_LIVE_SOURCE_USER_ID: 'sunqy-user-id',
  });
  assert.equal(options.enabled, true);
  assert.equal(options.maxRmb, '10.00');
  assert.equal(options.anchorCount, 2);
  assert.equal(options.targetDb, '/tmp/ai-video-platform-four-chapter.db');
  assert.deepEqual(options.configIds, [
    '18e068a4-200b-4f17-9ffa-c8b1ee108caa',
    '5f20af31-3cda-48e3-a6eb-fc766ba14549',
    'sunqy-volcano-seed-tts-2-0',
    '980cb5db-0281-4835-9486-a739fcb35d98',
  ]);
  assert.equal(options.configIds.includes('5a8d3813-ee43-4ed2-b40b-4935368e784e'), false);
  assert.equal(options.storageConfigId, '0e8091db-0d9c-4e12-9ae7-7ff26e42f03c');
  assert.deepEqual(options.serverBudgetEnvironment, {
    LIVE_CANARY_MAX_RMB: '10.00',
    LIVE_CANARY_IMAGE_ESTIMATE_RMB: '1.00',
    LIVE_CANARY_TTS_ESTIMATE_RMB: '0.50',
    LIVE_CANARY_VIDEO_ESTIMATE_RMB: '3.50',
  });
});

test('live environment cannot inherit the deterministic provider fake', () => {
  const base = buildFourChapterEnvironment('/tmp/ai-video-platform-four-chapter.db', 'live-user');
  const liveEnvironment = { ...base, FOUR_CHAPTER_DETERMINISTIC: '0', DETERMINISTIC_PROVIDER_FAKE: '0' };
  assert.equal(liveEnvironment.FOUR_CHAPTER_DETERMINISTIC, '0');
  assert.equal(liveEnvironment.DETERMINISTIC_PROVIDER_FAKE, '0');
});

test('live options fail closed for partial enablement, Wave 2, loose budget, or non-tmp source', () => {
  assert.equal(parseLiveCanaryOptions({}).enabled, false);
  assert.throws(() => parseLiveCanaryOptions({ PRODUCTION_OS_LIVE: '1' }), /LIVE_REQUIRED/);
  const base = {
    PRODUCTION_OS_LIVE: '1', PRODUCTION_OS_LIVE_REQUIRED: '1',
    PRODUCTION_OS_LIVE_MAX_RMB: '10', PRODUCTION_OS_LIVE_ANCHOR_COUNT: '2',
    FOUR_CHAPTER_LIVE_SOURCE_DB: '/tmp/source.db',
    FOUR_CHAPTER_LIVE_SOURCE_USER_ID: 'sunqy-user-id',
  };
  assert.throws(() => parseLiveCanaryOptions({ ...base, PRODUCTION_OS_LIVE_ANCHOR_COUNT: '6' }), /Wave 2/);
  assert.throws(() => parseLiveCanaryOptions({ ...base, PRODUCTION_OS_LIVE_MAX_RMB: '11' }), /exactly RMB 10/);
  assert.throws(() => parseLiveCanaryOptions({ ...base, FOUR_CHAPTER_LIVE_SOURCE_DB: '/repo/backend/ai_video.db' }), /source DB copy/);
});

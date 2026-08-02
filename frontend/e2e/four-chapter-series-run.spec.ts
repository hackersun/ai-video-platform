import { expect, test } from '@playwright/test';
import { pollAnchorGeneration } from '../src/features/series-runs/poll-anchor-generation';
import { writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fourChapterNovel } from './helpers/four-chapter-fixture';
import { isRecoverableReadonlyPreflight, stableChapterSnapshot } from './helpers/four-chapter-sync.mjs';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';
const manifestPath = process.env.FOUR_CHAPTER_E2E_MANIFEST;
const cases: any[] = [];
const chapterEvidence = fourChapterNovel.chapters.map((chapter, index) => ({
  order: index + 1, title: chapter.title,
  title_sha256: createHash('sha256').update(chapter.title).digest('hex'),
  content_sha256: createHash('sha256').update(chapter.content).digest('hex'),
}));

test.describe.configure({ mode: 'serial' });

test('anchor polling refreshes existing jobs and reconciles without resubmission', async () => {
  const statuses: string[] = [];
  const refreshed: string[] = [];
  let reconcileCalls = 0;
  const result = await pollAnchorGeneration({
    runId: 'run-1',
    initial: {
      status: 'provider_pending', selected_shot_ids: ['shot-1'], workflow_batches: [],
      quality_results: [], pending_video_job_ids: ['video-1'], pending_tts_job_ids: [],
    },
    client: {
      refreshVideoJob: async (jobId: string) => { refreshed.push(jobId); return { status: 'succeeded' }; },
      reconcileSelectedSeriesRunAnchors: async () => {
        reconcileCalls += 1;
        return reconcileCalls === 1
          ? { status: 'provider_pending', selected_shot_ids: ['shot-1'], workflow_batches: [], quality_results: [], pending_video_job_ids: ['video-1'], pending_tts_job_ids: [] }
          : { status: 'completed', selected_shot_ids: ['shot-1'], workflow_batches: [], quality_results: [{ shot_id: 'shot-1', overall_readiness: 'trusted_multimodal_evaluation_required' }], pending_video_job_ids: [], pending_tts_job_ids: [] };
      },
    },
    onStatus: (status) => statuses.push(status),
    wait: async () => undefined,
    maxAttempts: 3,
  });

  expect(result.status).toBe('completed');
  expect(refreshed).toEqual(['video-1', 'video-1']);
  expect(reconcileCalls).toBe(2);
  expect(statuses).toEqual(['provider_pending', 'provider_pending', 'completed']);
});

test('anchor polling survives a transient status refresh failure without resubmission', async () => {
  let refreshCalls = 0;
  let reconcileCalls = 0;
  const result = await pollAnchorGeneration({
    runId: 'run-1',
    initial: {
      status: 'provider_pending', selected_shot_ids: ['shot-1'], workflow_batches: [],
      quality_results: [], pending_video_job_ids: ['video-1'], pending_tts_job_ids: [],
    },
    client: {
      refreshVideoJob: async () => {
        refreshCalls += 1;
        if (refreshCalls === 1) throw new Error('temporary provider status failure');
        return { status: 'succeeded' };
      },
      reconcileSelectedSeriesRunAnchors: async () => {
        reconcileCalls += 1;
        return reconcileCalls === 1
          ? { status: 'provider_pending', selected_shot_ids: ['shot-1'], workflow_batches: [], quality_results: [], pending_video_job_ids: ['video-1'], pending_tts_job_ids: [] }
          : { status: 'completed', selected_shot_ids: ['shot-1'], workflow_batches: [], quality_results: [], pending_video_job_ids: [], pending_tts_job_ids: [] };
      },
    },
    wait: async () => undefined,
    maxAttempts: 3,
  });

  expect(result.status).toBe('completed');
  expect(refreshCalls).toBe(2);
  expect(reconcileCalls).toBe(2);
});
test.setTimeout(180_000);

async function browserApi(page: any, path: string, init: any = {}) {
  return page.evaluate(async ({ apiBase, apiPath, requestInit }) => {
    const token = localStorage.getItem('auth_token');
    const response = await fetch(`${apiBase}${apiPath}`, {
      ...requestInit,
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}`, ...(requestInit.headers || {}) },
    });
    const body = await response.json().catch(() => null);
    if (!response.ok) throw new Error(`${requestInit.method || 'GET'} ${apiPath}: ${response.status} ${JSON.stringify(body)}`);
    return body;
  }, { apiBase: API_BASE, apiPath: path, requestInit: init });
}

async function deterministicSetup(page: any, novelId: string) {
  return browserApi(page, '/series-runs/deterministic-acceptance/setup', {
    method: 'POST', body: JSON.stringify({ novel_id: novelId }),
  });
}

async function browserOriginReadonlyGet(page: any, path: string) {
  return page.evaluate(async ({ apiBase, apiPath }) => {
    const token = localStorage.getItem('auth_token');
    const response = await fetch(`${apiBase}${apiPath}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return { status: response.status, body: await response.json().catch(() => null) };
  }, { apiBase: API_BASE, apiPath: path });
}

async function pollReadonlyPreflight(page: any, path: string, expectedRunId: string) {
  let result: any = null;
  await expect.poll(async () => {
    result = await browserOriginReadonlyGet(page, path);
    if (result.status === 200) return result.body?.run_id;
    if (isRecoverableReadonlyPreflight(result.status, result.body)) return null;
    throw new Error(`GET ${path}: ${result.status}`);
  }, { timeout: 30_000, intervals: [250, 500, 1_000, 2_000] }).toBe(expectedRunId);
  return result.body;
}

async function waitForStableRun(page: any, runId: string) {
  let previous = '';
  let stableReads = 0;
  await expect.poll(async () => {
    const response = await browserOriginReadonlyGet(page, `/series-runs/${runId}`);
    if (response.status !== 200 || response.body?.status === 'created') return 0;
    const snapshot = `${response.body?.version}:${response.body?.status}`;
    stableReads = snapshot === previous ? stableReads + 1 : 1;
    previous = snapshot;
    return stableReads;
  }, { timeout: 30_000, intervals: [250, 500, 1_000] }).toBeGreaterThanOrEqual(3);
}

async function register(page: any, suffix: string) {
  const username = `fourchapter_${suffix}_${Date.now()}`;
  const password = 'DeterministicOnly123!';
  await page.goto('/register');
  await page.getByPlaceholder('请输入用户名').fill(username);
  await page.getByPlaceholder('请输入邮箱').fill(`${username}@example.invalid`);
  await page.getByPlaceholder('请输入密码（至少6位）').fill(password);
  await page.getByPlaceholder('请再次输入密码').fill(password);
  await page.getByRole('button', { name: '注册' }).click();
  await expect(page.getByText('注册成功！正在跳转...')).toBeVisible();
  await page.waitForURL(/\/dashboard/);
  return { username, user: JSON.parse(await page.evaluate(() => localStorage.getItem('user') || '{}')) };
}

async function createNovelAndChapters(page: any, mode: 'smoke' | 'full') {
  const title = `${fourChapterNovel.title}-${mode}-${Date.now()}`;
  await page.goto('/novels/new');
  await page.getByPlaceholder('输入小说标题').fill(title);
  await page.getByPlaceholder('简要介绍小说内容').fill('四章连续动漫真实隔离验收。');
  await page.locator('select').first().selectOption('mystery');
  await page.getByRole('button', { name: '保存草稿' }).click();
  await page.waitForURL(/\/novels$/);
  const link = page.getByRole('link', { name: new RegExp(title) }).first();
  const href = await link.getAttribute('href');
  expect(href).toMatch(/^\/novels\//);
  const novelId = href!.split('/').pop()!;
  await page.goto(`${href}?tab=chapters`);
  const persistedChapters: Array<{ id: string; title: string }> = [];
  for (let index = 0; index < fourChapterNovel.chapters.length; index += 1) {
    const source = fourChapterNovel.chapters[index];
    await page.getByRole('button', { name: '新建章节' }).click();
    await page.getByPlaceholder(/章节标题，可留空/).fill(source.title);
    await page.getByPlaceholder(/章节内容或创作方向/).fill(source.content);
    await page.getByRole('button', { name: '手动创建' }).click();
    let snapshot: Array<{ id: string; title: string }> | null = null;
    const expectedTitles = fourChapterNovel.chapters.slice(0, index + 1).map((chapter) => chapter.title);
    await expect.poll(async () => {
      const response = await browserOriginReadonlyGet(page, `/chapters/novel/${novelId}`);
      if (response.status !== 200) throw new Error(`GET chapters: ${response.status}`);
      snapshot = stableChapterSnapshot(response.body, expectedTitles);
      return snapshot?.length || 0;
    }, { timeout: 30_000, intervals: [250, 500, 1_000, 2_000] }).toBe(index + 1);
    persistedChapters.splice(0, persistedChapters.length, ...(snapshot || []));
    await page.reload();
    for (const chapter of persistedChapters) {
      const chapterLink = page.locator(`a[href="/novels/${novelId}/chapters/${chapter.id}"]`);
      await expect(chapterLink).toContainText(chapter.title);
      await expect(chapterLink).toBeVisible();
    }
  }
  await page.getByRole('tab', { name: /整书计划/ }).click();
  await page.getByRole('button', { name: '生成多集计划', exact: true }).click();
  await expect(page.getByTestId('series-run-panel')).toBeVisible();
  await page.getByRole('button', { name: '整书自动制作', exact: true }).click();
  await page.waitForFunction((id) => Boolean(localStorage.getItem(`series-run:${id}`)), novelId);
  await expect(page.getByRole('button', { name: '继续推进' })).toBeEnabled({ timeout: 30_000 });
  const runId = await page.evaluate((id) => localStorage.getItem(`series-run:${id}`), novelId);
  expect(runId).toBeTruthy();
  await waitForStableRun(page, runId!);
  const setup = await deterministicSetup(page, novelId);
  expect(setup.run_id).toBe(runId);
  await page.goto(`/novels/${novelId}?tab=series-plan`);
  await expect.poll(async () => {
    if (await page.getByText('前置状态加载中…', { exact: true }).count()) return true;
    if (await page.getByTestId('live-preflight-plan').count()) return true;
    const enable = page.getByRole('button', { name: '启用实模关键镜头验证' });
    return await enable.count() === 1 && await enable.isDisabled();
  }, { timeout: 30_000, intervals: [100, 250, 500] }).toBe(true);
  await pollReadonlyPreflight(page, `/series-runs/${runId}/live-preflight-plan`, runId!);
  await expect(page.getByTestId('live-preflight-plan')).toBeVisible({ timeout: 30_000 });
  const enableLive = page.getByRole('button', { name: '启用实模关键镜头验证' });
  await expect(enableLive).toBeEnabled();
  await enableLive.click();
  await expect(page.getByText(/实模关键镜头验证已启用/)).toBeVisible({ timeout: 30_000 });
  await waitForStableRun(page, runId!);
  await deterministicSetup(page, novelId);
  await pollReadonlyPreflight(page, `/series-runs/${runId}/live-preflight-plan`, runId!);
  await page.goto(`/novels/${novelId}?tab=series-plan`);
  await page.reload();
  const preflight = page.getByTestId('live-preflight-plan');
  await expect(preflight).toHaveCount(1, { timeout: 30_000 });
  await expect(preflight.getByLabel('配音声线')).toBeVisible({ timeout: 30_000 });
  await preflight.getByRole('button', { name: '锁定声线' }).click();
  await expect(preflight).toContainText('已锁定：', { timeout: 30_000 });
  await page.getByRole('button', { name: '继续推进' }).click();
  await expect(page.getByTestId('series-run-episodes').getByText('镜头就绪')).toHaveCount(4, { timeout: 180_000 });
  await expect(page.getByRole('button', { name: '继续推进' })).toBeEnabled({ timeout: 30_000 });
  await pollReadonlyPreflight(page, `/series-runs/${runId}/live-preflight-plan`, runId!);
  await waitForStableRun(page, runId!);
  await deterministicSetup(page, novelId);
  await pollReadonlyPreflight(page, `/series-runs/${runId}/live-preflight-plan`, runId!);
  await page.goto(`/novels/${novelId}?tab=series-plan`);
  await page.reload();
  await expect(page.getByTestId('series-run-panel')).toBeVisible();
  await expect(page.getByTestId('live-preflight-plan')).toHaveCount(1, { timeout: 30_000 });
  return { novelId, runId };
}

async function generateAndVerify(page: any, mode: 'smoke' | 'full') {
  const identity = await register(page, mode);
  const { novelId, runId } = await createNovelAndChapters(page, mode);
  await expect(page.getByText(/实模关键镜头验证已启用/)).toBeVisible();
  const preflight = page.getByTestId('live-preflight-plan');
  await expect(preflight).toContainText('上限 ¥10.00', { timeout: 30_000 });
  const voiceSelect = preflight.getByLabel('配音声线');
  await expect(voiceSelect).toBeVisible();
  await expect(voiceSelect.locator('option')).not.toHaveCount(0);
  await expect(preflight).toContainText('已锁定：');
  if (mode === 'full') await page.getByRole('button', { name: '6 镜头完整验证' }).click();
  await preflight.getByRole('button', { name: '准备故事锁' }).click();
  await expect(preflight).toContainText('故事锁：locked');
  const closureStatus = preflight.getByTestId('story-lock-closure-status');
  await expect(closureStatus).toContainText(
    /必需实体 \d+ · 无关候选 \d+ · 自动批准 \d+ · 手动批准 \d+ · 未解决 0/,
  );
  const closureText = await closureStatus.textContent();
  const counts = closureText?.match(
    /必需实体 (\d+) · 无关候选 (\d+) · 自动批准 (\d+) · 手动批准 (\d+) · 未解决 (\d+)/,
  );
  expect(counts, '故事锁闭包必须展示完整计数').not.toBeNull();
  const [, required, , autoApproved, manualApproved, unresolved] = counts!;
  expect(Number(required)).toBeGreaterThan(0);
  expect(Number(autoApproved) + Number(manualApproved)).toBe(Number(required));
  expect(Number(unresolved)).toBe(0);
  await expect(closureStatus).toContainText(/Bible v\d+/);
  await expect(closureStatus).toContainText(/闭包 [a-f0-9]{10}/);
  const lockResponse = await browserOriginReadonlyGet(page, `/series-runs/${runId}`);
  const rawRequiredIds = lockResponse.body?.run_metadata?.story_locks?.required_entity_ids || [];
  for (const entityId of rawRequiredIds) await expect(preflight).not.toContainText(entityId);
  const reference = preflight.getByRole('button', { name: '生成并锁定参考图' });
  await expect(reference).toBeEnabled();
  await reference.click();
  await expect(preflight).toContainText('参考图：locked');
  await expect(preflight).toContainText('角色：character_canonical、global_style_board');
  await expect(preflight).toContainText('实模前置准备 · 已就绪');
  const expectedCount = mode === 'smoke' ? 2 : 6;
  const generate = page.getByRole('button', { name: `生成所选 ${expectedCount} 个关键镜头` });
  await expect(generate).toBeEnabled();
  await generate.click();
  await expect(page.getByText('关键镜头一致性证据')).toBeVisible();
  await expect(page.getByText(/证据通过/)).toHaveCount(expectedCount);

  const run = await browserApi(page, `/series-runs/${runId}`);
  const jobs = await browserApi(page, `/media/jobs?novel_id=${novelId}`);
  const selected = run.run_metadata.selected_anchor_shot_ids;
  expect(selected).toHaveLength(expectedCount);
  expect(new Set(run.episodes.map((item: any) => item.episode_number))).toEqual(new Set([1, 2, 3, 4]));
  expect(run.episodes.every((item: any) => item.stage === 'shots_ready')).toBe(true);
  const selectedJobs = jobs.filter((job: any) => selected.includes(job.shot_id));
  expect(selectedJobs).toHaveLength(expectedCount);
  expect(selectedJobs.every((job: any) => job.media_type === 'audio_video' && job.output_video_url && job.output_audio_url)).toBe(true);
  expect(selectedJobs.every((job: any) => {
    const locks = job.input_assets || job.extra_data?.asset_version_locks || [];
    return locks.length > 0 && locks.every((item: any) => item.asset_id && item.asset_version && item.locked === true);
  })).toBe(true);
  expect(selectedJobs.every((job: any) => new Set((job.extra_data?.provider_calls || []).map((item: any) => item.capability)).size === 3)).toBe(true);
  expect(jobs.filter((job: any) => !selected.includes(job.shot_id))).toHaveLength(0);
  const reports = Object.values(run.run_metadata.anchor_quality_reports || {}) as any[];
  expect(reports).toHaveLength(expectedCount);
  expect(reports.every((item) => item.ready && item.job_id && item.artifact_id && item.evaluation_ids?.length === 6)).toBe(true);
  expect(reports.every((item) => item.artifact_id === item.job_id)).toBe(true);
  expect(reports.some((item) => Object.values(item.dimensions || {}).some((dimension: any) => Number(dimension.score) < 100))).toBe(true);
  cases.push({ mode, user_id: identity.user.id, novel_id: novelId, run_id: runId, selected_shot_ids: selected, job_ids: selectedJobs.map((job: any) => job.id), reports });
}

test('real isolated workbench persists exact two-shot smoke jobs and report lineage', async ({ page }) => {
  await generateAndVerify(page, 'smoke');
});

test('real isolated workbench independently persists six-shot full jobs and report lineage', async ({ page }) => {
  await generateAndVerify(page, 'full');
});

test('recovery card preserves completed work and displays truthful spent cost', async ({ page }) => {
  await register(page, 'recovery');
  const { novelId, runId } = await createNovelAndChapters(page, 'smoke');
  let operationStatus = 'confirmed_rejected_before_acceptance';
  await page.route(`${API_BASE}/series-runs/${runId}`, async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({ response, json: {
      ...body, cost_summary: { ...(body.cost_summary || {}), actual_rmb: '0', spent_rmb: '1.25' },
    } });
  });
  await page.route(`${API_BASE}/series-runs/${runId}/recovery`, async (route) => {
    const safeRetry = operationStatus === 'confirmed_rejected_before_acceptance';
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      run_id: runId, run_version: 3, blocked: !safeRetry,
      preserved_artifacts: [{ kind: 'reference_image', asset_id: 'reference-1', message: '参考图已锁定，不会重新生成' }],
      operations: [{
        operation_id: 'tts-operation-1', capability: 'tts', stage: 'tts_submission',
        operation_status: operationStatus, title: safeRetry ? '声音生成未受理' : '等待确认供应商状态',
        message: safeRetry ? '供应商明确未受理' : '请先人工对账', cost_state: safeRetry ? 'released' : 'held',
        safe_retry: safeRetry, retry_requires_confirmation: safeRetry,
        retry_scope: safeRetry ? 'failed_stage' : null,
        actions: safeRetry ? [
          { code: 'edit_voice', label: '修改声线' },
          { code: 'retest_config', label: '重新测试声音模型' },
          { code: 'retry_failed_stage', label: '修改后重试失败阶段' },
        ] : [{ code: 'refresh_status', label: '刷新供应商状态' }, { code: 'manual_reconcile', label: '人工对账' }],
      }],
    }) });
  });

  await page.goto(`/novels/${novelId}?tab=series-plan`);
  const recovery = page.getByTestId('series-run-recovery');
  await expect(recovery).toContainText('声音生成未受理');
  await expect(recovery).toContainText('失败阶段：配音提交');
  await expect(recovery).toContainText('本次 TTS 未扣费，预留已释放');
  await expect(recovery).toContainText('参考图已锁定，不会重新生成');
  await expect(recovery.getByRole('button', { name: '修改声线' })).toBeVisible();
  await expect(recovery.getByRole('button', { name: '重新测试声音模型' })).toBeVisible();
  await expect(recovery.getByRole('button', { name: '修改后重试失败阶段' })).toBeVisible();
  await expect(page.getByText('实际成本 ¥1.25')).toBeVisible();

  operationStatus = 'unknown_manual_reconcile';
  await page.reload();
  await expect(page.getByTestId('series-run-recovery')).toContainText('等待确认供应商状态');
  await expect(page.getByRole('button', { name: '修改后重试失败阶段' })).toHaveCount(0);
});

test('real workbench safely blocks ambiguous required entity with zero Story Lock writes', async ({ page }) => {
  await register(page, 'negative');
  const { novelId, runId } = await createNovelAndChapters(page, 'smoke');
  const entitiesResponse = await browserApi(page, `/story-bibles/entities?novel_id=${novelId}&limit=200`);
  const entities = Array.isArray(entitiesResponse) ? entitiesResponse : entitiesResponse.entities || [];
  const requiredProp = entities.find((entity: any) => entity.name === '连续性道具');
  expect(requiredProp?.id).toBeTruthy();
  const sentinel = 'RAW_CONFLICT_DO_NOT_RENDER_7F3A';
  await browserApi(page, `/story-bibles/entities/${requiredProp.id}`, {
    method: 'PUT', body: JSON.stringify({ attributes: {
      ...(requiredProp.attributes || {}), evidence_contract: {
        ...(requiredProp.attributes?.evidence_contract || {}), status: 'ambiguous',
        conflicting_values: [sentinel, 'RAW_CONFLICT_SECONDARY'],
      },
    } }),
  });
  const snapshot = async () => {
    const run = await browserApi(page, `/series-runs/${runId}`);
    const currentEntities = await browserApi(page, `/story-bibles/entities?novel_id=${novelId}&limit=200`);
    const entityRows = Array.isArray(currentEntities) ? currentEntities : currentEntities.entities || [];
    return {
      run: { status: run.status, episodes: run.episodes, run_metadata: run.run_metadata },
      required_entity: entityRows.find((entity: any) => entity.id === requiredProp.id),
      bibles: await browserApi(page, `/story-bibles?novel_id=${novelId}`),
    };
  };
  const before = JSON.stringify(await snapshot());
  await page.reload();
  const preflight = page.getByTestId('live-preflight-plan');
  await expect(preflight).toBeVisible();
  await preflight.getByRole('button', { name: '准备故事锁' }).click();
  await expect(preflight).toContainText(/required_entity_evidence_ambiguous|story_lock_preparation_blocked/);
  await expect(preflight).not.toContainText('conflict_fields');
  await expect(preflight).not.toContainText(sentinel);
  await expect(preflight).not.toContainText(requiredProp.id);
  const afterState = await snapshot();
  expect(JSON.stringify(afterState)).toBe(before);
  const bibles = Array.isArray(afterState.bibles) ? afterState.bibles : afterState.bibles?.items || [];
  expect(bibles).toHaveLength(0);
});

test.afterAll(async () => {
  if (!manifestPath) throw new Error('FOUR_CHAPTER_E2E_MANIFEST is required');
  await writeFile(manifestPath, `${JSON.stringify({ database: '/tmp/ai-video-platform-four-chapter.db', chapters: chapterEvidence, cases }, null, 2)}\n`, { mode: 0o600 });
});

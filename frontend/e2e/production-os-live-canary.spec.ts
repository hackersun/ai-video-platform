import { expect, test } from '@playwright/test';
import { devToken, fulfillJson } from './helpers/production-os-fixture';

function parsePositiveFiniteBudget(value: string | undefined): number | null {
  const parsed = Number(value ?? '');
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

const liveEnabled = process.env.PRODUCTION_OS_LIVE === '1';
const liveRequired = process.env.PRODUCTION_OS_LIVE_REQUIRED === '1';
const maxRmb = parsePositiveFiniteBudget(process.env.PRODUCTION_OS_LIVE_MAX_RMB);
const estimatedRmbPerJob = parsePositiveFiniteBudget(process.env.PRODUCTION_OS_LIVE_ESTIMATED_RMB_PER_JOB);
const episodeCount = Number(process.env.PRODUCTION_OS_LIVE_EPISODES || '3');
const shotsPerEpisode = Number(process.env.PRODUCTION_OS_LIVE_SHOTS_PER_EPISODE || '2');
const minimumQuality = Number(process.env.PRODUCTION_OS_LIVE_MIN_QUALITY || '60');
const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

type DimensionEvidence = {
  id?: string;
  artifact_id?: string;
  dimension?: string;
  blocking?: boolean;
  score?: number;
  threshold_version?: string;
  evaluator_version?: string;
};

type JobEvidence = {
  workflow_id?: string;
  episode_index?: number;
  shot_id?: string;
  job_id?: string;
  model_id?: string;
  contract_version?: string;
  artifact?: string;
  cost_rmb?: number;
  status?: string;
  retry_count?: number;
};

type Collection = {
  jobs: Map<string, JobEvidence>;
  failures: JobEvidence[];
  qualityByGeneration: Map<string, DimensionEvidence[]>;
};

function generationKey(workflowId?: string, shotId?: string, artifactId?: string) {
  return workflowId && shotId && artifactId ? `${workflowId}:${shotId}:${artifactId}` : '';
}

function collectRawEvidence(value: unknown, collection: Collection) {
  if (Array.isArray(value)) {
    value.forEach((item) => collectRawEvidence(item, collection));
    return;
  }
  if (!value || typeof value !== 'object') return;
  const item = value as Record<string, any>;
  const lineage = item.lineage && typeof item.lineage === 'object' ? item.lineage : {};
  const rawShotId = item.shot_id ?? lineage.shot_id;
  const knownJobObject = Boolean(
    item.id && rawShotId && (
      Object.prototype.hasOwnProperty.call(item, 'task_id') ||
      Object.prototype.hasOwnProperty.call(item, 'video_url') ||
      Object.prototype.hasOwnProperty.call(item, 'audio_url') ||
      Object.prototype.hasOwnProperty.call(item, 'output_video_url') ||
      Object.prototype.hasOwnProperty.call(item, 'media_type')
    ),
  );
  const record: JobEvidence = {
    workflow_id: item.workflow_id ?? lineage.workflow_id,
    episode_index: item.episode_index ?? lineage.episode_index,
    shot_id: rawShotId,
    job_id: item.job_id ?? (knownJobObject ? item.id : undefined),
    model_id: item.model_id ?? item.api_model_id,
    contract_version: item.episode_contract_version ?? item.contract_version ?? lineage.episode_contract_version,
    artifact: item.output_manifest_url ?? item.manifest_url ?? item.artifact_url ?? item.output_url,
    cost_rmb: item.cost_rmb,
    status: item.status,
    retry_count: item.retry_count ?? item.regeneration_count,
  };
  if (record.status && ['failed', 'cancelled', 'canceled'].includes(record.status)) {
    collection.failures.push(record);
  }
  if (record.job_id) {
    collection.jobs.set(record.job_id, { ...(collection.jobs.get(record.job_id) || {}), ...record });
  }
  const dimensions = item.quality_gate?.dimensions ?? item.quality_dimensions ?? item.dimensions;
  if (record.shot_id && Array.isArray(dimensions)) {
    const normalized = dimensions.map((dimension) => ({ ...dimension })) as DimensionEvidence[];
    const artifactIds = new Set(normalized.map((dimension) => dimension.artifact_id).filter(Boolean));
    const artifactId = item.artifact_id ?? item.job_id ?? (artifactIds.size === 1 ? Array.from(artifactIds)[0] : undefined);
    const key = generationKey(record.workflow_id, record.shot_id, artifactId);
    if (key) collection.qualityByGeneration.set(key, normalized);
  }
  Object.values(item).forEach((child) => collectRawEvidence(child, collection));
}

function freshQualityForJob(job: JobEvidence, collection: Collection, evaluationBaseline: Set<string>) {
  const dimensions = collection.qualityByGeneration.get(
    generationKey(job.workflow_id, job.shot_id, job.job_id),
  );
  if (!dimensions || dimensions.some((dimension) => !dimension.id || evaluationBaseline.has(dimension.id))) {
    return null;
  }
  return dimensions;
}

function missingJobLineage(job: JobEvidence) {
  return job.episode_index == null || !job.workflow_id || !job.shot_id || !job.job_id ||
    !job.model_id || !job.contract_version || !job.artifact || job.cost_rmb == null;
}

const exactDimensions = new Set([
  'narrative_truth', 'character_visual', 'scene_prop_state',
  'motion_camera', 'voice_lipsync', 'delivery_integrity',
]);

async function assertLiveStudioEntry(page: import('@playwright/test').Page) {
  await expect(page.getByRole('heading', { name: '系列动漫工作室' })).toBeVisible();
  await page.getByRole('tab', { name: '设定' }).click();
  await expect(page.getByRole('link', { name: '生成本集草片' })).toBeVisible();
}

test('budget parser and raw collector fail closed', () => {
  expect(parsePositiveFiniteBudget(undefined)).toBeNull();
  expect(parsePositiveFiniteBudget('Infinity')).toBeNull();
  expect(parsePositiveFiniteBudget('NaN')).toBeNull();
  expect(parsePositiveFiniteBudget('0')).toBeNull();
  expect(parsePositiveFiniteBudget('-1')).toBeNull();
  expect(parsePositiveFiniteBudget('12.5')).toBe(12.5);

  const collection: Collection = { jobs: new Map(), failures: [], qualityByGeneration: new Map() };
  collectRawEvidence({ status: 'failed', nested: { job_id: 'job-no-lineage', status: 'failed' } }, collection);
  expect(collection.failures.length).toBeGreaterThanOrEqual(1);
  expect(collection.jobs.get('job-no-lineage')?.shot_id).toBeUndefined();
  collectRawEvidence({ id: 'not-a-job', shot_id: 'shot-1', status: 'completed', model_id: 'model-1' }, collection);
  expect(collection.jobs.has('not-a-job')).toBe(false);

  collectRawEvidence({
    workflow_id: 'wf-1', shot_id: 'shot-1', artifact_id: 'job-old',
    quality_gate: { dimensions: Array.from(exactDimensions).map((dimension, index) => ({ id: `old-${index}`, artifact_id: 'job-old', dimension })) },
  }, collection);
  const newJob: JobEvidence = { workflow_id: 'wf-1', shot_id: 'shot-1', job_id: 'job-new' };
  expect(freshQualityForJob(newJob, collection, new Set(['old-0']))).toBeNull();
});

test('live canary Studio entry selectors stay visible before provider enablement', async ({ page }) => {
  await page.addInitScript(({ token, userId }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({ id: userId, username: userId, email: `${userId}@example.test` }));
  }, { token: devToken('live-canary-ui-smoke'), userId: 'live-canary-ui-smoke' });
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace(/\/+$/, '');
    if (path === '/api/v1/workflow') return fulfillJson(route, [{ workflow_id: 'wf-live-smoke', title: 'Canary Smoke', status: 'active' }]);
    if (path === '/api/v1/studio/workflows/wf-live-smoke/snapshot') return fulfillJson(route, {
      series_studio: { enabled: true, primary_console: 'series_studio', expert_drilldowns: [] },
      workflow: { id: 'wf-live-smoke', title: 'Canary Smoke', status: 'active', novel_id: 'novel-live-smoke' },
      story_context: { novel: { id: 'novel-live-smoke', title: 'Canary Smoke' } },
      production_bible_summary: { readiness_score: 100, counts: {}, asset_readiness: { ready: true } },
      production: { shot_count: 2, ready: true }, shots: [], assets: {}, jobs: { summary: {} },
      issues: [], actions: [], mode_policy: {}, guidance: { stages: [] },
    });
    if (path === '/api/v1/production-cards/novel/novel-live-smoke') return fulfillJson(route, { cards: [], summary: {} });
    if (path === '/api/v1/prompt-skills') return fulfillJson(route, { items: [], count: 0 });
    if (path === '/api/v1/video/models') return fulfillJson(route, { models: [] });
    return fulfillJson(route, {});
  });

  await page.goto('/studio?workflow_id=wf-live-smoke');
  await assertLiveStudioEntry(page);
});

test.skip('legacy three-episode canary is superseded by four-chapter Wave 1', async ({ page }) => {
  if (liveRequired) {
    expect(liveEnabled, 'PRODUCTION_OS_LIVE=1 is required by this verification command').toBeTruthy();
    expect(maxRmb, 'PRODUCTION_OS_LIVE_MAX_RMB must be finite and positive').not.toBeNull();
    expect(estimatedRmbPerJob, 'PRODUCTION_OS_LIVE_ESTIMATED_RMB_PER_JOB must be finite and positive').not.toBeNull();
  }
  test.skip(!liveEnabled, 'Set PRODUCTION_OS_LIVE=1 to enable real provider calls.');
  test.skip(maxRmb == null, 'A finite positive RMB budget is required.');
  test.skip(estimatedRmbPerJob == null, 'A finite positive per-job estimate is required.');
  const expectedJobs = episodeCount * shotsPerEpisode;
  expect(estimatedRmbPerJob! * expectedJobs, 'estimated run cost exceeds approved budget before any click').toBeLessThanOrEqual(maxRmb!);

  const workflowIds = (process.env.PRODUCTION_OS_LIVE_WORKFLOW_IDS || '').split(',').map((item) => item.trim()).filter(Boolean);
  expect(workflowIds.length, 'provide one persisted workflow per episode').toBeGreaterThanOrEqual(episodeCount);
  const collection: Collection = { jobs: new Map(), failures: [], qualityByGeneration: new Map() };
  page.on('response', async (response) => {
    if (!response.url().includes('/api/v1/')) return;
    try { collectRawEvidence(await response.json(), collection); } catch { /* non-JSON is not evidence */ }
  });
  const authToken = process.env.PRODUCTION_OS_LIVE_AUTH_TOKEN;
  if (authToken) await page.addInitScript((token) => localStorage.setItem('auth_token', token), authToken);

  const generationIdsByWorkflow = new Map<string, Set<string>>();
  for (const workflowId of workflowIds.slice(0, episodeCount)) {
    const cumulativeCost = Array.from(generationIdsByWorkflow.values()).flatMap((ids) => Array.from(ids))
      .reduce((sum, id) => sum + Number(collection.jobs.get(id)?.cost_rmb || 0), 0);
    expect(cumulativeCost + estimatedRmbPerJob! * shotsPerEpisode, 'remaining budget is insufficient before episode click').toBeLessThanOrEqual(maxRmb!);

    await page.goto(`/studio?workflow_id=${encodeURIComponent(workflowId)}`);
    await assertLiveStudioEntry(page);
    await page.getByRole('link', { name: '生成本集草片' }).click();
    await expect(page).toHaveURL(/\/producer\?workflow_id=/);
    const checkboxes = page.getByRole('checkbox', { name: /选择镜头/ });
    await expect(checkboxes.first()).toBeVisible();
    expect(await checkboxes.count()).toBeGreaterThanOrEqual(shotsPerEpisode);
    for (let index = 0; index < shotsPerEpisode; index += 1) {
      if (!(await checkboxes.nth(index).isChecked())) await checkboxes.nth(index).click();
    }

    const baseline = new Set(collection.jobs.keys());
    const qualityEvaluationBaseline = new Set(
      Array.from(collection.qualityByGeneration.values()).flatMap((dimensions) => dimensions.map((item) => item.id).filter(Boolean) as string[]),
    );
    const generate = page.getByRole('button', { name: '一键生成本集草片' });
    await expect(generate).toBeEnabled();
    await generate.click();
    await expect(generate).toBeEnabled({ timeout: 20 * 60 * 1000 });
    await expect.poll(() => {
      if (collection.failures.length) return -1;
      const newJobs = Array.from(collection.jobs.entries()).filter(([id, job]) => !baseline.has(id) && job.workflow_id === workflowId);
      generationIdsByWorkflow.set(workflowId, new Set(newJobs.map(([id]) => id)));
      return new Set(newJobs.map(([, job]) => job.shot_id).filter(Boolean)).size;
    }, { timeout: 20 * 60 * 1000, message: 'wait for this workflow generation-set only' }).toBe(shotsPerEpisode);

    const ids = generationIdsByWorkflow.get(workflowId)!;
    const episodeJobs = Array.from(ids).map((id) => collection.jobs.get(id)!);
    expect(collection.failures, 'any failed/cancelled response fails immediately').toHaveLength(0);
    expect(episodeJobs.filter(missingJobLineage), 'raw lineage may not be inherited or fabricated').toHaveLength(0);
    expect(new Set(episodeJobs.map((job) => job.shot_id)).size).toBe(shotsPerEpisode);
    episodeJobs.forEach((job) => {
      expect(Number(job.cost_rmb), `job ${job.job_id} cost must be nonnegative`).toBeGreaterThanOrEqual(0);
      expect(Number(job.cost_rmb), `job ${job.job_id} exceeds total approved budget`).toBeLessThanOrEqual(maxRmb!);
    });
    const episodeCost = episodeJobs.reduce((sum, job) => sum + Number(job.cost_rmb), 0);
    expect(episodeCost).toBeLessThanOrEqual(maxRmb!);
    const spent = Array.from(generationIdsByWorkflow.values()).flatMap((set) => Array.from(set))
      .reduce((sum, id) => sum + Number(collection.jobs.get(id)?.cost_rmb), 0);
    expect(spent, 'per-episode cumulative budget circuit breaker').toBeLessThanOrEqual(maxRmb!);
    for (const job of episodeJobs) {
      expect(
        freshQualityForJob(job, collection, qualityEvaluationBaseline),
        `job ${job.job_id} must have fresh artifact-bound quality evidence`,
      ).not.toBeNull();
    }
  }

  const generationIds = Array.from(generationIdsByWorkflow.values()).flatMap((ids) => Array.from(ids));
  for (const jobId of generationIds) {
    const job = collection.jobs.get(jobId)!;
    expect(job.status).toMatch(/succeeded|completed/);
    const dimensions = collection.qualityByGeneration.get(
      generationKey(job.workflow_id, job.shot_id, job.job_id),
    ) || [];
    expect(new Set(dimensions.map((item) => item.dimension))).toEqual(exactDimensions);
    expect(dimensions).toHaveLength(6);
    expect(dimensions.filter((item) => item.blocking)).toHaveLength(0);
    dimensions.forEach((item) => {
      expect(item.score).toBeGreaterThanOrEqual(minimumQuality);
      expect(item.threshold_version).toBeTruthy();
      expect(item.evaluator_version).toBeTruthy();
    });
  }

  const actualCost = generationIds.reduce((sum, id) => sum + Number(collection.jobs.get(id)?.cost_rmb), 0);
  const liveRun = {
    run_id: process.env.PRODUCTION_OS_LIVE_RUN_ID || `live-${Date.now()}`,
    date: new Date().toISOString().slice(0, 10),
    episodes: episodeCount,
    shots_per_episode: shotsPerEpisode,
    passed: true,
    thresholds_passed: true,
    manual_db_repair: false,
    actual_cost_rmb: actualCost,
    job_ids: generationIds,
  };
  const writeResult = await page.evaluate(async ({ endpoint, token, workflowId, run }) => {
    const response = await fetch(`${endpoint}/dashboard/analytics/production-readiness-evidence`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({ workflow_id: workflowId, live_run: run }),
    });
    return { ok: response.ok, body: await response.json() };
  }, { endpoint: apiBase, token: authToken || '', workflowId: workflowIds[0], run: liveRun });
  expect(writeResult.ok, JSON.stringify(writeResult.body)).toBe(true);
});

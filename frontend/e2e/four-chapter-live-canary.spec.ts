import { expect, test } from '@playwright/test';
import { writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fourChapterNovel } from './helpers/four-chapter-fixture';
import { devToken } from './helpers/production-os-fixture';

const enabled = process.env.PRODUCTION_OS_LIVE === '1';
const userId = process.env.FOUR_CHAPTER_CANARY_USER_ID || '';
const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';
const allowlist = new Set([
  'f03311c6-5ca3-4e88-a552-fb5623a394bd', '980cb5db-0281-4835-9486-a739fcb35d98',
]);

test.describe.configure({ retries: 0 });

export function liveGuard(env: Record<string, string | undefined>) {
  if (env.PRODUCTION_OS_LIVE !== '1') return false;
  if (env.PRODUCTION_OS_LIVE_REQUIRED !== '1') throw new Error('required flag missing');
  if (Number(env.PRODUCTION_OS_LIVE_MAX_RMB) !== 10) throw new Error('Wave 1 requires RMB 10');
  if (Number(env.PRODUCTION_OS_LIVE_ANCHOR_COUNT) !== 2) throw new Error('Wave 2 disabled');
  if (env.LIVE_EVIDENCE_CONTRACT !== 'model-execution-evidence-v1') throw new Error('live evidence contract missing');
  return true;
}

function redacted(data: any) {
  return {
    chapters: fourChapterNovel.chapters.map((chapter, index) => ({
      order: index + 1, title_sha256: createHash('sha256').update(chapter.title).digest('hex'),
      content_sha256: createHash('sha256').update(chapter.content).digest('hex'),
    })),
    run_id: data.run.id, status: data.run.status, selected_shot_ids: data.selected,
    spent_rmb: data.run.cost_summary?.spent_rmb,
    cost_summary: data.run.cost_summary,
    config_test_cost: 'unknown_not_reported_by_provider',
    reference: data.reference,
    bindings: Object.fromEntries(Object.entries(data.run.model_bindings?.capabilities || {}).map(([key, value]: any) => [key, {
      config_id: value.config_id, provider_id: value.provider_id, api_model_id: value.api_model_id, tested_at: value.tested_at,
      contract_version: value.contract_version, prompt_profile: value.prompt_profile,
      verification_status: value.verification_status,
      routing_mode: value.prompt_profile ? 'model_contract_profile' : 'legacy_unknown',
    }])),
    jobs: data.jobs.map((job: any) => ({ id: job.id, shot_id: job.shot_id, media_type: job.media_type, status: job.status,
      task_id: job.task_id, model_id: job.model_id, provider_id: job.provider_id,
      artifact: job.output_manifest_url || job.output_video_url || job.output_audio_url,
      capabilities: job.capabilities, cover_url: job.cover_url,
      video_native_audio: job.extra_data?.video_native_audio,
      source_job_ids: job.source_job_ids,
      config_id: job.extra_data?.model_config_id, cost_rmb: job.extra_data?.cost_rmb,
      provider_calls: job.extra_data?.provider_calls })),
    quality_status: 'trusted_multimodal_evaluation_required',
    quality: data.qualityResults.map((result: any) => ({ artifact_id: result.artifact_id, shot_id: result.shot_id,
      ready: result.ready, evaluation_ids: result.evaluation_ids, evidence_source: result.evidence_source,
      overall_readiness: result.overall_readiness })),
  };
}

test('live gate rejects partial enablement and Wave 2 without provider calls', ({}, testInfo) => {
  expect(testInfo.retry).toBe(0);
  expect(liveGuard({})).toBe(false);
  expect(() => liveGuard({ PRODUCTION_OS_LIVE: '1' })).toThrow(/required/);
  expect(() => liveGuard({ PRODUCTION_OS_LIVE: '1', PRODUCTION_OS_LIVE_REQUIRED: '1', PRODUCTION_OS_LIVE_MAX_RMB: '10', PRODUCTION_OS_LIVE_ANCHOR_COUNT: '6', LIVE_EVIDENCE_CONTRACT: 'model-execution-evidence-v1' })).toThrow(/Wave 2/);
});

test('live evidence records model contracts and redacts prompt text', () => {
  const manifest = redacted({
    run: { id: 'run-1', status: 'blocked', cost_summary: { spent_rmb: '1.00' }, model_bindings: { capabilities: {
      tts: { config_id: 'config-1', provider_id: 'volcano', api_model_id: 'seed-tts-2.0', tested_at: 'safe-time',
        contract_version: 'volcano.seed_tts.v3.v1', prompt_profile: 'volcano.seed_tts.v3', verification_status: 'verified', prompt: 'secret novel text' },
    } } },
    selected: [], reference: null, jobs: [], qualityResults: [],
  });
  expect(manifest.bindings.tts).toMatchObject({
    contract_version: 'volcano.seed_tts.v3.v1', prompt_profile: 'volcano.seed_tts.v3', verification_status: 'verified',
    routing_mode: 'model_contract_profile',
  });
  expect(JSON.stringify(manifest)).not.toContain('secret novel text');
});

test('frontend Wave 1 generates two cross-episode anchors with immutable evidence', async ({ page }, testInfo) => {
  test.setTimeout(25 * 60_000);
  test.skip(!enabled, 'explicit live enablement required');
  expect(testInfo.retry).toBe(0);
  expect(liveGuard(process.env)).toBe(true);
  expect(userId).toBeTruthy();
  const token = devToken(userId);
  const headers = { Authorization: `Bearer ${token}` };
  await page.addInitScript(({ id, tokenValue }) => {
    localStorage.setItem('auth_token', tokenValue);
    localStorage.setItem('user', JSON.stringify({ id, username: 'live-canary' }));
  }, { id: userId, tokenValue: token });

  // Fixture creation is non-provider setup; every production action below is a visible workbench control.
  const created = await page.request.post(`${apiBase}/novels`, { headers, data: { title: `四章3D实模验收-${Date.now()}`, genre: '3d-animation', description: '3D 动漫，跨章节角色一致性验收' } });
  expect(created.ok()).toBe(true);
  const novel = await created.json();
  const fakeProbe = await page.request.post(`${apiBase}/series-runs/deterministic-acceptance/setup`, { headers, data: { novel_id: novel.id } });
  expect(fakeProbe.status(), 'live backend must reject the deterministic provider fake').toBe(404);
  await page.goto(`/novels/${novel.id}?tab=chapters`);
  for (const chapter of fourChapterNovel.chapters) {
    await page.getByRole('button', { name: '新建章节' }).click();
    await page.getByPlaceholder(/章节标题，可留空/).fill(chapter.title);
    await page.getByPlaceholder(/章节内容或创作方向/).fill(chapter.content);
    await page.getByRole('button', { name: '手动创建' }).click();
    await expect(page.getByText(chapter.title, { exact: true })).toBeVisible();
  }
  await page.getByRole('tab', { name: /整书计划/ }).click();
  await page.getByRole('button', { name: '生成多集计划', exact: true }).click();
  const chapters = await (await page.request.get(`${apiBase}/chapters/novel/${novel.id}`, { headers })).json();
  let seriesPlan: any = null;
  await expect.poll(async () => {
    seriesPlan = await (await page.request.get(`${apiBase}/novels/${novel.id}/series-plan`, { headers })).json();
    return seriesPlan.episodes?.length || 0;
  }, { timeout: 30_000 }).toBe(4);
  const episodes = [...(seriesPlan.episodes || [])].map((episode: any, index: number) => {
    const chapterIds = episode.chapter_ids?.length ? episode.chapter_ids : (episode.chapters || []).map((item: any) => item.id).filter(Boolean);
    const ids = chapterIds.length ? chapterIds : [chapters[index].id];
    return { episode_number: index + 1, chapter_ids: ids, input_hash: ids.map((id: string) => `${id}:${chapters.find((item: any) => item.id === id)?.updated_at || ''}`).join('|') };
  });
  const createdRun = await page.request.post(`${apiBase}/series-runs`, { headers, data: {
    novel_id: novel.id, series_plan_version: String(seriesPlan.version || seriesPlan.updated_at || '1'),
    idempotency_key: `live-wave1-${seriesPlan.version || seriesPlan.updated_at || '1'}`,
    requested_stages: ['workflow', 'script', 'storyboard', 'shots'], model_bindings: {}, budget_policy: {}, episodes,
  }});
  expect(createdRun.ok(), `create run ${createdRun.status()}: ${await createdRun.text()}`).toBe(true);
  const initialRun = await createdRun.json();
  await page.evaluate(({ id, runId }) => localStorage.setItem(`series-run:${id}`, runId), { id: novel.id, runId: initialRun.id });
  await page.goto(`/novels/${novel.id}?tab=series-plan`);
  await page.getByRole('tab', { name: '整书计划 (4)', exact: true }).click();
  await expect(page.getByRole('button', { name: '继续推进' })).toBeVisible();

  const nativeAudioToggle = page.getByLabel('本次使用 Seedance 1.5 原生配音');
  await nativeAudioToggle.check();

  const sequence: string[] = [];
  let referenceEvidence: any = null;
  let voiceSelectionStatus: number | null = null;
  let reconciledQualityResults: any[] = [];
  let generationRequest: any = null;
  page.on('request', (request) => {
    if (/\/llm\/configs\/[^/]+\/test$/.test(request.url())) sequence.push('test');
    if (request.url().endsWith('/live-bindings/validate')) sequence.push('validate');
    if (request.url().endsWith('/generate-selected')) {
      sequence.push('generate');
      generationRequest = request.postDataJSON();
    }
  });
  page.on('response', async (response) => {
    if (response.url().endsWith('/prepare-reference') && response.ok()) referenceEvidence = await response.json();
    if (response.url().endsWith('/voice-selection')) voiceSelectionStatus = response.status();
    if (response.url().endsWith('/reconcile-selected') && response.ok()) {
      const reconciled = await response.json();
      if (reconciled.status === 'completed') reconciledQualityResults = reconciled.quality_results || [];
    }
  });
  await page.getByRole('button', { name: '启用实模关键镜头验证' }).click();
  await expect(page.getByText(/实模关键镜头验证已启用/)).toBeVisible({ timeout: 120_000 });
  expect(sequence).toEqual(['validate']);
  const preflight = page.getByTestId('live-preflight-plan');
  await expect(preflight.getByLabel('配音声线')).toHaveCount(0);
  await expect(preflight).toContainText('当前由视频模型原生配音，无需锁定 TTS 声线。');
  await page.getByRole('button', { name: '继续推进' }).click();
  await expect(page.getByTestId('series-run-episodes').getByText('镜头就绪')).toHaveCount(4, { timeout: 180_000 });
  await page.screenshot({ path: testInfo.outputPath('01-shots-ready.png'), fullPage: true });
  const selected = page.getByLabel(/选择第\d+章镜头/);
  await expect(selected).toHaveCount(2);
  const labels = await selected.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('aria-label')));
  expect(labels.sort()).toEqual(['选择第1章镜头', '选择第4章镜头']);
  const runId = initialRun.id;
  const beforePreparation = await (await page.request.get(`${apiBase}/series-runs/${runId}/live-preflight-plan?native_audio=true`, { headers })).json();
  expect(beforePreparation.anchor_dialogue_contracts).toHaveLength(2);
  expect(beforePreparation.anchor_dialogue_contracts.every((item: any) => item.audio_route === 'video_native_audio')).toBe(true);
  expect(Number(beforePreparation.budget.maximum_rmb)).toBeLessThanOrEqual(10);
  expect(Number(beforePreparation.budget.projected_increment_rmb)).toBeLessThanOrEqual(10);
  await page.screenshot({ path: testInfo.outputPath('02-cross-episode-anchors.png'), fullPage: true });
  const storyLockResponsePromise = page.waitForResponse((response) =>
    response.url().endsWith('/prepare-story-locks') && response.request().method() === 'POST');
  await page.getByRole('button', { name: '准备故事锁' }).click();
  const storyLockResponse = await storyLockResponsePromise;
  if (process.env.FOUR_CHAPTER_STORY_LOCK_DIAGNOSTIC === '1' && storyLockResponse.status() !== 200) {
    await page.waitForTimeout(60_000);
  }
  expect(storyLockResponse.status(), `story lock response: ${await storyLockResponse.text()}`).toBe(200);
  await expect(page.getByText(/故事锁：locked/)).toBeVisible({ timeout: 180_000 });
  if (process.env.FOUR_CHAPTER_STORY_LOCK_DIAGNOSTIC === '1') return;
  const confirmRequiredEntities = page.getByRole('button', { name: /确认定稿 \d+ 个必需实体/ });
  await expect(confirmRequiredEntities).toBeVisible();
  await confirmRequiredEntities.click();
  await expect(page.getByTestId('story-lock-closure-status')).toContainText('未解决 0', { timeout: 180_000 });
  await page.getByRole('button', { name: '生成并锁定参考图' }).click();
  await expect(page.getByText(/参考图：locked/)).toBeVisible({ timeout: 10 * 60_000 });
  expect(referenceEvidence?.operation?.provider_task_id || referenceEvidence?.operation?.id).toBeTruthy();
  expect(referenceEvidence?.artifact?.checksum).toBeTruthy();
  expect(Number(referenceEvidence?.artifact?.layout_evidence?.layout_score)).toBeGreaterThanOrEqual(0.75);
  const runWithSelection = await (await page.request.get(`${apiBase}/series-runs/${runId}`, { headers })).json();
  const selectedShotIds = runWithSelection.run_metadata?.selected_anchor_shot_ids || [];
  expect(selectedShotIds).toHaveLength(2);
  for (const shotId of selectedShotIds) {
    const imageResponse = await page.request.post(`${apiBase}/shots/${shotId}/generate-image`, {
      headers, data: { style: 'realistic-3d', model_config_id: 'f03311c6-5ca3-4e88-a552-fb5623a394bd' },
    });
    expect(imageResponse.ok(), `shot image ${shotId}: ${await imageResponse.text()}`).toBe(true);
    await expect.poll(async () => {
      const shot = await (await page.request.get(`${apiBase}/shots/${shotId}`, { headers })).json();
      return shot.image_status === 'succeeded' && Boolean(shot.image_url);
    }, { timeout: 10 * 60_000, intervals: [2_000, 5_000, 10_000] }).toBe(true);
  }
  const readyPlan = await (await page.request.get(`${apiBase}/series-runs/${runId}/live-preflight-plan?native_audio=true`, { headers })).json();
  expect(readyPlan.ready).toBe(true);
  expect(Number(readyPlan.budget.projected_increment_rmb)).toBeLessThanOrEqual(10);
  await page.screenshot({ path: testInfo.outputPath('03-reference-and-ready-plan.png'), fullPage: true });
  await expect(nativeAudioToggle).toBeChecked();
  await expect(preflight.getByLabel('配音声线')).toHaveCount(0);
  await expect(preflight).toContainText('当前由视频模型原生配音，无需锁定 TTS 声线。');
  const generationResponsePromise = page.waitForResponse((response) =>
    response.url().endsWith('/generate-selected') && response.request().method() === 'POST');
  await page.getByRole('button', { name: '生成所选 2 个关键镜头' }).click();
  const generationResponse = await generationResponsePromise;
  const generationText = await generationResponse.text();
  expect(generationResponse.status(), `generation response: ${generationText}`).toBe(200);
  expect(generationRequest).toMatchObject({ native_audio: true, mode: 'smoke' });
  const generation = JSON.parse(generationText);
  expect(generation.workflow_batches.flatMap((batch: any) => batch.tts_job_ids || [])).toHaveLength(0);
  let qualityResults = generation.quality_results || [];
  await expect.poll(() => sequence.at(-1)).toBe('generate');
  expect(sequence.filter((item) => item === 'generate')).toHaveLength(1);
  if (generation.status === 'provider_pending' || generation.status === 'provider_ready') {
    await expect(page.getByText(/等待云端原生有声视频完成/)).toBeVisible({ timeout: 120_000 });
  }
  await expect(page.getByText(/待可信多模态评估/)).toBeVisible({ timeout: 20 * 60_000 });
  qualityResults = reconciledQualityResults.length ? reconciledQualityResults : qualityResults;
  expect(sequence.filter((item) => item === 'generate')).toHaveLength(1);

  let data: any = null;
  await expect.poll(async () => {
    const run = await (await page.request.get(`${apiBase}/series-runs/${runId}`, { headers })).json();
    const selectedIds = run.run_metadata?.selected_anchor_shot_ids || [];
    const jobs = (await (await page.request.get(`${apiBase}/media/jobs?novel_id=${novel.id}`, { headers })).json()).filter((job: any) => selectedIds.includes(job.shot_id));
    const reports = Object.values(run.run_metadata?.anchor_quality_reports || {});
    data = { run, selected: selectedIds, jobs, reports, qualityResults, reference: referenceEvidence };
    return selectedIds.length === 2 && jobs.length === 2 && jobs.every((job: any) => ['completed', 'succeeded'].includes(job.status));
  }, { timeout: 20 * 60_000, intervals: [2_000, 5_000, 10_000] }).toBe(true);
  expect(new Set(Object.values(data.run.model_bindings.capabilities).map((item: any) => item.config_id))).toEqual(allowlist);
  Object.values(data.run.model_bindings.capabilities).forEach((binding: any) => {
    expect(binding.verification_status).toBe('verified');
    expect(binding.contract_version).not.toBe('unverified.v1');
    expect(binding.prompt_profile).toBeTruthy();
  });
  expect(Number(data.run.cost_summary.spent_rmb)).toBeLessThanOrEqual(10);
  data.jobs.forEach((job: any) => {
    expect(job.provider_id).not.toBe('deterministic-acceptance');
    expect(job.extra_data?.deterministic_provider_fake).not.toBe(true);
    expect(job.task_id || job.extra_data?.provider_task_id).toBeTruthy();
    expect(job.output_manifest_url || job.output_video_url || job.output_audio_url).toBeTruthy();
    expect(job.capabilities).toEqual(['video', 'native_audio']);
    expect(job.extra_data?.video_native_audio).toBe(true);
    expect(job.source_job_ids?.tts_job_id).toBeNull();
    expect(job.cover_url).not.toBe(referenceEvidence?.artifact?.url);
    expect(new Set((job.extra_data?.provider_calls || []).map((item: any) => item.capability))).toEqual(new Set(['reference', 'video']));
  });
  expect(data.reports).toHaveLength(0);
  expect(data.qualityResults).toHaveLength(2);
  data.qualityResults.forEach((result: any) => {
    expect(result.ready).toBe(false);
    expect(result.evaluation_ids).toEqual([]);
    expect(result.evidence_source).toBe('not_evaluated');
    expect(result.overall_readiness).toBe('trusted_multimodal_evaluation_required');
  });
  await page.screenshot({ path: testInfo.outputPath('04-generation-not-evaluated.png'), fullPage: true });
  const manifest = JSON.stringify(redacted(data), null, 2);
  expect(manifest).not.toMatch(/api[_-]?key|secret|password/i);
  expect(manifest).not.toContain('通过');
  await writeFile(testInfo.outputPath('redacted-manifest.json'), manifest, { mode: 0o600 });
});

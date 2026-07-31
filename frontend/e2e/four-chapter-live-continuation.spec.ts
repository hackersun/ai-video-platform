import { expect, test } from '@playwright/test';
import { devToken } from './helpers/production-os-fixture';

const userId = process.env.FOUR_CHAPTER_CANARY_USER_ID || '';
const novelId = process.env.FOUR_CHAPTER_CONTINUE_NOVEL_ID || '';
const runId = process.env.FOUR_CHAPTER_CONTINUE_RUN_ID || '';
const regenerateShotImages = process.env.FOUR_CHAPTER_REGENERATE_SHOT_IMAGES === '1';
const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';

test.describe.configure({ retries: 0 });

test('continue an authenticated four-chapter 3D native-audio run from the frontend', async ({ page }) => {
  test.setTimeout(25 * 60_000);
  expect(userId).toBeTruthy();
  expect(novelId).toBeTruthy();
  expect(runId).toBeTruthy();
  const token = devToken(userId);
  const headers = { Authorization: `Bearer ${token}` };
  await page.addInitScript(({ id, tokenValue, novel, run }) => {
    localStorage.setItem('auth_token', tokenValue);
    localStorage.setItem('user', JSON.stringify({ id, username: 'live-canary' }));
    localStorage.setItem(`series-run:${novel}`, run);
  }, { id: userId, tokenValue: token, novel: novelId, run: runId });

  await page.goto(`/novels/${novelId}`);
  await page.getByRole('tab', { name: '整书计划 (4)', exact: true }).click();
  const readyEpisodes = page.getByTestId('series-run-episodes').getByText('镜头就绪');
  if (await readyEpisodes.count() !== 4) {
    for (const configId of ['f03311c6-5ca3-4e88-a552-fb5623a394bd', '980cb5db-0281-4835-9486-a739fcb35d98']) {
      const tested = await page.request.post(`${apiBase}/llm/configs/${configId}/test`, {
        headers, data: { message: '四章前端实模连接验证' },
      });
      expect(tested.ok(), `model connection ${configId}: ${await tested.text()}`).toBe(true);
    }
    const enabled = await page.request.post(`${apiBase}/series-runs/${runId}/live-canary/enable`, { headers });
    expect(enabled.ok(), `enable live canary: ${await enabled.text()}`).toBe(true);
    const validated = await page.request.post(`${apiBase}/series-runs/${runId}/live-bindings/validate`, {
      headers, data: {
        image: 'f03311c6-5ca3-4e88-a552-fb5623a394bd',
        video: '980cb5db-0281-4835-9486-a739fcb35d98', native_audio: true,
      },
    });
    expect(validated.ok(), `validate live bindings: ${await validated.text()}`).toBe(true);
    await page.reload();
    await page.getByRole('tab', { name: '整书计划 (4)', exact: true }).click();
    await expect(page.getByText(/实模关键镜头验证已启用/)).toBeVisible({ timeout: 120_000 });
    await page.getByRole('button', { name: '继续推进' }).click();
  }
  await expect(page.getByTestId('series-run-episodes').getByText('镜头就绪')).toHaveCount(4, { timeout: 180_000 });
  const skillEvidence = page.getByTestId('series-run-skill-evidence');
  await expect(skillEvidence).toContainText('剧本 Skill');
  await expect(skillEvidence).toContainText('实体抽取 Skill');
  await expect(skillEvidence).toContainText('分镜 Skill');
  await expect(skillEvidence).toContainText('镜头提示词 Skill');
  const nativeAudio = page.getByLabel('本次使用 Seedance 1.5 原生配音');
  await nativeAudio.check();
  const preflight = page.getByTestId('live-preflight-plan');
  await expect(preflight).toContainText('当前由视频模型原生配音，无需锁定 TTS 声线。');

  const run = await (await page.request.get(`${apiBase}/series-runs/${runId}`, { headers })).json();
  const shotIds = run.run_metadata?.selected_anchor_shot_ids || [];
  expect(shotIds).toHaveLength(2);
  const existingMediaJobs = await (await page.request.get(
    `${apiBase}/media/jobs?novel_id=${novelId}`, { headers },
  )).json();
  const existingSelected = existingMediaJobs.filter((job: any) => shotIds.includes(job.shot_id));
  const alreadyCompleted = existingSelected.length === 2
    && existingSelected.every((job: any) => ['completed', 'succeeded'].includes(job.status));
  if (alreadyCompleted) {
    await expect(page.getByTestId('live-preflight-plan')).toContainText('再次生成前置检查');
    await expect(page.getByTestId('live-preflight-plan')).toContainText('已有成片不受本检查影响');
  }
  for (const shotId of shotIds) {
    const existing = await (await page.request.get(`${apiBase}/shots/${shotId}`, { headers })).json();
    if (!regenerateShotImages && existing.image_status === 'succeeded' && existing.image_url) continue;
    const image = await page.request.post(`${apiBase}/shots/${shotId}/generate-image`, {
      headers, data: { style: 'realistic-3d', model_config_id: 'f03311c6-5ca3-4e88-a552-fb5623a394bd' },
    });
    expect(image.ok(), `shot image ${shotId}: ${await image.text()}`).toBe(true);
    await expect.poll(async () => {
      const shot = await (await page.request.get(`${apiBase}/shots/${shotId}`, { headers })).json();
      return shot.image_status === 'succeeded' && Boolean(shot.image_url);
    }, { timeout: 10 * 60_000, intervals: [2_000, 5_000, 10_000] }).toBe(true);
  }

  if (!alreadyCompleted) {
    await page.getByRole('button', { name: '准备故事锁' }).click();
    await expect(page.getByText(/故事锁：locked/)).toBeVisible({ timeout: 180_000 });
    const confirm = page.getByRole('button', { name: /确认定稿 \d+ 个必需实体/ });
    if (await confirm.count()) await confirm.click();
    await expect(page.getByTestId('story-lock-closure-status')).toContainText('未解决 0', { timeout: 180_000 });
    const referenceLocked = page.getByText(/参考图：locked/);
    if (!await referenceLocked.isVisible()) {
      await page.getByRole('button', { name: '生成并锁定参考图' }).click();
    }
    await expect(referenceLocked).toBeVisible({ timeout: 10 * 60_000 });

    const responsePromise = page.waitForResponse((response) =>
      response.url().endsWith('/generate-selected') && response.request().method() === 'POST');
    await page.getByRole('button', { name: '生成所选 2 个关键镜头' }).click();
    const generation = await responsePromise;
    expect(generation.status(), await generation.text()).toBe(200);
  }
  await expect.poll(async () => {
    const jobs = await (await page.request.get(`${apiBase}/media/jobs?novel_id=${novelId}`, { headers })).json();
    const selected = jobs.filter((job: any) => shotIds.includes(job.shot_id));
    return selected.length === 2 && selected.every((job: any) => ['completed', 'succeeded'].includes(job.status));
  }, { timeout: 20 * 60_000, intervals: [5_000, 10_000] }).toBe(true);
  const completed = await (await page.request.get(
    `${apiBase}/media/jobs?novel_id=${novelId}`, { headers },
  )).json();
  const selected = completed.filter((job: any) => shotIds.includes(job.shot_id));
  expect(new Set(selected.map((job: any) => job.subtitle_track_id)).size).toBe(2);
  expect(selected.every((job: any) => job.extra_data?.subtitle_burned === true)).toBe(true);
  expect(selected.every((job: any) => job.extra_data?.audio_verification_required === true)).toBe(true);
  expect(selected.every((job: any) =>
    ['audio_activity_aligned_pending_semantic_verification', 'script_aligned_pending_audio_verification']
      .includes(job.extra_data?.subtitle_sync_status))).toBe(true);
});

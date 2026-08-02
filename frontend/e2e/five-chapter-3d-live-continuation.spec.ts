import { expect, test } from '@playwright/test';
import { writeFile } from 'node:fs/promises';

import { devToken } from './helpers/production-os-fixture';

const userId = process.env.FIVE_CHAPTER_LIVE_USER_ID || '';
const novelId = process.env.FIVE_CHAPTER_LIVE_NOVEL_ID || '';
const runId = process.env.FIVE_CHAPTER_LIVE_RUN_ID || '';
const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';
const mediaModels = [
  { capability: 'image_generation', profile: 'c6abf236-7020-52d8-9dcb-ede56b2c78e6', connection: '42ead6b0-3fd2-56cd-b3bf-e9799caa81b3', label: 'Seedream 图像' },
  { capability: 'video_generation', profile: 'f4352a4b-596e-5ba2-8e50-185b73e7150d', connection: '9c0c4a61-19f2-5a88-a50e-ec3203ebb8b2', label: 'Seedance 视频' },
] as const;

test.describe.configure({ retries: 0 });

test('continue the frontend-created five-chapter run through reference, first frames and three videos', async ({ page }, testInfo) => {
  test.setTimeout(30 * 60_000);
  expect(testInfo.retry).toBe(0);
  expect(userId).toBeTruthy();
  expect(novelId).toBeTruthy();
  expect(runId).toBeTruthy();
  const token = devToken(userId);
  const headers = { Authorization: `Bearer ${token}` };
  await page.addInitScript(({ id, tokenValue, novel, run }) => {
    localStorage.setItem('auth_token', tokenValue);
    localStorage.setItem('user', JSON.stringify({ id, username: 'sunqy' }));
    localStorage.setItem(`series-run:${novel}`, run);
  }, { id: userId, tokenValue: token, novel: novelId, run: runId });

  for (const model of mediaModels) {
    const query = new URLSearchParams({
      section: 'test-lab', capability: model.capability, level: 'connection',
      profileVersionId: model.profile, connectionId: model.connection,
    });
    await page.goto(`/llm-config?${query}`);
    await expect(page.getByLabel('兼容模型与连接')).toHaveValue(`${model.profile}:${model.connection}`, { timeout: 30_000 });
    await page.getByLabel('操作原因').fill(`五章3D续跑前置验证：${model.label}`);
    await page.getByRole('button', { name: '提交认证' }).click();
    await expect(page.getByText('已通过', { exact: true })).toBeVisible({ timeout: 120_000 });
  }

  await page.goto(`/novels/${novelId}?tab=series-plan`);
  await page.getByRole('tab', { name: '整书计划 (5)', exact: true }).click();
  const panel = page.getByTestId('series-run-panel');
  await expect(panel.getByTestId('series-run-episodes').getByText('镜头就绪')).toHaveCount(5, { timeout: 120_000 });
  await expect(panel.getByTestId('series-run-skill-evidence')).toContainText('剧本 Skill');
  await expect(panel.getByTestId('series-run-skill-evidence')).toContainText('实体抽取 Skill');
  await expect(panel.getByTestId('series-run-skill-evidence')).toContainText('分镜 Skill');
  await expect(panel.getByTestId('series-run-skill-evidence')).toContainText('镜头提示词 Skill');

  await panel.getByRole('button', { name: '3 镜头前中后代表验证' }).click();
  await expect(panel.getByLabel(/选择第\d+章镜头/)).toHaveCount(3);
  const labels = await panel.getByLabel(/选择第\d+章镜头/).evaluateAll((nodes: Element[]) => nodes.map((node) => node.getAttribute('aria-label')));
  expect(labels.sort()).toEqual(['选择第1章镜头', '选择第3章镜头', '选择第5章镜头']);
  await panel.getByLabel('本次使用 Seedance 1.5 原生配音').check();
  await panel.getByRole('button', { name: /启用实模关键镜头验证|重新验证模型绑定/ }).click();
  await expect(panel.getByText(/实模关键镜头验证已启用/)).toBeVisible({ timeout: 120_000 });

  const completedRun = await (await page.request.get(`${apiBase}/series-runs/${runId}`, { headers })).json();
  const completedShotIds = completedRun.run_metadata?.selected_anchor_shot_ids || [];
  const completedMedia = (await (await page.request.get(`${apiBase}/media/jobs?novel_id=${novelId}`, { headers })).json())
    .filter((job: any) => completedShotIds.includes(job.shot_id));
  if (completedShotIds.length === 3 && completedMedia.length === 3
      && completedMedia.every((job: any) => ['completed', 'succeeded'].includes(job.status))) {
    const repaired = await page.request.post(`${apiBase}/series-runs/${runId}/reconcile-selected`, { headers });
    expect(repaired.status(), await repaired.text()).toBe(200);
    const refreshedMedia = (await (await page.request.get(`${apiBase}/media/jobs?novel_id=${novelId}`, { headers })).json())
      .filter((job: any) => completedShotIds.includes(job.shot_id));
    expect(refreshedMedia.every((job: any) => job.subtitle_track_id)).toBe(true);
    expect(refreshedMedia.every((job: any) => job.extra_data?.subtitle_burned === true)).toBe(true);
    expect(refreshedMedia.every((job: any) => job.extra_data?.subtitle_timing_contract_version === 'native_audio_activity_v7')).toBe(true);
    await writeFile(testInfo.outputPath('live-evidence.json'), JSON.stringify({
      novel_id: novelId, run_id: runId, selected_shot_ids: completedShotIds,
      style: 'xianxia-3d', native_audio: true, spent_rmb: completedRun.cost_summary?.spent_rmb,
      jobs: refreshedMedia,
    }, null, 2));
    await page.screenshot({ path: testInfo.outputPath('02-three-videos-completed.png'), fullPage: true });
    return;
  }

  const staleStoryLock = panel.getByText(/story_lock_stale/);
  if (await staleStoryLock.count()) {
    await panel.getByRole('button', { name: '整理资产并重试' }).click();
    await expect(panel.getByTestId('story-asset-repair-result')).toContainText('已整理 5 章', { timeout: 180_000 });
    await expect(panel.getByText(/故事锁：locked/)).toBeVisible({ timeout: 180_000 });
  }

  const beforeReference = await (await page.request.get(`${apiBase}/series-runs/${runId}`, { headers })).json();
  if (!beforeReference.run_metadata?.reference_preparation?.asset_id) {
    await panel.getByRole('button', { name: '整理资产并重试' }).click();
    await expect(panel.getByTestId('story-asset-repair-result')).toContainText('已整理 5 章', { timeout: 180_000 });
    await expect(panel.getByText(/故事锁：locked/)).toBeVisible({ timeout: 180_000 });
    const confirm = panel.getByRole('button', { name: /确认定稿 \d+ 个必需实体/ });
    if (await confirm.count()) await confirm.click();
    await expect(panel.getByTestId('story-lock-closure-status')).toContainText('未解决 0', { timeout: 180_000 });
    const recoverReference = panel.getByRole('button', { name: '恢复已生成参考图' });
    if (await recoverReference.count()) await recoverReference.click();
    else await panel.getByRole('button', { name: '生成并锁定参考图' }).click();
  } else {
    const prepareReference = panel.getByRole('button', { name: '生成并锁定参考图' });
    if (await prepareReference.isEnabled()) await prepareReference.click();
  }
  await expect(panel.getByText(/参考图：locked/)).toBeVisible({ timeout: 10 * 60_000 });

  await panel.getByRole('button', { name: '生成 3 个镜头首帧' }).click();
  await expect.poll(async () => {
    if (await panel.getByText(/3 个镜头首帧已全部完成/).count()) return 'complete';
    if (await panel.getByRole('button', { name: /只重试 \d+ 个失败首帧/ }).count()) return 'retry';
    return 'pending';
  }, { timeout: 15 * 60_000, intervals: [2_000, 5_000, 10_000] }).not.toBe('pending');
  const retry = panel.getByRole('button', { name: /只重试 \d+ 个失败首帧/ });
  if (await retry.count()) await retry.click();
  await expect(panel.getByText(/3 个镜头首帧已全部完成/)).toBeVisible({ timeout: 15 * 60_000 });

  const runBeforeVideo = await (await page.request.get(`${apiBase}/series-runs/${runId}`, { headers })).json();
  const selectedShotIds = runBeforeVideo.run_metadata?.selected_anchor_shot_ids || [];
  expect(selectedShotIds).toHaveLength(3);
  let jobs: any[] = [];
  const existingJobs = await (await page.request.get(`${apiBase}/media/jobs?novel_id=${novelId}`, { headers })).json();
  jobs = existingJobs.filter((job: any) => selectedShotIds.includes(job.shot_id));
  const alreadyCompleted = jobs.length === 3
    && jobs.every((job: any) => ['completed', 'succeeded'].includes(job.status));
  if (!alreadyCompleted) {
    const preflight = panel.getByTestId('live-preflight-plan');
    await expect(preflight).toContainText('已就绪', { timeout: 120_000 });
    await expect(preflight).toContainText('本轮预计 ¥6.00');
  }
  await page.screenshot({ path: testInfo.outputPath('01-reference-and-first-frames-ready.png'), fullPage: true });
  if (!alreadyCompleted) {
    const response = page.waitForResponse((item) => item.url().endsWith('/generate-selected') && item.request().method() === 'POST');
    await panel.getByRole('button', { name: '生成所选 3 个关键镜头' }).click();
    const generated = await response;
    expect(generated.status(), await generated.text()).toBe(200);
  }
  await expect.poll(async () => {
    const allJobs = await (await page.request.get(`${apiBase}/media/jobs?novel_id=${novelId}`, { headers })).json();
    jobs = allJobs.filter((job: any) => selectedShotIds.includes(job.shot_id));
    return jobs.length === 3 && jobs.every((job: any) => ['completed', 'succeeded'].includes(job.status));
  }, { timeout: 20 * 60_000, intervals: [5_000, 10_000] }).toBe(true);

  const subtitleRepair = await page.request.post(`${apiBase}/series-runs/${runId}/reconcile-selected`, { headers });
  expect(subtitleRepair.status(), await subtitleRepair.text()).toBe(200);
  jobs = (await (await page.request.get(`${apiBase}/media/jobs?novel_id=${novelId}`, { headers })).json())
    .filter((job: any) => selectedShotIds.includes(job.shot_id));

  const finalRun = await (await page.request.get(`${apiBase}/series-runs/${runId}`, { headers })).json();
  const evidence = {
    novel_id: novelId, run_id: runId, selected_shot_ids: selectedShotIds,
    style: 'xianxia-3d', native_audio: true, spent_rmb: finalRun.cost_summary?.spent_rmb,
    jobs: jobs.map((job: any) => ({
      id: job.id, shot_id: job.shot_id, status: job.status,
      output_video_url: job.output_video_url, output_manifest_url: job.output_manifest_url,
      subtitle_track_id: job.subtitle_track_id,
      subtitle_burned: job.extra_data?.subtitle_burned,
      subtitle_sync_status: job.extra_data?.subtitle_sync_status,
      subtitle_timing_contract_version: job.extra_data?.subtitle_timing_contract_version,
      audio_verification_required: job.extra_data?.audio_verification_required,
    })),
  };
  expect(jobs.every((job: any) => job.subtitle_track_id)).toBe(true);
  expect(jobs.every((job: any) => job.extra_data?.subtitle_burned === true)).toBe(true);
  expect(jobs.every((job: any) => job.extra_data?.subtitle_timing_contract_version === 'native_audio_activity_v7')).toBe(true);
  await writeFile(testInfo.outputPath('live-evidence.json'), JSON.stringify(evidence, null, 2));
  await page.screenshot({ path: testInfo.outputPath('02-three-videos-completed.png'), fullPage: true });
});

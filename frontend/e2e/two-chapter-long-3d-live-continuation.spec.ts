import { expect, test } from '@playwright/test';
import { writeFile } from 'node:fs/promises';

import { devToken } from './helpers/production-os-fixture';

const userId = process.env.TWO_CHAPTER_LIVE_USER_ID || '';
const novelId = process.env.TWO_CHAPTER_LIVE_NOVEL_ID || '';
const runId = process.env.TWO_CHAPTER_LIVE_RUN_ID || '';
const repairShotId = process.env.TWO_CHAPTER_LIVE_REPAIR_SHOT_ID || '';
const retestModels = process.env.TWO_CHAPTER_LIVE_RETEST_MODELS === '1';
const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';
const mediaModels = [
  {
    capability: 'image_generation',
    profile: 'c6abf236-7020-52d8-9dcb-ede56b2c78e6',
    connection: '42ead6b0-3fd2-56cd-b3bf-e9799caa81b3',
    label: 'Seedream 5.0 Pro 图像',
  },
  {
    capability: 'video_generation',
    profile: 'f4352a4b-596e-5ba2-8e50-185b73e7150d',
    connection: '9c0c4a61-19f2-5a88-a50e-ec3203ebb8b2',
    label: 'Seedance 1.5 Pro 视频',
  },
] as const;

test.describe.configure({ retries: 0 });

test('continue the frontend-created two-chapter run through two native-audio videos', async ({ page }, testInfo) => {
  test.setTimeout(30 * 60_000);
  expect(testInfo.retry).toBe(0);
  expect(userId).toBeTruthy();
  expect(novelId).toBeTruthy();
  expect(runId).toBeTruthy();

  const token = devToken(userId);
  const headers = { Authorization: `Bearer ${token}` };
  const initialRun = await (await page.request.get(`${apiBase}/series-runs/${runId}`, { headers })).json();
  const referenceAlreadyLocked = Boolean(initialRun.run_metadata?.reference_preparation?.asset_id);
  const initialShotIds = initialRun.run_metadata?.selected_anchor_shot_ids || [];
  const initialJobs = (await (await page.request.get(`${apiBase}/media/jobs?novel_id=${novelId}`, { headers })).json())
    .filter((job: any) => initialShotIds.includes(job.shot_id));
  const deliveriesAlreadyCompleted = initialShotIds.length === 2 && initialJobs.length === 2
    && initialJobs.every((job: any) => ['completed', 'succeeded'].includes(job.status));
  await page.addInitScript(({ id, tokenValue, novel, run }) => {
    localStorage.setItem('auth_token', tokenValue);
    localStorage.setItem('user', JSON.stringify({ id, username: 'sunqy' }));
    localStorage.setItem(`series-run:${novel}`, run);
  }, { id: userId, tokenValue: token, novel: novelId, run: runId });

  for (const model of (retestModels ? mediaModels : []).filter((item) => (
    (!deliveriesAlreadyCompleted || Boolean(repairShotId))
      && (!referenceAlreadyLocked || item.capability === 'video_generation')
  ))) {
    const query = new URLSearchParams({
      section: 'test-lab',
      capability: model.capability,
      level: 'connection',
      profileVersionId: model.profile,
      connectionId: model.connection,
    });
    await page.goto(`/llm-config?${query}`);
    await expect(page.getByLabel('兼容模型与连接')).toHaveValue(
      `${model.profile}:${model.connection}`,
      { timeout: 30_000 },
    );
    await page.getByLabel('操作原因').fill(`两章长篇3D断点续验：${model.label}`);
    await page.getByRole('button', { name: '提交认证' }).click();
    await expect(page.getByText('已通过', { exact: true })).toBeVisible({ timeout: 120_000 });
  }

  await page.goto(`/novels/${novelId}?tab=series-plan`);
  await page.getByRole('tab', { name: '整书计划 (2)', exact: true }).click();
  const panel = page.getByTestId('series-run-panel');
  await expect(panel.getByTestId('series-run-episodes').getByText('镜头就绪')).toHaveCount(2, { timeout: 10 * 60_000 });
  for (const skill of ['剧本 Skill', '实体抽取 Skill', '分镜 Skill', '镜头提示词 Skill']) {
    await expect(panel.getByTestId('series-run-skill-evidence')).toContainText(skill);
  }

  await panel.getByRole('button', { name: '2 镜头冒烟验证' }).click();
  await expect(panel.getByLabel(/选择第\d+章镜头/)).toHaveCount(2);
  const labels = await panel.getByLabel(/选择第\d+章镜头/).evaluateAll(
    (nodes: Element[]) => nodes.map((node) => node.getAttribute('aria-label')),
  );
  expect(labels.sort()).toEqual(['选择第1章镜头', '选择第2章镜头']);
  await panel.getByLabel('本次使用 Seedance 1.5 原生配音').check();
  await panel.getByRole('button', {
    name: initialRun.budget_policy?.live_canary === true
      ? /重新验证视频绑定|重新验证模型绑定/
      : '启用实模关键镜头验证',
  }).click();
  await expect(panel.getByText(/实模关键镜头验证已启用/)).toBeVisible({ timeout: 120_000 });

  const beforeReference = await (await page.request.get(`${apiBase}/series-runs/${runId}`, { headers })).json();
  if (!beforeReference.run_metadata?.reference_preparation?.asset_id) {
    const prepareStoryLock = panel.getByRole('button', { name: '准备故事锁', exact: true });
    const repairStoryLock = panel.getByRole('button', { name: '整理资产并重试', exact: true });
    await expect.poll(async () => {
      if (await prepareStoryLock.isEnabled()) return 'prepare';
      if (await repairStoryLock.isEnabled()) return 'repair';
      return 'pending';
    }, { timeout: 180_000, intervals: [1_000, 2_000, 5_000] }).not.toBe('pending');
    const storyLockReady = panel.getByText(/故事锁：locked/);
    if (await prepareStoryLock.isEnabled()) {
      await prepareStoryLock.click();
      await expect.poll(async () => (
        await storyLockReady.count() > 0 || await repairStoryLock.isEnabled()
      ), { timeout: 180_000, intervals: [1_000, 2_000, 5_000] }).toBe(true);
      if (!await storyLockReady.count()) await repairStoryLock.click();
    } else {
      await repairStoryLock.click();
    }
    await expect(storyLockReady).toBeVisible({ timeout: 180_000 });
    const confirm = panel.getByRole('button', { name: /确认定稿 \d+ 个必需实体/ });
    if (await confirm.count()) await confirm.click();
    await expect(panel.getByTestId('story-lock-closure-status')).toContainText('未解决 0', { timeout: 180_000 });
    const lockedRun = await (await page.request.get(`${apiBase}/series-runs/${runId}`, { headers })).json();
    const lockedShotIds = lockedRun.run_metadata?.selected_anchor_shot_ids || [];
    const lockedShots = await Promise.all(lockedShotIds.map(async (shotId: string) => (
      await (await page.request.get(`${apiBase}/shots/${shotId}`, { headers })).json()
    )));
    const characterIds = new Set(lockedShots.flatMap((shot: any) => (
      (shot.character_refs || []).map((ref: any) => String(ref.entity_id || ref.id || ref))
    )));
    expect(lockedShots).toHaveLength(2);
    expect(characterIds.size).toBe(1);
    const recoverReference = panel.getByRole('button', { name: '恢复已生成参考图' });
    if (await recoverReference.count()) await recoverReference.click();
    else await panel.getByRole('button', { name: '生成并锁定参考图' }).click();
  }
  await expect(panel.getByText(/参考图：locked/)).toBeVisible({ timeout: 10 * 60_000 });

  const firstFramesReady = panel.getByText(/2 个镜头首帧已全部完成/);
  if (!await firstFramesReady.count()) {
    await panel.getByRole('button', { name: '生成 2 个镜头首帧' }).click();
    await expect.poll(async () => {
      if (await firstFramesReady.count()) return 'complete';
      if (await panel.getByRole('button', { name: /只重试 \d+ 个失败首帧/ }).count()) return 'failed';
      return 'pending';
    }, { timeout: 15 * 60_000, intervals: [2_000, 5_000, 10_000] }).not.toBe('pending');
  }
  await expect(firstFramesReady).toBeVisible({ timeout: 30_000 });
  const refreshReferenceDelivery = panel.getByRole('button', { name: '刷新参考图公网地址' });
  if (await refreshReferenceDelivery.count() && await refreshReferenceDelivery.isEnabled()) {
    await refreshReferenceDelivery.click();
  }

  const runBeforeVideo = await (await page.request.get(`${apiBase}/series-runs/${runId}`, { headers })).json();
  const selectedShotIds = runBeforeVideo.run_metadata?.selected_anchor_shot_ids || [];
  expect(selectedShotIds).toHaveLength(2);
  if (repairShotId) {
    expect(selectedShotIds).toContain(repairShotId);
    const repairShot = await (await page.request.get(`${apiBase}/shots/${repairShotId}`, { headers })).json();
    if (!repairShot.extra_data?.first_frame_revision) {
      const episodeNumber = selectedShotIds.indexOf(repairShotId) + 1;
      const shotCard = panel.getByLabel(`选择第${episodeNumber}章镜头`).locator('..');
      await shotCard.getByRole('button', { name: '单独重做本镜头参考' }).click();
      await expect(panel.getByText('当前镜头参考已更新；其他章节继续复用原有角色三视图。')).toBeVisible({ timeout: 10 * 60_000 });
    }
  }
  await page.screenshot({ path: testInfo.outputPath('01-reference-and-first-frames-ready.png'), fullPage: true });

  let jobs: any[] = (await (await page.request.get(`${apiBase}/media/jobs?novel_id=${novelId}`, { headers })).json())
    .filter((job: any) => selectedShotIds.includes(job.shot_id));
  const alreadyCompleted = !repairShotId && jobs.length === 2
    && jobs.every((job: any) => ['completed', 'succeeded'].includes(job.status));
  if (!alreadyCompleted) {
    await expect(panel.getByTestId('live-preflight-plan')).toContainText('已就绪', { timeout: 120_000 });
    const response = page.waitForResponse(
      (item) => item.url().endsWith('/generate-selected') && item.request().method() === 'POST',
    );
    await panel.getByRole('button', { name: '生成所选 2 个关键镜头' }).click();
    const generated = await response;
    const generationText = await generated.text();
    expect(generated.status(), generationText).toBe(200);
    const generation = JSON.parse(generationText);
    const pendingVideoJobIds = generation.pending_video_job_ids || [];
    if (pendingVideoJobIds.length) {
      await expect.poll(async () => {
        const refreshed = await Promise.all(pendingVideoJobIds.map(async (jobId: string) => (
          await (await page.request.post(`${apiBase}/video/jobs/${jobId}/refresh`, { headers })).json()
        )));
        await page.request.post(`${apiBase}/series-runs/${runId}/reconcile-selected`, { headers });
        return refreshed.every((job: any) => ['completed', 'succeeded'].includes(job.status));
      }, { timeout: 20 * 60_000, intervals: [5_000, 10_000] }).toBe(true);
    }
  }

  await expect.poll(async () => {
    const allJobs = await (await page.request.get(`${apiBase}/media/jobs?novel_id=${novelId}`, { headers })).json();
    jobs = allJobs.filter((job: any) => selectedShotIds.includes(job.shot_id));
    return jobs.length === 2 && jobs.every((job: any) => ['completed', 'succeeded'].includes(job.status));
  }, { timeout: 20 * 60_000, intervals: [5_000, 10_000] }).toBe(true);

  const reconcile = await page.request.post(`${apiBase}/series-runs/${runId}/reconcile-selected`, { headers });
  expect(reconcile.status(), await reconcile.text()).toBe(200);
  jobs = (await (await page.request.get(`${apiBase}/media/jobs?novel_id=${novelId}`, { headers })).json())
    .filter((job: any) => selectedShotIds.includes(job.shot_id));
  const finalRun = await (await page.request.get(`${apiBase}/series-runs/${runId}`, { headers })).json();
  const chapters = await (await page.request.get(`${apiBase}/chapters/novel/${novelId}`, { headers })).json();
  const evidence = {
    novel_id: novelId,
    run_id: runId,
    chapter_lengths: chapters.map((chapter: any) => ({
      chapter_number: chapter.chapter_number,
      non_whitespace_chars: String(chapter.content || '').replace(/\s/g, '').length,
    })),
    selected_shot_ids: selectedShotIds,
    style: 'xianxia-3d',
    native_audio: true,
    spent_rmb: finalRun.cost_summary?.spent_rmb,
    jobs: jobs.map((job: any) => ({
      id: job.id,
      shot_id: job.shot_id,
      status: job.status,
      output_video_url: job.output_video_url,
      public_video_url: job.extra_data?.subtitle_public_video_url,
      subtitle_track_id: job.subtitle_track_id,
      subtitle_burned: job.extra_data?.subtitle_burned,
      subtitle_timing_contract_version: job.extra_data?.subtitle_timing_contract_version,
      provider_label_removed: job.extra_data?.provider_label_removed,
      native_audio_loudness: job.extra_data?.native_audio_loudness,
    })),
  };
  expect(evidence.chapter_lengths).toHaveLength(2);
  expect(evidence.chapter_lengths.every(
    (item: any) => item.non_whitespace_chars >= 600 && item.non_whitespace_chars <= 800,
  )).toBe(true);
  expect(jobs.every((job: any) => job.subtitle_track_id)).toBe(true);
  expect(jobs.every((job: any) => job.extra_data?.subtitle_burned === true)).toBe(true);
  expect(jobs.every(
    (job: any) => job.extra_data?.subtitle_timing_contract_version === 'native_audio_activity_v9',
  )).toBe(true);
  expect(jobs.every((job: any) => job.extra_data?.provider_label_removed === true)).toBe(true);
  await writeFile(testInfo.outputPath('live-evidence.json'), JSON.stringify(evidence, null, 2));
  await page.screenshot({ path: testInfo.outputPath('02-two-videos-completed.png'), fullPage: true });
});

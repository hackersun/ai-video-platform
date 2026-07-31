import { expect, test } from '@playwright/test';
import { writeFile } from 'node:fs/promises';

import { devToken } from './helpers/production-os-fixture';
import { twoChapterLong3dNovel } from './helpers/two-chapter-long-3d-fixture';

const enabled = process.env.TWO_CHAPTER_LIVE === '1';
const userId = process.env.TWO_CHAPTER_LIVE_USER_ID || '';
const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';

const certifiedModels = [
  { capability: 'text_generation', profile: '14a411fa-c5ff-5c2a-bb95-7352d5ef9355', connection: '776d3482-027b-4145-8fde-7f3ae77ced71', label: 'Coding Plan 文本' },
  { capability: 'image_generation', profile: 'c6abf236-7020-52d8-9dcb-ede56b2c78e6', connection: '42ead6b0-3fd2-56cd-b3bf-e9799caa81b3', label: 'Seedream 5.0 Pro 图像' },
  { capability: 'video_generation', profile: 'f4352a4b-596e-5ba2-8e50-185b73e7150d', connection: '9c0c4a61-19f2-5a88-a50e-ec3203ebb8b2', label: 'Seedance 1.5 Pro 视频' },
] as const;

async function certifyFromUi(page: any, model: typeof certifiedModels[number]) {
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
  await page.getByLabel('操作原因').fill(`两章长篇3D实模前置验证：${model.label}`);
  await page.getByRole('button', { name: '提交认证' }).click();
  await expect(page.getByText('已通过', { exact: true })).toBeVisible({ timeout: 120_000 });
}

test.describe.configure({ retries: 0 });

test('sunqy creates two long chapters and completes two native-audio videos from UI', async ({ page }, testInfo) => {
  test.setTimeout(30 * 60_000);
  test.skip(!enabled, 'explicit two-chapter live authorization required');
  expect(testInfo.retry).toBe(0);
  expect(userId).toBeTruthy();
  expect(Number(process.env.TWO_CHAPTER_LIVE_MAX_RMB)).toBe(10);
  for (const chapter of twoChapterLong3dNovel.chapters) {
    expect(chapter.content.replace(/\s/g, '').length).toBeGreaterThanOrEqual(600);
    expect(chapter.content.replace(/\s/g, '').length).toBeLessThanOrEqual(800);
  }

  const token = devToken(userId);
  const headers = { Authorization: `Bearer ${token}` };
  await page.addInitScript(({ id, tokenValue }) => {
    localStorage.setItem('auth_token', tokenValue);
    localStorage.setItem('user', JSON.stringify({ id, username: 'sunqy' }));
  }, { id: userId, tokenValue: token });

  for (const model of certifiedModels) await certifyFromUi(page, model);

  const title = `${twoChapterLong3dNovel.title}-${Date.now()}`;
  await page.goto('/novels/new');
  await page.getByPlaceholder('输入小说标题').fill(title);
  await page.getByPlaceholder('简要介绍小说内容').fill(twoChapterLong3dNovel.description);
  await page.locator('select').first().selectOption('fantasy');
  await page.getByRole('button', { name: '保存草稿' }).click();
  await page.waitForURL(/\/novels$/);
  const href = await page.getByRole('link', { name: new RegExp(title) }).first().getAttribute('href');
  expect(href).toMatch(/^\/novels\//);
  const novelId = String(href).split('/').at(-1)!;
  await page.goto(`${href}?tab=chapters`);

  for (const chapter of twoChapterLong3dNovel.chapters) {
    await page.getByRole('button', { name: '新建章节' }).click();
    await page.getByPlaceholder(/章节标题，可留空/).fill(chapter.title);
    await page.getByPlaceholder(/章节内容或创作方向/).fill(chapter.content);
    await page.getByRole('button', { name: '手动创建' }).click();
    await expect(page.getByText(chapter.title, { exact: true })).toBeVisible({ timeout: 30_000 });
  }

  await page.getByRole('tab', { name: /整书计划/ }).click();
  await page.getByLabel('更多风格').selectOption('xianxia-3d');
  await page.getByRole('button', { name: '生成多集计划', exact: true }).click();
  await expect(page.getByText('xianxia-3d · 9:16')).toBeVisible({ timeout: 120_000 });
  const panel = page.getByTestId('series-run-panel');
  await panel.getByRole('button', { name: '整书自动制作', exact: true }).click();
  await expect(panel.getByTestId('series-run-episodes').getByText('镜头就绪')).toHaveCount(2, { timeout: 240_000 });
  await expect(panel.getByTestId('series-run-skill-evidence')).toContainText('剧本 Skill');
  await expect(panel.getByTestId('series-run-skill-evidence')).toContainText('实体抽取 Skill');
  await expect(panel.getByTestId('series-run-skill-evidence')).toContainText('分镜 Skill');
  await expect(panel.getByTestId('series-run-skill-evidence')).toContainText('镜头提示词 Skill');

  await panel.getByRole('button', { name: '2 镜头冒烟验证' }).click();
  await expect(panel.getByLabel(/选择第\d+章镜头/)).toHaveCount(2);
  const labels = await panel.getByLabel(/选择第\d+章镜头/).evaluateAll(
    (nodes: Element[]) => nodes.map((node) => node.getAttribute('aria-label')),
  );
  expect(labels.sort()).toEqual(['选择第1章镜头', '选择第2章镜头']);
  await panel.getByLabel('本次使用 Seedance 1.5 原生配音').check();
  await panel.getByRole('button', { name: '启用实模关键镜头验证' }).click();
  await expect(panel.getByText(/实模关键镜头验证已启用/)).toBeVisible({ timeout: 120_000 });

  await panel.getByRole('button', { name: '准备故事锁' }).click();
  await expect(panel.getByText(/故事锁：locked/)).toBeVisible({ timeout: 180_000 });
  const confirm = panel.getByRole('button', { name: /确认定稿 \d+ 个必需实体/ });
  if (await confirm.count()) await confirm.click();
  await expect(panel.getByTestId('story-lock-closure-status')).toContainText('未解决 0', { timeout: 180_000 });
  await panel.getByRole('button', { name: '生成并锁定参考图' }).click();
  await expect(panel.getByText(/参考图：locked/)).toBeVisible({ timeout: 10 * 60_000 });

  await panel.getByRole('button', { name: '生成 2 个镜头首帧' }).click();
  await expect.poll(async () => {
    if (await panel.getByText(/2 个镜头首帧已全部完成/).count()) return 'complete';
    if (await panel.getByRole('button', { name: /只重试 \d+ 个失败首帧/ }).count()) return 'retry';
    return 'pending';
  }, { timeout: 15 * 60_000, intervals: [2_000, 5_000, 10_000] }).not.toBe('pending');
  const retry = panel.getByRole('button', { name: /只重试 \d+ 个失败首帧/ });
  if (await retry.count()) await retry.click();
  await expect(panel.getByText(/2 个镜头首帧已全部完成/)).toBeVisible({ timeout: 15 * 60_000 });
  await expect(panel.getByTestId('live-preflight-plan')).toContainText('已就绪', { timeout: 120_000 });

  const runId = await page.evaluate((id) => localStorage.getItem(`series-run:${id}`), novelId);
  expect(runId).toBeTruthy();
  const runBeforeVideo = await (await page.request.get(`${apiBase}/series-runs/${runId}`, { headers })).json();
  const selectedShotIds = runBeforeVideo.run_metadata?.selected_anchor_shot_ids || [];
  expect(selectedShotIds).toHaveLength(2);
  await page.screenshot({ path: testInfo.outputPath('01-two-chapter-ready.png'), fullPage: true });

  const generationResponse = page.waitForResponse(
    (response) => response.url().endsWith('/generate-selected')
      && response.request().method() === 'POST',
  );
  await panel.getByRole('button', { name: '生成所选 2 个关键镜头' }).click();
  expect((await generationResponse).status()).toBe(200);

  let jobs: any[] = [];
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
    title,
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
      native_audio_loudness: job.extra_data?.native_audio_loudness,
    })),
  };
  expect(evidence.chapter_lengths).toHaveLength(2);
  expect(evidence.chapter_lengths.every((item: any) => item.non_whitespace_chars >= 600 && item.non_whitespace_chars <= 800)).toBe(true);
  expect(jobs.every((job: any) => job.subtitle_track_id)).toBe(true);
  expect(jobs.every((job: any) => job.extra_data?.subtitle_burned === true)).toBe(true);
  expect(jobs.every((job: any) => job.extra_data?.subtitle_timing_contract_version === 'native_audio_activity_v6')).toBe(true);
  await writeFile(testInfo.outputPath('live-evidence.json'), JSON.stringify(evidence, null, 2));
  await page.screenshot({ path: testInfo.outputPath('02-two-videos-completed.png'), fullPage: true });
});

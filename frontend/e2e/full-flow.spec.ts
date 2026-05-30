import { expect, test } from '@playwright/test';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `e2e-user-${Date.now()}`;
  const token = devToken(userId);
  await page.addInitScript(({ authToken, authUserId }) => {
    localStorage.setItem('auth_token', authToken);
    localStorage.setItem('user', JSON.stringify({
      id: authUserId,
      username: authUserId,
      email: `${authUserId}@example.test`,
    }));
  }, { authToken: token, authUserId: userId });
});

async function apiPost(page: any, endpoint: string, body: any) {
  return page.evaluate(async ({ url, payload }) => {
    const token = localStorage.getItem('auth_token');
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(`${url} failed: HTTP ${response.status} ${JSON.stringify(data)}`);
    }
    return data;
  }, { url: `${API_BASE}${endpoint}`, payload: body });
}

async function apiGet(page: any, endpoint: string) {
  return page.evaluate(async (url) => {
    const token = localStorage.getItem('auth_token');
    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(`${url} failed: HTTP ${response.status} ${JSON.stringify(data)}`);
    }
    return data;
  }, `${API_BASE}${endpoint}`);
}

async function apiPut(page: any, endpoint: string, body: any) {
  return page.evaluate(async ({ url, payload }) => {
    const token = localStorage.getItem('auth_token');
    const response = await fetch(url, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(`${url} failed: HTTP ${response.status} ${JSON.stringify(data)}`);
    }
    return data;
  }, { url: `${API_BASE}${endpoint}`, payload: body });
}

test('DEV_MODE novel to anime video flow is runnable from the frontend session', async ({ page }) => {
  const stamp = Date.now();
  await page.goto('/dashboard');
  await expect(page.locator('body')).toBeVisible();

  const novel = await apiPost(page, '/novels', {
    title: `E2E完整流程小说-${stamp}`,
    description: '一名少年在雨夜城市中觉醒星光能力。',
    genre: 'fantasy',
    style: 'anime',
    status: 'writing',
  });

  const chapter = await apiPost(page, '/chapters', {
    novel_id: novel.id,
    title: '第一章 雨夜星光',
    chapter_number: 1,
    content: '雨夜中，林澈听见远处钟声。他抬头看见云层裂开，星光落在掌心。',
  });

  const character = await apiPost(page, '/characters', {
    name: `林澈-${stamp}`,
    description: '主角，谨慎但坚定。',
    appearance: '黑发，蓝色外套，掌心有星光纹路。',
    personality: '冷静、善良、行动力强',
    voice: 'female-shaonj',
    tags: ['主角'],
  });

  const avatar = await apiPost(page, '/images/generate', {
    prompt: 'anime boy, black hair, blue jacket, star light in palm',
    style: 'anime',
    character_id: character.id,
  });
  expect(avatar.status).toBe('succeeded');
  expect(avatar.image_urls.length).toBeGreaterThan(0);

  const script = await apiPost(page, '/scripts', {
    novel_id: novel.id,
    title: `E2E完整流程剧本-${stamp}`,
    description: '雨夜觉醒场景',
    content: '场景：雨夜街道。林澈抬头望向裂开的云层。\n台词：林澈：这道光，在回应我。',
    genre: 'fantasy',
    style: 'anime',
  });

  const storyboard = await apiPost(page, '/storyboards', {
    script_id: script.id,
    title: `E2E完整流程分镜-${stamp}`,
    description: '主角觉醒分镜',
    content: { style: 'anime', consistency: 'same character and rainy city scene' },
  });

  const shot = await apiPost(page, '/shots', {
    storyboard_id: storyboard.id,
    shot_number: 1,
    duration: 4,
    prompt: 'anime cinematic shot, rainy neon street, boy raises glowing hand, consistent character',
    dialogue: '林澈：这道光，在回应我。',
    visual_description: '雨夜霓虹街道，主角掌心星光照亮脸庞。',
    camera_angle: 'medium shot',
    character_refs: [{ character_id: character.id, expression: 'determined' }],
  });

  const shotImage = await apiPost(page, '/images/generate', {
    prompt: shot.prompt,
    style: 'anime',
    shot_id: shot.id,
  });
  expect(shotImage.status).toBe('succeeded');

  const tts = await apiPost(page, '/tts/generate', {
    text_content: shot.dialogue,
    title: `E2E完整流程配音-${stamp}`,
    voice_model: 'female-shaonj',
    speed: 1,
    novel_id: novel.id,
    chapter_id: chapter.id,
    script_id: script.id,
    storyboard_id: storyboard.id,
    shot_id: shot.id,
    character_id: character.id,
  });
  expect(tts.status).toBe('succeeded');
  expect(tts.audio_url).toBeTruthy();

  const video = await apiPost(page, '/video/generate', {
    prompt: shot.prompt,
    duration: 4,
    resolution: '720p',
    image_url: shotImage.image_urls[0],
    novel_id: novel.id,
    script_id: script.id,
    storyboard_id: storyboard.id,
    shot_id: shot.id,
  });
  expect(video.status).toBe('succeeded');

  const videoStatus = await apiGet(page, `/video/status/${video.task_id}`);
  expect(videoStatus.status).toBe('succeeded');
  expect(videoStatus.video_url).toBeTruthy();

  const synthesis = await apiPost(page, '/synthesis/create', {
    title: `E2E完整流程成片-${stamp}`,
    video_job_id: video.job_id,
    tts_job_id: tts.job_id || tts.id,
  });
  expect(synthesis.status).toBe('succeeded');
  expect(synthesis.output_url).toBeTruthy();

  const refreshedShot = await apiGet(page, `/shots/${shot.id}`);
  expect(refreshedShot.image_status).toBe('succeeded');
  expect(refreshedShot.audio_status).toBe('succeeded');
  expect(refreshedShot.video_status).toBe('succeeded');

  await page.goto('/jobs');
  await page.waitForLoadState('networkidle');
  await expect(page.getByRole('heading', { name: '任务队列' })).toBeVisible();
  await expect(page.getByText(`E2E完整流程成片-${stamp}`)).toBeVisible({ timeout: 10000 });
});

test('jobs page can cancel and archive a video task', async ({ page }) => {
  const stamp = Date.now();
  const taskTitle = `E2E任务中心视频-${stamp}`;
  await page.goto('/dashboard');
  await expect(page.locator('body')).toBeVisible();

  const video = await apiPost(page, '/video/generate', {
    prompt: taskTitle,
    duration: 4,
    resolution: '720p',
  });
  expect(video.status).toBe('succeeded');

  await apiPut(page, `/video/jobs/${video.job_id}`, {
    title: taskTitle,
    status: 'running',
    progress: 20,
  });

  await page.goto('/jobs');
  await page.waitForLoadState('networkidle');
  await expect(page.getByText(taskTitle)).toBeVisible({ timeout: 10_000 });
  const cancellableJobCard = page.locator('div').filter({ hasText: taskTitle }).filter({ has: page.getByTitle('取消任务') }).first();
  await cancellableJobCard.getByTitle('取消任务').click();
  const cancelledJobCard = page.locator('div').filter({ hasText: taskTitle }).filter({ hasText: '已取消' }).first();
  await expect(cancelledJobCard.getByText('已取消')).toBeVisible({ timeout: 10_000 });

  await cancelledJobCard.getByTitle('删除归档').click();
  await expect(page.getByText(taskTitle)).toHaveCount(0, { timeout: 10_000 });
});

test('management pages can create and archive templates entities and publications', async ({ page }) => {
  const stamp = Date.now();
  await page.goto('/dashboard');
  await expect(page.locator('body')).toBeVisible();

  const templateName = `E2E自定义模板-${stamp}`;
  await page.goto('/templates');
  await expect(page.getByRole('heading', { name: '模板库' })).toBeVisible({ timeout: 10_000 });
  await page.getByPlaceholder('模板名称').fill(templateName);
  await page.getByPlaceholder('标签，用逗号分隔').fill('悬疑,E2E');
  await page.getByPlaceholder('模板用途和适用场景').fill('用于验证自定义模板持久化');
  await page.getByRole('button', { name: '保存模板' }).click();
  await expect(page.getByText(templateName)).toBeVisible({ timeout: 10_000 });
  const templateCard = page.locator('div').filter({ hasText: templateName }).filter({ hasText: '归档' }).first();
  await templateCard.getByRole('button', { name: /归档/ }).click();
  await expect(page.getByText(templateName)).toHaveCount(0, { timeout: 10_000 });

  const entityName = `E2E实体-${stamp}`;
  await page.goto('/entities');
  await expect(page.getByRole('heading', { name: '实体库' })).toBeVisible({ timeout: 10_000 });
  await page.getByPlaceholder('名称').fill(entityName);
  await page.getByPlaceholder('别名，用逗号分隔').fill('测试实体');
  await page.getByPlaceholder('外观、空间、道具状态或事件说明').fill('用于验证实体管理台');
  await page.getByRole('button', { name: '保存实体' }).click();
  await expect(page.getByText(entityName)).toBeVisible({ timeout: 10_000 });
  const entityRow = page.locator('div').filter({ hasText: entityName }).filter({ hasText: '删除' }).first();
  await entityRow.getByRole('button', { name: /删除/ }).click();
  await expect(page.getByText(entityName)).toHaveCount(0, { timeout: 10_000 });

  const publishTitle = `E2E发布记录-${stamp}`;
  const synthesis = await apiPost(page, '/synthesis/create', {
    title: publishTitle,
    video_url: 'https://example.com/e2e-source.mp4',
    audio_url: 'https://example.com/e2e-audio.mp3',
  });
  await apiPost(page, '/synthesis/publish', {
    synthesis_job_id: synthesis.id,
    title: publishTitle,
    metadata: { channel: 'e2e' },
  });

  await page.goto('/synthesis');
  await expect(page.getByRole('heading', { name: '发布记录' })).toBeVisible({ timeout: 10_000 });
  const publicationRow = page.locator('div').filter({ hasText: publishTitle }).filter({ hasText: 'local' }).last();
  await expect(publicationRow.getByText(publishTitle)).toBeVisible({ timeout: 10_000 });
  await publicationRow.getByTitle('撤销发布').click();
  await expect(page.getByText('已撤销')).toBeVisible({ timeout: 10_000 });
  await publicationRow.getByTitle('归档发布记录').click();
  await expect(page.getByText(publishTitle)).toHaveCount(0, { timeout: 10_000 });
});

test('quick start creates an editable first episode workspace', async ({ page }) => {
  test.setTimeout(60_000);
  const stamp = Date.now();
  await page.goto('/quick-start');
  await expect(page.getByRole('heading', { name: '极速向导' })).toBeVisible({ timeout: 10_000 });

  await page.getByRole('button', { name: '生成首集工程' }).click();
  await expect(page.getByText(/请先补齐：/)).toBeVisible();
  await page.getByPlaceholder('作品名').fill(`E2E极速向导-${stamp}`);
  await page.getByPlaceholder('故事梗概').fill('雨夜旧城中，少年追查一封会发光的密信，并发现自己能听见星辰回声。');
  await page.getByPlaceholder('首章正文').fill('雨水敲打霓虹招牌，林澈在旧城巷口捡起密信。纸面亮起星光，远处钟声回应他的心跳。');
  await page.locator('input[type="number"]').fill('3');
  await page.getByRole('button', { name: '保存草稿' }).click();
  await expect(page.getByText(/草稿会自动保存在本机/)).toBeVisible();
  await page.getByRole('button', { name: '生成首集工程' }).click();

  await expect(page.getByText('已创建')).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText('审核分镜')).toBeVisible();
  await expect(page.getByText('进入工作流')).toBeVisible();
  await expect(page.getByText('查看脚本')).toBeVisible();
});

test('management pages can edit templates and entities', async ({ page }) => {
  const stamp = Date.now();
  await page.goto('/dashboard');
  await expect(page.locator('body')).toBeVisible();

  const template = await apiPost(page, '/assets', {
    category: 'template',
    asset_type: 'text',
    name: `E2E可编辑模板-${stamp}`,
    description: '编辑前模板',
    tags: ['E2E'],
    style_tags: ['storyboard'],
    prompt_template: '{{角色}}进入{{场景}}',
    shot_template: { shot_count: 2, shots: [] },
  });

  await page.goto('/templates');
  await expect(page.getByText(template.name)).toBeVisible({ timeout: 10_000 });
  await page.getByTitle(`编辑${template.name}`).click();
  await page.getByPlaceholder('模板名称').last().fill(`E2E已编辑模板-${stamp}`);
  await page.getByPlaceholder('模板用途和适用场景').last().fill('编辑后模板');
  await page.getByRole('button', { name: /^保存$/ }).click();
  await expect(page.getByText(`E2E已编辑模板-${stamp}`)).toBeVisible({ timeout: 10_000 });

  const entity = await apiPost(page, '/story-bibles/entities', {
    entity_type: 'character',
    name: `E2E可编辑实体-${stamp}`,
    description: '编辑前实体',
    source: 'manual',
  });

  await page.goto('/entities');
  await expect(page.getByText(entity.name)).toBeVisible({ timeout: 10_000 });
  await page.getByTitle(`编辑${entity.name}`).click();
  await page.getByPlaceholder('名称').last().fill(`E2E已编辑实体-${stamp}`);
  await page.getByPlaceholder('外观、空间、道具状态或事件说明').last().fill('编辑后实体');
  await page.getByRole('button', { name: /^保存$/ }).click();
  await expect(page.getByText(`E2E已编辑实体-${stamp}`)).toBeVisible({ timeout: 10_000 });
});

test('script generation shows chapter continuity context and consistency check', async ({ page }) => {
  test.setTimeout(60_000);
  const stamp = Date.now();
  await page.goto('/dashboard');
  await expect(page.locator('body')).toBeVisible();

  const novel = await apiPost(page, '/novels', {
    title: `E2E剧本连续性小说-${stamp}`,
    description: '角色：沈砚、林栀。场景：雾港暗巷。道具：铜铃。事件：密信失踪。',
    genre: '悬疑',
    style: '冷色赛璐璐悬疑动漫',
    status: 'writing',
  });

  const firstChapter = await apiPost(page, '/chapters', {
    novel_id: novel.id,
    title: '第一章 雾中来信',
    chapter_number: 1,
    content: '沈砚和林栀在雾港旧码头发现铜铃，确认密信已经失踪。',
  });
  const secondChapter = await apiPost(page, '/chapters', {
    novel_id: novel.id,
    title: '第二章 暗巷回声',
    chapter_number: 2,
    content: '沈砚和林栀进入雾港暗巷，铜铃再次响起，密信被转移的线索浮现。',
  });
  const thirdChapter = await apiPost(page, '/chapters', {
    novel_id: novel.id,
    title: '第三章 灯塔真相',
    chapter_number: 3,
    content: '沈砚抵达废弃灯塔，发现密信背后的真相。',
  });
  expect(thirdChapter.id).toBeTruthy();

  await apiPost(page, '/story-bibles/generate-from-novel', {
    novel_id: novel.id,
    style: '冷色赛璐璐悬疑动漫',
  });
  await apiPost(page, '/story-bibles/entities', {
    novel_id: novel.id,
    chapter_id: firstChapter.id,
    entity_type: 'character',
    name: '沈砚',
    description: '追查密信失踪的主角',
    attributes: {
      relationships: [{ target: '林栀', relation: '同伴', status: '共同追查密信失踪' }],
    },
  });
  await apiPost(page, '/story-bibles/entities', {
    novel_id: novel.id,
    chapter_id: secondChapter.id,
    entity_type: 'scene',
    name: '雾港暗巷',
    description: '潮湿狭窄的雾港暗巷，回荡铜铃声',
  });
  await apiPost(page, '/story-bibles/entities', {
    novel_id: novel.id,
    chapter_id: secondChapter.id,
    entity_type: 'prop',
    name: '铜铃',
    description: '提示密信去向的关键道具',
  });
  await apiPost(page, '/story-bibles/entities', {
    novel_id: novel.id,
    chapter_id: secondChapter.id,
    entity_type: 'event',
    name: '暗巷遭遇',
    description: '沈砚和林栀确认密信被转移',
  });

  await page.goto(`/scripts?novel_id=${novel.id}&chapter_id=${secondChapter.id}`);
  await expect(page.getByRole('heading', { name: '剧本管理' })).toBeVisible({ timeout: 10_000 });
  await page.getByRole('button', { name: /AI生成剧本/ }).click();
  await expect(page.getByText('生成上下文预览')).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText('前情：第一章 雾中来信；后续约束：第三章 灯塔真相')).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/人物\s+[1-9]\d*/)).toBeVisible();
  await expect(page.getByText(/场景\s+[1-9]\d*/)).toBeVisible();
  await expect(page.getByText(/道具\s+[1-9]\d*/)).toBeVisible();
  await expect(page.getByText(/事件\s+[1-9]\d*/)).toBeVisible();
  await expect(page.getByText(/关系\s+1/)).toBeVisible();
  await expect(page.locator('div', { hasText: /^人物：/ })).toContainText('沈砚');
  await expect(page.locator('div', { hasText: /^场景\/道具\/事件：/ })).toContainText('雾港暗巷');
  await expect(page.locator('div', { hasText: /^场景\/道具\/事件：/ })).toContainText('铜铃');
  await expect(page.locator('div', { hasText: /^场景\/道具\/事件：/ })).toContainText('暗巷遭遇');

  await page.getByRole('button', { name: '开始生成' }).click();
  await expect(page.getByText('生成结果')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/生成后一致性检查/)).toBeVisible({ timeout: 10_000 });
  await expect(page.locator('div', { hasText: /^【第1场】/ })).toContainText('雾港暗巷');
  await expect(page.locator('div', { hasText: /^【第1场】/ })).toContainText('第三章 灯塔真相');

  const scripts = await apiGet(page, `/scripts?novel_id=${novel.id}&chapter_id=${secondChapter.id}`);
  const generatedScript = scripts.find((script: any) => script.chapter_id === secondChapter.id && script.status === 'completed');
  expect(generatedScript).toBeTruthy();

  const check = await apiGet(page, `/scripts/${generatedScript.id}/check-consistency`);
  expect(check.summary.has_generation_context).toBe(true);
});

test('video generation page preserves novel chapter script storyboard shot lineage', async ({ page }) => {
  test.setTimeout(60_000);
  const stamp = Date.now();
  await page.goto('/dashboard');
  await expect(page.locator('body')).toBeVisible();

  const novel = await apiPost(page, '/novels', {
    title: `E2E视频链路小说-${stamp}`,
    description: '角色：沈砚。场景：旧城雨巷。道具：铜铃。事件：密信被黑影夺走。',
    genre: 'suspense',
    style: 'anime',
    status: 'writing',
  });

  const chapter = await apiPost(page, '/chapters', {
    novel_id: novel.id,
    title: '第一章 雨巷铜铃',
    chapter_number: 1,
    content: '角色：沈砚。场景：旧城雨巷。道具：铜铃。事件：密信被黑影夺走。沈砚在旧城雨巷听见铜铃声，密信被黑影夺走。',
  });

  const storyboard = await apiPost(page, '/storyboards/generate-smart', {
    novel_id: novel.id,
    chapter_id: chapter.id,
    shot_count: 3,
    style: 'anime',
    use_ai_refine: false,
  });
  const shot = storyboard.shots[0];

  await page.goto(`/storyboards?storyboard_id=${storyboard.id}`);
  await expect(page.getByText('上游链路')).toBeVisible({ timeout: 10_000 });
  const lineagePanel = page.getByTestId('storyboard-lineage');
  await expect(lineagePanel).toBeVisible();
  await expect(lineagePanel).toContainText(novel.title);
  await expect(lineagePanel).toContainText(chapter.title);
  await page.getByTitle(`生成镜头${shot.shot_number}视频`).click();
  await page.waitForURL(/\/video-generation\?/);
  expect(page.url()).toContain(`novel_id=${novel.id}`);
  expect(page.url()).toContain(`chapter_id=${chapter.id}`);
  expect(page.url()).toContain(`storyboard_id=${storyboard.id}`);
  expect(page.url()).toContain(`shot_id=${shot.id}`);

  await page.goto(
    `/video-generation?novel_id=${novel.id}&chapter_id=${chapter.id}&script_id=${storyboard.script_id}&storyboard_id=${storyboard.id}&shot_id=${shot.id}`
  );
  await expect(page.getByText('制作链路')).toBeVisible();
  await expect(page.getByText('视频描述')).toBeVisible({ timeout: 10_000 });
  await expect(page.locator('textarea').first()).toHaveValue(/.+/);
  await expect(page.getByText(/人物：.*沈砚/).first()).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/场景：.*旧城雨巷/).first()).toBeVisible();
  await expect(page.getByText(/道具：.*铜铃/).first()).toBeVisible();
  await expect(page.getByText(/事件：.*密信被黑影夺走/).first()).toBeVisible();
  await expect(page.getByText(/字幕：/).first()).toBeVisible();

  const generateButton = page.getByRole('button', { name: /开始生成/ });
  await expect(generateButton).toBeEnabled({ timeout: 10_000 });
  await generateButton.click();
  await expect(page.getByRole('button', { name: /生成完成/ })).toBeVisible({ timeout: 15_000 });
  const previewVideo = page.locator('video').first();
  await expect(previewVideo).toHaveAttribute('src', /\/static\/dev\/video-/, { timeout: 10_000 });
  await page.getByTitle('播放视频').first().click();
  await expect(previewVideo).toHaveAttribute('src', /\/static\/dev\/video-/);
  const downloadResponse = page.waitForResponse(
    (response) => response.url().includes('/api/v1/video/download') && response.status() === 200
  );
  await page.getByTitle('下载视频').first().click();
  await downloadResponse;

  const jobs = await apiGet(
    page,
    `/video/jobs?novel_id=${novel.id}&chapter_id=${chapter.id}&script_id=${storyboard.script_id}&storyboard_id=${storyboard.id}&shot_id=${shot.id}`
  );
  expect(jobs.length).toBeGreaterThan(0);
  expect(jobs[0].novel_id).toBe(novel.id);
  expect(jobs[0].chapter_id).toBe(chapter.id);
  expect(jobs[0].script_id).toBe(storyboard.script_id);
  expect(jobs[0].storyboard_id).toBe(storyboard.id);
  expect(jobs[0].shot_id).toBe(shot.id);
  expect(jobs[0].character_refs?.[0]?.name).toContain('沈砚');
  expect(jobs[0].scene_refs?.[0]?.name).toContain('旧城雨巷');
  expect(jobs[0].prop_refs?.[0]?.name).toContain('铜铃');
  expect(jobs[0].subtitle_text).toBeTruthy();
  await expect(page.getByText(/人物：.*沈砚/).first()).toBeVisible();
  await expect(page.getByText(/字幕：/).first()).toBeVisible();
});

test('video generation page can create direct audio video with subtitle track', async ({ page }) => {
  test.setTimeout(60_000);
  const stamp = Date.now();
  await page.goto('/dashboard');
  await expect(page.locator('body')).toBeVisible();

  const novel = await apiPost(page, '/novels', {
    title: `E2E直生音视频小说-${stamp}`,
    description: '角色：沈砚。场景：旧城雨巷。道具：铜铃。',
    genre: 'suspense',
    style: 'anime',
    status: 'writing',
  });
  const chapter = await apiPost(page, '/chapters', {
    novel_id: novel.id,
    title: '第一章 雨巷',
    chapter_number: 1,
    content: '沈砚在旧城雨巷听见铜铃声。',
  });
  const storyboard = await apiPost(page, '/storyboards/generate-smart', {
    novel_id: novel.id,
    chapter_id: chapter.id,
    shot_count: 2,
    style: 'anime',
    use_ai_refine: false,
  });
  const shot = storyboard.shots[0];

  await page.goto(
    `/video-generation?novel_id=${novel.id}&chapter_id=${chapter.id}&script_id=${storyboard.script_id}&storyboard_id=${storyboard.id}&shot_id=${shot.id}`
  );
  await expect(page.getByText('生成模式')).toBeVisible({ timeout: 10_000 });
  await page.getByRole('button', { name: '直生音视频' }).click();
  await page.getByRole('button', { name: /生成音视频/ }).click();
  await expect(page.getByRole('button', { name: /生成完成/ })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText('字幕轨已生成')).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText('音视频直生历史')).toBeVisible();
  await expect(page.getByText(/字幕：/).first()).toBeVisible();

  const mediaJobs = await apiGet(page, `/media/jobs?task_type=shot_audio_video&shot_id=${shot.id}`);
  expect(mediaJobs.length).toBeGreaterThan(0);
  expect(mediaJobs[0].output_video_url).toContain('/static/dev/video-');
  expect(mediaJobs[0].output_audio_url).toContain('/static/dev/audio-');
  expect(mediaJobs[0].subtitle_track_id).toBeTruthy();

  const exportResponse = page.waitForResponse(
    (response) => response.url().includes('/api/v1/subtitles/tracks/') && response.url().includes('/export') && response.status() === 200
  );
  await page.getByRole('button', { name: '字幕', exact: true }).click();
  await exportResponse;
});

test('workflow page shows multi-shot continuous final video manifest', async ({ page }) => {
  test.setTimeout(60_000);
  const stamp = Date.now();
  await page.goto('/dashboard');
  await expect(page.locator('body')).toBeVisible();

  const novel = await apiPost(page, '/novels', {
    title: `E2E连续成片小说-${stamp}`,
    description: '两名角色在旧城追查失踪的记忆碎片。',
    genre: 'suspense',
    style: 'anime',
    status: 'writing',
  });

  const chapter = await apiPost(page, '/chapters', {
    novel_id: novel.id,
    title: '第一章 旧城回声',
    chapter_number: 1,
    content: '雨夜里，主角穿过旧城街口，看见墙面映出过去的影像。',
  });

  const storyboard = await apiPost(page, '/storyboards/generate-smart', {
    novel_id: novel.id,
    chapter_id: chapter.id,
    shot_count: 2,
    style: 'anime',
    use_ai_refine: false,
  });

  const workflow = await apiPost(page, '/workflow/start', {
    title: `E2E连续成片工作流-${stamp}`,
    novel_id: novel.id,
    chapter_id: chapter.id,
    script_id: storyboard.script_id,
    storyboard_id: storyboard.id,
  });

  const videoJobIds: string[] = [];
  const ttsJobIds: string[] = [];
  for (const [index, shot] of storyboard.shots.slice(0, 2).entries()) {
    const video = await apiPost(page, '/video/generate', {
      prompt: shot.prompt,
      duration: Math.max(4, shot.duration || 4),
      resolution: '720p',
      workflow_id: workflow.workflow_id,
      shot_id: shot.id,
    });
    videoJobIds.push(video.job_id);

    const tts = await apiPost(page, '/tts/generate', {
      text_content: shot.dialogue || `第 ${index + 1} 个镜头台词`,
      title: `E2E连续成片配音-${index + 1}-${stamp}`,
      voice_model: 'female-shaonj',
      speed: 1,
      workflow_id: workflow.workflow_id,
      novel_id: novel.id,
      chapter_id: chapter.id,
      script_id: storyboard.script_id,
      storyboard_id: storyboard.id,
      shot_id: shot.id,
    });
    ttsJobIds.push(tts.job_id || tts.id);
  }

  const synthesis = await apiPost(page, `/workflow/concatenate/${workflow.workflow_id}`, {
    video_job_ids: videoJobIds,
    tts_job_ids: ttsJobIds,
    title: `E2E连续成片-${stamp}`,
    transition_style: 'fade',
    include_subtitles: true,
    subtitle_mode: 'dialogue',
    audio_mix_strategy: 'match_by_shot',
    quality_profile: 'review',
  });

  expect(synthesis.segment_count).toBe(2);
  expect(synthesis.manifest_url).toContain('/static/exports/');
  expect(synthesis.output_url).toContain('/static/dev/final-');

  await page.goto(`/workflow?workflow_id=${workflow.workflow_id}`);
  await expect(page.getByText('多镜头连续成片')).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText('连续成片清单已生成')).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText('查看成片清单')).toBeVisible();
  await expect(page.getByText('成片段落')).toBeVisible();
  await expect(page.getByText('渲染预检与本地渲染包')).toBeVisible();

  await page.getByRole('button', { name: /渲染预检/ }).click();
  await expect(page.getByText('预检通过，可以生成本地渲染包。')).toBeVisible({ timeout: 10_000 });

  await page.getByRole('button', { name: /生成渲染包|重新渲染/ }).click();
  await expect(page.getByText('HTML 预览')).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText('SRT 字幕')).toBeVisible();
  await expect(page.getByText('时间线 EDL')).toBeVisible();
  await expect(page.getByText('渲染清单')).toBeVisible();
});

test('workflow page can batch generate direct audio video and render package', async ({ page }) => {
  test.setTimeout(60_000);
  const stamp = Date.now();
  await page.goto('/dashboard');
  await expect(page.locator('body')).toBeVisible();

  const novel = await apiPost(page, '/novels', {
    title: `E2E工作流直生小说-${stamp}`,
    description: '角色：沈砚。场景：旧城雨巷。道具：铜铃。事件：星光密信出现。',
    genre: 'suspense',
    style: 'anime',
    status: 'writing',
  });
  const chapter = await apiPost(page, '/chapters', {
    novel_id: novel.id,
    title: '第一章 雨巷密信',
    chapter_number: 1,
    content: '沈砚在旧城雨巷听见铜铃声，星光密信在雨水中发亮。',
  });
  const storyboard = await apiPost(page, '/storyboards/generate-smart', {
    novel_id: novel.id,
    chapter_id: chapter.id,
    shot_count: 2,
    style: 'anime',
    use_ai_refine: false,
  });
  const workflow = await apiPost(page, '/workflow/start', {
    title: `E2E工作流直生-${stamp}`,
    novel_id: novel.id,
    chapter_id: chapter.id,
    script_id: storyboard.script_id,
    storyboard_id: storyboard.id,
  });

  await page.goto(`/workflow?workflow_id=${workflow.workflow_id}`);
  await expect(page.getByText('生产就绪检查')).toBeVisible({ timeout: 10_000 });
  await page.getByRole('button', { name: '视频 生成视频' }).click();
  await expect(page.getByRole('button', { name: '批量直生音视频' })).toBeVisible({ timeout: 10_000 });
  await page.getByRole('button', { name: /批量直生音视频/ }).click();
  await expect(page.getByText(/已有 0 个静音视频、2 个直生音视频/)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/已有 2 条可导出字幕轨/)).toBeVisible();

  await page.getByRole('button', { name: '合成 音视频合成' }).click();
  await expect(page.getByText('多镜头连续成片')).toBeVisible({ timeout: 10_000 });
  await page.getByRole('button', { name: /生成连续成片/ }).click();
  await expect(page.getByText('连续成片清单已生成')).toBeVisible({ timeout: 10_000 });
  await page.getByRole('button', { name: /渲染预检/ }).click();
  await expect(page.getByText('预检通过，可以生成本地渲染包。')).toBeVisible({ timeout: 10_000 });
  await page.getByRole('button', { name: /生成渲染包|重新渲染/ }).click();
  await expect(page.getByRole('button', { name: 'HTML 预览' })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole('button', { name: 'SRT 字幕' })).toBeVisible();

  const status = await apiGet(page, `/workflow/status/${workflow.workflow_id}`);
  expect(status.media_jobs.length).toBe(2);
  expect(status.subtitle_tracks.length).toBe(2);
  expect(status.synthesis_jobs[0].extra_data.media_job_ids.length).toBe(2);
});

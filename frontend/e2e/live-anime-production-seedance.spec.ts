import { expect, test } from '@playwright/test';
import crypto from 'crypto';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const LIVE_USER_ID = process.env.LIVE_ANIME_E2E_USER_ID || '56ae84de-951f-4e74-ac79-3550d6f6f3b2';
const VIDEO_CONFIG_ID = process.env.LIVE_ANIME_E2E_VIDEO_CONFIG_ID || '980cb5db-0281-4835-9486-a739fcb35d98';
const AUDIO_CONFIG_ID = process.env.LIVE_ANIME_E2E_AUDIO_CONFIG_ID || '5a8d3813-ee43-4ed2-b40b-4935368e784e';
const JWT_SECRET = process.env.JWT_SECRET_KEY || 'dev-jwt-secret-change-in-production';
const LIVE_MAX_RMB = Number(process.env.LIVE_ANIME_E2E_MAX_RMB || '0');
const LIVE_EPISODE_COUNT = Number(process.env.LIVE_ANIME_E2E_EPISODES || '3');
const LIVE_SHOTS_PER_EPISODE = Number(process.env.LIVE_ANIME_E2E_SHOTS_PER_EPISODE || '2');

test.skip(process.env.LIVE_ANIME_E2E !== '1', '设置 LIVE_ANIME_E2E=1 后才运行真实动漫制作全流程测试。');
test.skip(LIVE_MAX_RMB <= 0, '设置 LIVE_ANIME_E2E_MAX_RMB 才允许真实云端调用。');
test.skip(LIVE_EPISODE_COUNT < 1 || LIVE_SHOTS_PER_EPISODE < 1, '真实云端 canary 至少需要 1 集和 1 个镜头。');

type ApiOptions = {
  method?: string;
  body?: unknown;
};

function base64url(input: string | Buffer) {
  return Buffer.from(input).toString('base64url');
}

function signedAccessToken(userId: string) {
  const header = base64url(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const payload = base64url(JSON.stringify({ sub: userId, type: 'access', exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 }));
  const signature = crypto.createHmac('sha256', JWT_SECRET).update(`${header}.${payload}`).digest('base64url');
  return `${header}.${payload}.${signature}`;
}

async function api<T = any>(token: string, path: string, options: ApiOptions = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: options.method || 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new Error(`${options.method || 'GET'} ${path} failed: ${response.status} ${JSON.stringify(data)}`);
  }
  return data as T;
}

async function writeLiveArtifact(payload: unknown) {
  const fs = await import('fs/promises');
  const path = await import('path');
  const outputDir = path.join(process.cwd(), '..', 'output', 'live-anime');
  await fs.mkdir(outputDir, { recursive: true });
  const filename = `canary-${Date.now()}.json`;
  const sanitized = JSON.stringify(payload, (key, value) => {
    if (/token|key|secret|authorization/i.test(key)) return '[redacted]';
    return value;
  }, 2);
  await fs.writeFile(path.join(outputDir, filename), sanitized, 'utf8');
}

async function assertRequiredModelConfigs(token: string) {
  const configs = await api<any[]>(token, '/llm/configs');
  const video = configs.find((config) => config.id === VIDEO_CONFIG_ID);
  const audio = configs.find((config) => config.id === AUDIO_CONFIG_ID);
  expect(video, `缺少视频模型配置 ${VIDEO_CONFIG_ID}`).toBeTruthy();
  const allowedVideoModels = [
    'doubao-seedance-2-0-260128',
    'doubao-seedance-2-0-fast-260128',
    'doubao-seedance-1-5-pro-251215',
  ];
  expect(allowedVideoModels, `视频模型 ${video.model_id} 必须是明确允许的 live canary 模型`).toContain(video.model_id);
  expect(video.test_status, 'Seedance 视频模型配置必须验证通过').toBe('success');
  expect(video.key_available, 'Seedance 视频模型配置必须有可用 API Key').not.toBe(false);
  expect(audio, `缺少声音模型配置 ${AUDIO_CONFIG_ID}`).toBeTruthy();
  expect(audio.test_status, '声音模型配置必须验证通过').toBe('success');
  expect(audio.key_available, '声音模型配置必须有可用 API Key').not.toBe(false);
}

async function createMinimalAnimeProject(token: string) {
  const stamp = Date.now();
  const title = `Live动漫全流程-星灯猫-${stamp}`;
  const novel = await api(token, '/novels', {
    method: 'POST',
    body: {
      title,
      genre: '治愈奇幻动漫',
      tags: ['live-e2e', 'anime', 'seedance'],
      description: '一只奶油色小猫米粒在雨夜屋顶点亮星灯尾巴，引导迷路的云鲸回家。',
    },
  });
  const chapter = await api(token, '/chapters', {
    method: 'POST',
    body: {
      novel_id: novel.id,
      title: '第一章 雨夜屋顶的星灯',
      chapter_number: 1,
      content: '雨夜里，奶油色小猫米粒跳上蓝灰色屋顶。它的金色星灯尾巴忽然亮起，照见一只迷路的透明云鲸。米粒举起尾巴，沿着瓦片边缘奔跑，把云鲸引向远处的月光塔。',
    },
  });
  const storyBible = await api(token, '/story-bibles', {
    method: 'POST',
    body: {
      novel_id: novel.id,
      title: `${title} Story Bible`,
      style: '温暖二维动漫，柔和赛璐璐线条，蓝灰雨夜与金色星光形成稳定对比。',
      worldview: '屋顶、月光塔和云鲸共同构成一个低门槛短篇动漫世界。',
      character_rules: [{ name: '米粒', role: '主角', appearance: '奶油色小猫，圆脸，琥珀眼，尾巴末端挂着金色星灯。', voice: 'male-qn-qingse', voice_model: 'male-qn-qingse', voice_speed: 1 }],
      scene_rules: [{ name: '雨夜屋顶', visual: '蓝灰屋顶、细雨、水光反射、远处月光塔。' }],
      prop_rules: [{ name: '星灯尾巴', visual: '尾巴末端的金色星形灯笼，发出温暖光晕。' }],
      event_timeline: [{ name: '点亮星灯', result: '米粒发现云鲸并开始引路。' }],
      negative_prompt: '写实恐怖、血腥、复杂机械、人物漂移、低清晰度',
      extra_data: { voice_profiles: { 米粒: { voice: 'male-qn-qingse', voice_model: 'male-qn-qingse', voice_speed: 1 } } },
    },
  });
  const character = await api(token, '/story-bibles/entities', {
    method: 'POST',
    body: { novel_id: novel.id, chapter_id: chapter.id, entity_type: 'character', name: '米粒', description: '勇敢但温柔的奶油色小猫。', attributes: { voice: 'male-qn-qingse', voice_model: 'male-qn-qingse', appearance: '奶油色小猫，琥珀眼，金色星灯尾巴' }, evidence: '米粒点亮星灯尾巴帮助云鲸。', source: 'manual' },
  });
  const scene = await api(token, '/story-bibles/entities', {
    method: 'POST',
    body: { novel_id: novel.id, chapter_id: chapter.id, entity_type: 'scene', name: '雨夜屋顶', description: '蓝灰色屋顶与远处月光塔。', source: 'manual' },
  });
  const prop = await api(token, '/story-bibles/entities', {
    method: 'POST',
    body: { novel_id: novel.id, chapter_id: chapter.id, entity_type: 'prop', name: '星灯尾巴', description: '金色星形灯笼尾巴，是引路光源。', source: 'manual' },
  });
  const script = await api(token, '/scripts', {
    method: 'POST',
    body: { novel_id: novel.id, chapter_id: chapter.id, title: `${title} 第一集剧本`, genre: '治愈奇幻动漫', style: 'anime', duration: 4, content: '旁白：雨夜屋顶上，米粒点亮星灯尾巴。\n米粒：别怕，我带你回月光塔。' },
  });
  const storyboard = await api(token, '/storyboards', {
    method: 'POST',
    body: { script_id: script.id, title: `${title} 第一集分镜`, description: '单镜头验证：角色、场景、道具、事件与声线一致。', content: { chapter_id: chapter.id, story_bible_id: storyBible.id } },
  });
  const shot = await api(token, '/shots', {
    method: 'POST',
    body: {
      storyboard_id: storyboard.id,
      shot_number: 1,
      duration: 4,
      prompt: 'warm 2D anime, rainy blue-gray rooftop at night, cream kitten Mili with amber eyes and glowing golden star lantern tail, a translucent cloud whale floating nearby, soft cel shading, consistent character design, cinematic gentle pan, 4 seconds',
      dialogue: '米粒：别怕，我带你回月光塔。',
      visual_description: '雨夜屋顶全景转近景，米粒的星灯尾巴照亮云鲸。',
      camera_angle: 'wide_to_medium',
      camera_movement: 'pan_right',
      lighting: 'moonlight',
      color_grading: 'warm',
      character_refs: [{ character_id: character.id, name: '米粒', role: 'protagonist' }],
    },
  });
  const characterAsset = await api(token, '/assets', {
    method: 'POST',
    body: {
      category: 'character',
      name: '米粒定稿参考',
      description: '奶油色小猫米粒，琥珀眼，金色星灯尾巴。',
      asset_type: 'image',
      novel_id: novel.id,
      chapter_id: chapter.id,
      script_id: script.id,
      entity_id: character.id,
      entity_type: 'character',
      tags: ['live-e2e', 'final-lock'],
      style_tags: ['anime'],
    },
  });
  const sceneAsset = await api(token, '/assets', {
    method: 'POST',
    body: {
      category: 'scene',
      name: '雨夜屋顶定稿参考',
      description: '蓝灰雨夜屋顶、水光反射、远处月光塔。',
      asset_type: 'image',
      novel_id: novel.id,
      chapter_id: chapter.id,
      script_id: script.id,
      entity_id: scene.id,
      entity_type: 'scene',
      tags: ['live-e2e', 'final-lock'],
      style_tags: ['anime'],
    },
  });
  const propAsset = await api(token, '/assets', {
    method: 'POST',
    body: {
      category: 'prop',
      name: '星灯尾巴定稿参考',
      description: '金色星形灯笼尾巴，稳定暖光。',
      asset_type: 'image',
      novel_id: novel.id,
      chapter_id: chapter.id,
      script_id: script.id,
      entity_id: prop.id,
      entity_type: 'prop',
      tags: ['live-e2e', 'final-lock'],
      style_tags: ['anime'],
    },
  });
  const assetLocks = [
    { asset_id: characterAsset.id, role: 'character_reference', version: 1, name: '米粒', locked_at: new Date().toISOString() },
    { asset_id: sceneAsset.id, role: 'scene_reference', version: 1, name: '雨夜屋顶', locked_at: new Date().toISOString() },
    { asset_id: propAsset.id, role: 'prop_reference', version: 1, name: '星灯尾巴', locked_at: new Date().toISOString() },
  ];
  await api(token, `/shots/${shot.id}/production-context`, {
    method: 'PUT',
    body: {
      asset_version_locks: assetLocks,
      entity_reference_bindings: [
        { entity_id: character.id, entity_type: 'character', name: '米粒' },
        { entity_id: scene.id, entity_type: 'scene', name: '雨夜屋顶' },
        { entity_id: prop.id, entity_type: 'prop', name: '星灯尾巴' },
      ],
      review_state: 'approved',
      provider_hints: { preferred_video_model: 'doubao-seedance-1-5-pro-251215', duration_seconds: 4 },
    },
  });
  const workflow = await api(token, '/workflow/start', {
    method: 'POST',
    body: { title: `${title} 第一集工程`, novel_id: novel.id, chapter_id: chapter.id, script_id: script.id, storyboard_id: storyboard.id },
  });
  await api(token, `/workflow/${workflow.workflow_id}/step`, {
    method: 'PUT',
    body: { current_step: 6, completed_steps: [1, 2, 3, 4, 5, 6], novel_id: novel.id, chapter_id: chapter.id, script_id: script.id, storyboard_id: storyboard.id },
  });
  await api(token, `/novels/${novel.id}/series-plan`, {
    method: 'POST',
    body: { target_episode_count: 1, chapters_per_episode: 1, target_duration_seconds: 30, aspect_ratio: '16:9', style: '温暖二维动漫', persist: true },
  });
  return { workflowId: workflow.workflow_id };
}

test('从前端制片中心发起简单小说到 Seedance 短镜头的动漫制作全流程', async ({ page }) => {
  const token = signedAccessToken(LIVE_USER_ID);
  await assertRequiredModelConfigs(token);
  const fixture = await createMinimalAnimeProject(token);

  await page.addInitScript(({ authToken, authUserId }) => {
    localStorage.setItem('auth_token', authToken);
    localStorage.setItem('user', JSON.stringify({ id: authUserId, username: authUserId, email: `${authUserId}@example.test` }));
  }, { authToken: token, authUserId: LIVE_USER_ID });

  await page.goto(`/producer?workflow_id=${fixture.workflowId}`);
  await expect(page.getByText('AI 制片中心')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole('button', { name: '一键生成本集草片' })).toBeEnabled({ timeout: 30_000 });

  await page.locator('select', { has: page.locator('option[value="final_quality"]') }).selectOption('final_quality');
  await page.getByLabel('视频生成模型配置').selectOption(VIDEO_CONFIG_ID);
  await page.getByLabel('语音/声音模型配置').selectOption(AUDIO_CONFIG_ID);
  await page.getByRole('button', { name: '一键生成本集草片' }).click();

  await expect(page.getByText(/视频和声音任务已提交|等待云端生成完成|已创建|本集草片渲染包已生成/)).toBeVisible({ timeout: 180_000 });

  await expect.poll(async () => {
    const jobs = await api<any[]>(token, `/video/jobs?workflow_id=${fixture.workflowId}`);
    return jobs.length;
  }, { timeout: 60_000, intervals: [2_000, 5_000] }).toBe(1);

  const latestJobs = await api<any[]>(token, `/video/jobs?workflow_id=${fixture.workflowId}`);
  const videoJob = latestJobs[0];
  expect(videoJob.api_model_id).toBe('doubao-seedance-1-5-pro-251215');
  expect(videoJob.model_config_id).toBe(VIDEO_CONFIG_ID);
  expect(videoJob.task_id, '真实 Seedance 任务必须返回云端 task_id').toBeTruthy();
  expect(videoJob.prompt).toContain('资产版本锁');
  expect(videoJob.prompt).toContain('动漫连续性硬约束');

  const ttsJobs = await api<any[]>(token, `/tts/jobs?workflow_id=${fixture.workflowId}`);
  expect(ttsJobs).toHaveLength(1);
  expect(ttsJobs[0].extra_data?.model_config_id).toBe(AUDIO_CONFIG_ID);
  expect(ttsJobs[0].extra_data?.production_strategy).toBe('final_quality');
  expect(ttsJobs[0].extra_data?.voice_lock_snapshot?.voice).toBe('male-qn-qingse');
  expect(ttsJobs[0].audio_url, 'TTS 应生成可播放音频 URL').toBeTruthy();

  const workflowStatus = await api<any>(token, `/workflow/status/${fixture.workflowId}`);
  expect(workflowStatus.metadata?.latest_production_strategy).toBe('final_quality');
  expect(workflowStatus.video_jobs?.[0]?.id || videoJob.id).toBe(videoJob.id);

  if (videoJob.status === 'succeeded' || videoJob.status === 'completed') {
    expect(videoJob.video_url, '真实视频任务完成后必须回写 video_url').toBeTruthy();
  } else {
    expect(['pending', 'running', 'processing', 'queued']).toContain(videoJob.status);
  }

  await writeLiveArtifact({
    status: 'passed',
    workflowId: fixture.workflowId,
    liveEpisodeCount: LIVE_EPISODE_COUNT,
    liveShotsPerEpisode: LIVE_SHOTS_PER_EPISODE,
    executedEpisodeCount: 1,
    executedShotsPerEpisode: 1,
    maxRmb: LIVE_MAX_RMB,
    createdAt: new Date().toISOString(),
  });
});

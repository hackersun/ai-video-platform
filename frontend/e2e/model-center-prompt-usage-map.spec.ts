import { expect, Page, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(JSON.stringify({
    sub: userId,
    exp: Math.floor(Date.now() / 1000) + 86400,
  })).toString('base64url');
  return `dev.${payload}.sig`;
}

function stage(
  id: string,
  name: string,
  status: string = 'effective',
  templateName: string | null = '标准生产模板',
) {
  const usesPrompt = status !== 'not_applicable';
  return {
    id,
    name,
    uses_prompt: usesPrompt,
    status,
    message: status === 'not_applicable'
      ? '此环节不使用提示词模板。'
      : status === 'internal_fallback'
        ? '尚未配置模板，将使用代码内置提示词。'
        : '当前模型已匹配可用模板。',
    model: usesPrompt ? {
      profile_version_id: 'model-v1', provider_code: 'volcengine',
      provider_name: '火山方舟', api_model_id: `${id}-model`,
      name: '生产默认模型', capabilities: ['text_generation'],
    } : null,
    template: templateName ? {
      id: `profile-${id}`, profile_version_id: `prompt-${id}-v3`,
      name: templateName, version: 3,
    } : null,
    routing: {
      source_label: status === 'overridden' ? '模型专用覆盖'
        : status === 'internal_fallback' ? '内置兜底'
          : status === 'not_applicable' ? '无需提示词' : '环节通用模板',
    },
  };
}

export const promptUsageMap = {
  summary: {
    total: 12,
    counts: { effective: 7, overridden: 1, internal_fallback: 2, not_applicable: 2 },
  },
  groups: [
    { id: 'story_development', name: '故事开发', stages: [
      stage('chapter_writing', '章节续写'),
      stage('character_extraction', '角色提取', 'internal_fallback', null),
      stage('scene_prop_extraction', '场景/道具提取', 'internal_fallback', null),
    ] },
    { id: 'content_production', name: '内容制作', stages: [
      stage('script_generation', '剧本生成'),
      stage('storyboard_generation', '分镜生成', 'overridden', '标准分镜创建'),
    ] },
    { id: 'visual_production', name: '视觉生产', stages: [
      stage('character_image', '角色定稿图'),
      stage('scene_reference_image', '场景参考图'),
      stage('prop_image', '道具参考图'),
      stage('shot_video', '镜头视频'),
    ] },
    { id: 'audio_delivery', name: '声音与交付', stages: [
      stage('tts_dialogue', '对白配音'),
      stage('subtitle', '字幕', 'not_applicable', null),
      stage('synthesis', '成片合成', 'not_applicable', null),
    ] },
  ],
};

async function installRoutes(page: Page) {
  const userId = `prompt-map-${Date.now()}`;
  await page.addInitScript(({ token, id }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({ id, username: id }));
  }, { token: devToken(userId), id: userId });
  await page.route('**/api/v1/model-center/prompt-usage-map', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify(promptUsageMap),
  }));
  await page.route('**/api/v1/model-center/**', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ items: [], meta: { page: 1, page_size: 20, total: 0 } }),
  }));
}

test('opens the prompt usage map before the template library', async ({ page }) => {
  await installRoutes(page);
  await page.goto('/llm-config?section=prompts');

  await expect(page.getByRole('heading', { name: '提示词使用地图' })).toBeVisible();
  await expect(page.getByText('分镜生成')).toBeVisible();
  await expect(page.getByText('标准分镜创建 · v3')).toBeVisible();
  await expect(page.getByText('模型专用覆盖')).toBeVisible();
  await expect(page.getByText('此环节不使用提示词模板。')).toBeVisible();
  await expect(page.getByLabel('输入映射 JSON')).toHaveCount(0);
});

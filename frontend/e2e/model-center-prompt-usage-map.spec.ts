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
  let promptProfileRequests = 0;
  const userId = `prompt-map-${Date.now()}`;
  await page.addInitScript(({ token, id }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({ id, username: id }));
  }, { token: devToken(userId), id: userId });
  await page.route('**/api/v1/model-center/**', (route) => {
    if (route.request().url().includes('/prompt-profiles')) promptProfileRequests += 1;
    return route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [], meta: { page: 1, page_size: 20, total: 0 } }),
    });
  });
  await page.route('**/api/v1/model-center/prompt-usage-map', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify(promptUsageMap),
  }));
  return { promptProfileRequests: () => promptProfileRequests };
}

test('opens the prompt usage map before the template library', async ({ page }) => {
  const requests = await installRoutes(page);
  await page.goto('/llm-config?section=prompts');

  await expect(page.getByRole('heading', { name: '提示词使用地图' })).toBeVisible();
  await expect(page.getByText('分镜生成')).toBeVisible();
  await expect(page.getByText('标准分镜创建 · v3')).toBeVisible();
  await expect(page.getByText('模型专用覆盖')).toBeVisible();
  await expect(page.getByText('此环节不使用提示词模板。', { exact: true }).first()).toBeVisible();
  await expect(page.getByTestId('prompt-usage-summary')).toContainText('12 个环节');
  await expect(page.getByLabel('输入映射 JSON')).toHaveCount(0);

  await page.getByRole('button', { name: '只看问题环节' }).click();
  await expect(page.getByText('场景/道具提取')).toBeVisible();
  await expect(page.getByText('剧本生成')).toHaveCount(0);
  await page.getByRole('button', { name: '查看全部环节' }).click();

  await page.getByText('分镜生成').click();
  await expect(page.getByText('当前使用的模板')).toBeVisible();
  await expect(page.getByText('生产默认模型')).toBeVisible();
  await expect(page.getByText('高级设置')).toBeVisible();
  expect(requests.promptProfileRequests()).toBe(0);

  await page.getByRole('button', { name: '模板库', exact: true }).click();
  await expect(page.getByText('提示词版本工作台')).toBeVisible();
});

test('creates a model-specific draft before production can change', async ({ page }) => {
  const assignmentRequests: unknown[] = [];
  await installRoutes(page);
  await page.route('**/api/v1/model-center/prompt-profiles**', async (route) => {
    const url = route.request().url();
    const head = {
      id: 'draft-version-1', version: 1, status: 'draft', stage: null,
      content: '镜头模板', system_contract: '保持角色一致。', task_template: '生成连续镜头。',
      input_mapping: {}, output_schema: {}, negative_constraints: [],
      model_family_overrides: {}, validation_fixtures: [], release_notes: '模型专用草稿',
      checksum: 'a'.repeat(64), created_at: null, published_at: null,
    };
    const body = url.includes('?')
      ? { items: [{
        id: 'draft-profile-1', key: 'usage.shot_video', name: '镜头连续性 · 生产默认模型',
        task: 'shot_video', head_version_id: head.id, head_version: 1, status: 'draft',
      }], meta: { page: 1, page_size: 20, total: 1 } }
      : { id: 'draft-profile-1', key: 'usage.shot_video', name: '镜头连续性 · 生产默认模型', task: 'shot_video', head, versions: [head], legacy_skill: null };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.route('**/prompt-usage-map/stages/shot_video/candidates', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ items: [{
      id: 'prompt-video-generic-v2', profile_id: 'video-generic', name: '镜头连续性',
      task: 'shot_video', version: 2, status: 'published',
    }] }),
  }));
  await page.route('**/prompt-usage-map/stages/shot_video/assignment-drafts', async (route) => {
    assignmentRequests.push(route.request().postDataJSON());
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({
      profile_id: 'draft-profile-1', version_id: 'draft-version-1',
      name: '镜头连续性 · 生产默认模型', task: 'shot_video', version: 1, status: 'draft',
      routing: { provider_filter: ['volcengine'], model_filter: ['shot-video-model'] },
    }) });
  });
  await page.goto('/llm-config?section=prompts');

  await page.getByText('镜头视频', { exact: true }).click();
  await page.getByRole('button', { name: '更换模板' }).click();
  await expect(page.getByRole('dialog', { name: '更换镜头视频模板' })).toContainText('生产任务不会改变');
  await page.getByLabel('选择已发布模板').selectOption('prompt-video-generic-v2');
  await page.getByRole('button', { name: '创建模型专用草稿' }).click();

  await expect.poll(() => assignmentRequests.length).toBe(1);
  expect(assignmentRequests[0]).toEqual({
    prompt_version_id: 'prompt-video-generic-v2',
    reason: '用于当前默认镜头视频模型',
  });
  await expect(page.getByText('提示词版本工作台')).toBeVisible();
  await expect(page.getByRole('button', { name: '发布此版本' })).toBeVisible();
});

import { expect, test } from '@playwright/test';

const bindings = {
  items: [
    { id: 'binding-text', scope_type: 'system', scope_id: '', task: 'script_generation', capability: 'text_generation', profile_version_id: 'profile-text', connection_id: 'connection-text', priority: 10, route_policy: 'final_quality', is_active: true, revision: 1 },
    { id: 'binding-image', scope_type: 'system', scope_id: '', task: 'shot_image', capability: 'image_generation', profile_version_id: 'profile-image', connection_id: 'connection-image', priority: 10, route_policy: 'final_quality', is_active: true, revision: 1 },
    { id: 'binding-video', scope_type: 'system', scope_id: '', task: 'shot_video', capability: 'video_generation', profile_version_id: 'profile-video', connection_id: 'connection-video', priority: 10, route_policy: 'direct_av_first', is_active: true, revision: 1 },
    { id: 'binding-audio', scope_type: 'system', scope_id: '', task: 'shot_speech', capability: 'speech_generation', profile_version_id: 'profile-audio', connection_id: 'connection-audio', priority: 10, route_policy: 'separate_video_tts', is_active: true, revision: 1 },
    { id: 'binding-render', scope_type: 'system', scope_id: '', task: 'workflow_render', capability: 'media_render', profile_version_id: 'profile-render', connection_id: 'connection-render', priority: 10, route_policy: 'final_quality', is_active: true, revision: 1 },
    { id: 'binding-storage', scope_type: 'system', scope_id: '', task: 'workflow_storage', capability: 'object_storage', profile_version_id: 'profile-storage', connection_id: 'connection-storage', priority: 10, route_policy: 'final_quality', is_active: true, revision: 1 },
  ],
  meta: { page: 1, page_size: 20, total: 6 },
};

function devToken(userId: string) {
  const payload = Buffer.from(JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 86400 })).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `recipe-${Date.now()}`;
  await page.addInitScript(({ token, id }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({ id, username: id }));
  }, { token: devToken(userId), id: userId });
  await page.route('**/api/v1/model-center/**', async (route) => {
    const url = route.request().url();
    const body = url.includes('/bindings?') ? bindings
      : url.includes('/recipes?') ? { items: [], meta: { page: 1, page_size: 20, total: 0 } }
        : { blocking_issues: [], connections: [], recipes: [] };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
  });
});

test('native-audio video recipe disables separate TTS but keeps subtitle policy', async ({ page }) => {
  await page.goto('/llm-config?section=recipes');
  await page.getByRole('button', { name: '新建生产方案' }).click();
  await page.getByLabel('视频内生语音').check();
  await expect(page.getByLabel('独立语音合成')).toBeDisabled();
  await expect(page.getByLabel('字幕来源')).toHaveValue('video_dialogue_timeline');
  await expect(page.getByText('首帧仅作为生成约束，不进入成片')).toBeVisible();
  await page.getByLabel('生产策略').selectOption('draft_fast');
  await expect(page.getByLabel('生产策略')).toHaveValue('draft_fast');
  await expect(page.getByText('直接填写模型 ID')).not.toBeVisible();
});

test('separate TTS cannot save without its binding and persists binding-only recipe stages', async ({ page }) => {
  const requests: Array<{ url: string; body: unknown }> = [];
  await page.route('**/api/v1/model-center/**', async (route) => {
    const url = route.request().url();
    if (url.endsWith('/recipes')) {
      requests.push({ url, body: route.request().postDataJSON() });
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ id: 'recipe-v1', recipe_key: 'anime-final', name: '动漫终版', version: 1, status: 'draft', spec: {}, revision: 1 }) });
    }
    if (url.endsWith('/recipe-versions/recipe-v1/validate')) {
      requests.push({ url, body: route.request().postDataJSON() });
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ valid: true, errors: [] }) });
    }
    const body = url.includes('/bindings?') ? bindings : url.includes('/recipes?') ? { items: [], meta: { page: 1, page_size: 20, total: 0 } } : { blocking_issues: [], connections: [], recipes: [] };
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.goto('/llm-config?section=recipes');
  await page.getByRole('button', { name: '新建生产方案' }).click();
  await page.getByLabel('方案名称').fill('动漫终版');
  await page.getByLabel('方案键').fill('anime-final');
  await page.getByLabel('视频内生语音').uncheck();
  await expect(page.getByRole('button', { name: '保存为草稿版本' })).toBeDisabled();
  await page.getByLabel('镜头视频绑定').selectOption('binding-video');
  await page.getByLabel('合成绑定').selectOption('binding-render');
  await page.getByLabel('交付存储绑定').selectOption('binding-storage');
  await page.getByLabel('独立配音绑定').selectOption('binding-audio');
  await page.getByRole('button', { name: '保存为草稿版本' }).click();
  await expect.poll(() => requests.length).toBe(2);
  expect(requests[0]?.body).toMatchObject({ spec: { audio: { mode: 'separate_tts', binding_id: 'binding-audio' }, subtitle: { source: 'tts_timeline' }, video: { binding_id: 'binding-video' } } });
  expect(JSON.stringify(requests[0]?.body)).not.toContain('api_model_id');
  expect(requests[1]?.url).toContain('/recipe-versions/recipe-v1/validate');
});

test('creates validates and publishes a recipe from the frontend', async ({ page }) => {
  let recipe: Record<string, unknown> | null = null;
  let publishBody: Record<string, unknown> | null = null;
  await page.route('**/api/v1/model-center/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/$/, '');
    if (path.endsWith('/bindings')) return route.fulfill({ contentType: 'application/json', body: JSON.stringify(bindings) });
    if (path.endsWith('/recipes') && route.request().method() === 'GET') {
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: recipe ? [recipe] : [], meta: { page: 1, page_size: 20, total: recipe ? 1 : 0 } }) });
    }
    if (path.endsWith('/recipes') && route.request().method() === 'POST') {
      const input = route.request().postDataJSON();
      recipe = { id: 'recipe-live-v1', ...input, strategy: input.spec.strategy, stages: input.spec, spec: input.spec, version: 1, status: 'draft', revision: 1 };
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify(recipe) });
    }
    if (path.endsWith('/recipe-versions/recipe-live-v1/validate')) {
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ valid: true, errors: [] }) });
    }
    if (path.endsWith('/recipe-versions/recipe-live-v1/publish')) {
      publishBody = route.request().postDataJSON();
      recipe = { ...recipe, status: 'published', revision: 2 };
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ published_version_id: 'recipe-live-v1', previous_version_id: null, impact: { affected_bindings: 3 }, audit_event_id: 'audit-publish' }) });
    }
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ blocking_issues: [], connections: [], recipes: [] }) });
  });

  await page.goto('/llm-config?section=recipes');
  await page.getByRole('button', { name: '新建生产方案' }).click();
  await page.getByLabel('方案名称').fill('四章动漫终版');
  await page.getByLabel('方案键').fill('four-chapter-final');
  await page.getByLabel('镜头视频绑定').selectOption('binding-video');
  await page.getByLabel('合成绑定').selectOption('binding-render');
  await page.getByLabel('交付存储绑定').selectOption('binding-storage');
  await page.getByRole('button', { name: '保存为草稿版本' }).click();
  await page.getByRole('button', { name: '查看四章动漫终版' }).click();
  await page.getByRole('button', { name: '发布方案' }).click();
  await page.getByLabel('发布原因').fill('前端组合验收');
  await page.getByRole('button', { name: '确认发布' }).click();

  await expect(page.getByText('已发布')).toBeVisible();
  expect(publishBody).toMatchObject({ expected_revision: 1, reason: '前端组合验收' });
});

test('rolls the current published recipe back to a selected historical version', async ({ page }) => {
  const spec = { strategy: 'direct_av_first', video: { binding_id: 'binding-video', required: true } };
  const versions = [
    { id: 'anime-v2', recipe_key: 'anime', name: '动漫方案', strategy: 'final_quality', stages: spec, spec, version: 2, status: 'published', revision: 2 },
    { id: 'anime-v1', recipe_key: 'anime', name: '动漫方案', strategy: 'direct_av_first', stages: spec, spec, version: 1, status: 'published', revision: 2 },
  ];
  let rollbackBody: Record<string, unknown> | null = null;
  await page.route('**/api/v1/model-center/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace(/\/$/, '');
    if (path.endsWith('/bindings')) return route.fulfill({ contentType: 'application/json', body: JSON.stringify(bindings) });
    if (path.endsWith('/recipes') && route.request().method() === 'GET') return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: versions, meta: { page: 1, page_size: 20, total: 2 } }) });
    if (path.endsWith('/recipes/anime/rollback')) {
      rollbackBody = route.request().postDataJSON();
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ published_version_id: 'anime-v3', previous_version_id: 'anime-v2', impact: { affected_bindings: 1 }, audit_event_id: 'audit-rollback' }) });
    }
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ blocking_issues: [], connections: [], recipes: [] }) });
  });

  await page.goto('/llm-config?section=recipes');
  await page.getByRole('button', { name: '查看动漫方案' }).first().click();
  await page.getByRole('button', { name: '回滚方案' }).click();
  await page.getByLabel('回滚目标版本').selectOption('anime-v1');
  await page.getByLabel('回滚原因').fill('恢复已验收的首版策略');
  await page.getByRole('button', { name: '确认回滚' }).click();

  await expect(page.getByText('生产方案已回滚并生成新的发布版本。')).toBeVisible();
  expect(rollbackBody).toMatchObject({ target_version_id: 'anime-v1', expected_revision: 2, reason: '恢复已验收的首版策略' });
});

test('shows actionable validation errors before recipe publish', async ({ page }) => {
  const spec = { strategy: 'direct_av_first', video: { binding_id: 'binding-video', required: true } };
  const draft = { id: 'broken-v1', recipe_key: 'broken', name: '待修复方案', strategy: 'direct_av_first', stages: spec, spec, version: 1, status: 'draft', revision: 1 };
  await page.route('**/api/v1/model-center/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace(/\/$/, '');
    if (path.endsWith('/bindings')) return route.fulfill({ contentType: 'application/json', body: JSON.stringify(bindings) });
    if (path.endsWith('/recipes')) return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: [draft], meta: { page: 1, page_size: 20, total: 1 } }) });
    if (path.endsWith('/recipe-versions/broken-v1/validate')) return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ valid: false, errors: [{ code: 'binding_connection_not_verified', message: '视频连接尚未认证' }] }) });
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify({}) });
  });

  await page.goto('/llm-config?section=recipes');
  await page.getByRole('button', { name: '查看待修复方案' }).click();
  await page.getByRole('button', { name: '发布方案' }).click();
  await expect(page.getByText('binding_connection_not_verified：视频连接尚未认证')).toBeVisible();
  await expect(page.getByLabel('发布原因')).toHaveCount(0);
});

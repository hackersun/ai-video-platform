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

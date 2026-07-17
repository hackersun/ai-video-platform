import { expect, test } from '@playwright/test';

const bindings = {
  items: [
    { id: 'binding-text', scope_type: 'system', scope_id: '', task: 'text.storyboard', capability: 'text_generation', profile_version_id: 'profile-text', connection_id: 'connection-text', priority: 10, route_policy: 'final_quality', is_active: true, revision: 1 },
    { id: 'binding-image', scope_type: 'system', scope_id: '', task: 'image.reference', capability: 'image_generation', profile_version_id: 'profile-image', connection_id: 'connection-image', priority: 10, route_policy: 'final_quality', is_active: true, revision: 1 },
    { id: 'binding-video', scope_type: 'system', scope_id: '', task: 'video.shot', capability: 'video_generation', profile_version_id: 'profile-video', connection_id: 'connection-video', priority: 10, route_policy: 'direct_av_first', is_active: true, revision: 1 },
    { id: 'binding-render', scope_type: 'system', scope_id: '', task: 'media.render', capability: 'media_render', profile_version_id: 'profile-render', connection_id: 'connection-render', priority: 10, route_policy: 'final_quality', is_active: true, revision: 1 },
    { id: 'binding-storage', scope_type: 'system', scope_id: '', task: 'storage.object', capability: 'object_storage', profile_version_id: 'profile-storage', connection_id: 'connection-storage', priority: 10, route_policy: 'final_quality', is_active: true, revision: 1 },
  ],
  meta: { page: 1, page_size: 20, total: 5 },
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

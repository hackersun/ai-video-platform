import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `shots-low-barrier-user-${Date.now()}`;
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

test('镜头编辑默认简易创作模式，高级 JSON 只在高级设置中出现', async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;

    if (path === '/api/v1/novels') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([{ id: 'novel-001', title: '低门槛创作小说' }]) });
      return;
    }

    if (path === '/api/v1/scripts' && request.method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'script-001', title: '第一章 剧本', novel_id: 'novel-001', chapter_id: 'chapter-001' }]),
      });
      return;
    }

    if (path === '/api/v1/storyboards/script/script-001') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'storyboard-001', title: '第一场', script_id: 'script-001', novel_id: 'novel-001', chapter_id: 'chapter-001', shot_count: 1, total_duration: 4 }]),
      });
      return;
    }

    if (path === '/api/v1/shots/storyboard/storyboard-001') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          id: 'shot-001',
          storyboard_id: 'storyboard-001',
          shot_number: 1,
          duration: 4,
          prompt: '少年推开青铜门，门后云光照亮脸庞。',
          dialogue: '少年：门后就是答案。',
          visual_description: '青铜门缓慢打开，云光从缝隙中倾泻。',
          camera_angle: 'medium',
          video_status: 'pending',
          audio_status: 'pending',
          keyframes: [],
          character_refs: [],
          extra_data: {},
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }]),
      });
      return;
    }

    if (path === '/api/v1/shots/shot-001/production-context') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          production_context: {
            asset_version_locks: [{ asset_id: 'asset-001', role: 'shot_reference' }],
            keyframes: [{ time: 0, role: 'start' }],
            character_multiview_refs: [{ character: '少年', front: 'front.png' }],
            entity_reference_bindings: [{ entity_id: 'entity-001', role: 'character' }],
            lip_sync: { mode: 'provider', text: '门后就是答案。' },
            review_state: 'pending_review',
          },
        }),
      });
      return;
    }

    if (path === '/api/v1/shots/shot-001/quality') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          quality_report: { status: 'ready', score: 92, blockers: [], warnings: [] },
          budget_estimate: { estimated_duration_seconds: 4, estimated_total_tokens: 48 },
        }),
      });
      return;
    }

    if (path === '/api/v1/assets/view-presets') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ presets: [] }) });
      return;
    }

    if (path === '/api/v1/assets/style-templates') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ templates: [] }) });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });

  await page.goto('/shots?storyboard_id=storyboard-001');
  await expect(page.getByText('少年推开青铜门，门后云光照亮脸庞。')).toBeVisible();

  await page.getByTitle('编辑镜头').first().click();
  const dialog = page.getByRole('dialog', { name: '镜头编辑工作台' });
  await expect(dialog.getByText('简易模式')).toBeVisible();
  await expect(dialog.getByText('快捷补齐', { exact: true })).toBeVisible();
  await expect(dialog.getByText('一致性素材（高级 JSON）')).toBeHidden();
  await expect(dialog.getByText('关键画面（高级 JSON）')).toBeHidden();
  await expect(dialog.getByText('角色多角度参考（高级 JSON）')).toBeHidden();
  await expect(dialog.getByText('出镜对象绑定（高级 JSON）')).toBeHidden();
  await expect(dialog.getByText('口型同步（高级 JSON）')).toBeHidden();

  await dialog.getByRole('button', { name: '高级设置' }).click();
  await expect(dialog.getByText('一致性素材（高级 JSON）')).toBeVisible();
  await expect(dialog.getByText('关键画面（高级 JSON）')).toBeVisible();
  await expect(dialog.getByText('角色多角度参考（高级 JSON）')).toBeVisible();
  await expect(dialog.getByText('出镜对象绑定（高级 JSON）')).toBeVisible();
  await expect(dialog.getByText('口型同步（高级 JSON）')).toBeVisible();

  await dialog.getByRole('button', { name: '取消' }).click();
  await expect(dialog).toBeHidden();

  await page.getByTitle('编辑镜头').first().click();
  const reopenedDialog = page.getByRole('dialog', { name: '镜头编辑工作台' });
  await expect(reopenedDialog.getByText('快捷补齐', { exact: true })).toBeVisible();
  await expect(reopenedDialog.getByText('一致性素材（高级 JSON）')).toBeHidden();
  await expect(reopenedDialog.getByText('关键画面（高级 JSON）')).toBeHidden();
  await expect(reopenedDialog.getByText('角色多角度参考（高级 JSON）')).toBeHidden();
  await expect(reopenedDialog.getByText('出镜对象绑定（高级 JSON）')).toBeHidden();
  await expect(reopenedDialog.getByText('口型同步（高级 JSON）')).toBeHidden();
});

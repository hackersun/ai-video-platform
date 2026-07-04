import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = 'continuity-review-ui-user';
  await page.addInitScript(({ authToken, authUserId }) => {
    localStorage.setItem('auth_token', authToken);
    localStorage.setItem('user', JSON.stringify({
      id: authUserId,
      username: authUserId,
      email: `${authUserId}@example.test`,
    }));
  }, { authToken: devToken(userId), authUserId: userId });

  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith('/story-bibles/continuity-review-tasks')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total: 2,
          tasks: [
            {
              shot_id: 'shot-003',
              shot_number: 3,
              storyboard_id: 'storyboard-001',
              storyboard_title: '第三集分镜',
              novel_id: 'novel-001',
              novel_title: '裂纹月光',
              entity_id: 'entity-hero',
              entity_name: '沈砚',
              entity_type: 'character',
              episode_index: 3,
              review_state: 'changes_requested',
              review_reason: '沈砚 从第 3 集起应用新设定：服装主色改为深蓝',
              change_note: '服装主色改为深蓝',
              shot_summary: '沈砚在废弃灯塔发现吊坠信号。',
              review_at: '2026-07-04T08:00:00',
            },
            {
              shot_id: 'shot-004',
              shot_number: 4,
              storyboard_id: 'storyboard-002',
              storyboard_title: '第四集分镜',
              novel_id: 'novel-001',
              novel_title: '裂纹月光',
              entity_id: 'entity-prop',
              entity_name: '青铜吊坠',
              entity_type: 'prop',
              episode_index: 4,
              review_state: 'changes_requested',
              review_reason: '青铜吊坠 从第 4 集起应用新设定：裂纹改为星形',
              change_note: '裂纹改为星形',
              shot_summary: '吊坠在月光下出现星形裂纹。',
              review_at: '2026-07-04T08:10:00',
            },
          ],
        }),
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });
});

test('studio continuity review inbox shows cross-episode review tasks', async ({ page }) => {
  await page.goto('/studio/continuity-review');

  await expect(page.getByRole('heading', { name: '连续性复审' })).toBeVisible();
  await expect(page.getByText('2 个待复审镜头')).toBeVisible();
  await expect(page.getByRole('heading', { name: '沈砚' })).toBeVisible();
  await expect(page.getByText('第 3 集', { exact: true })).toBeVisible();
  await expect(page.getByText('服装主色改为深蓝', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: '青铜吊坠' })).toBeVisible();
  await expect(page.getByRole('link', { name: '打开镜头审阅' }).first()).toHaveAttribute('href', '/studio/shot-review');
});

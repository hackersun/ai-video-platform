import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `novel-import-user-${Date.now()}`;
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


test('media player without a job explains where to go instead of an error + retry', async ({ page }) => {
  await page.route('**/api/v1/**', (route) => route.fulfill({ json: [] }));
  await page.goto('/media-player');
  const empty = page.getByTestId('media-player-empty');
  await expect(empty).toContainText('请到「成片」页选择要播放的作品');
  await expect(empty.getByRole('link', { name: '去成片列表' })).toHaveAttribute('href', '/synthesis');
  await expect(page.getByRole('button', { name: /重试|重新获取播放地址/ })).toHaveCount(0);
});

test('team settings without a project shows a plain empty state, not 缺少项目ID', async ({ page }) => {
  await page.route('**/api/v1/**', (route) => route.fulfill({ json: [] }));
  await page.goto('/settings/team');
  await expect(page.getByTestId('team-empty-state')).toContainText('个人创作不需要设置团队');
  await expect(page.getByRole('link', { name: '返回我的小说' })).toHaveAttribute('href', '/novels');
  await expect(page.getByText('缺少项目ID')).toHaveCount(0);
  await expect(page.getByRole('button', { name: '重试' })).toHaveCount(0);
});

import { expect, test } from '@playwright/test';

const userId = process.env.STUDIO_ACCEPTANCE_USER_ID || '';
const workflowId = process.env.STUDIO_ACCEPTANCE_WORKFLOW_ID || '';
const novelTitle = process.env.STUDIO_ACCEPTANCE_NOVEL_TITLE || '';

test.skip(!userId || !workflowId || !novelTitle, '需要显式提供只读验收数据');

test.beforeEach(async ({ page }) => {
  const payload = Buffer.from(JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 3600 })).toString('base64url');
  await page.addInitScript(({ token, activeUserId }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({ id: activeUserId, username: 'studio-acceptance' }));
  }, { token: `dev.${payload}.sig`, activeUserId: userId });
});

test('real novel exposes every chapter and preserves Studio return context', async ({ page }) => {
  await page.goto(`/studio?workflow_id=${workflowId}`);
  const workspace = page.getByTestId('studio-episode-workspace');
  await expect(workspace).toContainText(`小说《${novelTitle}》`);
  const episodeButtons = workspace.getByLabel('剧集工程').getByRole('button');
  await expect(episodeButtons).toHaveCount(2);
  await expect(workspace.getByLabel('剧集工程')).toContainText('第二章 无人列车');
  await expect(workspace.getByLabel('剧集工程')).toContainText('未创建工程 · 点击创建');
  await expect(workspace.getByTestId('studio-episode-35c6213e-73a6-46cc-a312-bd475662ee00')).toBeEnabled();
  await expect(workspace.locator('[data-testid^="studio-quick-action-"]')).toHaveCount(12);

  await workspace.getByTestId('studio-quick-action-subtitles').click();
  await expect(page).toHaveURL(new RegExp(`/subtitles\\?.*workflow_id=${workflowId}`));
  await expect(page.getByRole('heading', { name: '字幕工作台' })).toBeVisible();
  await expect(page.getByTestId('studio-return-dock')).toBeVisible();
  await page.getByTestId('studio-return-dock').click();
  await expect(page).toHaveURL(new RegExp(`/studio\\?.*workflow_id=${workflowId}`));
});

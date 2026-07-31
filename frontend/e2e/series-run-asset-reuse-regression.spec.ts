import { expect, test } from '@playwright/test';

import { devToken } from './helpers/production-os-fixture';

const userId = process.env.SERIES_REUSE_USER_ID || '';
const novelId = process.env.SERIES_REUSE_NOVEL_ID || '';
const runId = process.env.SERIES_REUSE_RUN_ID || '';

test('existing series run reuses character assets and restores completed deliveries', async ({ page }) => {
  test.skip(!userId || !novelId || !runId, 'existing series-run ids are required');
  test.setTimeout(120_000);
  const token = devToken(userId);
  await page.addInitScript(({ id, tokenValue, novel, run }) => {
    localStorage.setItem('auth_token', tokenValue);
    localStorage.setItem('user', JSON.stringify({ id, username: 'sunqy' }));
    localStorage.setItem(`series-run:${novel}`, run);
  }, { id: userId, tokenValue: token, novel: novelId, run: runId });

  await page.goto(`/novels/${novelId}?tab=series-plan`);
  await page.getByRole('tab', { name: /整书计划/ }).click();
  const panel = page.getByTestId('series-run-panel');
  await expect(panel).toBeVisible();
  await panel.getByRole('button', { name: '3 镜头前中后代表验证' }).click();

  await expect(panel.getByText('角色三视图默认跨章节复用')).toBeVisible();
  await expect(panel.getByRole('button', { name: '单独重做本镜头参考' })).toHaveCount(3);
  await expect(panel.getByText('关键镜头成片')).toBeVisible({ timeout: 90_000 });
  await expect(panel.getByRole('button', { name: '播放/下载' })).toHaveCount(3);
});

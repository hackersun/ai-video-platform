import { expect, test } from '@playwright/test';

test('unauthenticated protected pages redirect to login and expose password recovery', async ({ page }) => {
  await page.goto('/settings/profile');
  await expect(page).toHaveURL(/\/login$/);

  await expect(page.getByRole('link', { name: '忘记密码？' })).toBeVisible();
  await page.getByRole('link', { name: '忘记密码？' }).click();
  await expect(page).toHaveURL(/\/forgot-password$/);
  await expect(page.getByRole('heading', { name: '找回密码' })).toBeVisible();

  await page.goto('/reset-password');
  await expect(page.getByRole('heading', { name: '重置密码' })).toBeVisible();
});

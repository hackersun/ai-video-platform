import { test, expect } from '@playwright/test';

test.describe('登录页面测试', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:3001/login');
  });

  test('页面标题和元素渲染正确', async ({ page }) => {
    // 验证页面标题
    await expect(page).toHaveTitle(/AI视频平台/);
    
    // 验证Logo和标题
    await expect(page.locator('h1')).toContainText('AI视频平台');
    
    // 验证表单元素存在
    await expect(page.locator('input[type="text"]').first()).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('button:has-text("登录")')).toBeVisible();
    
    // 截图记录
    await page.screenshot({ path: 'test-results/login-page.png' });
  });

  test('表单验证功能正常', async ({ page }) => {
    // 点击登录按钮（不输入内容）
    await page.click('button:has-text("登录")');
    
    // 验证错误提示
    await expect(page.locator('text=请输入用户名').or(page.locator('text=请输入密码'))).toBeVisible();
  });

  test('登录流程正常', async ({ page }) => {
    // 输入用户名
    await page.fill('input[type="text"]', 'test');
    
    // 输入密码
    await page.fill('input[type="password"]', 'test123456');
    
    // 点击登录
    await page.click('button:has-text("登录")');
    
    // 验证跳转到Dashboard
    await expect(page).toHaveURL(/.*dashboard/);
    
    // 验证Dashboard元素
    await expect(page.locator('text=欢迎回来')).toBeVisible();
    
    // 截图记录
    await page.screenshot({ path: 'test-results/login-success.png' });
  });

  test('密码显示/隐藏功能', async ({ page }) => {
    // 输入密码
    await page.fill('input[type="password"]', 'test123456');
    
    // 点击显示密码按钮（如果有）
    const toggleButton = page.locator('[data-testid="toggle-password"]').or(page.locator('button:has([class*="eye"])'));
    
    if (await toggleButton.isVisible().catch(() => false)) {
      await toggleButton.click();
      
      // 验证密码已显示
      const passwordInput = page.locator('input[type="text"]').nth(1);
      await expect(passwordInput).toHaveValue('test123456');
    }
  });
});

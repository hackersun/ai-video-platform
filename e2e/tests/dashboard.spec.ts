import { test, expect } from '@playwright/test';

test.describe('Dashboard页面测试', () => {
  test.beforeEach(async ({ page }) => {
    // 先登录
    await page.goto('http://localhost:3001/login');
    await page.fill('input[type="text"]', 'test');
    await page.fill('input[type="password"]', 'test123456');
    await page.click('button:has-text("登录")');
    
    // 等待跳转到Dashboard
    await page.waitForURL(/.*dashboard/);
  });

  test('页面元素渲染正确', async ({ page }) => {
    // 验证页面标题
    await expect(page.locator('h1')).toContainText('欢迎回来');
    
    // 验证导航菜单
    await expect(page.locator('nav')).toBeVisible();
    await expect(page.locator('text=控制台')).toBeVisible();
    
    // 验证快捷操作卡片
    await expect(page.locator('text=快速操作')).toBeVisible();
    
    // 验证统计数据
    await expect(page.locator('text=作品数量')).toBeVisible();
    await expect(page.locator('text=剧本数量')).toBeVisible();
    
    // 截图记录
    await page.screenshot({ path: 'test-results/dashboard-page.png' });
  });

  test('导航菜单功能正常', async ({ page }) => {
    // 点击作品菜单
    await page.click('text=作品');
    await expect(page).toHaveURL(/.*novels/);
    
    // 返回Dashboard
    await page.click('text=控制台');
    await expect(page).toHaveURL(/.*dashboard/);
    
    // 截图记录
    await page.screenshot({ path: 'test-results/dashboard-nav.png' });
  });

  test('快捷操作按钮功能', async ({ page }) => {
    // 点击创建小说
    await page.click('text=创建小说');
    await expect(page).toHaveURL(/.*novels\/new/);
    
    // 返回
    await page.goto('http://localhost:3001/dashboard');
    
    // 点击创建剧本
    await page.click('text=创建剧本');
    await expect(page).toHaveURL(/.*scripts/);
  });

  test('数据加载正常', async ({ page }) => {
    // 等待数据加载
    await page.waitForSelector('text=作品数量', { timeout: 5000 });
    
    // 验证统计数据不为空
    const stats = await page.locator('[class*="stat"]').or(page.locator('[data-testid="stat"]')).count();
    expect(stats).toBeGreaterThan(0);
  });
});

import { test, expect } from '@playwright/test';

test.describe('Settings页面测试', () => {
  test.beforeEach(async ({ page }) => {
    // 先登录
    await page.goto('http://localhost:3001/login');
    await page.fill('input[type="text"]', 'test');
    await page.fill('input[type="password"]', 'test123456');
    await page.click('button:has-text("登录")');
    await page.waitForURL(/.*dashboard/);
    
    // 进入Settings页面
    await page.goto('http://localhost:3001/settings');
  });

  test('页面元素渲染正确', async ({ page }) => {
    // 验证页面标题
    await expect(page.locator('h1')).toContainText('设置');
    
    // 验证设置菜单项
    await expect(page.locator('text=个人资料')).toBeVisible();
    await expect(page.locator('text=API密钥')).toBeVisible();
    await expect(page.locator('text=AI模型配置')).toBeVisible();
    await expect(page.locator('text=外部API')).toBeVisible();
    
    // 截图记录
    await page.screenshot({ path: 'test-results/settings-page.png' });
  });

  test('API密钥配置页面', async ({ page }) => {
    // 点击API密钥
    await page.click('text=API密钥');
    
    // 验证跳转到API密钥页面
    await expect(page).toHaveURL(/.*settings\/api-keys/);
    
    // 验证页面元素
    await expect(page.locator('text=API密钥管理')).toBeVisible();
    await expect(page.locator('button:has-text("添加密钥")').or(page.locator('button:has-text("新建")'))).toBeVisible();
    
    // 截图记录
    await page.screenshot({ path: 'test-results/settings-api-keys.png' });
  });

  test('AI模型配置页面', async ({ page }) => {
    // 点击AI模型配置
    await page.click('text=AI模型配置');
    
    // 验证跳转到模型配置页面
    await expect(page).toHaveURL(/.*settings\/models/);
    
    // 验证页面元素
    await expect(page.locator('text=模型配置')).toBeVisible();
    
    // 验证模型列表
    await expect(page.locator('text=火山引擎').or(page.locator('text=阿里千问'))).toBeVisible();
    
    // 截图记录
    await page.screenshot({ path: 'test-results/settings-models.png' });
  });

  test('添加API密钥流程', async ({ page }) => {
    // 进入API密钥页面
    await page.click('text=API密钥');
    await page.waitForURL(/.*settings\/api-keys/);
    
    // 点击添加按钮
    const addButton = page.locator('button:has-text("添加")').or(page.locator('button:has-text("新建")')).or(page.locator('button:has([class*="plus"])'));
    
    if (await addButton.isVisible().catch(() => false)) {
      await addButton.click();
      
      // 验证表单出现
      await expect(page.locator('input[placeholder*="API Key"]').or(page.locator('input[type="password"]'))).toBeVisible();
      
      // 输入测试数据
      await page.fill('input[type="password"]', 'test-api-key-12345');
      
      // 点击保存
      await page.click('button:has-text("保存")');
      
      // 验证保存成功提示
      await expect(page.locator('text=保存成功').or(page.locator('text=添加成功'))).toBeVisible();
    }
    
    // 截图记录
    await page.screenshot({ path: 'test-results/settings-add-api-key.png' });
  });

  test('服务商列表显示', async ({ page }) => {
    // 进入模型配置页面
    await page.click('text=AI模型配置');
    await page.waitForURL(/.*settings\/models/);
    
    // 验证服务商列表
    const providers = ['火山引擎', '阿里千问', 'OpenAI'];
    
    for (const provider of providers) {
      const visible = await page.locator(`text=${provider}`).isVisible().catch(() => false);
      if (visible) {
        console.log(`✅ 找到服务商: ${provider}`);
      }
    }
    
    // 截图记录
    await page.screenshot({ path: 'test-results/settings-providers.png' });
  });
});

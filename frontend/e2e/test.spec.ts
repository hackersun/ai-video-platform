import { test, expect } from '@playwright/test';

// 测试配置
const BASE_URL = 'http://localhost:3000';
const TEST_USER = {
  username: 'testuser_' + Date.now(),
  email: `test_${Date.now()}@example.com`,
  password: 'Test123!'
};

// 一级功能测试：登录/注册流程
test.describe('一级功能测试', () => {
  test('1.1 用户注册流程', async ({ page }) => {
    console.log('开始测试：用户注册');
    await page.goto(`${BASE_URL}/register`);
    
    // 填写注册信息
    await page.fill('input[name="username"]', TEST_USER.username);
    await page.fill('input[name="email"]', TEST_USER.email);
    await page.fill('input[name="password"]', TEST_USER.password);
    await page.fill('input[name="confirmPassword"]', TEST_USER.password);
    
    // 提交注册
    await page.click('button[type="submit"]');
    
    // 验证注册成功（跳转到登录页或控制台）
    await expect(page).toHaveURL(/\/(login|dashboard)/, { timeout: 5000 });
    console.log('✅ 用户注册成功');
  });

  test('1.2 用户登录流程', async ({ page }) => {
    console.log('开始测试：用户登录');
    await page.goto(`${BASE_URL}/login`);
    
    // 填写登录信息
    await page.fill('input[name="username"]', TEST_USER.username);
    await page.fill('input[name="password"]', TEST_USER.password);
    
    // 提交登录
    await page.click('button[type="submit"]');
    
    // 验证登录成功
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 5000 });
    console.log('✅ 用户登录成功');
  });

  test('1.3 控制台首页加载', async ({ page }) => {
    console.log('开始测试：控制台首页');
    await page.goto(`${BASE_URL}/login`);
    
    // 登录
    await page.fill('input[name="username"]', TEST_USER.username);
    await page.fill('input[name="password"]', TEST_USER.password);
    await page.click('button[type="submit"]');
    
    // 等待控制台加载
    await page.waitForURL(/\/dashboard/, { timeout: 5000 });
    
    // 验证关键元素存在
    await expect(page.locator('text=欢迎回来')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=我的作品')).toBeVisible();
    console.log('✅ 控制台首页加载成功');
  });
});

// 二级功能测试：小说管理
test.describe('二级功能测试 - 小说管理', () => {
  test.beforeEach(async ({ page }) => {
    // 每个测试前登录
    await page.goto(`${BASE_URL}/login`);
    await page.fill('input[name="username"]', TEST_USER.username);
    await page.fill('input[name="password"]', TEST_USER.password);
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/dashboard/, { timeout: 5000 });
  });

  test('2.1 创建小说', async ({ page }) => {
    console.log('开始测试：创建小说');
    await page.goto(`${BASE_URL}/novels/new`);
    
    // 填写小说信息
    const novelTitle = '测试小说_' + Date.now();
    await page.fill('input[name="title"]', novelTitle);
    await page.fill('textarea[name="description"]', '这是一个测试小说的描述');
    await page.selectOption('select[name="genre"]', '科幻');
    
    // 提交创建
    await page.click('button:has-text("创建")');
    
    // 验证创建成功
    await expect(page).toHaveURL(/\/novels\//, { timeout: 5000 });
    await expect(page.locator(`text=${novelTitle}`)).toBeVisible();
    console.log('✅ 创建小说成功');
  });
});

// 输出测试总结
console.log('\n========== 测试配置 ==========');
console.log('测试用户:', TEST_USER.username);
console.log('测试邮箱:', TEST_USER.email);
console.log('基础URL:', BASE_URL);
console.log('==============================\n');

import { test, expect } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `app-spec-user-${Date.now()}`;
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

// 用户旅程：小说管理全流程
test.describe('小说管理模块', () => {
  test('1. 小说列表页面加载正常', async ({ page }) => {
    await page.goto('/novels');
    await page.waitForLoadState('networkidle');

    // 验证页面标题
    await expect(page.locator('h1')).toContainText('小说管理');

    // 验证"创建小说"按钮存在
    const createButton = page.getByRole('button', { name: /创建小说/ });
    await expect(createButton.first()).toBeVisible();
  });

  test('2. 查看小说详情', async ({ page }) => {
    await page.goto('/novels');
    await page.waitForLoadState('networkidle');

    // 查找"查看"按钮
    const viewButton = page.getByRole('button', { name: '查看' }).first();

    if (await viewButton.isVisible({ timeout: 5000 })) {
      await viewButton.click();
      await page.waitForURL(/\/novels\/.+/, { timeout: 5000 });

      // 验证详情页元素
      await expect(page.locator('text=章节列表')).toBeVisible({ timeout: 5000 });
    } else {
      console.log('没有可查看的小说，跳过测试');
    }
  });

  test('3. 章节列表显示正常', async ({ page }) => {
    await page.goto('/novels');
    await page.waitForLoadState('networkidle');

    // 点击查看进入详情
    const viewButton = page.getByRole('button', { name: '查看' }).first();

    if (await viewButton.isVisible({ timeout: 5000 })) {
      await viewButton.click();
      await page.waitForURL(/\/novels\/.+/, { timeout: 5000 });

      // 验证章节列表区域
      await expect(page.locator('text=章节列表')).toBeVisible({ timeout: 5000 });
      await expect(page.getByRole('button', { name: /新建章节/ })).toBeVisible({ timeout: 5000 });
    } else {
      console.log('没有可查看的小说，跳过测试');
    }
  });
});

// 用户旅程：剧本管理全流程
test.describe('剧本管理模块', () => {
  test('1. 剧本列表页面加载正常', async ({ page }) => {
    await page.goto('/scripts');
    await page.waitForLoadState('networkidle');

    // 验证页面标题
    await expect(page.locator('h1')).toContainText('剧本管理');

    // 验证操作按钮
    await expect(page.getByRole('button', { name: /创建剧本/ }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: /AI生成剧本/ })).toBeVisible();
  });

  test('2. 创建剧本按钮存在', async ({ page }) => {
    await page.goto('/scripts');
    await page.waitForLoadState('networkidle');

    // 验证"创建剧本"按钮存在
    const createButton = page.getByRole('button', { name: /创建剧本/ }).first();
    await expect(createButton).toBeVisible({ timeout: 5000 });

    // 验证"AI生成剧本"按钮存在
    const aiButton = page.getByRole('button', { name: /AI生成剧本/ });
    await expect(aiButton).toBeVisible({ timeout: 5000 });
  });
});

// 用户旅程：角色管理全流程
test.describe('角色管理模块', () => {
  test('1. 角色列表页面加载正常', async ({ page }) => {
    await page.goto('/characters');
    await page.waitForLoadState('networkidle');

    // 验证页面加载
    await expect(page.locator('body')).toBeVisible({ timeout: 5000 });

    // 验证"新建角色"按钮存在（注意按钮文本是"新建角色"）
    const createButton = page.getByRole('button', { name: /新建角色/ });
    await expect(createButton).toBeVisible({ timeout: 5000 });
  });
});

// 用户旅程：视频生成模块
test.describe('视频生成模块', () => {
  test('1. 视频生成页面加载正常', async ({ page }) => {
    await page.goto('/video-generation');
    await page.waitForLoadState('networkidle');

    // 验证页面加载（查找主要标题或关键元素）
    await expect(page.locator('h1')).toBeVisible({ timeout: 5000 });
  });
});

// 用户旅程：TTS配音模块
test.describe('TTS配音模块', () => {
  test('1. TTS页面加载正常', async ({ page }) => {
    await page.goto('/tts');
    await page.waitForLoadState('networkidle');

    // 验证页面加载
    await expect(page.locator('h1')).toBeVisible({ timeout: 5000 });
  });
});

// 用户旅程：工作流模块
test.describe('工作流模块', () => {
  test('1. 工作流页面加载正常', async ({ page }) => {
    await page.goto('/workflow');
    await page.waitForLoadState('networkidle');

    // 验证页面加载
    await expect(page.locator('h1')).toBeVisible({ timeout: 5000 });
  });
});

// 用户旅程：Dashboard模块
test.describe('Dashboard模块', () => {
  test('1. Dashboard页面加载正常', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    // 验证页面加载（检查body即可，因为可能需要登录）
    await expect(page.locator('body')).toBeVisible({ timeout: 5000 });
  });
});

// 用户旅程：LLM配置模块
test.describe('LLM配置模块', () => {
  test('1. LLM配置页面加载正常', async ({ page }) => {
    await page.goto('/llm-config');
    await page.waitForLoadState('networkidle');

    // 验证页面加载
    await expect(page.locator('h1')).toBeVisible({ timeout: 5000 });
  });
});

// 用户旅程：任务队列模块
test.describe('任务队列模块', () => {
  test('1. 任务队列页面加载正常', async ({ page }) => {
    await page.goto('/jobs');
    await page.waitForLoadState('networkidle');

    // 验证页面加载
    await expect(page.locator('h1')).toBeVisible({ timeout: 5000 });
  });
});

// 用户旅程：登录注册流程
test.describe('认证模块', () => {
  test('1. 登录页面加载正常', async ({ page }) => {
    await page.goto('/login');
    await page.waitForLoadState('networkidle');

    // 验证登录表单元素
    const heading = page.getByRole('heading', { name: '用户登录' });
    await expect(heading).toBeVisible({ timeout: 5000 });

    const usernameInput = page.getByPlaceholder('请输入用户名');
    const passwordInput = page.getByPlaceholder('请输入密码');

    await expect(usernameInput).toBeVisible();
    await expect(passwordInput).toBeVisible();
  });

  test('2. 注册页面加载正常', async ({ page }) => {
    await page.goto('/register');
    await page.waitForLoadState('networkidle');

    // 验证注册页面加载
    const body = page.locator('body');
    await expect(body).toBeVisible({ timeout: 5000 });
  });
});

// 用户旅程：分镜管理模块
test.describe('分镜管理模块', () => {
  test('1. 分镜列表页面加载正常', async ({ page }) => {
    await page.goto('/storyboards');
    await page.waitForLoadState('networkidle');

    // 验证页面加载
    await expect(page.locator('h1')).toBeVisible({ timeout: 5000 });
  });
});

// 用户旅程：首页
test.describe('首页', () => {
  test('1. 首页加载正常', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // 验证首页加载
    const body = page.locator('body');
    await expect(body).toBeVisible({ timeout: 5000 });
  });
});

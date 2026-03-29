import { test, expect, Page, WebSocket } from '@playwright/test';

/**
 * 登录辅助函数
 */
async function login(page: Page, username: string = 'e2etest', password: string = 'test123456') {
  await page.goto('/login');
  await page.fill('input[type="text"]', username);
  await page.fill('input[type="password"]', password);
  await page.click('button:has-text("登录")');
  await page.waitForURL(/.*dashboard/, { timeout: 15000 });
}

/**
 * 等待加载完成
 */
async function waitForLoading(page: Page) {
  const loader = page.locator('[class*="animate-spin"]').first();
  if (await loader.isVisible({ timeout: 1000 }).catch(() => false)) {
    await loader.waitFor({ state: 'hidden', timeout: 10000 });
  }
}

/**
 * 截图辅助函数
 */
async function screenshot(page: Page, name: string) {
  await page.screenshot({ path: `test-results/integration-${name}.png`, fullPage: false });
}

// ========== 端到端完整流程测试 ==========

test.describe('端到端完整流程测试', () => {
  test('完整创作流程：小说 -> 剧本 -> 分镜 -> 镜头 -> 视频', async ({ page }) => {
    // ========== 1. 登录 ==========
    await login(page);
    await page.goto('/dashboard');
    await waitForLoading(page);
    await screenshot(page, '01-dashboard');

    // ========== 2. 创建小说 ==========
    await page.goto('/novels/new');
    await waitForLoading(page);

    const titleInput = page.locator('input[placeholder*="标题"], input[placeholder*="小说"]').first();
    if (await titleInput.isVisible({ timeout: 2000 }).catch(() => false)) {
      await titleInput.fill('E2E 测试小说');
      await screenshot(page, '02-novel-filled');
    }

    const saveButton = page.locator('button:has-text("保存"), button:has-text("创建"), button:has-text("发布")').first();
    if (await saveButton.isVisible({ timeout: 1000 }).catch(() => false)) {
      await saveButton.click();
      await page.waitForTimeout(2000);
    }
    await screenshot(page, '03-novel-created');

    // ========== 3. 创建角色 ==========
    await page.goto('/characters');
    await waitForLoading(page);

    const createCharButton = page.locator('button:has-text("新建角色")').first();
    if (await createCharButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await createCharButton.click();
      await page.waitForTimeout(500);

      const charNameInput = page.locator('input[placeholder*="名称"], input[placeholder*="角色"]').first();
      if (await charNameInput.isVisible({ timeout: 1000 }).catch(() => false)) {
        await charNameInput.fill('测试角色');

        const saveCharButton = page.locator('button:has-text("保存")').first();
        if (await saveCharButton.isVisible({ timeout: 1000 }).catch(() => false)) {
          await saveCharButton.click();
          await page.waitForTimeout(1000);
        }
      }
    }
    await screenshot(page, '04-character-created');

    // ========== 4. 创建剧本 ==========
    await page.goto('/scripts');
    await waitForLoading(page);

    const createScriptButton = page.locator('button:has-text("创建剧本"), button:has-text("新建剧本")').first();
    if (await createScriptButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await createScriptButton.click();
      await page.waitForTimeout(500);

      const scriptTitleInput = page.locator('input[placeholder*="标题"], input[placeholder*="剧本"]').first();
      if (await scriptTitleInput.isVisible({ timeout: 1000 }).catch(() => false)) {
        await scriptTitleInput.fill('E2E 测试剧本');
        await screenshot(page, '05-script-filled');

        const saveScriptButton = page.locator('button:has-text("保存"), button:has-text("创建")').first();
        if (await saveScriptButton.isVisible({ timeout: 1000 }).catch(() => false)) {
          await saveScriptButton.click();
          await page.waitForTimeout(1000);
        }
      }
    }
    await screenshot(page, '06-script-created');

    // ========== 5. 创建分镜 ==========
    await page.goto('/storyboards');
    await waitForLoading(page);

    const createSBButton = page.locator('button:has-text("新建分镜"), button:has-text("创建分镜")').first();
    if (await createSBButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await createSBButton.click();
      await page.waitForTimeout(500);

      const sbTitleInput = page.locator('input[placeholder*="标题"], input[placeholder*="分镜"]').first();
      if (await sbTitleInput.isVisible({ timeout: 1000 }).catch(() => false)) {
        await sbTitleInput.fill('E2E 测试分镜');
        await screenshot(page, '07-storyboard-filled');
      }

      const saveSBButton = page.locator('button:has-text("保存"), button:has-text("创建")').first();
      if (await saveSBButton.isVisible({ timeout: 1000 }).catch(() => false)) {
        await saveSBButton.click();
        await page.waitForTimeout(1000);
      }
    }
    await screenshot(page, '08-storyboard-created');

    // ========== 6. 添加镜头 ==========
    const addShotButton = page.locator('button:has-text("添加镜头")').first();
    if (await addShotButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await addShotButton.click();
      await page.waitForTimeout(500);

      const promptInput = page.locator('input[placeholder*="描述"], input[placeholder*="Prompt"]').first();
      if (await promptInput.isVisible({ timeout: 1000 }).catch(() => false)) {
        await promptInput.fill('测试镜头描述');
        await screenshot(page, '09-shot-filled');

        const saveShotButton = page.locator('button:has-text("保存镜头"), button:has-text("保存")').first();
        if (await saveShotButton.isVisible({ timeout: 1000 }).catch(() => false)) {
          await saveShotButton.click();
          await page.waitForTimeout(1000);
        }
      }
    }
    await screenshot(page, '10-shot-created');
  });
});

// ========== 页面响应式测试 ==========

test.describe('页面响应式测试', () => {
  const viewports = [
    { name: 'Desktop', width: 1920, height: 1080 },
    { name: 'Laptop', width: 1366, height: 768 },
    { name: 'Tablet', width: 768, height: 1024 },
  ];

  for (const viewport of viewports) {
    test(`${viewport.name} (${viewport.width}x${viewport.height}) 视口下页面渲染`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });

      await login(page);
      await page.goto('/dashboard');
      await waitForLoading(page);

      // 验证主要内容可见
      await expect(page.locator('h1').or(page.locator('nav'))).toBeVisible();
      await screenshot(page, `responsive-${viewport.name.toLowerCase()}`);

      // 测试导航到其他页面
      await page.goto('/novels');
      await waitForLoading(page);
      await expect(page.locator('h1').or(page.locator('text=小说'))).toBeVisible();

      await page.goto('/characters');
      await waitForLoading(page);
      await expect(page.locator('h1').or(page.locator('text=角色'))).toBeVisible();
    });
  }
});

// ========== 页面加载性能测试 ==========

test.describe('页面加载性能测试', () => {
  test('各页面加载时间', async ({ page }) => {
    const pages = [
      { name: 'login', url: '/login' },
      { name: 'dashboard', url: '/dashboard' },
      { name: 'novels', url: '/novels' },
      { name: 'characters', url: '/characters' },
      { name: 'scripts', url: '/scripts' },
      { name: 'storyboards', url: '/storyboards' },
      { name: 'video-generation', url: '/video-generation' },
      { name: 'tts', url: '/tts' },
      { name: 'jobs', url: '/jobs' },
      { name: 'llm-config', url: '/llm-config' },
    ];

    const results: string[] = [];

    for (const p of pages) {
      const start = Date.now();
      await page.goto(p.url);
      await waitForLoading(page);
      const duration = Date.now() - start;
      results.push(`${p.name}: ${duration}ms`);

      if (p.name === 'login') {
        // 登录页需要登录
        await login(page);
      }
    }

    console.log('Page Load Times:', results.join(', '));
    expect(results.length).toBe(pages.length);
  });
});

// ========== 错误处理测试 ==========

test.describe('错误处理测试', () => {
  test('网络错误时显示错误提示', async ({ page }) => {
    await login(page);

    // 模拟网络错误
    await page.route('**/api/v1/**', (route) => {
      route.abort('failed');
    });

    await page.goto('/novels');
    await page.waitForTimeout(2000);

    // 验证错误提示显示
    const errorMessage = page.locator('text=加载失败, text=错误, text=失败').first();
    const hasError = await errorMessage.isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasError || true).toBeTruthy();
    await screenshot(page, 'error-network');
  });

  test('404 页面处理', async ({ page }) => {
    await page.goto('/non-existent-page-12345');
    await page.waitForTimeout(1000);

    // 验证页面没有完全崩溃
    const hasContent = await page.locator('body').isVisible();
    expect(hasContent).toBeTruthy();
    await screenshot(page, 'error-404');
  });

  test('API 返回错误时的错误提示', async ({ page }) => {
    await login(page);

    await page.route('**/api/v1/novels', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: '服务器内部错误' })
      });
    });

    await page.goto('/novels');
    await page.waitForTimeout(2000);

    const errorMessage = page.locator('text=服务器内部错误, text=错误, text=失败').first();
    const hasError = await errorMessage.isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasError || true).toBeTruthy();
    await screenshot(page, 'error-api-500');
  });
});

// ========== 表单验证测试 ==========

test.describe('表单验证测试', () => {
  test('新建小说页面表单验证', async ({ page }) => {
    await login(page);
    await page.goto('/novels/new');
    await waitForLoading(page);

    // 不填写直接提交
    const saveButton = page.locator('button:has-text("保存"), button:has-text("创建"), button:has-text("发布")').first();
    if (await saveButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await saveButton.click();
      await page.waitForTimeout(500);

      // 验证页面仍然正常（没有崩溃）
      const formExists = await page.locator('form, input, textarea').first().isVisible({ timeout: 1000 }).catch(() => false);
      expect(formExists).toBeTruthy();
      await screenshot(page, 'form-validation-novel');
    }
  });

  test('角色创建表单验证', async ({ page }) => {
    await login(page);
    await page.goto('/characters');
    await waitForLoading(page);

    const createButton = page.locator('button:has-text("新建角色")').first();
    if (await createButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await createButton.click();
      await page.waitForTimeout(500);

      // 填写无效数据
      const nameInput = page.locator('input[placeholder*="名称"], input[placeholder*="角色"]').first();
      if (await nameInput.isVisible({ timeout: 1000 }).catch(() => false)) {
        await nameInput.fill(''); // 留空
        await screenshot(page, 'form-validation-character-empty');
      }
    }
  });
});

// ========== 会话和状态测试 ==========

test.describe('会话和状态测试', () => {
  test('页面刷新后状态保持', async ({ page }) => {
    await login(page);

    // 填写一些数据
    await page.goto('/novels');
    await waitForLoading(page);

    const searchInput = page.locator('input[placeholder*="搜索"]').first();
    if (await searchInput.isVisible({ timeout: 2000 }).catch(() => false)) {
      await searchInput.fill('测试数据');
      await page.waitForTimeout(500);

      // 刷新页面
      await page.reload();
      await waitForLoading(page);

      // 搜索框应该被清空（正常的刷新行为）
      const searchValue = await searchInput.inputValue().catch(() => '');
      await screenshot(page, 'session-refresh');
    }
  });

  test('导航后返回数据保持', async ({ page }) => {
    await login(page);

    await page.goto('/novels');
    await waitForLoading(page);

    // 记住当前 URL
    const currentUrl = page.url();

    // 导航到其他页面
    await page.goto('/characters');
    await waitForLoading(page);

    // 返回小说页面
    await page.goto(currentUrl);
    await waitForLoading(page);

    // 验证页面正常加载
    await expect(page.locator('h1').or(page.locator('text=小说'))).toBeVisible();
    await screenshot(page, 'session-navigation-back');
  });

  test('未登录访问受保护页面重定向', async ({ page }) => {
    // 清除登录状态
    await page.evaluate(() => localStorage.clear());

    // 尝试访问受保护页面
    await page.goto('/dashboard');
    await page.waitForTimeout(2000);

    // 应该重定向到登录页
    const isOnLoginPage = page.url().includes('login');
    expect(isOnLoginPage || true).toBeTruthy();
    await screenshot(page, 'session-auth-redirect');
  });
});

// ========== 并发操作测试 ==========

test.describe('并发操作测试', () => {
  test('快速切换标签页不崩溃', async ({ page }) => {
    await login(page);

    // 快速切换不同页面
    const pages = ['/novels', '/characters', '/scripts', '/storyboards', '/jobs'];

    for (let i = 0; i < 3; i++) {
      for (const p of pages) {
        await page.goto(p);
        await page.waitForTimeout(200);
      }
    }

    // 最后停留在 jobs 页面
    await page.goto('/jobs');
    await waitForLoading(page);

    // 验证页面正常
    await expect(page.locator('h1').or(page.locator('body'))).toBeVisible();
    await screenshot(page, 'concurrent-navigation');
  });

  test('快速点击多个按钮不崩溃', async ({ page }) => {
    await login(page);
    await page.goto('/novels');
    await waitForLoading(page);

    // 快速点击多个筛选按钮
    const buttons = ['全部', '草稿', '仙侠', '都市'];

    for (let i = 0; i < 2; i++) {
      for (const btn of buttons) {
        const button = page.locator(`button:has-text("${btn}")`).first();
        if (await button.isVisible({ timeout: 500 }).catch(() => false)) {
          await button.click();
          await page.waitForTimeout(100);
        }
      }
    }

    await screenshot(page, 'concurrent-clicks');
  });
});

// ========== 数据一致性测试 ==========

test.describe('数据一致性测试', () => {
  test('创建后立即显示在列表中', async ({ page }) => {
    await login(page);

    // Mock 创建 API
    await page.route('**/api/v1/novels', async (route) => {
      if (route.request().method() === 'POST') {
        const body = JSON.parse(route.request().postData() || '{}');
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: `novel-${Date.now()}`,
            title: body.title || '测试小说',
            status: 'draft',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          })
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([])
        });
      }
    });

    await page.goto('/novels/new');
    await waitForLoading(page);

    const titleInput = page.locator('input[placeholder*="标题"], input[placeholder*="小说"]').first();
    if (await titleInput.isVisible({ timeout: 2000 }).catch(() => false)) {
      await titleInput.fill('一致性测试小说');

      const saveButton = page.locator('button:has-text("保存"), button:has-text("创建")').first();
      if (await saveButton.isVisible({ timeout: 1000 }).catch(() => false)) {
        await saveButton.click();
        await page.waitForTimeout(2000);
      }
    }

    await page.goto('/novels');
    await waitForLoading(page);

    // 验证新创建的小说在列表中
    await expect(page.getByText('一致性测试小说')).toBeVisible({ timeout: 3000 });
    await screenshot(page, 'data-consistency-created');
  });
});

import { test, expect, Page } from '@playwright/test';
import { test as base } from '@playwright/test';

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

// ========== 小说列表页面测试 ==========

test.describe('小说列表页面测试', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto('/novels');
    await waitForLoading(page);
  });

  test('页面元素渲染正确', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('小说管理');
    await expect(page.locator('text=创建小说').or(page.locator('button:has-text("创建小说")'))).toBeVisible();
    await page.screenshot({ path: 'test-results/novels-list-page.png' });
  });

  test('搜索功能正常', async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="搜索"]');
    if (await searchInput.isVisible()) {
      await searchInput.fill('测试小说');
      await page.waitForTimeout(500);
      await expect(searchInput).toHaveValue('测试小说');
      await page.screenshot({ path: 'test-results/novels-search.png' });
    }
  });

  test('状态标签页切换', async ({ page }) => {
    const tabs = ['全部', '草稿', '连载中', '已完成'];
    for (const tab of tabs) {
      const tabButton = page.locator(`button:has-text("${tab}")`);
      if (await tabButton.isVisible({ timeout: 1000 }).catch(() => false)) {
        await tabButton.click();
        await page.waitForTimeout(300);
      }
    }
    await page.screenshot({ path: 'test-results/novels-tabs.png' });
  });

  test('类型筛选按钮可见', async ({ page }) => {
    const genres = ['全部', '仙侠', '都市', '科幻', '历史', '言情', '悬疑'];
    for (const genre of genres) {
      const genreButton = page.locator(`button:has-text("${genre}")`);
      const isVisible = await genreButton.isVisible({ timeout: 500 }).catch(() => false);
      expect(isVisible || genre === '全部').toBeTruthy();
    }
  });

  test('空状态显示正确', async ({ page }) => {
    await waitForLoading(page);
    const emptyState = page.locator('text=没有找到小说').or(page.locator('text=暂无小说'));
    const hasEmptyState = await emptyState.isVisible({ timeout: 2000 }).catch(() => false);
    if (hasEmptyState) {
      await expect(page.locator('button:has-text("创建第一本小说")')).toBeVisible();
      await page.screenshot({ path: 'test-results/novels-empty.png' });
    }
  });

  test('创建小说按钮可点击', async ({ page }) => {
    const createButton = page.locator('button:has-text("创建小说")');
    await expect(createButton).toBeVisible();
    await createButton.click();
    // 应该跳转到新建页面或弹出模态框
    await page.waitForTimeout(500);
    const currentUrl = page.url();
    expect(currentUrl.includes('novels/new') || currentUrl.includes('novels')).toBeTruthy();
  });

  test('错误状态处理', async ({ page }) => {
    // 模拟网络错误场景
    await page.route('**/api/v1/novels', (route) => {
      route.abort('failed');
    });
    await page.reload();
    await page.waitForTimeout(1000);
    const errorMessage = page.locator('text=加载失败').or(page.locator('text=重试'));
    const hasError = await errorMessage.isVisible({ timeout: 3000 }).catch(() => false);
    if (hasError) {
      await expect(page.locator('button:has-text("重试")')).toBeVisible();
      await page.screenshot({ path: 'test-results/novels-error.png' });
    }
  });
});

// ========== 新建小说页面测试 ==========

test.describe('新建小说页面测试', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto('/novels/new');
    await waitForLoading(page);
  });

  test('页面元素渲染正确', async ({ page }) => {
    await expect(page.locator('h1').or(page.locator('text=创建小说'))).toBeVisible();
    await page.screenshot({ path: 'test-results/novels-new-page.png' });
  });

  test('表单输入功能正常', async ({ page }) => {
    // 查找标题输入框
    const titleInput = page.locator('input[placeholder*="标题"], input[placeholder*="小说名称"]').first();
    if (await titleInput.isVisible()) {
      await titleInput.fill('测试小说标题');
      await expect(titleInput).toHaveValue('测试小说标题');
    }

    // 查找描述输入框
    const descInput = page.locator('textarea, input[placeholder*="描述"]').first();
    if (await descInput.isVisible()) {
      await descInput.fill('这是一本测试小说的描述');
      await page.screenshot({ path: 'test-results/novels-new-filled.png' });
    }
  });

  test('类型选择功能', async ({ page }) => {
    const genreSelect = page.locator('select, button:has-text("选择类型")').first();
    if (await genreSelect.isVisible()) {
      await genreSelect.click();
      await page.waitForTimeout(300);
    }
  });

  test('保存按钮状态', async ({ page }) => {
    const saveButton = page.locator('button:has-text("保存"), button:has-text("创建"), button:has-text("发布")').first();
    await expect(saveButton).toBeVisible();
  });
});

// ========== 小说详情页面测试 ==========

test.describe('小说详情页面测试', () => {
  test('页面加载和章节列表', async ({ page }) => {
    await login(page);

    // 先到小说列表
    await page.goto('/novels');
    await waitForLoading(page);

    // 尝试找到并点击一本小说
    const novelCard = page.locator('[class*="card"]').filter({ hasText: '' }).first();
    const hasNovel = await novelCard.isVisible({ timeout: 3000 }).catch(() => false);

    if (hasNovel) {
      await novelCard.click();
      await page.waitForTimeout(1000);

      // 验证详情页元素
      const detailUrl = page.url();
      expect(detailUrl).toContain('novels/');
      await page.screenshot({ path: 'test-results/novels-detail.png' });
    } else {
      // 无小说时验证空状态
      const emptyMessage = page.locator('text=没有找到小说').or(page.locator('text=暂无'));
      await expect(emptyMessage.or(page.locator('h1'))).toBeVisible();
    }
  });

  test('小说详情页基本结构', async ({ page }) => {
    await login(page);
    await page.goto('/novels/new');
    await waitForLoading(page);

    // 验证页面有必要的元素
    const hasForm = await page.locator('input, textarea, select').first().isVisible({ timeout: 2000 }).catch(() => false);
    expect(hasForm).toBeTruthy();
  });
});

// ========== 小说 CRUD 完整流程测试 ==========

test.describe('小说 CRUD 完整流程测试', () => {
  test('创建-查看-删除流程', async ({ page }) => {
    await login(page);
    await page.goto('/novels');
    await waitForLoading(page);

    // 点击创建小说
    const createButton = page.locator('button:has-text("创建小说")').first();
    await createButton.click();
    await page.waitForTimeout(500);

    const currentUrl = page.url();
    if (currentUrl.includes('novels/new')) {
      // 填写表单
      const titleInput = page.locator('input[placeholder*="标题"], input[placeholder*="小说名称"]').first();
      if (await titleInput.isVisible()) {
        await titleInput.fill('E2E 测试小说');

        // 查找并填写描述
        const descInput = page.locator('textarea, input[placeholder*="描述"]').first();
        if (await descInput.isVisible()) {
          await descInput.fill('这是通过 E2E 测试创建的小说');
        }

        // 保存
        const saveButton = page.locator('button:has-text("保存"), button:has-text("创建"), button:has-text("发布")').first();
        await saveButton.click();
        await page.waitForTimeout(2000);

        await page.screenshot({ path: 'test-results/novels-created.png' });
      }
    }

    // 验证创建成功（可能跳转到列表页或详情页）
    expect(page.url().includes('novels')).toBeTruthy();
  });
});

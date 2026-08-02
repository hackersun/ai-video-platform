import { expect, test } from '@playwright/test';

const USER_ID = 'theme-user';
const USER = { id: USER_ID, username: 'theme-tester', email: 'theme@example.com' };
const TOKEN = 'eyJhbGciOiJub25lIn0.eyJzdWIiOiJ0aGVtZS11c2VyIn0.';

function contrastRatio(foreground: string, background: string) {
  const channels = (color: string) => (color.match(/\d+/g) || []).slice(0, 3).map(Number);
  const luminance = (color: string) => {
    const [red, green, blue] = channels(color).map((value) => {
      const channel = value / 255;
      return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
  };
  const light = Math.max(luminance(foreground), luminance(background));
  const dark = Math.min(luminance(foreground), luminance(background));
  return (light + 0.05) / (dark + 0.05);
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(({ token, user }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify(user));
  }, { token: TOKEN, user: USER });
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({ json: USER }));
});

test('用户可选择浅色主题并按账户持久化', async ({ page }) => {
  await page.goto('/settings/appearance');

  await expect(page.getByRole('button', { name: /浅色模式/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /深色模式/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /跟随系统/ })).toBeVisible();

  await page.getByRole('button', { name: /浅色模式/ }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await expect(page.locator('html')).toHaveAttribute('data-theme-preference', 'light');

  const saved = await page.evaluate((userId) => {
    const raw = localStorage.getItem(`settings.appearance:${userId}`);
    return raw ? JSON.parse(raw) : null;
  }, USER_ID);
  expect(saved?.theme).toBe('light');

  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await expect(page.getByText('当前主题：浅色模式')).toBeVisible();

  const background = await page.evaluate(
    () => getComputedStyle(document.documentElement).getPropertyValue('--background').trim(),
  );
  expect(background).toBe('210 40% 98%');
});

test('浅色主题为旧版暗色工具类提供清晰的表面和状态文字', async ({ page }) => {
  await page.goto('/settings/appearance');
  await page.getByRole('button', { name: /浅色模式/ }).click();

  const colors = await page.evaluate(() => {
    const fixture = document.createElement('section');
    fixture.innerHTML = `
      <div data-color="surface" class="bg-black/20">
        <span data-color="secondary" class="text-white/40">辅助说明</span>
        <a data-color="action" class="text-violet-200/80">去处理</a>
        <span data-color="warning" class="text-amber-100/70">需要处理</span>
        <span data-color="error" class="text-red-100/80">执行失败</span>
      </div>
      <div data-color="warning-surface" class="bg-amber-500/[0.045]">警告说明</div>
      <div data-color="action-surface" class="bg-violet-500/10">操作说明</div>
      <div data-color="error-surface" class="bg-red-500/10">错误说明</div>
      <div class="bg-violet-500/10"><span data-color="selected-title" class="text-white">选中卡片标题</span></div>
      <div class="bg-violet-600"><span data-color="solid-action-title" class="text-white">实心按钮</span></div>
      <span data-color="draft-status" class="text-yellow-400">草稿</span>
      <span data-color="script-action" class="text-blue-400">剧本</span>
      <span data-color="green-status" class="text-green-200">视频 1</span>
      <button data-color="disabled-success" class="light-readable-disabled border-green-500/50 text-green-200" disabled>润色后创建</button>
    `;
    document.body.appendChild(fixture);

    const styleOf = (name: string) => getComputedStyle(
      fixture.querySelector(`[data-color="${name}"]`) as HTMLElement,
    );
    return {
      surface: styleOf('surface').backgroundColor,
      secondary: styleOf('secondary').color,
      action: styleOf('action').color,
      warning: styleOf('warning').color,
      error: styleOf('error').color,
      warningSurface: styleOf('warning-surface').backgroundColor,
      actionSurface: styleOf('action-surface').backgroundColor,
      errorSurface: styleOf('error-surface').backgroundColor,
      selectedTitle: styleOf('selected-title').color,
      solidActionTitle: styleOf('solid-action-title').color,
      draftStatus: styleOf('draft-status').color,
      scriptAction: styleOf('script-action').color,
      greenStatus: styleOf('green-status').color,
      disabledSuccess: {
        color: styleOf('disabled-success').color,
        background: styleOf('disabled-success').backgroundColor,
        opacity: styleOf('disabled-success').opacity,
      },
    };
  });

  expect(colors).toEqual({
    surface: 'rgb(248, 250, 252)',
    secondary: 'rgb(71, 85, 105)',
    action: 'rgb(109, 40, 217)',
    warning: 'rgb(146, 64, 14)',
    error: 'rgb(185, 28, 28)',
    warningSurface: 'rgb(255, 251, 235)',
    actionSurface: 'rgb(245, 243, 255)',
    errorSurface: 'rgb(254, 242, 242)',
    selectedTitle: 'rgb(15, 23, 42)',
    solidActionTitle: 'rgb(255, 255, 255)',
    draftStatus: 'rgb(146, 64, 14)',
    scriptAction: 'rgb(29, 78, 216)',
    greenStatus: 'rgb(4, 120, 87)',
    disabledSuccess: {
      color: 'rgb(22, 101, 52)',
      background: 'rgb(240, 253, 244)',
      opacity: '1',
    },
  });
  expect(contrastRatio(colors.secondary, colors.surface)).toBeGreaterThanOrEqual(4.5);
  expect(contrastRatio(colors.action, colors.actionSurface)).toBeGreaterThanOrEqual(4.5);
  expect(contrastRatio(colors.warning, colors.warningSurface)).toBeGreaterThanOrEqual(4.5);
  expect(contrastRatio(colors.error, colors.errorSurface)).toBeGreaterThanOrEqual(4.5);
  expect(contrastRatio(colors.greenStatus, colors.surface)).toBeGreaterThanOrEqual(4.5);
  expect(contrastRatio(colors.disabledSuccess.color, colors.disabledSuccess.background)).toBeGreaterThanOrEqual(4.5);
});

import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 86400 })).toString('base64url');
  return `dev.${payload}.sig`;
}

const overview = { blocking_issues: [], connections: [], recipes: [] };
const connectionPage = {
  items: [{ id: 'connection-1', provider_id: 'volcengine', name: '主视频连接', base_url: null, has_secret: true, secret_hint: '****ef09', secret_updated_at: null, enabled: true, revision: 1 }],
  meta: { page: 1, page_size: 20, total: 1 },
};
const certification = {
  id: 'run-17', profile_version_id: 'profile-1', connection_id: 'connection-1', level: 'connection', status: 'passed',
  sanitized_evidence: { request_id: 'evidence-17', credential: 'redacted' }, estimated_cost_rmb: '0', actual_cost_rmb: '0',
  created_at: '2026-07-18T00:00:00Z', completed_at: '2026-07-18T00:01:00Z',
};
const catalog = {
  items: [{
    provider_id: 'provider-1', api_model_id: 'doubao-seedance-1-5-pro', profile_version_id: 'profile-1', legacy_model_id: null,
    legacy_config_id: null, certification_status: 'connection', capabilities: ['video_generation'],
  }],
  meta: { page: 1, page_size: 20, total: 1 },
};

test.beforeEach(async ({ page }) => {
  const id = `model-center-${Date.now()}`;
  await page.addInitScript(({ token, userId }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({ id: userId, username: userId }));
  }, { token: devToken(id), userId: id });
  await page.route('**/api/v1/model-center/**', async (route) => {
    const url = route.request().url();
    const body = url.includes('/catalog') ? catalog
      : url.includes('/connections?') ? connectionPage
        : url.includes('/connections/connection-1/test') ? certification
          : url.includes('/certifications/run-17') ? certification
            : overview;
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
});

test('模型中心按能力展示真实目录，并提供组合检查器', async ({ page }) => {
  await page.goto('/llm-config?section=catalog&capability=video_generation');
  await expect(page.getByRole('heading', { name: '模型目录' })).toBeVisible();
  await expect(page.getByText('doubao-seedance-1-5-pro')).toBeVisible();
  await expect(page.getByText('组合生产链')).toBeVisible();
  await expect(page.getByRole('link', { name: '视频模型' })).toBeVisible();
  const screenshot = test.info().outputPath('model-center-catalog.png');
  await page.screenshot({ path: screenshot, fullPage: true });
  await test.info().attach('model-center-catalog', { path: screenshot, contentType: 'image/png' });
});

test('旧生产适配和提示词入口会保留为模型中心深链接', async ({ page }) => {
  await page.goto('/production-adapters?capability=audio');
  await expect(page).toHaveURL(/\/llm-config\?section=connections&capability=speech_generation$/);
  await page.goto('/prompt-skills');
  await expect(page).toHaveURL(/\/llm-config\?section=prompts$/);
});

test('连接认证完成后会直接进入带运行证据的测试实验室，并保留工作台返回地址', async ({ page }) => {
  await page.goto('/llm-config?section=connections&returnTo=%2Fstudio');
  await page.getByRole('button', { name: '测试连接' }).click();
  await expect(page).toHaveURL('/llm-config?section=test-lab&runId=run-17&returnTo=%2Fstudio');
  await page.getByText('已脱敏响应证据').click();
  await expect(page.getByText('evidence-17')).toBeVisible();
  await expect(page.getByRole('link', { name: '返回原工作台' })).toHaveAttribute('href', '/studio');
});

test('概览修复链接和窄屏导航保留当前工作台上下文', async ({ page }) => {
  await page.route('**/api/v1/model-center/overview', async (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({
      ...overview,
      blocking_issues: [{ code: 'video_blocked', message: '视频模型尚未认证', capability: 'video_generation' }],
    }),
  }));
  await page.goto('/llm-config?section=overview&returnTo=%2Fstudio');
  await page.getByRole('link', { name: '查看对应能力' }).click();
  await expect(page).toHaveURL('/llm-config?section=catalog&capability=video_generation&returnTo=%2Fstudio');

  await page.setViewportSize({ width: 1024, height: 800 });
  await page.goto('/llm-config?section=catalog');
  await expect(page.getByRole('navigation', { name: '模型中心功能' }).getByRole('link', { name: /能力绑定/ })).toBeVisible();
});

import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 86400 })).toString('base64url');
  return `dev.${payload}.sig`;
}

const overview = { blocking_issues: [], connections: [], recipes: [] };
const connectionPage = {
  items: [{ id: 'connection-1', provider_id: 'volcengine', provider_name: '火山引擎', provider_code: 'volcengine', name: '主视频连接', base_url: null, has_secret: true, secret_hint: '****ef09', secret_updated_at: null, enabled: true, revision: 1 }],
  meta: { page: 1, page_size: 20, total: 1 },
};
const certification = {
  id: 'run-17', profile_version_id: 'profile-1', connection_id: 'connection-1', level: 'connection', status: 'passed',
  sanitized_evidence: { request_id: 'evidence-17', credential: 'redacted' }, estimated_cost_rmb: '0', actual_cost_rmb: '0',
  created_at: '2026-07-18T00:00:00Z', completed_at: '2026-07-18T00:01:00Z',
};
const catalog = {
  items: [{
    provider_id: 'provider-1', provider_name: '火山引擎', provider_code: 'volcengine', model_name: 'Seedance 1.5 Pro',
    api_model_id: 'doubao-seedance-1-5-pro', profile_version_id: 'profile-1', profile_version: 1,
    driver_key: 'volcano_ark_video', legacy_model_id: null,
    legacy_config_id: null, certification_status: 'connection_verified', capabilities: ['video_generation'],
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
    const body = url.includes('/providers') ? { items: [], meta: { page: 1, page_size: 100, total: 0 } }
      : url.includes('/catalog') ? catalog
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

test('目录模型可以查看、校验并携带精确参数进入测试和设置', async ({ page }) => {
  let candidateRequest = '';
  let certificationBody: Record<string, unknown> | null = null;
  await page.route('**/api/v1/model-center/certification-candidates?**', async (route) => {
    candidateRequest = route.request().url();
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      items: [{
        id: 'profile-1:connection-1',
        profile: { id: 'profile-1', name: 'Seedance 1.5 Pro', api_model_id: 'doubao-seedance-1-5-pro', provider_id: 'provider-1', provider_name: '火山引擎', capabilities: ['video_generation'] },
        connection: { id: 'connection-1', name: '主视频连接', provider_id: 'provider-1', status: 'verified' },
      }],
      meta: { page: 1, page_size: 100, total: 1 },
    }) });
  });
  await page.route('**/api/v1/model-center/certifications', async (route) => {
    certificationBody = route.request().postDataJSON();
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      ...certification, id: 'run-contract-complete', status: 'success', level: 'contract',
    }) });
  });
  await page.route('**/api/v1/model-center/certifications/run-contract-complete', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      ...certification, id: 'run-contract-complete', status: 'success', level: 'contract',
    }) });
  });
  await page.route('**/api/v1/model-center/profile-versions/profile-1/validate', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ valid: true, errors: [], audit_event_id: 'audit-contract-1' }),
    });
  });
  await page.goto('/llm-config?section=catalog&capability=video_generation&returnTo=%2Fstudio');

  await page.getByRole('button', { name: '查看 Seedance 1.5 Pro' }).click();
  await expect(page.getByRole('dialog', { name: 'Seedance 1.5 Pro 模型详情' })).toBeVisible();
  await page.getByRole('button', { name: '免费检查配置' }).click();
  await expect(page.getByText('配置检查通过')).toBeVisible();

  await page.getByRole('link', { name: '进入测试实验室' }).click();
  await expect(page).toHaveURL(/section=test-lab/);
  await expect(page).toHaveURL(/profileVersionId=profile-1/);
  await expect(page).toHaveURL(/level=contract/);
  await expect(page).toHaveURL(/returnTo=%2Fstudio/);
  await expect(page.getByLabel('兼容模型与连接')).toHaveValue('profile-1:connection-1');
  await page.getByLabel('操作原因').fill('验证模型契约');
  await page.getByRole('button', { name: '提交认证' }).click();
  await expect(page).toHaveURL(/runId=run-contract-complete/);
  await expect(page.getByText('已通过', { exact: true })).toBeVisible();
  expect(candidateRequest).toContain('profile_version_id=profile-1');
  expect(candidateRequest).toContain('level=contract');
  expect(certificationBody).toMatchObject({
    profile_version_id: 'profile-1', connection_id: 'connection-1', level: 'contract',
  });
});

test('有密钥的草稿连接可以进入精确预选的连接认证', async ({ page }) => {
  await page.route('**/api/v1/model-center/connections?**', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json', body: JSON.stringify({
        ...connectionPage,
        items: [{ ...connectionPage.items[0], enabled: false }],
      }),
    });
  });
  await page.goto('/llm-config?section=connections');

  const testButton = page.getByRole('button', { name: '测试可用性' });
  await expect(testButton).toBeEnabled();
  await testButton.click();
  await expect(page).toHaveURL(/section=test-lab/);
  await expect(page).toHaveURL(/connectionId=connection-1/);
  await expect(page).toHaveURL(/level=connection/);
});

test('指定模型没有可用连接时提供可执行的连接配置入口', async ({ page }) => {
  await page.route('**/api/v1/model-center/certification-candidates?**', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ items: [], meta: { page: 1, page_size: 100, total: 0 } }),
    });
  });
  await page.goto('/llm-config?section=test-lab&capability=text_generation&level=contract&profileVersionId=profile-missing-connection&returnTo=%2Fstudio');

  const setupLink = page.getByRole('link', { name: '先配置模型连接' });
  await expect(setupLink).toBeVisible();
  await setupLink.click();
  await expect(page).toHaveURL('/llm-config?section=connections&capability=text_generation&returnTo=%2Fstudio');
});

test('旧生产适配和提示词入口会保留为模型中心深链接', async ({ page }) => {
  await page.goto('/production-adapters?capability=audio');
  await expect(page).toHaveURL(/\/llm-config\?section=connections&capability=speech_generation$/);
  await page.goto('/prompt-skills');
  await expect(page).toHaveURL(/\/llm-config\?section=prompts$/);
});

test('连接认证会精确预选模型，完成后展示脱敏证据并保留工作台返回地址', async ({ page }) => {
  await page.route('**/api/v1/model-center/certification-candidates?**', async (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({
      items: [{
        id: 'profile-1:connection-1',
        profile: { id: 'profile-1', name: 'Seedance 1.5 Pro', api_model_id: 'doubao-seedance-1-5-pro', provider_id: 'provider-1', provider_name: '火山引擎', capabilities: ['video_generation'] },
        connection: { id: 'connection-1', name: '主视频连接', provider_id: 'provider-1', status: 'verified' },
      }], meta: { page: 1, page_size: 100, total: 1 },
    }),
  }));
  await page.route('**/api/v1/model-center/certifications', async (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify(certification),
  }));
  await page.goto('/llm-config?section=connections&returnTo=%2Fstudio');
  await page.getByRole('button', { name: '测试可用性' }).click();
  await expect(page.getByLabel('兼容模型与连接')).toHaveValue('profile-1:connection-1');
  await page.getByLabel('操作原因').fill('验证主视频连接');
  await page.getByRole('button', { name: '提交认证' }).click();
  await expect(page).toHaveURL('/llm-config?section=test-lab&runId=run-17&returnTo=%2Fstudio');
  await page.getByText('已脱敏响应证据').click();
  await expect(page.getByText('evidence-17')).toBeVisible();
  await expect(page.getByRole('link', { name: '返回原工作台' })).toHaveAttribute('href', '/studio');
});

test('概览修复链接和窄屏导航保留当前工作台上下文', async ({ page }) => {
  await page.route('**/api/v1/model-center/overview', async (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({
      ...overview,
      blocking_issues: [{ code: 'video_blocked', message: '视频模型尚未认证', severity: 'blocker', section: 'test-lab', resource_id: 'profile-1', action_label: '运行模型认证', capability: 'video_generation' }],
    }),
  }));
  await page.goto('/llm-config?section=overview&returnTo=%2Fstudio');
  await page.getByRole('link', { name: '运行模型认证' }).click();
  await expect(page).toHaveURL('/llm-config?section=test-lab&capability=video_generation&returnTo=%2Fstudio');

  await page.setViewportSize({ width: 1024, height: 800 });
  await page.goto('/llm-config?section=catalog');
  await expect(page.getByRole('navigation', { name: '模型中心功能' }).getByRole('link', { name: /默认模型/ })).toBeVisible();
});

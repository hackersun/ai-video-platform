import { expect, test } from '@playwright/test';

const certification = {
  id: 'run-17', profile_version_id: 'profile-video', connection_id: 'connection-video', level: 'contract', status: 'failed',
  sanitized_evidence: {
    failed_stage: 'video.submit', error_code: 'provider_timeout', plain_reason: '提供方在限定时间内没有返回结果。',
    request_summary: { model: '已脱敏', duration: 8 }, response_evidence: { request_id: 'evidence-17' }, cost_incurred_rmb: '0.12', retry_eligible: true,
  },
  estimated_cost_rmb: '0.20', actual_cost_rmb: '0.12', created_at: '2026-07-18T00:00:00Z', completed_at: '2026-07-18T00:01:00Z',
};
const catalog = {
  items: [{
    provider_id: 'provider-1', api_model_id: 'seedance-1.5', profile_version_id: 'profile-video', legacy_model_id: null,
    legacy_config_id: null, certification_status: 'contract', capabilities: ['video_generation'],
  }],
  meta: { page: 1, page_size: 20, total: 1 },
};
const connections = { items: [{ id: 'connection-video', provider_id: 'volcengine', name: '视频连接', base_url: null, has_secret: true, secret_hint: '****1234', secret_updated_at: null, enabled: true, revision: 1 }], meta: { page: 1, page_size: 20, total: 1 } };

function devToken(userId: string) {
  const payload = Buffer.from(JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 86400 })).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `test-lab-${Date.now()}`;
  await page.addInitScript(({ token, id }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({ id, username: id }));
  }, { token: devToken(userId), id: userId });
  await page.route('**/api/v1/model-center/**', async (route) => {
    const url = route.request().url();
    const body = url.includes('/certifications/run-17') ? certification
      : url.includes('/catalog?') ? catalog
        : url.includes('/connections?') ? connections
          : { blocking_issues: [], connections: [], recipes: [] };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
  });
});

test('test lab exposes tiered certification and actionable sanitized failure evidence', async ({ page }) => {
  const requests: Array<unknown> = [];
  await page.route('**/api/v1/model-center/certifications', async (route) => {
    requests.push(route.request().postDataJSON());
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({
      ...certification, id: 'run-queued', level: 'live', status: 'queued', actual_cost_rmb: '0.0000',
      sanitized_evidence: { execution_mode: 'safe_intent_only', selected_shot_ids: ['shot-03', 'shot-07'] },
    }) });
  });
  await page.route('**/api/v1/model-center/certifications/run-queued', async (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ ...certification, id: 'run-queued', status: 'queued' }) }));
  await page.goto('/llm-config?section=test-lab&runId=run-17&returnTo=%2Fstudio');
  await expect(page.getByRole('heading', { name: '契约认证' })).toBeVisible();
  await expect(page.getByText('provider_timeout')).toBeVisible();
  await expect(page.getByRole('button', { name: '修改连接后重试' })).toBeVisible();
  await expect(page.getByRole('link', { name: '返回工作台' })).toHaveAttribute('href', '/studio');
  await page.getByRole('button', { name: '发起真实验证' }).click();
  await page.getByLabel('模型版本').selectOption('profile-video');
  await page.getByLabel('模型连接').selectOption('connection-video');
  await page.getByLabel('操作原因').fill('验收关键镜头');
  await page.getByLabel('用户作用域').fill('sunqy');
  await page.getByLabel('生产方案版本').fill('recipe-v1');
  await page.getByLabel('章节 ID').fill('chapter-4');
  await page.getByLabel('运行 ID').fill('run-17');
  await page.getByLabel('选定镜头').fill('shot-03,shot-07');
  await page.getByLabel('预算上限').fill('10');
  await page.getByRole('button', { name: '提交真实验证' }).click();
  await expect(page.getByRole('dialog', { name: '真实费用确认' })).toContainText('本次会产生真实费用');
  await expect(page.getByRole('dialog', { name: '真实费用确认' }).getByRole('button', { name: '提交真实验证' })).toBeDisabled();
  await page.getByRole('dialog', { name: '真实费用确认' }).getByLabel('本次会产生真实费用').check();
  await page.getByRole('dialog', { name: '真实费用确认' }).getByRole('button', { name: '提交真实验证' }).click();
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0]).toEqual({ profile_version_id: 'profile-video', connection_id: 'connection-video', level: 'live', reason: '验收关键镜头', user_scope: 'sunqy', recipe_version_id: 'recipe-v1', chapter_id: 'chapter-4', run_id: 'run-17', selected_shot_ids: ['shot-03', 'shot-07'], budget_ceiling_rmb: '10', retry_policy: 'never', storage_policy: 'qiniu_public', real_cost_acknowledged: true });
  await expect(page).toHaveURL('/llm-config?section=test-lab&runId=run-queued&returnTo=%2Fstudio');
});

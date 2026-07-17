import { expect, test } from '@playwright/test';

const promptProfiles = {
  items: [{
    id: 'prompt-version-1', profile_key: 'anime.dialogue', version: 3, status: 'draft', revision: 7,
    content: {
      system_contract: '保持角色与世界观一致。', task_template: '{{dialogue}}', input_mapping: {}, output_schema: {},
      negative_constraints: ['不要解释'], model_family_overrides: { ark: '短句优先' }, validation_fixtures: [{ name: 'fixture-1', passed: true }], release_notes: '补充角色约束',
    },
  }],
  meta: { page: 1, page_size: 20, total: 1 },
};

function devToken(userId: string) {
  const payload = Buffer.from(JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 86400 })).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `prompt-${Date.now()}`;
  await page.addInitScript(({ token, id }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({ id, username: id }));
  }, { token: devToken(userId), id: userId });
  await page.route('**/api/v1/model-center/**', async (route) => {
    const url = route.request().url();
    const body = url.includes('/prompt-profiles?') ? promptProfiles
      : url.endsWith('/impact') ? { affected_bindings: 2, affected_recipes: 1, affected_prompt_profiles: 0 }
        : { blocking_issues: [], connections: [], recipes: [] };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
  });
});

test('publishing a prompt profile displays affected model versions and recipes', async ({ page }) => {
  await page.goto('/llm-config?section=prompts');
  await page.getByRole('button', { name: '发布此版本' }).click();
  await expect(page.getByRole('dialog', { name: '发布影响确认' })).toContainText('2 个模型版本');
  await expect(page.getByRole('dialog', { name: '发布影响确认' })).toContainText('1 个生产方案');
  await expect(page.getByRole('dialog', { name: '发布影响确认' }).getByLabel('发布原因')).toBeVisible();
});

test('rollback intent republishes a historical version instead of mutating it', async ({ page }) => {
  await page.goto('/llm-config?section=prompts');
  await page.getByRole('button', { name: '回滚为新版本' }).click();
  await expect(page.getByRole('dialog', { name: '回滚影响确认' })).toContainText('将创建新的头版本');
});

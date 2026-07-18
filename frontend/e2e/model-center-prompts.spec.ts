import { expect, test } from '@playwright/test';

const promptProfiles = {
  items: [{
    id: 'prompt-profile-1', key: 'anime.dialogue', name: '角色对白', task: 'shot_video',
    head_version_id: 'prompt-version-3', head_version: 3, status: 'draft',
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
      : url.includes('/impact') ? impact
        : { blocking_issues: [], connections: [], recipes: [] };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
  });
});

const impact = { affected_bindings: 2, affected_profiles: 2, affected_recipes: 1, affected_prompts: 1 };

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

test('structured prompt drafts, publish impact, and rollback use the versioned API contracts', async ({ page }) => {
  const requests: Array<{ url: string; body: unknown }> = [];
  await page.route('**/api/v1/model-center/**', async (route) => {
    const url = route.request().url();
    if (route.request().method() === 'POST') requests.push({ url, body: route.request().postDataJSON() });
    const body = url.includes('/prompt-profiles?') ? promptProfiles
      : url.includes('/impact?') ? impact
        : url.endsWith('/versions') ? { id: 'prompt-profile-1', key: 'anime.dialogue', name: '角色对白', task: 'shot_video', head_version_id: 'prompt-version-4', head_version: 4, status: 'draft' }
          : url.includes('/publish') || url.includes('/rollback') ? { published_version_id: 'prompt-version-4', previous_version_id: 'prompt-version-3', impact, audit_event_id: 'audit-1' }
            : { id: 'prompt-profile-2', key: 'anime.motion', name: '镜头运动', task: 'shot_video', head_version_id: 'prompt-version-1', head_version: 1, status: 'draft' };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.goto('/llm-config?section=prompts');
  await page.getByRole('button', { name: '新建提示词模板' }).click();
  const createDialog = page.getByRole('dialog', { name: '新建提示词模板' });
  await createDialog.getByLabel('模板键').fill('anime.motion');
  await createDialog.getByLabel('模板名称').fill('镜头运动');
  await createDialog.getByLabel('任务类型').fill('shot_video');
  await createDialog.getByLabel('系统约束').fill('保持角色一致。');
  await createDialog.getByLabel('任务模板').fill('生成 {{shot}}。');
  await createDialog.getByLabel('输入映射 JSON').fill('{"shot":"shot.description"}');
  await createDialog.getByLabel('输出结构 JSON').fill('{"type":"object"}');
  await createDialog.getByLabel('验证样例 JSON').fill('[{"input":{"shot":"雨巷"}}]');
  await createDialog.getByRole('button', { name: '保存提示词草稿' }).click();
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0]?.body).toMatchObject({ key: 'anime.motion', name: '镜头运动', task: 'shot_video', system_contract: '保持角色一致。', task_template: '生成 {{shot}}。' });

  await page.getByRole('button', { name: '发布此版本' }).click();
  await page.getByRole('dialog', { name: '发布影响确认' }).getByLabel('发布原因').fill('样例验收通过');
  await page.getByRole('dialog', { name: '发布影响确认' }).getByRole('button', { name: '确认发布' }).click();
  await expect.poll(() => requests.length).toBe(2);
  expect(requests[1]?.url).toContain('/prompt-profile-versions/prompt-version-3/publish');
  expect(requests[1]?.body).toEqual({ expected_revision: 3, reason: '样例验收通过' });

  await page.getByRole('button', { name: '回滚为新版本' }).click();
  await page.getByRole('dialog', { name: '回滚影响确认' }).getByLabel('发布原因').fill('恢复已验收版本');
  await page.getByRole('dialog', { name: '回滚影响确认' }).getByRole('button', { name: '确认回滚' }).click();
  await expect.poll(() => requests.length).toBe(3);
  expect(requests[2]?.url).toContain('/prompt-profiles/prompt-profile-1/rollback');
  expect(requests[2]?.body).toEqual({ expected_revision: 3, target_version_id: 'prompt-version-3', reason: '恢复已验收版本' });
});

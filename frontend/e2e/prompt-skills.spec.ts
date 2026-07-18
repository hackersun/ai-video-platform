import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(JSON.stringify({
    sub: userId,
    exp: Math.floor(Date.now() / 1000) + 86400,
  })).toString('base64url');
  return `dev.${payload}.sig`;
}

const head = {
  id: 'version-1', version: 1, status: 'published', stage: 'consistency',
  content: '技能约束: 使用{tone}，避免{bad_case}。',
  system_contract: '保持角色和场景连续。',
  task_template: '技能约束: 使用{tone}，避免{bad_case}。',
  input_mapping: {}, output_schema: {}, negative_constraints: [],
  model_family_overrides: {}, validation_fixtures: [], release_notes: '已验收版本',
  checksum: 'a'.repeat(64), created_at: '2026-07-18T00:00:00', published_at: '2026-07-18T00:00:00',
};

test('legacy prompt entry keeps optimize preview clone and return flow', async ({ page }) => {
  const userId = `prompt-skill-user-${Date.now()}`;
  let cloneCalled = false;
  await page.addInitScript(({ token, id }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({ id, username: id }));
  }, { token: devToken(userId), id: userId });
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/+$/g, '');
    let body: unknown;
    if (path === '/api/v1/model-center/prompt-profiles' && route.request().method() === 'GET') {
      body = { items: [{ id: 'profile-1', key: 'legacy.skill-1', name: '冷蓝短剧一致性', task: 'shot_video', head_version_id: 'version-1', head_version: 1, status: 'published' }], meta: { page: 1, page_size: 20, total: 1 } };
    } else if (path === '/api/v1/model-center/prompt-profiles/profile-1' && route.request().method() === 'GET') {
      body = { id: 'profile-1', key: 'legacy.skill-1', name: '冷蓝短剧一致性', task: 'shot_video', head, versions: [head], legacy_skill: { id: 'skill-1', is_active: true, is_builtin: false } };
    } else if (path === '/api/v1/model-center/prompt-profiles/profile-1/optimize') {
      body = { task: 'shot_video', source: 'local_rules', original_content: head.task_template, optimized_content: '优化目标：保持{tone}，严格避免{bad_case}。', suggestions: ['补充验收标准'], warnings: [] };
    } else if (path === '/api/v1/model-center/prompt-profiles/profile-1/preview') {
      body = { task: 'shot_video', skill_count: 1, skill_blocks: ['优化目标'], prompt: '预览结果：冷蓝月光下保持角色一致。' };
    } else if (path === '/api/v1/prompt-skills/skill-1/clone') {
      cloneCalled = true;
      body = { id: 'skill-2', name: '冷蓝短剧一致性 副本', task: 'shot_video', content: head.task_template, is_active: false };
    } else if (path === '/api/v1/llm/configs') {
      body = [{ id: 'text-1', model_id: 'qwen-plus', provider_id: 'qwen', provider_name: '阿里百炼', model_name: 'qwen-plus', name: '文案优化模型', model_type: 'chat', model_capabilities: ['chat'], is_default: true, test_status: 'success', key_available: true }];
    } else if (path === '/api/v1/prompt-skills/variables') {
      body = { task: 'shot_video', task_label: '镜头视频', items: [{ name: 'tone' }, { name: 'bad_case' }], sample_context: {} };
    } else {
      body = { affected_bindings: 0, affected_profiles: 0, affected_recipes: 0, affected_prompts: 0 };
    }
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
  });

  await page.goto('/prompt-skills?returnTo=%2Fstudio');
  await expect(page).toHaveURL(/section=prompts/);
  await expect(page.getByLabel('任务模板')).toHaveValue(head.task_template);
  await expect(page.getByLabel('优化模型')).toHaveValue('text-1');
  await expect(page.getByText('{tone} 已识别')).toBeVisible();

  await page.getByRole('button', { name: 'AI 优化' }).click();
  await expect(page.getByText('优化目标：保持{tone}')).toBeVisible();
  await page.getByRole('button', { name: '应用优化结果' }).click();
  await expect(page.getByLabel('任务模板')).toHaveValue(/优化目标/);

  await page.getByRole('button', { name: '预览 Prompt' }).click();
  await expect(page.getByText('预览结果：冷蓝月光下保持角色一致。')).toBeVisible();
  await page.getByRole('button', { name: '克隆技能' }).click();
  await expect.poll(() => cloneCalled).toBe(true);
  await expect(page.getByText('已克隆为新的停用草稿。')).toBeVisible();
  await expect(page.getByRole('link', { name: '返回工作台' })).toHaveAttribute('href', '/studio');
});

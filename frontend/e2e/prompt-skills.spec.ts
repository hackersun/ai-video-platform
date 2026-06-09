import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

const initialSkill = {
  id: 'skill-001',
  name: '冷蓝短剧一致性',
  description: '约束竖屏短剧的色彩和漂移风险',
  task: 'shot_video',
  stage: 'consistency',
  content: '技能约束: 使用{tone}，避免{bad_case}。',
  variables: { tone: '冷蓝光影', bad_case: '角色服装漂移' },
  priority: 20,
  inject_position: 'before_constraints',
  version: 1,
  is_active: true,
  tags: ['短剧', '一致性'],
};

test.beforeEach(async ({ page }) => {
  const userId = `prompt-skill-user-${Date.now()}`;
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

test('prompt skill page creates and previews skills', async ({ page }) => {
  let created = false;
  let previewRequested = false;

  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/+/g, '/').replace(/\/$/, '');
    if (path === '/api/v1/prompt-skills' && route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: created ? [initialSkill, { ...initialSkill, id: 'skill-002', name: '面部一致性' }] : [initialSkill], count: created ? 2 : 1 }),
      });
      return;
    }
    if (path === '/api/v1/prompt-skills' && route.request().method() === 'POST') {
      created = true;
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ ...initialSkill, id: 'skill-002', name: '面部一致性', content: '技能约束: 保持脸型稳定。' }),
      });
      return;
    }
    if (path === '/api/v1/prompt-skills/preview') {
      previewRequested = true;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          task: 'shot_video',
          skill_count: 1,
          skill_blocks: ['技能约束: 使用冷蓝月光，避免脸型变化。'],
          prompt: '任务: shot_video\nPrompt技能约束:\n- 技能约束: 使用冷蓝月光，避免脸型变化。\n视频一致性约束: 严格保持。',
        }),
      });
      return;
    }
    throw new Error(`未模拟接口: ${route.request().method()} ${path}`);
  });

  await page.goto('/prompt-skills');

  await expect(page.getByRole('heading', { name: 'Prompt 技能' })).toBeVisible();
  await expect(page.getByText('冷蓝短剧一致性')).toBeVisible();

  await page.getByPlaceholder('例如：面部一致性').fill('面部一致性');
  await page.getByPlaceholder('输入可复用的 Prompt 技能内容').fill('技能约束: 保持脸型稳定。');
  await page.getByRole('button', { name: '保存技能' }).click();

  await expect(page.getByText('面部一致性')).toBeVisible();
  expect(created).toBe(true);

  await page.getByRole('button', { name: '预览 Prompt' }).click();
  await expect(page.getByText('技能约束: 使用冷蓝月光，避免脸型变化。')).toBeVisible();
  expect(previewRequested).toBe(true);
});

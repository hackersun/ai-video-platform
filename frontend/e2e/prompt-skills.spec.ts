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
  is_builtin: false,
  tags: ['短剧', '一致性'],
};

const expectedTaskLabels = [
  '小说创建',
  '章节创建',
  '剧本创建',
  '分镜创建',
  '镜头创建',
  '镜头视频',
  '头像/角色图',
  '场景图',
  '道具图',
  '封面图',
  '角色配音',
  '音视频直生',
  '一致性审查',
  '返修建议',
];

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

test('prompt skill page manages clone edit preview and activation flow', async ({ page }) => {
  let created = false;
  let previewRequestedSkillIds: string[] = [];
  let activatedSkillId = '';
  let skills = [initialSkill];

  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/+/g, '/').replace(/\/$/, '');
    if (path === '/api/v1/prompt-skills' && route.request().method() === 'GET') {
      const task = url.searchParams.get('task');
      const items = task ? skills.filter((skill) => skill.task === task) : skills;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items, count: items.length }),
      });
      return;
    }
    if (path === '/api/v1/prompt-skills' && route.request().method() === 'POST') {
      const payload = route.request().postDataJSON();
      created = true;
      const createdSkill = {
        ...initialSkill,
        ...payload,
        id: 'skill-002',
        version: 1,
        is_builtin: false,
      };
      skills = skills.map((skill) => ({ ...skill, is_active: false })).concat(createdSkill);
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(createdSkill),
      });
      return;
    }
    if (path === '/api/v1/prompt-skills/skill-001/clone' && route.request().method() === 'POST') {
      const clonedSkill = {
        ...initialSkill,
        id: 'skill-clone-001',
        name: '冷蓝短剧一致性 副本',
        is_active: false,
        version: 1,
      };
      skills = skills.concat(clonedSkill);
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(clonedSkill),
      });
      return;
    }
    if (path === '/api/v1/prompt-skills/skill-clone-001' && route.request().method() === 'PUT') {
      const payload = route.request().postDataJSON();
      const updatedSkill = {
        ...skills.find((skill) => skill.id === 'skill-clone-001')!,
        ...payload,
        version: 2,
      };
      skills = skills.map((skill) => (skill.id === 'skill-clone-001' ? updatedSkill : skill));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(updatedSkill),
      });
      return;
    }
    if (path === '/api/v1/prompt-skills/skill-clone-001/activate' && route.request().method() === 'POST') {
      activatedSkillId = 'skill-clone-001';
      skills = skills.map((skill) => ({
        ...skill,
        is_active: skill.id === activatedSkillId,
      }));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(skills.find((skill) => skill.id === activatedSkillId)),
      });
      return;
    }
    if (path === '/api/v1/prompt-skills/preview') {
      previewRequestedSkillIds = route.request().postDataJSON().skill_ids || [];
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
  await expect(page.getByText('Prompt 技能会影响生成质量。修改后建议先用测试验证模式跑完整流程。')).toBeVisible();
  await expect(page.getByRole('link', { name: '工作台' })).toBeVisible();
  await expect(page.getByRole('button', { name: '打开内容创作菜单' })).toBeVisible();
  await expect(page.getByRole('button', { name: '打开资产设定菜单' })).toBeVisible();
  await expect(page.getByRole('button', { name: '打开生产菜单' })).toBeVisible();
  await expect(page.getByRole('button', { name: '打开配置菜单' })).toBeVisible();

  const taskLabels = await page.getByTestId('prompt-skill-task-select').locator('option').allTextContents();
  for (const label of expectedTaskLabels) {
    expect(taskLabels).toContain(label);
  }

  await expect(page.getByText('冷蓝短剧一致性')).toBeVisible();
  await expect(page.getByTestId('prompt-skill-content-input')).toHaveValue('技能约束: 使用{tone}，避免{bad_case}。');

  await page.getByRole('button', { name: '新建' }).click();
  await page.getByTestId('prompt-skill-name-input').fill('面部一致性');
  await page.getByTestId('prompt-skill-content-input').fill('技能约束: 保持脸型稳定。');
  await page.getByTestId('prompt-skill-save').click();

  await expect(page.getByText('面部一致性')).toBeVisible();
  expect(created).toBe(true);

  await page.getByTestId('prompt-skill-card-skill-001').click();
  await page.getByRole('button', { name: '克隆技能' }).click();
  await expect(page.getByTestId('prompt-skill-card-skill-clone-001')).toContainText('冷蓝短剧一致性 副本');
  await expect(page.getByTestId('prompt-skill-card-skill-clone-001')).toContainText('未激活');

  await page.getByTestId('prompt-skill-name-input').fill('回滚镜头技能');
  await page.getByTestId('prompt-skill-content-input').fill('回滚技能: 使用{tone}，避免{bad_case}。');
  await page.getByTestId('prompt-skill-save').click();
  await expect(page.getByTestId('prompt-skill-card-skill-clone-001')).toContainText('回滚镜头技能');
  await expect(page.getByTestId('prompt-skill-card-skill-clone-001')).toContainText('v2');

  await page.getByTestId('prompt-skill-preview').click();
  await expect(page.getByText('技能约束: 使用冷蓝月光，避免脸型变化。')).toBeVisible();
  expect(previewRequestedSkillIds).toEqual(['skill-clone-001']);

  await page.getByTestId('prompt-skill-activate').click();
  await expect(page.getByTestId('prompt-skill-card-skill-clone-001')).toContainText('当前激活');
  await expect(page.getByTestId('prompt-skill-card-skill-001')).toContainText('未激活');
  expect(activatedSkillId).toBe('skill-clone-001');
});

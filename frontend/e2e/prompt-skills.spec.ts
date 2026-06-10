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
  '实体/资产抽取',
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

const optimizationModelConfigs = [
  {
    id: 'text-config-ok',
    model_id: 'model-text-ok',
    provider_id: 'qwen',
    provider_name: '阿里百炼',
    model_name: 'qwen-plus',
    name: '文案优化模型',
    model_type: 'chat',
    model_capabilities: ['chat'],
    is_default: true,
    test_status: 'success',
    test_message: '验证通过',
    key_available: true,
  },
  {
    id: 'text-config-failed',
    model_id: 'model-text-failed',
    provider_id: 'volcano',
    provider_name: '火山引擎',
    model_name: 'doubao-pro',
    name: '未验证文本模型',
    model_type: 'chat',
    model_capabilities: ['chat'],
    is_default: false,
    test_status: 'failed',
    test_message: 'API Key 不可用，请重新验证',
    key_available: false,
  },
];

const variableGuides: Record<string, any> = {
  shot_video: {
    task: 'shot_video',
    task_label: '镜头视频',
    items: [
      {
        name: 'duration',
        label: '视频时长',
        description: '镜头视频生成时长。',
        example: '4秒',
        source: '系统上下文',
        system_fill: true,
        required: false,
      },
      {
        name: 'dialogue',
        label: '对白/台词',
        description: '当前镜头 dialogue 字段，会用于字幕和有声视频约束。',
        example: '沈砚：铜铃又响了。',
        source: '系统上下文',
        system_fill: true,
        required: false,
      },
      {
        name: 'subtitle_text',
        label: '字幕文本',
        description: '当前镜头字幕文本，视频生成和字幕导出会使用。',
        example: '沈砚：铜铃又响了。',
        source: '系统上下文',
        system_fill: true,
        required: false,
      },
      {
        name: 'tone',
        label: '色调',
        description: '镜头色彩或气氛倾向。',
        example: '冷蓝月光',
        source: '模板默认值',
        system_fill: false,
        required: false,
      },
      {
        name: 'bad_case',
        label: '负面示例',
        description: '需要避免的生成失败类型。',
        example: '脸型变化',
        source: '技能默认值',
        system_fill: false,
        required: false,
      },
    ],
    sample_context: {
      duration: '4秒',
      dialogue: '沈砚：铜铃又响了。',
      subtitle_text: '沈砚：铜铃又响了。',
      tone: '冷蓝月光',
      bad_case: '脸型变化',
    },
  },
  entity_extraction: {
    task: 'entity_extraction',
    task_label: '实体/资产抽取',
    items: [
      {
        name: 'source_content',
        label: '来源正文',
        description: '用于抽取实体和资产候选的小说、章节、剧本或分镜文本。',
        example: '沈砚在雨夜旧码头听见铜铃声。',
        source: '系统上下文',
        system_fill: true,
        required: false,
      },
      {
        name: 'entity_types',
        label: '实体类型',
        description: '本次允许抽取的实体类型中文列表。',
        example: 'character、scene、prop、event',
        source: '系统上下文',
        system_fill: true,
        required: false,
      },
    ],
    sample_context: {
      source_content: '沈砚在雨夜旧码头听见铜铃声。',
      entity_types: 'character、scene、prop、event',
    },
  },
  storyboard_generation: {
    task: 'storyboard_generation',
    task_label: '分镜创建',
    items: [
      {
        name: 'shot_count',
        label: '镜头数量',
        description: '分镜生成入口指定或模板推断的镜头数量。',
        example: 8,
        source: '系统上下文',
        system_fill: true,
        required: false,
      },
      {
        name: 'dialogue',
        label: '对白/台词',
        description: '分镜中的台词字段，建议使用“角色名：台词”格式。',
        example: '沈砚：铜铃又响了。',
        source: '系统上下文',
        system_fill: true,
        required: false,
      },
      {
        name: 'subtitle_text',
        label: '字幕文本',
        description: '镜头 extra_data.subtitle_text 或 dialogue 的字幕文本。',
        example: '沈砚：铜铃又响了。',
        source: '系统上下文',
        system_fill: true,
        required: false,
      },
    ],
    sample_context: {
      shot_count: 8,
      dialogue: '沈砚：铜铃又响了。',
      subtitle_text: '沈砚：铜铃又响了。',
    },
  },
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

test('prompt skill page manages clone edit preview and activation flow', async ({ page }) => {
  let created = false;
  let previewRequestedSkillIds: string[] = [];
  let previewDraftContent = '';
  let previewRequestContext: any = null;
  let optimizeRequested = false;
  let optimizeRequestBody: any = null;
  let activatedSkillId = '';
  let deletedSkillId = '';
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
    if (path === '/api/v1/llm/configs' && route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(optimizationModelConfigs),
      });
      return;
    }
    if (path === '/api/v1/prompt-skills/variables' && route.request().method() === 'GET') {
      const task = url.searchParams.get('task') || 'shot_video';
      const guide = variableGuides[task] || variableGuides.shot_video;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(guide),
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
    if (path === '/api/v1/prompt-skills/skill-clone-001' && route.request().method() === 'DELETE') {
      deletedSkillId = 'skill-clone-001';
      skills = skills.filter((skill) => skill.id !== deletedSkillId);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ deleted: true, id: deletedSkillId }),
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
      const payload = route.request().postDataJSON();
      previewRequestedSkillIds = payload.skill_ids || [];
      previewDraftContent = payload.draft_content || '';
      previewRequestContext = payload.context || {};
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
    if (path === '/api/v1/prompt-skills/optimize') {
      optimizeRequested = true;
      optimizeRequestBody = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          task: 'shot_video',
          source: 'local_rules',
          original_content: optimizeRequestBody.content,
          optimized_content: '优化目标：强化镜头一致性。\n执行规则：保持脸型、服装、道具和场景连续。\n禁止项：不要乱变、不要新增无关角色。',
          suggestions: ['补充镜头运动', '补充禁止项'],
          warnings: ['本次使用本地规则优化，可继续接入模型配置。'],
        }),
      });
      return;
    }
    throw new Error(`未模拟接口: ${route.request().method()} ${path}`);
  });

  await page.goto('/prompt-skills');

  await expect(page.getByRole('heading', { name: 'Prompt 技能' })).toBeVisible();
  await expect(page.getByText('当前任务：镜头视频')).toBeVisible();
  await expect(page.getByText('修改后先预览草稿，再保存并用测试验证模式跑完整流程。')).toBeVisible();
  await expect(page.getByText('统一变量说明')).toBeVisible();
  await expect(page.getByText('{dialogue}').first()).toBeVisible();
  await expect(page.getByText('字幕文本', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('系统可填').first()).toBeVisible();
  await expect(page.getByRole('link', { name: '工作台' })).toBeVisible();
  await expect(page.getByRole('button', { name: '打开内容创作菜单' })).toBeVisible();
  await expect(page.getByRole('button', { name: '打开资产设定菜单' })).toBeVisible();
  await expect(page.getByRole('button', { name: '打开生产菜单' })).toBeVisible();
  await expect(page.getByRole('button', { name: '打开配置菜单' })).toBeVisible();
  await page.getByLabel('选择冷蓝短剧一致性').check();
  await expect(page.getByRole('button', { name: '批量克隆' })).toBeVisible();
  await expect(page.getByRole('button', { name: '批量标签' })).toBeVisible();
  await expect(page.getByRole('button', { name: '批量删除' })).toBeVisible();

  const taskLabels = await page.getByTestId('prompt-skill-task-select').locator('option').allTextContents();
  for (const label of expectedTaskLabels) {
    expect(taskLabels).toContain(label);
  }

  await page.getByTestId('prompt-skill-task-select').selectOption('storyboard_generation');
  await expect(page.getByText('分镜创建变量')).toBeVisible();
  await expect(page.getByText('镜头数量', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('建议使用“角色名：台词”格式')).toBeVisible();
  await page.getByTestId('prompt-skill-task-select').selectOption('entity_extraction');
  await expect(page.getByText('实体/资产抽取变量')).toBeVisible();
  await expect(page.getByText('来源正文', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('实体类型', { exact: true }).first()).toBeVisible();
  await page.getByTestId('prompt-skill-task-select').selectOption('shot_video');
  await expect(page.getByText('冷蓝短剧一致性')).toBeVisible();

  await expect(page.getByText('冷蓝短剧一致性')).toBeVisible();
  await expect(page.getByText('选择任务后会显示可用技能。')).toBeVisible();
  await expect(page.getByText('优化模型', { exact: true })).toBeVisible();
  await expect(page.getByTestId('prompt-skill-optimize-model-select')).toHaveValue('text-config-ok');
  await expect(page.getByText('技能内容不能为空')).toBeVisible();
  await expect(page.getByTestId('prompt-skill-content-input')).toHaveValue('技能约束: 使用{tone}，避免{bad_case}。');
  await expect(page.getByTestId('prompt-skill-delete')).toBeDisabled();

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
  await expect(page.getByTestId('prompt-skill-delete')).toBeEnabled();

  page.once('dialog', async (dialog) => {
    expect(dialog.message()).toContain('删除');
    await dialog.accept();
  });
  await page.getByTestId('prompt-skill-delete').click();
  await expect(page.getByTestId('prompt-skill-card-skill-clone-001')).toHaveCount(0);
  expect(deletedSkillId).toBe('skill-clone-001');

  await page.getByTestId('prompt-skill-card-skill-001').click();
  await page.getByRole('button', { name: '克隆技能' }).click();
  await expect(page.getByTestId('prompt-skill-card-skill-clone-001')).toContainText('冷蓝短剧一致性 副本');

  await page.getByTestId('prompt-skill-name-input').fill('回滚镜头技能');
  await page.getByTestId('prompt-skill-content-input').fill('回滚技能: 使用{tone}，避免{bad_case}。');
  await page.getByTestId('prompt-skill-optimize-model-select').selectOption('text-config-failed');
  await expect(page.getByText('API Key 不可用，请重新验证')).toBeVisible();
  await expect(page.getByText('去配置模型')).toBeVisible();
  await expect(page.getByTestId('prompt-skill-optimize')).toBeDisabled();
  await page.getByTestId('prompt-skill-optimize-model-select').selectOption('text-config-ok');
  await expect(page.getByTestId('prompt-skill-optimize')).toBeEnabled();
  await page.getByTestId('prompt-skill-optimize').click();
  await expect(page.getByText('优化目标：强化镜头一致性。')).toBeVisible();
  await page.getByTestId('prompt-skill-apply-optimization').click();
  await expect(page.getByTestId('prompt-skill-content-input')).toHaveValue(/优化目标：强化镜头一致性/);
  expect(optimizeRequested).toBe(true);
  expect(optimizeRequestBody.model_config_id).toBe('text-config-ok');
  await page.getByTestId('prompt-skill-save').click();
  await expect(page.getByTestId('prompt-skill-card-skill-clone-001')).toContainText('回滚镜头技能');
  await expect(page.getByTestId('prompt-skill-card-skill-clone-001')).toContainText('v2');

  await page.getByTestId('prompt-skill-preview').click();
  await expect(page.getByText('技能约束: 使用冷蓝月光，避免脸型变化。')).toBeVisible();
  expect(previewRequestedSkillIds).toEqual([]);
  expect(previewDraftContent).toContain('优化目标：强化镜头一致性');
  expect(previewRequestContext.dialogue).toBe('沈砚：铜铃又响了。');
  expect(previewRequestContext.tone).toBe('冷蓝月光');

  await page.getByTestId('prompt-skill-activate').click();
  await expect(page.getByTestId('prompt-skill-card-skill-clone-001')).toContainText('当前激活');
  await expect(page.getByTestId('prompt-skill-card-skill-001')).toContainText('未激活');
  expect(activatedSkillId).toBe('skill-clone-001');
});

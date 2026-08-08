import { expect, test } from '@playwright/test';

const promptProfiles = {
  items: [{
    id: 'prompt-profile-1', key: 'anime.dialogue', name: '角色对白', task: 'shot_video',
    head_version_id: 'prompt-version-3', head_version: 3, status: 'draft',
  }],
  meta: { page: 1, page_size: 20, total: 1 },
};

const promptHead = {
  id: 'prompt-version-3', version: 3, status: 'draft', stage: 'consistency',
  content: '保持角色 {{name}} 的对白节奏。',
  system_contract: '保持角色、场景和事件连续。',
  task_template: '保持角色 {{name}} 的对白节奏。',
  input_mapping: { name: 'shot.character_name' }, output_schema: { type: 'string' },
  negative_constraints: ['不得新增角色'], model_family_overrides: {},
  validation_fixtures: [{ input: { name: '沈砚' } }], release_notes: '恢复的历史正文',
  checksum: 'a'.repeat(64), created_at: '2026-07-18T00:00:00', published_at: null,
};
const promptDetail = {
  id: 'prompt-profile-1', key: 'anime.dialogue', name: '角色对白', task: 'shot_video',
  head: promptHead, versions: [promptHead],
  legacy_skill: { id: 'skill-001', is_active: true, is_builtin: false },
};

const promptUsageMap = {
  summary: { total: 1, counts: { effective: 1 } },
  groups: [{ id: 'visual_production', name: '视觉生产', stages: [{
    id: 'shot_video', name: '镜头视频', uses_prompt: true, status: 'effective',
    message: '当前模型使用此环节的通用模板。',
    model: { profile_version_id: 'model-v1', provider_code: 'volcengine', provider_name: '火山方舟', api_model_id: 'video-model', name: '视频模型', capabilities: ['video_generation'] },
    template: { id: 'prompt-profile-1', profile_version_id: 'prompt-version-3', name: '角色对白', version: 3 },
    routing: { source_label: '环节通用模板' },
  }] }],
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
  await page.route('**/api/v1/llm/configs', (route) => route.fulfill({
    contentType: 'application/json', body: '[]',
  }));
  await page.route('**/api/v1/prompt-skills/variables**', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ task: 'shot_video', task_label: '镜头视频', items: [{ name: 'name' }], sample_context: {} }),
  }));
  await page.route('**/api/v1/model-center/**', async (route) => {
    const url = route.request().url();
    const body = url.endsWith('/prompt-usage-map') ? promptUsageMap
      : url.endsWith('/prompt-profiles/prompt-profile-1') ? promptDetail
      : url.includes('/prompt-profiles?') ? promptProfiles
      : url.includes('/impact') ? impact
        : { blocking_issues: [], connections: [], recipes: [] };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
  });
});

async function openPromptLibrary(page: import('@playwright/test').Page, url = '/llm-config?section=prompts') {
  await page.goto(url);
  await page.getByRole('button', { name: '模板库', exact: true }).click();
}

const impact = { affected_bindings: 2, affected_profiles: 2, affected_recipes: 1, affected_prompts: 1 };

test('loads saved prompt body and keeps the legacy entry actionable', async ({ page }) => {
  await openPromptLibrary(page, '/prompt-skills?returnTo=%2Fstudio');
  await expect(page).toHaveURL(/section=prompts/);
  await expect(page.getByLabel('任务模板')).toHaveValue('保持角色 {{name}} 的对白节奏。');
  await expect(page.getByRole('button', { name: 'AI 优化' })).toBeVisible();
  await expect(page.getByRole('button', { name: '预览 Prompt' })).toBeVisible();
  await expect(page.getByLabel('优化模型')).toBeVisible();
  await expect(page.getByRole('button', { name: '克隆技能' })).toBeVisible();
  await expect(page.getByRole('link', { name: '返回工作台' })).toHaveAttribute('href', '/studio');
});

test('explicit local optimization never selects a configured provider model', async ({ page }) => {
  let optimizeBody: Record<string, unknown> | null = null;
  await page.route('**/api/v1/model-center/prompt-profiles/prompt-profile-1/optimize', async (route) => {
    optimizeBody = route.request().postDataJSON();
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({
      task: 'shot_video', source: 'local_rules', original_content: promptHead.task_template,
      optimized_content: '本地规则优化结果', suggestions: [], warnings: [],
    }) });
  });
  await openPromptLibrary(page);
  await page.getByLabel('优化模型').selectOption('__local_rules__');
  await page.getByRole('button', { name: 'AI 优化' }).click();

  await expect(page.getByText('优化建议 · 本地规则')).toBeVisible();
  expect(optimizeBody).toEqual({
    version_id: 'prompt-version-3', mode: 'productionize', model_config_id: '__local_rules__',
  });
});

test('publishing a prompt profile displays affected model versions and recipes', async ({ page }) => {
  await openPromptLibrary(page);
  await page.getByRole('button', { name: '发布此版本' }).click();
  await expect(page.getByRole('dialog', { name: '发布影响确认' })).toContainText('2 个模型版本');
  await expect(page.getByRole('dialog', { name: '发布影响确认' })).toContainText('1 个生产方案');
  await expect(page.getByRole('dialog', { name: '发布影响确认' }).getByLabel('发布原因')).toBeVisible();
});

test('published prompt head is not offered as a publishable version', async ({ page }) => {
  const publishedHead = { ...promptHead, status: 'published', published_at: '2026-08-08T00:00:00' };
  await page.route('**/api/v1/model-center/**', async (route) => {
    const url = route.request().url();
    const body = url.endsWith('/prompt-usage-map') ? promptUsageMap
      : url.endsWith('/prompt-profiles/prompt-profile-1') ? { ...promptDetail, head: publishedHead, versions: [publishedHead] }
        : url.includes('/prompt-profiles?') ? { ...promptProfiles, items: [{ ...promptProfiles.items[0], status: 'published' }] }
          : url.includes('/impact') ? impact
            : { blocking_issues: [], connections: [], recipes: [] };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
  });

  await openPromptLibrary(page);

  await expect(page.getByRole('button', { name: '当前版本已发布' })).toBeDisabled();
  await expect(page.getByRole('button', { name: '发布此版本' })).toHaveCount(0);
});

test('publishing uses the current detail head instead of a stale list revision', async ({ page }) => {
  const requests: Array<{ url: string; body: unknown }> = [];
  const currentHead = { ...promptHead, id: 'prompt-version-4', version: 4 };
  await page.route('**/api/v1/model-center/**', async (route) => {
    const url = route.request().url();
    if (route.request().method() === 'POST') requests.push({ url, body: route.request().postDataJSON() });
    const body = url.endsWith('/prompt-usage-map') ? promptUsageMap
      : url.endsWith('/prompt-profiles/prompt-profile-1') ? { ...promptDetail, head: currentHead, versions: [currentHead, promptHead] }
        : url.includes('/prompt-profiles?') ? { ...promptProfiles, items: [{ ...promptProfiles.items[0], head_version_id: 'prompt-version-3', head_version: 3 }] }
          : url.includes('/impact') ? impact
            : url.includes('/publish') ? { published_version_id: currentHead.id, previous_version_id: null, impact, audit_event_id: 'audit-current' }
              : { blocking_issues: [], connections: [], recipes: [] };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
  });
  await openPromptLibrary(page);

  await page.getByRole('button', { name: '发布此版本' }).click();
  await page.getByRole('dialog', { name: '发布影响确认' }).getByLabel('发布原因').fill('确认发布最新草稿');
  await page.getByRole('dialog', { name: '发布影响确认' }).getByRole('button', { name: '确认发布' }).click();

  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0]?.url).toContain('/prompt-profile-versions/prompt-version-4/publish');
  expect(requests[0]?.body).toEqual({ expected_revision: 4, reason: '确认发布最新草稿' });
});

test('publish conflict refreshes state and shows a Chinese next action', async ({ page }) => {
  let listRequests = 0;
  await page.route('**/api/v1/model-center/**', async (route) => {
    const url = route.request().url();
    if (url.includes('/prompt-profiles?')) listRequests += 1;
    if (url.includes('/publish')) {
      await route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({ detail: { code: 'revision_conflict', message: 'Configuration has changed.' } }),
      });
      return;
    }
    const body = url.endsWith('/prompt-usage-map') ? promptUsageMap
      : url.endsWith('/prompt-profiles/prompt-profile-1') ? promptDetail
        : url.includes('/prompt-profiles?') ? promptProfiles
          : url.includes('/impact') ? impact
            : { blocking_issues: [], connections: [], recipes: [] };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
  });
  await openPromptLibrary(page);

  await page.getByRole('button', { name: '发布此版本' }).click();
  await page.getByRole('dialog', { name: '发布影响确认' }).getByLabel('发布原因').fill('发布最新草稿');
  await page.getByRole('dialog', { name: '发布影响确认' }).getByRole('button', { name: '确认发布' }).click();

  await expect(page.getByText('提示词版本已更新，已刷新最新状态，请确认后重新发布。')).toBeVisible();
  await expect(page.getByText(/revision_conflict/)).toHaveCount(0);
  await expect.poll(() => listRequests).toBeGreaterThanOrEqual(2);
});

test('rollback intent republishes a historical version instead of mutating it', async ({ page }) => {
  await openPromptLibrary(page);
  await page.getByRole('button', { name: '回滚为新版本' }).click();
  await expect(page.getByRole('dialog', { name: '回滚影响确认' })).toContainText('将创建新的头版本');
});

test('structured prompt drafts, publish impact, and rollback use the versioned API contracts', async ({ page }) => {
  const requests: Array<{ url: string; body: unknown }> = [];
  await page.route('**/api/v1/model-center/**', async (route) => {
    const url = route.request().url();
    if (route.request().method() === 'POST') requests.push({ url, body: route.request().postDataJSON() });
    const body = url.endsWith('/prompt-usage-map') ? promptUsageMap
      : url.endsWith('/prompt-profiles/prompt-profile-1') ? promptDetail
      : url.includes('/prompt-profiles?') ? promptProfiles
      : url.includes('/impact?') ? impact
        : url.endsWith('/versions') ? { id: 'prompt-profile-1', key: 'anime.dialogue', name: '角色对白', task: 'shot_video', head_version_id: 'prompt-version-4', head_version: 4, status: 'draft' }
          : url.includes('/publish') || url.includes('/rollback') ? { published_version_id: 'prompt-version-4', previous_version_id: 'prompt-version-3', impact, audit_event_id: 'audit-1' }
            : { id: 'prompt-profile-2', key: 'anime.motion', name: '镜头运动', task: 'shot_video', head_version_id: 'prompt-version-1', head_version: 1, status: 'draft' };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
  });
  await openPromptLibrary(page);
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

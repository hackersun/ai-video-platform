import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

const blockingIssue = {
  code: 'missing_asset_locks',
  message: '2 个镜头缺少角色/场景/道具资产锁，生产出片前必须锁定。',
  severity: 'blocking',
  repair_action: { code: 'apply_asset_locks', label: '应用资产锁', risk: 'safe' },
};

function studioSnapshot(mode: 'test' | 'production' = 'production') {
  return {
    workflow: {
      id: 'wf-gates',
      title: '门禁验证工作流',
      status: 'active',
      current_step: 6,
    },
    story_context: {
      novel: { id: 'novel-gates', title: '裂纹月光', genre: '都市异能' },
      chapter: { id: 'chapter-gates', title: '第一章', chapter_number: 1 },
      script: { id: 'script-gates', title: '第一集剧本', status: 'draft' },
      storyboard: { id: 'storyboard-gates', title: '第一集分镜', shot_count: 2 },
    },
    story_bible: {
      id: 'bible-gates',
      title: '门禁 Story Bible',
      character_rule_count: 1,
      scene_rule_count: 1,
      prop_rule_count: 0,
      event_count: 1,
    },
    production: { shot_count: 2, asset_lock_coverage: 0, entity_ref_coverage: 0.5, ready: false },
    shots: [
      { id: 'shot-gates-1', shot_number: 1, prompt: '吊坠裂开', entity_ref_count: 1, asset_lock_count: 0 },
      { id: 'shot-gates-2', shot_number: 2, prompt: '黑影出现', entity_ref_count: 1, asset_lock_count: 0 },
    ],
    assets: { total_count: 2, locked_count: 0, final_count: 0, by_category: { character: 1 } },
    jobs: { summary: { video_count: 0, tts_count: 0, synthesis_count: 0, media_count: 0 } },
    timeline: {},
    issues: [mode === 'test' ? { ...blockingIssue, severity: 'confirmable', original_severity: 'blocking' } : blockingIssue],
    actions: [{ code: 'apply_asset_locks', label: '应用资产锁', risk: 'safe' }],
    mode_policy: {
      mode,
      ready: mode === 'test',
      blocking_issue_count: mode === 'test' ? 0 : 1,
      confirmable_issue_count: mode === 'test' ? 1 : 0,
      warning_issue_count: 0,
    },
  };
}

function finalQualityMissingLocksSnapshot() {
  const base = studioSnapshot('production');
  return {
    ...base,
    workflow: {
      ...base.workflow,
      latest_production_strategy: 'final_quality',
      latest_production_strategy_label: '高质量终稿',
      latest_production_strategy_intent: 'final',
    },
    production_bible_summary: {
      story_bible_id: 'bible-gates',
      asset_readiness: { asset_count: 2, missing_asset_count: 2, ready: false },
      voices: [],
      counts: { characters: 1, scenes: 1, props: 0, events: 1 },
    },
    assets: { total_count: 2, locked_count: 0, final_count: 0, by_category: { character: 1 } },
  };
}

test.beforeEach(async ({ page }) => {
  const userId = `studio-gates-user-${Date.now()}`;
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

test('test mode requires a reason and records temporary skip audit', async ({ page }) => {
  let skipPayload: any = null;

  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/+/g, '/').replace(/\/$/, '');
    if (path === '/api/v1/workflow') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ workflow_id: 'wf-gates', title: '门禁验证工作流', status: 'active' }]),
      });
      return;
    }
    if (path === '/api/v1/studio/workflows/wf-gates/snapshot') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(studioSnapshot(url.searchParams.get('mode') === 'test' ? 'test' : 'production')),
      });
      return;
    }
    if (path === '/api/v1/studio/workflows/wf-gates/actions' && route.request().method() === 'POST') {
      skipPayload = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'skip-action-001',
          workflow_id: 'wf-gates',
          code: 'skip_issue',
          label: '测试模式跳过',
          status: 'skipped',
          risk: 'confirm',
          source_issue_code: 'missing_asset_locks',
          result: { bypass_audit: { reason: skipPayload.bypass_reason, count: 1 } },
        }),
      });
      return;
    }
    if (path === '/api/v1/prompt-skills') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], count: 0 }),
      });
      return;
    }
    throw new Error(`未模拟接口: ${route.request().method()} ${path}`);
  });

  await page.goto('/studio?workflow_id=wf-gates');
  await page.getByRole('button', { name: '测试验证' }).click();

  await expect(page.getByText('测试验证模式允许临时跳过部分限制，产物不能视为最终出片。')).toBeVisible();
  await expect(page.getByText('此操作只用于测试验证，生产出片仍需修复该问题。')).toBeVisible();
  await page.getByRole('button', { name: '确认临时跳过并继续验证' }).click();
  await expect(page.getByText('测试模式跳过需要至少 8 个字符')).toBeVisible();

  await page.getByPlaceholder('说明为什么临时跳过，以及后续如何补齐。至少 8 个字符。').fill('本地验证完整链路后补齐资产锁');
  await page.getByRole('button', { name: '确认临时跳过并继续验证' }).click();

  await expect(page.getByText('最近动作：')).toBeVisible();
  expect(skipPayload).toMatchObject({
    code: 'skip_issue',
    mode: 'test',
    allow_test_bypass: true,
    bypass_reason: '本地验证完整链路后补齐资产锁',
    source_issue_code: 'missing_asset_locks',
  });
});

test('production mode blocks temporary skip and keeps repair action visible', async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/+/g, '/').replace(/\/$/, '');
    if (path === '/api/v1/workflow') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ workflow_id: 'wf-gates', title: '门禁验证工作流', status: 'active' }]),
      });
      return;
    }
    if (path === '/api/v1/studio/workflows/wf-gates/snapshot') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(studioSnapshot('production')),
      });
      return;
    }
    if (path === '/api/v1/prompt-skills') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], count: 0 }),
      });
      return;
    }
    throw new Error(`未模拟接口: ${route.request().method()} ${path}`);
  });

  await page.goto('/studio?workflow_id=wf-gates');

  await expect(page.getByText('生产出片模式会强制执行资产锁、模型验证、公开素材地址和一致性要求。')).toBeVisible();
  await expect(page.getByRole('button', { name: '应用资产锁' })).toBeVisible();
  await expect(page.getByRole('button', { name: '确认临时跳过并继续验证' })).toHaveCount(0);
});

test('final quality snapshot shows blocking asset and voice lock requirements', async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/+/g, '/').replace(/\/$/, '');
    if (path === '/api/v1/workflow') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ workflow_id: 'wf-gates', title: '门禁验证工作流', status: 'active' }]),
      });
      return;
    }
    if (path === '/api/v1/studio/workflows/wf-gates/snapshot') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(finalQualityMissingLocksSnapshot()),
      });
      return;
    }
    if (path === '/api/v1/prompt-skills') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], count: 0 }),
      });
      return;
    }
    throw new Error(`未模拟接口: ${route.request().method()} ${path}`);
  });

  await page.goto('/studio?workflow_id=wf-gates');

  await expect(page.getByText('终稿门禁：缺少定稿参考图、资产锁覆盖或角色声线时会阻断终稿生产。')).toBeVisible();
  await expect(page.getByText('缺失 · 定稿参考图')).toBeVisible();
  await expect(page.getByText('缺失 · 资产锁覆盖')).toBeVisible();
  await expect(page.getByText('缺失 · 角色声线')).toBeVisible();
  await expect(page.getByText('缺角色声线，回 Story Bible/角色设定绑定。')).toBeVisible();
  await expect(page.getByRole('link', { name: '补齐资产/声线' })).toHaveAttribute('href', '/assets');
  await expect(page.getByText(/缺锁会阻断终稿/)).toBeVisible();
});

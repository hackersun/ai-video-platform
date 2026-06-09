import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

const baseIssue = {
  code: 'missing_asset_locks',
  message: '2 个镜头缺少角色/场景/道具资产锁，生产出片前必须锁定。',
  severity: 'blocking',
  repair_action: { code: 'apply_asset_locks', label: '应用资产锁', risk: 'safe' },
};

const modelIssue = {
  code: 'model_unverified',
  message: '当前视频模型尚未验证，生产出片前需要完成模型配置检查。',
  severity: 'blocking',
  repair_action: { code: 'open_model_config', label: '配置模型', risk: 'navigation', href: '/llm-config' },
};

const activeSkill = {
  id: 'skill-active-001',
  name: '冷蓝短剧一致性',
  description: '约束竖屏短剧的色彩和漂移风险',
  task: 'shot_video',
  stage: 'consistency',
  content: '技能约束: 使用冷蓝月光，避免脸型变化。',
  version: 3,
  is_active: true,
  tags: ['短剧', '一致性'],
};

function snapshot({
  mode = 'production',
  locksApplied = false,
}: {
  mode?: 'test' | 'production';
  locksApplied?: boolean;
} = {}) {
  const remainingIssue = mode === 'test'
    ? { ...modelIssue, severity: 'confirmable', original_severity: 'blocking' }
    : modelIssue;
  const issues = locksApplied ? [remainingIssue] : [baseIssue, remainingIssue];
  return {
    workflow: {
      id: 'wf-full',
      title: '裂纹月光 第一集',
      status: 'active',
      current_step: 6,
      novel_id: 'novel-full',
      chapter_id: 'chapter-full',
      script_id: 'script-full',
      storyboard_id: 'storyboard-full',
    },
    story_context: {
      novel: { id: 'novel-full', title: '裂纹月光', genre: '都市异能' },
      chapter: { id: 'chapter-full', title: '第一章 裂纹月光', chapter_number: 1 },
      script: { id: 'script-full', title: '第一集剧本', status: 'draft' },
      storyboard: { id: 'storyboard-full', title: '裂纹月光分镜', shot_count: 2 },
    },
    story_bible: {
      id: 'bible-full',
      title: '短剧 Story Bible',
      character_rule_count: 1,
      scene_rule_count: 1,
      prop_rule_count: 1,
      event_count: 1,
    },
    production: {
      shot_count: 2,
      asset_lock_coverage: locksApplied ? 1 : 0,
      entity_ref_coverage: 0.5,
      ready: false,
    },
    shots: [
      { id: 'shot-full-1', shot_number: 1, prompt: '吊坠突然裂开', entity_ref_count: 1, asset_lock_count: locksApplied ? 2 : 0 },
      { id: 'shot-full-2', shot_number: 2, prompt: '黑影穿过冷蓝月光', entity_ref_count: 1, asset_lock_count: locksApplied ? 2 : 0 },
    ],
    assets: { total_count: 4, locked_count: locksApplied ? 4 : 0, final_count: 0, by_category: { character: 1 } },
    jobs: { summary: { video_count: 0, tts_count: 0, synthesis_count: 0, media_count: 0 } },
    timeline: { id: 'timeline-full', name: '第一集时间线', clip_count: 0 },
    issues,
    actions: [{ code: 'apply_asset_locks', label: '应用资产锁', risk: 'safe' }],
    mode_policy: {
      mode,
      ready: false,
      blocking_issue_count: mode === 'test' ? 0 : issues.length,
      confirmable_issue_count: mode === 'test' ? 1 : 0,
      warning_issue_count: 0,
    },
  };
}

test.beforeEach(async ({ page }) => {
  const userId = `studio-full-user-${Date.now()}`;
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

test('studio supports repair, test bypass audit, production gate, and active prompt skill summary', async ({ page }) => {
  let locksApplied = false;
  let skipPayload: any = null;

  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/+/g, '/').replace(/\/$/, '');
    if (path === '/api/v1/workflow') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ workflow_id: 'wf-full', title: '裂纹月光 第一集', status: 'active' }]),
      });
      return;
    }
    if (path === '/api/v1/studio/workflows/wf-full/snapshot') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(snapshot({
          mode: url.searchParams.get('mode') === 'test' ? 'test' : 'production',
          locksApplied,
        })),
      });
      return;
    }
    if (path === '/api/v1/studio/workflows/wf-full/actions' && route.request().method() === 'POST') {
      const payload = route.request().postDataJSON();
      if (payload.code === 'apply_asset_locks') {
        locksApplied = true;
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 'lock-action-001',
            workflow_id: 'wf-full',
            code: 'apply_asset_locks',
            label: '应用资产锁',
            status: 'succeeded',
            risk: 'safe',
            result: { applied_shot_count: 2 },
          }),
        });
        return;
      }
      if (payload.code === 'skip_issue') {
        skipPayload = payload;
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 'skip-action-full',
            workflow_id: 'wf-full',
            code: 'skip_issue',
            label: '测试模式跳过',
            status: 'skipped',
            risk: 'confirm',
            source_issue_code: payload.source_issue_code,
            result: { bypass_audit: { reason: payload.bypass_reason, count: 1 } },
          }),
        });
        return;
      }
    }
    if (path === '/api/v1/prompt-skills') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [activeSkill], count: 1 }),
      });
      return;
    }
    throw new Error(`未模拟接口: ${route.request().method()} ${path}`);
  });

  await page.goto('/studio?workflow_id=wf-full');

  await expect(page.getByText('统一创作工作台')).toBeVisible();
  await expect(page.getByText('短剧 Story Bible')).toBeVisible();
  await expect(page.getByText('当前激活 Prompt 技能')).toBeVisible();
  await expect(page.getByText('冷蓝短剧一致性')).toBeVisible();
  await expect(page.getByText('v3')).toBeVisible();

  await page.getByRole('button', { name: '应用资产锁' }).click();
  await expect(page.getByText('100%')).toBeVisible();
  await expect(page.getByText('当前视频模型尚未验证，生产出片前需要完成模型配置检查。').first()).toBeVisible();

  await page.getByRole('button', { name: '测试验证' }).click();
  await page.getByPlaceholder('说明为什么临时跳过，以及后续如何补齐。至少 8 个字符。').fill('先验证全链路，稍后完成模型配置');
  await page.getByRole('button', { name: '确认临时跳过并继续验证' }).click();
  await expect(page.getByText('最近动作：')).toBeVisible();
  expect(skipPayload).toMatchObject({
    code: 'skip_issue',
    mode: 'test',
    allow_test_bypass: true,
    bypass_reason: '先验证全链路，稍后完成模型配置',
    source_issue_code: 'model_unverified',
  });

  await page.getByRole('button', { name: '生产出片' }).click();
  await expect(page.getByRole('button', { name: '确认临时跳过并继续验证' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: /配置模型/ })).toHaveAttribute('href', '/llm-config');
  await expect(page.getByRole('link', { name: /管理 Prompt 技能/ })).toHaveAttribute('href', '/prompt-skills');
});

import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

const snapshot = {
  workflow: {
    id: 'wf-001',
    title: '裂纹月光 第一集',
    status: 'active',
    current_step: 6,
    novel_id: 'novel-001',
    chapter_id: 'chapter-001',
    script_id: 'script-001',
    storyboard_id: 'storyboard-001',
  },
  story_context: {
    novel: { id: 'novel-001', title: '裂纹月光', genre: '都市异能' },
    chapter: { id: 'chapter-001', title: '第一章 裂纹月光', chapter_number: 1 },
    script: { id: 'script-001', title: '第一集剧本', status: 'draft' },
    storyboard: { id: 'storyboard-001', title: '裂纹月光分镜', shot_count: 3 },
  },
  story_bible: {
    id: 'bible-001',
    title: '短剧 Story Bible',
    character_rule_count: 1,
    scene_rule_count: 1,
    prop_rule_count: 1,
    event_count: 1,
  },
  production: { shot_count: 3, asset_lock_coverage: 0, entity_ref_coverage: 0.67, ready: false },
  shots: [
    { id: 'shot-001', shot_number: 1, prompt: '吊坠突然裂开', entity_ref_count: 2, asset_lock_count: 0 },
    { id: 'shot-002', shot_number: 2, prompt: '黑影穿过冷蓝月光', entity_ref_count: 2, asset_lock_count: 0 },
  ],
  assets: { total_count: 4, locked_count: 0, final_count: 0, by_category: { character: 1 } },
  jobs: { summary: { video_count: 0, tts_count: 0, synthesis_count: 0, media_count: 0 } },
  timeline: {},
  issues: [
    {
      code: 'missing_asset_locks',
      message: '2 个镜头缺少角色/场景/道具资产锁，生产出片前必须锁定。',
      severity: 'blocking',
      repair_action: { code: 'apply_asset_locks', label: '应用资产锁', risk: 'safe' },
    },
  ],
  actions: [{ code: 'apply_asset_locks', label: '应用资产锁', risk: 'safe' }],
  mode_policy: { mode: 'production', ready: false, blocking_issue_count: 1, warning_issue_count: 0 },
};

test.beforeEach(async ({ page }) => {
  const userId = `studio-user-${Date.now()}`;
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

test('studio workspace renders snapshot and repair path', async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/+/g, '/').replace(/\/$/, '');
    if (path === '/api/v1/workflow') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ workflow_id: 'wf-001', title: '裂纹月光 第一集', status: 'active' }]),
      });
      return;
    }
    if (path === '/api/v1/studio/workflows/wf-001/snapshot') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(snapshot) });
      return;
    }
    if (path === '/api/v1/production-control/workflow/wf-001/asset-locks') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ applied_shots: [] }) });
      return;
    }
    throw new Error(`未模拟接口: ${route.request().method()} ${path}`);
  });

  await page.goto('/studio?workflow_id=wf-001');

  await expect(page.getByText('统一创作工作台')).toBeVisible();
  await expect(page.getByText('生产出片模式会强制执行资产锁、模型验证、公开素材地址和一致性要求。')).toBeVisible();
  await expect(page.getByText('短剧 Story Bible')).toBeVisible();
  await expect(page.getByText('角色/场景/道具锁覆盖')).toBeVisible();
  await expect(page.getByText('0%')).toBeVisible();
  await expect(page.getByText('2 个镜头缺少角色/场景/道具资产锁，生产出片前必须锁定。').first()).toBeVisible();
  await expect(page.getByRole('button', { name: '应用资产锁' })).toBeVisible();
});

import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

function reviewTasks() {
  return [
    {
      shot_id: 'shot-003',
      shot_number: 3,
      storyboard_id: 'storyboard-001',
      storyboard_title: '第三集分镜',
      novel_id: 'novel-001',
      novel_title: '裂纹月光',
      entity_id: 'entity-hero',
      entity_name: '沈砚',
      entity_type: 'character',
      workflow_id: 'wf-001',
      workflow_title: '裂纹月光 第三集',
      episode_index: 3,
      review_state: 'changes_requested',
      review_reason: '沈砚 从第 3 集起应用新设定：服装主色改为深蓝',
      change_note: '服装主色改为深蓝',
      shot_summary: '沈砚在废弃灯塔发现吊坠信号。',
      review_at: '2026-07-04T08:00:00',
      shot_review_url: '/studio/shot-review?workflow_id=wf-001&shot_id=shot-003',
      shot_url: '/shots?shot_id=shot-003',
      storyboard_url: '/storyboards?storyboard_id=storyboard-001',
    },
    {
      shot_id: 'shot-004',
      shot_number: 4,
      storyboard_id: 'storyboard-002',
      storyboard_title: '第四集分镜',
      novel_id: 'novel-001',
      novel_title: '裂纹月光',
      entity_id: 'entity-prop',
      entity_name: '青铜吊坠',
      entity_type: 'prop',
      workflow_id: 'wf-001',
      workflow_title: '裂纹月光 第四集',
      episode_index: 4,
      review_state: 'changes_requested',
      review_reason: '青铜吊坠 从第 4 集起应用新设定：裂纹改为星形',
      change_note: '裂纹改为星形',
      shot_summary: '吊坠在月光下出现星形裂纹。',
      review_at: '2026-07-04T08:10:00',
      shot_review_url: '/studio/shot-review?workflow_id=wf-001&shot_id=shot-004',
      shot_url: '/shots?shot_id=shot-004',
      storyboard_url: '/storyboards?storyboard_id=storyboard-002',
    },
  ];
}

test.beforeEach(async ({ page }) => {
  const userId = 'continuity-review-ui-user';
  let tasks = reviewTasks();
  const regenerateRequests: any[] = [];
  const qualityRequests: any[] = [];
  await page.addInitScript(({ authToken, authUserId }) => {
    localStorage.setItem('auth_token', authToken);
    localStorage.setItem('user', JSON.stringify({
      id: authUserId,
      username: authUserId,
      email: `${authUserId}@example.test`,
    }));
  }, { authToken: devToken(userId), authUserId: userId });

  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const request = route.request();
    if (url.pathname.endsWith('/story-bibles/continuity-review-tasks')) {
      const entityId = url.searchParams.get('entity_id');
      const episodeIndex = url.searchParams.get('episode_index');
      const filtered = tasks.filter((task) => (
        (!entityId || task.entity_id === entityId)
        && (!episodeIndex || String(task.episode_index) === episodeIndex)
      ));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total: filtered.length,
          tasks: filtered,
          filters: {
            entity_id: entityId,
            episode_index: episodeIndex ? Number(episodeIndex) : null,
            status: url.searchParams.get('status') || 'open',
            review_state: url.searchParams.get('review_state'),
          },
          sort: url.searchParams.get('sort') || 'updated_desc',
        }),
      });
      return;
    }
    if (
      url.pathname.endsWith('/story-bibles/continuity-review-tasks/shot-003/resolve')
      && request.method() === 'POST'
    ) {
      tasks = tasks.filter((task) => task.shot_id !== 'shot-003');
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'resolved',
          shot_id: 'shot-003',
          review_state: 'approved',
          resolved_at: '2026-07-04T09:00:00',
          resolution_note: '连续性复审已完成',
        }),
      });
      return;
    }
    if (
      url.pathname.endsWith('/story-bibles/continuity-review-tasks/resolve-batch')
      && request.method() === 'POST'
    ) {
      const payload = request.postDataJSON();
      const selectedIds = payload.shot_ids || [];
      tasks = tasks.filter((task) => !selectedIds.includes(task.shot_id));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'resolved',
          resolved_count: selectedIds.length,
          shot_ids: selectedIds,
          tasks: selectedIds.map((shot_id: string) => ({
            status: 'resolved',
            shot_id,
            review_state: 'approved',
            resolved_at: '2026-07-04T09:20:00',
          })),
        }),
      });
      return;
    }
    if (url.pathname.endsWith('/workflow/wf-001/regenerate-shots') && request.method() === 'POST') {
      regenerateRequests.push(request.postDataJSON());
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ workflow_id: 'wf-001', regenerated_shot_ids: ['shot-003'], ready_for_concatenate: false }),
      });
      return;
    }
    if (url.pathname.endsWith('/shots/quality/batch') && request.method() === 'POST') {
      qualityRequests.push(request.postDataJSON());
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [{ shot_id: 'shot-003', quality_report: { status: 'ready' } }] }),
      });
      return;
    }
    if (url.pathname.endsWith('/workflow/wf-001/render/preflight')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ready: true, issues: [], workflow_id: 'wf-001' }),
      });
      return;
    }
    if (url.pathname.endsWith('/workflow/wf-001/shot-review')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow_id: 'wf-001',
          shots: [
            { shot_id: 'shot-003', shot_number: 3, status: 'completed', duration: 4, character_names: ['沈砚'] },
            { shot_id: 'shot-004', shot_number: 4, status: 'completed', duration: 4, character_names: ['青铜吊坠'] },
          ],
        }),
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });
});

test('studio continuity review inbox shows cross-episode review tasks', async ({ page }) => {
  await page.goto('/studio/continuity-review');

  await expect(page.getByRole('heading', { name: '连续性复审' })).toBeVisible();
  await expect(page.getByText('2 个待复审镜头')).toBeVisible();
  await expect(page.getByRole('heading', { name: '沈砚' })).toBeVisible();
  await expect(page.getByText('第 3 集', { exact: true })).toBeVisible();
  await expect(page.getByText('服装主色改为深蓝', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: '青铜吊坠' })).toBeVisible();
  await expect(page.getByRole('link', { name: '打开镜头审阅' }).first()).toHaveAttribute('href', '/studio/shot-review?workflow_id=wf-001&shot_id=shot-003');
});

test('studio continuity review inbox applies filters and sorting', async ({ page }) => {
  await page.goto('/studio/continuity-review');

  await page.getByLabel('实体筛选').selectOption('entity-prop');
  await page.getByLabel('集数筛选').fill('4');
  await page.getByLabel('状态筛选').selectOption('open');
  await page.getByLabel('排序方式').selectOption('episode_desc');
  const filteredRequest = page.waitForRequest((request) => {
    const url = new URL(request.url());
    return url.pathname.endsWith('/api/v1/story-bibles/continuity-review-tasks')
      && url.searchParams.get('entity_id') === 'entity-prop'
      && url.searchParams.get('episode_index') === '4'
      && url.searchParams.get('status') === 'open'
      && url.searchParams.get('sort') === 'episode_desc';
  });
  await page.getByRole('button', { name: '应用筛选' }).click();
  await filteredRequest;

  await expect(page.getByRole('heading', { name: '沈砚' })).toBeHidden();
  await expect(page.getByRole('heading', { name: '青铜吊坠' })).toBeVisible();
  await expect(page.getByText('1 个待复审镜头')).toBeVisible();
  await expect(page.getByLabel('实体筛选').locator('option', { hasText: '沈砚' })).toHaveCount(1);
});

test('studio continuity review inbox can resolve a reviewed task', async ({ page }) => {
  await page.goto('/studio/continuity-review');

  const resolveRequest = page.waitForRequest((request) => (
    request.method() === 'POST'
    && request.url().endsWith('/api/v1/story-bibles/continuity-review-tasks/shot-003/resolve')
  ));
  await page.getByRole('button', { name: '标记已复审' }).first().click();
  await resolveRequest;

  await expect(page.getByRole('heading', { name: '沈砚' })).toBeHidden();
  await expect(page.getByText('1 个待复审镜头')).toBeVisible();
  await expect(page.getByRole('heading', { name: '青铜吊坠' })).toBeVisible();
});

test('studio continuity review inbox supports batch resolve', async ({ page }) => {
  await page.goto('/studio/continuity-review');

  await page.getByLabel('选择镜头 3').check();
  await page.getByLabel('选择镜头 4').check();
  const batchRequest = page.waitForRequest((request) => (
    request.method() === 'POST'
    && request.url().endsWith('/api/v1/story-bibles/continuity-review-tasks/resolve-batch')
  ));
  await page.getByRole('button', { name: '批量标记已复审' }).click();
  const request = await batchRequest;
  expect(request.postDataJSON()).toMatchObject({ shot_ids: ['shot-003', 'shot-004'] });

  await expect(page.getByText('暂无待复审镜头')).toBeVisible();
});

test('studio continuity review inbox connects post-review production actions', async ({ page }) => {
  await page.goto('/studio/continuity-review');

  await page.getByLabel('选择镜头 3').check();
  const regenerateRequest = page.waitForRequest((request) => (
    request.method() === 'POST'
    && request.url().endsWith('/api/v1/workflow/wf-001/regenerate-shots')
  ));
  await page.getByRole('button', { name: '重生选中镜头' }).click();
  expect((await regenerateRequest).postDataJSON()).toMatchObject({ shot_ids: ['shot-003'] });
  await expect(page.getByText('已提交重生任务')).toBeVisible();

  const qualityRequest = page.waitForRequest((request) => (
    request.method() === 'POST'
    && request.url().endsWith('/api/v1/shots/quality/batch')
  ));
  await page.getByRole('button', { name: '刷新质量检查' }).click();
  expect((await qualityRequest).postDataJSON()).toMatchObject({ shot_ids: ['shot-003'] });
  await expect(page.getByText('质量检查已刷新')).toBeVisible();

  const preflightRequest = page.waitForRequest((request) => (
    request.method() === 'GET'
    && request.url().includes('/api/v1/workflow/wf-001/render/preflight')
  ));
  await page.getByRole('button', { name: '成片预检' }).click();
  await preflightRequest;
  await expect(page.getByText('成片预检通过')).toBeVisible();
});

test('studio shot review deep link selects the target shot from a review task', async ({ page }) => {
  await page.goto('/studio/shot-review?workflow_id=wf-001&shot_id=shot-003');

  await expect(page.getByRole('heading', { name: '镜头审阅' })).toBeVisible();
  await expect(page.getByLabel('选择镜头 3')).toBeChecked();
  await expect(page.getByTestId('shot-review-card-shot-003')).toHaveAttribute('data-target-shot', 'true');
});

test('studio continuity review inbox blocks preflight for mixed workflows', async ({ page }) => {
  await page.unroute('**/api/v1/**');
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    if (!url.pathname.endsWith('/story-bibles/continuity-review-tasks')) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
      return;
    }
    const mixedTasks = reviewTasks().map((task, index) => ({
      ...task,
      workflow_id: index === 0 ? 'wf-001' : 'wf-002',
      workflow_title: index === 0 ? '裂纹月光 第三集' : '裂纹月光 第四集',
    }));
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ total: mixedTasks.length, tasks: mixedTasks, filters: { status: 'open' }, sort: 'updated_desc' }),
    });
  });

  await page.goto('/studio/continuity-review');
  await page.getByLabel('选择镜头 3').check();
  await page.getByLabel('选择镜头 4').check();
  await page.getByRole('button', { name: '成片预检' }).click();

  await expect(page.getByText('请选择同一工作流的镜头执行成片预检')).toBeVisible();
});

test('studio continuity review inbox does not offer resolve action for resolved tasks', async ({ page }) => {
  await page.unroute('**/api/v1/**');
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    if (!url.pathname.endsWith('/story-bibles/continuity-review-tasks')) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
      return;
    }
    const resolvedTasks = reviewTasks().slice(0, 1).map((task) => ({
      ...task,
      status: 'resolved',
      review_state: 'approved',
    }));
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ total: resolvedTasks.length, tasks: resolvedTasks, filters: { status: 'resolved' }, sort: 'updated_desc' }),
    });
  });

  await page.goto('/studio/continuity-review');

  await expect(page.getByText('已复审完成')).toBeVisible();
  await expect(page.getByRole('button', { name: /^标记已复审$/ })).toHaveCount(0);
});

test('studio continuity review inbox keeps resolved tasks visible in all status mode', async ({ page }) => {
  await page.goto('/studio/continuity-review');

  await page.getByLabel('状态筛选').selectOption('all');
  await page.getByRole('button', { name: '应用筛选' }).click();
  const resolveRequest = page.waitForRequest((request) => (
    request.method() === 'POST'
    && request.url().endsWith('/api/v1/story-bibles/continuity-review-tasks/shot-003/resolve')
  ));
  await page.getByRole('button', { name: /^标记已复审$/ }).first().click();
  await resolveRequest;

  await expect(page.getByRole('heading', { name: '沈砚' })).toBeVisible();
  await expect(page.getByText('已复审完成')).toBeVisible();
  await expect(page.getByText('2 个复审镜头')).toBeVisible();
});

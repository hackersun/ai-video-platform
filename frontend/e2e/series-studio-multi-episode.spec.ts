import { expect, test } from '@playwright/test';
import {
  fourChapterApiContract,
  fourChapterNovel,
  syntheticVideoCatalog,
} from './helpers/four-chapter-fixture';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

function studioSnapshot({ locked = false, resumed = false } = {}) {
  const workflowId = fourChapterApiContract.workflows[0].workflow_id;
  const chapter = fourChapterNovel.chapters[1];
  const failedResume = !resumed;
  const stageIds = ['facts', 'assets', 'episode_contract', 'draft', 'review', 'final', 'render', 'publish'];
  return {
    series_studio: { enabled: true, primary_console: 'series_studio', expert_drilldowns: [] },
    workflow: {
      id: workflowId,
      title: '雾港铜铃 第二集',
      status: 'active',
      novel_id: fourChapterNovel.id,
      chapter_id: chapter.id,
      latest_production_strategy_label: '快速草稿',
    },
    story_context: {
      novel: { id: fourChapterNovel.id, title: fourChapterNovel.title, genre: '悬疑' },
      chapter: {
        id: chapter.id,
        title: chapter.title,
        chapter_number: chapter.chapterNumber,
      },
    },
    production_bible_summary: {
      readiness_score: 88,
      style: { visual_style: '冷色悬疑动漫' },
      characters: [],
      scenes: [],
      props: [],
      events: [],
      voices: [],
      missing_requirements: [],
      asset_readiness: { asset_count: 0, missing_asset_count: 0, ready: true },
      counts: { characters: 0, scenes: 0, props: 0, events: 0 },
    },
    series_plan: fourChapterApiContract.seriesPlan,
    whole_book_gaps: fourChapterApiContract.wholeBookGaps,
    episode_contract: locked ? {
      contract_id: 'contract-locked',
      workflow_id: workflowId,
      novel_id: fourChapterNovel.id,
      chapter_id: chapter.id,
      locked_at: '2026-07-04T00:00:00+00:00',
      production_bible_hash: 'abcdef1234567890abcdef1234567890',
      entity_locks: [{ entity_id: 'char-1', name: '沈砚' }],
      required_checks: ['style', 'characters', 'reference_package'],
    } : null,
    production_graph: {
      version: 2,
      hash: 'graph-hash-2',
      story_order: [],
      production_revisions: [],
    },
    consistency_ledger: { overall_score: 76, findings: [{ code: 'episode-2-check', severity: 'warning' }] },
    guidance: {
      current_stage: failedResume ? 'draft' : locked ? 'draft' : 'episode_contract',
      stages: stageIds.map((id, index) => ({ id, label: id, status: index < (locked ? 3 : 2) ? 'ready' : index === (locked ? 3 : 2) ? 'working' : 'blocked' })),
      blockers: failedResume ? [{ code: 'draft_provider_timeout', message: '草片任务超时', severity: 'blocking' }] : [],
      confirmable_warnings: [{ code: 'state_drift_warning', message: '铜铃状态需要人工确认', severity: 'confirmable' }],
      completed_evidence: [
        { stage: 'facts', hash: 'graph-hash-2' },
        { stage: 'assets', evidence_ids: ['asset-2'] },
        ...(locked ? [{ stage: 'episode_contract', evidence_id: 'contract-locked', hash: 'abcdef1234567890abcdef1234567890' }] : []),
      ],
      recommended_action: failedResume
        ? { code: 'retry_orchestration', label: '安全重试失败阶段', risk: 'safe', params: { task_id: 'task-episode-2' } }
        : { code: locked ? 'open_producer' : 'lock_episode_contract', label: locked ? '生成本集草片' : '锁定剧集合约', risk: locked ? 'navigation' : 'safe', href: locked ? '/producer' : undefined },
      next_action: failedResume
        ? { code: 'retry_orchestration', label: '安全重试失败阶段', risk: 'safe', params: { task_id: 'task-episode-2' } }
        : { code: locked ? 'open_producer' : 'lock_episode_contract', label: locked ? '生成本集草片' : '锁定剧集合约', risk: locked ? 'navigation' : 'safe', href: locked ? '/producer' : undefined },
      orchestration_resume: failedResume ? {
        task_id: 'task-episode-2', status: 'failed', failed_stage: 'draft', completed_stages: ['facts', 'assets', 'episode_contract'], safe_retry: true,
      } : {},
    },
    production: { shot_count: 4, asset_lock_coverage: 1, entity_ref_coverage: 1, ready: true },
    shots: [],
    assets: { total_count: 2, locked_count: 2, final_count: 2, by_category: {} },
    jobs: { summary: { video_count: 2, tts_count: 1, synthesis_count: 0, media_count: 0 } },
    issues: [],
    actions: [],
    mode_policy: { mode: 'production', ready: true, blocking_issue_count: 0 },
  };
}

test.beforeEach(async ({ page }) => {
  const userId = `series-studio-episodes-${Date.now()}`;
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

test('multi episode plan and contract are visible', async ({ page }) => {
  let locked = false;
  let resumed = false;
  let resumeRequests = 0;
  let consumedSnapshot: ReturnType<typeof studioSnapshot> | null = null;
  const consumedWorkflows: Array<{ workflow_id: string }> = [];
  let consumedVideoCatalog = false;

  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/+/g, '/').replace(/\/$/, '');
    if (path === '/api/v1/workflow') {
      consumedWorkflows.push(...fourChapterApiContract.workflows);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(fourChapterApiContract.workflows),
      });
      return;
    }
    if (path === `/api/v1/novels/${fourChapterNovel.id}`) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: fourChapterNovel.id,
          title: fourChapterNovel.title,
          cover_url: null,
          chapter_count: fourChapterNovel.chapters.length,
          total_chapters: fourChapterNovel.chapters.length,
          updated_at: '2026-07-15T00:00:00+00:00',
        }),
      });
      return;
    }
    if (path === `/api/v1/chapters/novel/${fourChapterNovel.id}`) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(fourChapterNovel.chapters.map((chapter) => ({
          id: chapter.id,
          title: chapter.title,
          chapter_number: chapter.chapterNumber,
        }))),
      });
      return;
    }
    if (path === '/api/v1/studio/workflows/wf-four-chapter-current/snapshot') {
      consumedSnapshot = studioSnapshot({ locked, resumed });
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(consumedSnapshot),
      });
      return;
    }
    if (path === '/api/v1/studio/workflows/wf-four-chapter-current/orchestration/task-episode-2/resume' && route.request().method() === 'POST') {
      resumeRequests += 1;
      resumed = true;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow_id: 'wf-four-chapter-current', task_id: 'task-episode-2', status: 'handoff_ready', resumed_stage: 'draft',
          completed_stages: ['facts', 'assets', 'episode_contract'],
          safe_next_action: {
            code: 'open_producer', label: '打开安全恢复入口',
            href: `/producer?workflow_id=wf-four-chapter-current&novel_id=${fourChapterNovel.id}&chapter_id=${fourChapterNovel.chapters[1].id}&resume_task_id=task-episode-2`,
          },
        }),
      });
      return;
    }
    if (
      path === '/api/v1/workflow/wf-four-chapter-current/episode-contract/lock' &&
      route.request().method() === 'POST'
    ) {
      locked = true;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(studioSnapshot({ locked: true }).episode_contract),
      });
      return;
    }
    if (path === `/api/v1/production-cards/novel/${fourChapterNovel.id}`) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ novel_id: fourChapterNovel.id, cards: [], summary: { ready: 0, incomplete: 0 } }) });
      return;
    }
    if (path === '/api/v1/prompt-skills') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], count: 0 }) });
      return;
    }
    if (path === '/api/v1/video/models') {
      consumedVideoCatalog = true;
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(syntheticVideoCatalog) });
      return;
    }
    if (resumed) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
      return;
    }
    throw new Error(`未模拟接口: ${route.request().method()} ${path}`);
  });

  await page.goto('/studio?workflow_id=wf-four-chapter-current');
  await page.getByRole('tab', { name: '设定' }).click();

  await expect(page.getByTestId('episode-plan-panel').getByRole('heading', { name: '多集计划' })).toBeVisible();
  await expect(page.getByTestId('episode-plan-panel')).toContainText('4 集');
  expect(new Set(consumedWorkflows.map((workflow) => workflow.workflow_id))).toEqual(new Set(['wf-four-chapter-current']));
  expect(consumedSnapshot?.series_plan.episodes).toHaveLength(4);
  expect((consumedSnapshot as any)?.whole_book_gaps).toEqual({
    story_bible: null,
    story_state_machine: null,
    voice_locks: [],
    cross_episode_shot_selection: null,
  });
  expect(consumedVideoCatalog).toBe(true);
  expect(syntheticVideoCatalog.models[0].id).toMatch(/^test\./);
  expect(syntheticVideoCatalog.models[0].api_model_id).not.toMatch(/seedance|sunqy/i);
  expect(Object.fromEntries([...fourChapterNovel.entities, ...fourChapterNovel.events].map((item) => [item.id, item.expectedFirstEvidenceChapter]))).toEqual({
    'entity-character-shen-yan': 1,
    'entity-prop-blue-coat': 1,
    'entity-prop-copper-bell': 2,
    'entity-prop-damaged-lantern': 3,
    'entity-location-north-cape-lighthouse': 4,
    'event-arrive-mist-harbor': 1,
    'event-bell-warning': 2,
    'event-lantern-damaged': 3,
    'event-lighthouse-collapse': 4,
  });
  await expect(page.getByText('第 1 集 · 第1集')).toBeVisible();
  await expect(page.getByTestId('episode-plan-panel')).toContainText('承接明细：沈砚、深蓝旧呢大衣、铜铃');
  await expect(page.getByTestId('episode-contract-panel').getByRole('heading', { name: '剧集合约' })).toBeVisible();

  await expect(page.getByTestId('studio-command-bar')).toContainText('Readiness 88%');
  await page.getByRole('tab', { name: '生产' }).click();
  await expect(page.getByText('视频：2')).toBeVisible();
  await expect(page.getByText('已锁定 2 · 定稿 2', { exact: true })).toBeVisible();
  await expect(page.getByText('任务 task-episode-2')).toBeVisible();
  await expect(page.getByText(/可安全重试当前阶段/)).toBeVisible();
  await expect(page.getByTestId('studio-stage-audit')).toContainText('draft_provider_timeout');
  await expect(page.getByTestId('studio-stage-audit')).toContainText('state_drift_warning');
  await expect(page.getByTestId('studio-stage-audit')).toContainText('graph-hash-2');
  await expect(page.getByTestId('studio-command-bar').getByRole('button', { name: '安全重试失败阶段' })).toBeVisible();
  await page.getByTestId('studio-command-bar').getByRole('button', { name: '安全重试失败阶段' }).click();
  await expect.poll(() => resumeRequests).toBe(1);
  await expect(page).toHaveURL(/\/producer\?.*workflow_id=wf-four-chapter-current.*resume_task_id=task-episode-2/);

  await page.goto('/studio?workflow_id=wf-four-chapter-current');
  await expect(page.getByText('任务 task-episode-2')).toHaveCount(0);
  await page.getByRole('tab', { name: '复审' }).click();
  await expect(page.getByTestId('production-graph-panel')).toContainText('版本 2');
  await expect(page.getByTestId('consistency-ledger-panel')).toContainText('76');
  await page.getByRole('tab', { name: '设定' }).click();

  await page.getByTestId('studio-command-bar').getByRole('button', { name: '锁定剧集合约' }).click();
  await expect(page.getByText('abcdef123456...567890')).toBeVisible();
  expect(locked).toBe(true);
  await expect(page.getByText('生成本集草片', { exact: true })).toHaveCount(1);

  await page.setViewportSize({ width: 390, height: 844 });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

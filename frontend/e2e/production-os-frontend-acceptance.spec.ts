import { REAL_BACKEND, expect, frontendApi, fulfillJson, observeProductionRequests, test } from './helpers/production-os-fixture';

test.describe('Production OS deterministic frontend contracts', () => {
  test.skip(() => REAL_BACKEND, 'mocked contracts are separated from isolated real-backend acceptance');

  test('model contract, approved entity evidence and graph are visible in Studio', async ({ page }) => {
    const duplicateKeyWarnings: string[] = [];
    page.on('console', (message) => {
      if (message.text().includes('two children with the same key')) duplicateKeyWarnings.push(message.text());
    });
    const requests = observeProductionRequests(page);
    await page.route('**/api/v1/**', async (route) => {
      const path = new URL(route.request().url()).pathname.replace(/\/+$/, '');
      if (path === '/api/v1/workflow') return fulfillJson(route, [{ workflow_id: 'wf-os', title: '第二集', status: 'active' }]);
      if (path === '/api/v1/studio/workflows/wf-os/snapshot') return fulfillJson(route, {
        series_studio: { enabled: true, primary_console: 'series_studio', expert_drilldowns: [] },
        workflow: { id: 'wf-os', title: '第二集', status: 'active', novel_id: 'novel-os' },
        story_context: { novel: { id: 'novel-os', title: '雾港铜铃' } },
        production_bible_summary: { readiness_score: 100, counts: { characters: 1 }, missing_requirements: [], asset_readiness: { ready: true }, characters: [{ id: 'char-1', name: '林澈', approved: true, review_status: 'approved', evidence: '第二章第3段' }] },
        production_graph: { version: 2, hash: 'abcdef123456', story_order: [{ id: 'event-1', event_type: 'prop_owner_changed', production_version: 2, episode_index: 2, story_time: { episode_index: 2, sequence: 1 }, production_time: { stage: 'review' }, affected_episode_indices: [2], affected_shots: [{ id: 'shot-2', review_url: '/studio/shot-review?workflow_id=wf-os&shot_id=shot-2' }] }], production_revisions: [] },
        guidance: { stages: ['facts', 'assets', 'episode_contract', 'draft', 'review', 'final', 'render', 'publish'].map((id) => ({ id, label: id, status: 'ready' })) },
        production: { shot_count: 1, ready: true }, shots: [], assets: {}, jobs: { summary: {} }, issues: [], actions: [], mode_policy: {},
      });
      if (path === '/api/v1/production-cards/novel/novel-os') return fulfillJson(route, { cards: [], summary: {} });
      if (path === '/api/v1/prompt-skills') return fulfillJson(route, { items: [], count: 0 });
      if (path === '/api/v1/video/models') return fulfillJson(route, { models: [{ id: 'volcano.seedance.2_0', name: 'Seedance 2.0', contract_status: 'experimental', verified: false, verification_gaps: ['live_canary_job_id'] }] });
      if (path === '/api/v1/workflow/wf-os/shot-review') return fulfillJson(route, { workflow_id: 'wf-os', shots: [], latest_render_artifacts: null });
      return fulfillJson(route, {});
    });
    await page.goto('/studio?workflow_id=wf-os');
    await expect(page.getByTestId('production-bible-panel')).toContainText('林澈');
    await expect(page.getByTestId('production-bible-panel')).toContainText('已确认');
    await expect(page.getByTestId('production-bible-panel')).toContainText('证据：第二章第3段');
    expect(duplicateKeyWarnings).toEqual([]);
    await expect(page.getByTestId('studio-model-contracts')).toContainText('Seedance 2.0');
    await expect(page.getByTestId('studio-model-contracts')).toContainText('实验中 · 未验证');
    await expect(page.getByTestId('studio-model-contracts')).toContainText('缺少实模验收任务编号');
    await expect(page.getByTestId('studio-stage-flow')).toContainText('8阶段');
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
    await page.getByRole('tab', { name: '复审' }).click();
    const graph = page.getByTestId('production-graph-panel');
    await expect(graph).toContainText('Production Graph');
    await graph.getByRole('link', { name: '查看受影响镜头' }).click();
    await expect(page).toHaveURL(/shot_id=shot-2/);
    await page.goto('/studio?workflow_id=wf-os');
    expect(requests.some((item) => item.path.endsWith('/video/models'))).toBeTruthy();
  });

  test('canonical card creates selected-model binding from a visible action', async ({ page }) => {
    let ready = false;
    const requests = observeProductionRequests(page);
    await page.route('**/api/v1/production-cards/novel/novel-os', (route) => fulfillJson(route, { novel_id: 'novel-os', summary: { ready: 1, incomplete: 0 }, cards: [{ entity_id: 'char-1', entity_type: 'character', name: '林澈', novel_id: 'novel-os', visual: { locked_count: 1, missing_views: [], views: [{ view_key: 'front', asset_id: 'asset-v3', version: 3, url: '/static/front.png', is_locked: true, is_final: true }] }, usage: { shot_count: 2 }, voice: { locked: true }, readiness: { score: 100, final_ready: true, gaps: [] } }] }));
    await page.route('**/api/v1/assets/bindings/health**', (route) => fulfillJson(route, { provider_id: 'volcano', model_id: 'doubao-seedance-2-0-260128', assets: [{ asset_id: 'asset-v3', asset_version: 3, canonical_ready: true, binding_required: true, binding_ready: ready }] }));
    await page.route('**/api/v1/assets/asset-v3/bindings', async (route) => { ready = true; await fulfillJson(route, { id: 'binding-1', verified: true }, 201); });
    await page.goto('/studio/cards?novel_id=novel-os&provider_id=volcano&model_id=doubao-seedance-2-0-260128');
    await page.getByRole('button', { name: '生成模型引用' }).click();
    await expect(page.getByText('doubao-seedance-2-0-260128 引用已验证')).toBeVisible();
    expect(requests.some((item) => item.method === 'POST' && item.path.endsWith('/assets/asset-v3/bindings'))).toBeTruthy();
  });

  test('quality evaluation and minimal repair originate from Shot Review', async ({ page }) => {
    let evaluated = false; let repaired = false;
    const requests = observeProductionRequests(page);
    await page.route('**/api/v1/workflow/wf-os/shot-review', (route) => {
      const qualityGate = !evaluated ? null : repaired
        ? { ready: true, overall_readiness: 'ready', blockers: [], warnings: [], dimensions: [], suggested_repair: null }
        : {
            ready: false, overall_readiness: 'blocked', blockers: [{ code: 'wrong_speaker' }], warnings: [], dimensions: [],
            suggested_repair: { issue_code: 'wrong_speaker', actions: ['regenerate_tts', 'rerun_lipsync', 'rerender_audio'], affected_artifact_ids: ['tts-1'], available: true, cost_risk: { cost: 'low', risk: 'low', scope: 'audio_only' } },
          };
      return fulfillJson(route, { workflow_id: 'wf-os', shots: [{ shot_id: 'shot-1', shot_number: 1, status: 'succeeded', duration: 4, evidence: {}, quality_gate: qualityGate }] });
    });
    await page.route('**/api/v1/workflow/wf-os/quality/evaluate', async (route) => { evaluated = true; await fulfillJson(route, { ready: false, blockers: [{ code: 'wrong_speaker' }] }); });
    await page.route('**/api/v1/workflow/wf-os/quality/repair', async (route) => { repaired = true; await fulfillJson(route, { unchanged_artifact_ids: ['video-1', 'video-2', 'tts-2'], evaluation_ready: true }); });
    await page.goto('/studio/shot-review?workflow_id=wf-os');
    await page.getByRole('button', { name: '开始检查镜头 1' }).click();
    await page.getByRole('button', { name: '重新生成镜头 1 配音并重跑口型' }).click();
    await expect(page.getByTestId('quality-gate-shot-1')).toContainText('全部通过，可以进入成片复审');
    expect(requests.filter((item) => item.path.includes('/quality/')).map((item) => item.path)).toEqual(['/api/v1/workflow/wf-os/quality/evaluate', '/api/v1/workflow/wf-os/quality/repair']);
  });

  test('production analytics renders database-backed readiness and unavailable cost honestly', async ({ page }) => {
    await page.route('**/api/v1/dashboard/analytics**', (route) => fulfillJson(route, {
      data_source: 'database', is_mock: false, generated_at: '2026-07-11T00:00:00Z', period_days: 14,
      content_stats: { novels_count: 1, chapters_count: 3, scripts_count: 1, storyboards_count: 1, shots_count: 6, characters_count: 2, assets_count: 4 },
      usage_summary: { total_requests: 0, today_requests: 0, total_tokens: 0, total_cost: 0 },
      task_summary: { total: 0, succeeded: 0, failed: 0, running: 0, success_rate: 0 },
      task_by_type: [], daily_series: [], model_usage: [], recent_activities: [],
      production_metrics: {
        first_pass_shot_acceptance_rate: 0.75,
        main_character_hard_failure_rate: 0.1,
        state_continuity_conflict_rate: 0.05,
        voice_lipsync_hard_failure_rate: 0.02,
        regenerated_shots_per_accepted_shot: 0.25,
        rmb_per_accepted_final_minute: null,
        wall_clock_minutes_per_accepted_final_minute: 18,
        human_review_repair_minutes_per_accepted_final_minute: 4,
        failed_abandoned: { attempt_count: 2, cost_rmb: 1.25 },
        readiness: { current_tier: 'deterministic_ready', tiers: { deterministic_ready: true } },
      },
    }));

    await page.goto('/analytics');
    const metrics = page.getByTestId('production-metrics');
    await expect(metrics).toContainText('连续动漫生产指标');
    await expect(metrics).toContainText('确定性验证就绪');
    await expect(metrics).toContainText('首轮镜头接收率75.0%');
    await expect(metrics).toContainText('每终稿分钟成本不可用');
    await expect(metrics).toContainText('失败/放弃尝试保持可见：2 次，成本 ¥1.2500');
  });
});

test.describe('Production OS isolated real backend', () => {
  test.skip(() => !REAL_BACKEND, 'set PRODUCTION_OS_REAL_BACKEND=1 with an isolated DEV_MODE backend');
  test('visible quick-start enters Studio and advances the primary contract action', async ({ page }) => {
    const requests = observeProductionRequests(page);
    await page.goto('/quick-start');
    await page.getByPlaceholder('例如：星灯邮差').fill(`Production OS ${Date.now()}`);
    await page.getByPlaceholder(/写 2-5 句话即可/).fill('现代奇幻连续动漫，主角在雨夜寻找失落铜铃。');
    await page.getByPlaceholder(/粘贴首章正文/).fill('林澈走进雾港雨巷，确认铜铃仍由自己保管。');
    const auto = page.getByLabel('自动生成首集可预览草片、字幕和本地渲染包');
    if (await auto.isChecked()) await auto.uncheck();
    await page.getByRole('button', { name: /生成第一集|开始生成/ }).click();
    await page.getByRole('link', { name: /进入工作室|打开工作室/ }).first().click();
    await expect(page.getByRole('heading', { name: '系列动漫工作室' })).toBeVisible({ timeout: 120_000 });
    const workflowId = new URL(page.url()).searchParams.get('workflow_id');
    expect(workflowId).toBeTruthy();
    const before = await frontendApi<any>(page, `/studio/workflows/${workflowId}/snapshot`);
    const primary = page.getByTestId('studio-command-bar').getByRole('button').first();
    await expect(primary).toBeVisible();
    await primary.click();
    const dialog = page.getByRole('dialog');
    if (await dialog.isVisible()) {
      await dialog.getByRole('button').filter({ hasNotText: '取消' }).last().click();
    }
    await expect.poll(() => requests.some((item) => item.method === 'POST' && (
      item.path.includes('/episode-contract/lock') || item.path.includes('/studio/workflows/')
    ))).toBeTruthy();
    let after: any;
    await expect.poll(async () => {
      after = await frontendApi<any>(page, `/studio/workflows/${workflowId}/snapshot`);
      return JSON.stringify(after) !== JSON.stringify(before);
    }, { timeout: 30_000, message: 'primary action must persist a changed Studio snapshot' }).toBeTruthy();
    expect(after.workflow.id).toBe(workflowId);
  });
});

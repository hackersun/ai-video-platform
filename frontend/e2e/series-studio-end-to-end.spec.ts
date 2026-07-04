import { mkdirSync } from 'fs';
import { expect, test, type Page, type Route } from '@playwright/test';
import { collectConsoleHealth } from './helpers/console-health';
import { expectedSections, sampleNovel, seriesStudioIds as ids } from './helpers/series-studio-fixtures';

const outputDir = '/tmp/ai-video-platform-series-studio-e2e';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

async function fulfillJson(route: Route, data: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(data),
  });
}

type ScenarioState = {
  entityApproved: boolean;
  contractLocked: boolean;
  ledgerFinding: boolean;
};

function episodeContract(locked = true) {
  if (!locked) return null;
  return {
    contract_id: 'contract-series-e2e',
    workflow_id: ids.workflowId,
    novel_id: ids.novelId,
    chapter_ids: [ids.chapterId],
    episode_index: 1,
    production_bible_hash: 'pb-hash-series-e2e',
    locked_at: '2026-07-04T00:00:00Z',
    entity_locks: [{ entity_id: ids.characterId, entity_type: 'character', name: '林澈', approved_asset_ids: ['asset-lin-front'] }],
    model_strategy: { draft_video: 'seedance-fast', final_video: 'seedance-pro', image: 'seedream', tts: 'minimax', fallback_policy: 'visible_fallback' },
    required_checks: ['style', 'characters', 'voice', 'subtitle_timing'],
  };
}

function studioSnapshot(state: ScenarioState) {
  const character = {
    entity_id: ids.characterId,
    name: '林澈',
    description: '雾城旧车站少年，核心钥匙持有者。',
    approved: state.entityApproved,
  };
  return {
    series_studio: {
      enabled: true,
      primary_console: 'series_studio',
      expert_drilldowns: ['/story-bibles', '/studio/cards', '/studio/shot-review', '/workflow', '/producer', '/video-generation'],
    },
    workflow: {
      id: ids.workflowId,
      title: `${sampleNovel.title} 第一集`,
      status: 'active',
      novel_id: ids.novelId,
      chapter_id: ids.chapterId,
      script_id: ids.scriptId,
      storyboard_id: ids.storyboardId,
      latest_production_strategy: 'draft_fast',
      latest_production_strategy_label: '草稿快速',
    },
    story_context: {
      novel: { id: ids.novelId, title: sampleNovel.title, genre: sampleNovel.genre },
      chapter: { id: ids.chapterId, title: '第一章 雾城旧车站', chapter_number: 1 },
      script: { id: ids.scriptId, title: '第一集剧本', status: 'draft' },
      storyboard: { id: ids.storyboardId, title: '第一集分镜', shot_count: 3 },
    },
    production_bible_summary: {
      readiness_score: state.entityApproved ? 96 : 82,
      style: {
        visual_style: sampleNovel.style,
        worldview: '雾城、黑塔追兵、沉睡机甲共同构成热血科幻世界。',
        negative_prompt: '避免人物脸型漂移，避免机甲钥匙颜色变化。',
      },
      counts: { characters: 2, scenes: 2, props: 2, events: 2, voices: 2 },
      characters: [character, { entity_id: 'char-a-lan', name: '阿岚', approved: true, description: '机械少女，隐藏黑塔实验体身份。' }],
      scenes: [{ entity_id: 'scene-station', name: '雾城旧车站', approved: true }],
      props: [{ entity_id: 'prop-core-key', name: '核心钥匙', approved: true }],
      events: [{ entity_id: 'event-chase', name: '黑塔追兵靠近', approved: true }],
      voices: [{ entity_id: ids.characterId, character_name: '林澈', voice: '少年热血声线' }],
      missing_requirements: state.entityApproved ? [] : [{ code: 'character_approval_missing', message: '林澈人物设定待确认' }],
      asset_readiness: { asset_count: 4, missing_asset_count: 0, ready: true },
      next_actions: [],
    },
    series_plan: {
      novel_id: ids.novelId,
      current_episode: { episode_index: 1, title: '第一集 雾城核心钥匙' },
      episodes: [
        {
          episode_index: 1,
          title: '雾城核心钥匙',
          status: 'in_production',
          workflow_id: ids.workflowId,
          chapter_ids: [ids.chapterId],
          chapter_range: { label: '第 1 章' },
          carry_over_state: { characters: ['林澈', '阿岚'], props: ['核心钥匙'], events: ['黑塔追兵靠近'] },
          summary: '林澈在旧车站发现核心钥匙，阿岚登场。',
        },
        {
          episode_index: 2,
          title: '雨夜集市的机甲回声',
          status: 'planned',
          chapter_ids: ['chapter-2'],
          chapter_range: { label: '第 2 章' },
          carry_over_state: { characters: ['林澈', '阿岚'], props: ['核心钥匙'], events: ['机甲苏醒'] },
        },
      ],
    },
    episode_contract: episodeContract(state.contractLocked),
    consistency_ledger: {
      workflow_id: ids.workflowId,
      overall_score: state.ledgerFinding ? 70 : 94,
      dimensions: {
        style: 100,
        character_visual: state.ledgerFinding ? 0 : 95,
        scene: 92,
        prop_state: 94,
        voice: 90,
        event_continuity: 96,
        subtitle_timing: 92,
      },
      findings: state.ledgerFinding ? [{
        code: 'shot_character_unbound',
        severity: 'blocking',
        shot_id: ids.shotId,
        message: '镜头没有绑定角色参考，人物一致性不可控',
        repair_action: { code: 'bind_character_reference', label: '绑定角色参考', risk: 'navigation' },
      }] : [],
    },
    production: { shot_count: 3, asset_lock_coverage: 1, entity_ref_coverage: 1, ready: !state.ledgerFinding },
    shots: [
      { id: ids.shotId, shot_number: 1, prompt: '林澈在旧车站举起核心钥匙', dialogue: '林澈：这把钥匙在发光。', entity_ref_count: 2, asset_lock_count: 3 },
    ],
    assets: { total_count: 4, locked_count: 4, final_count: 4, by_category: { character: 2, scene: 1, prop: 1 } },
    jobs: {
      summary: { video_count: 1, tts_count: 1, synthesis_count: 1, media_count: 0 },
      video_jobs: [{
        id: 'video-series-1',
        status: 'succeeded',
        reference_package_mode: '多参考包',
        reference_package: { mode: 'multimodal', image_count: 3, video_count: 1 },
      }],
    },
    issues: [],
    actions: [],
    mode_policy: { mode: 'production', ready: !state.ledgerFinding, blocking_issue_count: state.ledgerFinding ? 1 : 0 },
  };
}

function shotReviewPayload() {
  return {
    workflow_id: ids.workflowId,
    latest_render_artifacts: {
      preview_url: '/static/e2e/series-preview.html',
      source_manifest_url: '/static/e2e/series-manifest.json',
      srt_url: '/static/e2e/series.srt',
      timeline_url: '/static/e2e/series-timeline.json',
      render_manifest_url: '/static/e2e/series-render.json',
      output_url: '/static/e2e/series.mp4',
    },
    shots: [{
      shot_id: ids.shotId,
      shot_number: 1,
      video_url: '/static/e2e/shot-1.mp4',
      status: 'succeeded',
      duration: 4,
      subtitle_text: '林澈举起发光的核心钥匙。',
      character_names: ['林澈', '阿岚'],
      evidence: {
        strategy_routing: 'draft_fast · visible_fallback',
        reference_package_mode: '多角色参考包',
        reference_package: { mode: 'multimodal', image_count: 3, video_count: 1, dropped: [{ entity_name: '备用侧脸参考', reason: '超出模型容量' }] },
        generation_preflight: 'visible_fallback：参考包超出容量，裁剪后继续生成',
        visual_consistency: { score: 88, status: 'pass', frame_count: 3 },
      },
      visual_consistency_score: 88,
      regeneration_count: 0,
    }],
  };
}

async function installSeriesStudioRoutes(page: Page, options: Partial<ScenarioState> = {}) {
  const state: ScenarioState = {
    entityApproved: options.entityApproved ?? false,
    contractLocked: options.contractLocked ?? false,
    ledgerFinding: options.ledgerFinding ?? false,
  };

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/\/+/g, '/').replace(/\/$/, '');

    if (path === '/api/v1/llm/configs') return fulfillJson(route, []);
    if (path === '/api/v1/llm/models') {
      return fulfillJson(route, [{
        id: 'model-video-fast',
        model_id: 'seedance-fast',
        model_name: 'seedance-fast',
        model_name_cn: 'Seedance 草稿快速',
        model_type: 'video',
        capabilities: ['video'],
        is_default: true,
        limits: { reference_images: 3, reference_videos: 1 },
      }]);
    }
    if (path.startsWith('/api/v1/llm/api-key/')) return fulfillJson(route, { configured: true, dev_mode: true });
    if (path === '/api/v1/external/configs') return fulfillJson(route, []);

    if (path === '/api/v1/novels') {
      if (request.method() === 'POST') return fulfillJson(route, { id: ids.novelId, title: sampleNovel.title, genre: sampleNovel.genre, style: sampleNovel.style });
      return fulfillJson(route, [{ id: ids.novelId, title: sampleNovel.title, genre: sampleNovel.genre, style: sampleNovel.style }]);
    }
    if (path === `/api/v1/chapters/novel/${ids.novelId}`) return fulfillJson(route, [{ id: ids.chapterId, novel_id: ids.novelId, title: '第一章 雾城旧车站', chapter_number: 1 }]);
    if (path === '/api/v1/chapters') return fulfillJson(route, { id: ids.chapterId, novel_id: ids.novelId, title: '第一章 雾城旧车站', chapter_number: 1 });
    if (path === '/api/v1/story-bibles/generate-from-novel') return fulfillJson(route, { id: ids.storyBibleId });
    if (path === '/api/v1/storyboards/generate-smart') {
      return fulfillJson(route, {
        id: ids.storyboardId,
        script_id: ids.scriptId,
        shot_count: 3,
        shots: [{ id: ids.shotId }, { id: 'shot-series-2' }, { id: 'shot-series-3' }],
      });
    }
    if (path === '/api/v1/workflow/start') return fulfillJson(route, { workflow_id: ids.workflowId });
    if (path === '/api/v1/workflow') return fulfillJson(route, [{ workflow_id: ids.workflowId, title: `${sampleNovel.title} 第一集`, status: 'active' }]);
    if (path === `/api/v1/workflow/status/${ids.workflowId}`) {
      return fulfillJson(route, {
        workflow_id: ids.workflowId,
        novel_id: ids.novelId,
        chapter_id: ids.chapterId,
        script_id: ids.scriptId,
        storyboard_id: ids.storyboardId,
        video_jobs: [],
        tts_jobs: [],
        synthesis_jobs: [],
      });
    }
    if (path === `/api/v1/studio/workflows/${ids.workflowId}/snapshot`) return fulfillJson(route, studioSnapshot(state));
    if (path === `/api/v1/production-cards/novel/${ids.novelId}`) {
      return fulfillJson(route, { novel_id: ids.novelId, cards: [], summary: { ready: 4, incomplete: 0 } });
    }
    if (path === '/api/v1/prompt-skills') return fulfillJson(route, { items: [], count: 0 });
    if (path === `/api/v1/story-bibles/entities/${ids.characterId}/approve` && request.method() === 'POST') {
      state.entityApproved = true;
      return fulfillJson(route, { entity_id: ids.characterId, approved: true });
    }
    if (path === `/api/v1/workflow/${ids.workflowId}/episode-contract/lock` && request.method() === 'POST') {
      state.contractLocked = true;
      return fulfillJson(route, episodeContract(true));
    }
    if (path === `/api/v1/workflow/${ids.workflowId}/shot-review`) return fulfillJson(route, shotReviewPayload());

    if (path === '/api/v1/scripts') return fulfillJson(route, [{ id: ids.scriptId, title: '第一集剧本', novel_id: ids.novelId, chapter_id: ids.chapterId }]);
    if (path === `/api/v1/storyboards/script/${ids.scriptId}`) return fulfillJson(route, [{ id: ids.storyboardId, title: '第一集分镜', script_id: ids.scriptId, novel_id: ids.novelId, chapter_id: ids.chapterId }]);
    if (path === `/api/v1/storyboards/${ids.storyboardId}`) return fulfillJson(route, { id: ids.storyboardId, title: '第一集分镜', script_id: ids.scriptId, novel_id: ids.novelId, chapter_id: ids.chapterId });
    if (path === '/api/v1/storyboards') return fulfillJson(route, [{ id: ids.storyboardId, title: '第一集分镜', script_id: ids.scriptId, novel_id: ids.novelId, chapter_id: ids.chapterId }]);
    if (path === `/api/v1/shots/storyboard/${ids.storyboardId}`) {
      return fulfillJson(route, [{ id: ids.shotId, storyboard_id: ids.storyboardId, shot_number: 1, duration: 4, prompt: '林澈在旧车站举起核心钥匙', video_status: 'succeeded', video_url: '/static/e2e/shot-1.mp4' }]);
    }
    if (path === `/api/v1/shots/${ids.shotId}`) {
      return fulfillJson(route, { id: ids.shotId, storyboard_id: ids.storyboardId, shot_number: 1, duration: 4, prompt: '林澈在旧车站举起核心钥匙', video_status: 'succeeded', video_url: '/static/e2e/shot-1.mp4' });
    }
    if (path === `/api/v1/shots/${ids.shotId}/production-context`) return fulfillJson(route, { production_context: {} });
    if (path === '/api/v1/assets/view-presets') return fulfillJson(route, { presets: [] });
    if (path === '/api/v1/characters') return fulfillJson(route, []);

    if (path === '/api/v1/video/jobs') {
      return fulfillJson(route, [{
        id: 'video-history-series',
        task_id: 'task-history-series',
        title: 'draft_fast 策略兜底历史',
        prompt: '林澈在旧车站举起核心钥匙',
        status: 'succeeded',
        progress: 100,
        video_url: '/static/e2e/history.mp4',
        shot_id: ids.shotId,
        duration: 4,
        resolution: '720p',
        api_model_id: 'seedance-fast',
        provider_id: 'volcano',
        created_at: new Date().toISOString(),
        extra_data: {
          generation_preflight: {
            ready: false,
            blocking_issue_count: 1,
            issues: [{ code: 'visible_fallback', severity: 'blocking', message: 'visible_fallback：参考图非公网，使用纯文本兜底' }],
          },
          reference_package: {
            mode: 'multimodal',
            image_count: 3,
            video_count: 1,
            dropped: [{ entity_name: '核心钥匙侧面参考', reason: '超出容量' }],
          },
        },
      }]);
    }
    if (path === '/api/v1/media/jobs') return fulfillJson(route, []);

    return fulfillJson(route, {});
  });

  return state;
}

test.beforeEach(async ({ page }) => {
  mkdirSync(outputDir, { recursive: true });
  const userId = `series-studio-e2e-${Date.now()}`;
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

test('full novel to episode production is controlled from the frontend', async ({ page }) => {
  const consoleHealth = collectConsoleHealth(page);
  await installSeriesStudioRoutes(page, { entityApproved: true, contractLocked: true });

  await page.goto('/quick-start');
  await page.getByPlaceholder('例如：星灯邮差').fill(sampleNovel.title);
  await page.getByPlaceholder(/写 2-5 句话即可/).fill(`${sampleNovel.genre}。${sampleNovel.style}。${sampleNovel.content}`);
  await page.getByPlaceholder(/粘贴首章正文/).fill(sampleNovel.content);
  await page.getByLabel('自动生成首集可预览草片、字幕和本地渲染包').uncheck();
  await page.getByRole('button', { name: /生成第一集|开始生成/ }).click();
  await expect(page.getByText(/生成完成|已生成/).first()).toBeVisible({ timeout: 120_000 });
  await page.getByRole('link', { name: /进入工作室|打开工作室/ }).first().click();

  await expect(page.getByRole('heading', { name: '系列动漫工作室' })).toBeVisible({ timeout: 30_000 });
  for (const section of expectedSections.filter((item) => item !== '系列动漫工作室')) {
    await expect(page.getByText(section).first()).toBeVisible({ timeout: 30_000 });
  }
  await expect(page.getByText(/角色/).first()).toBeVisible();
  await expect(page.getByText(/场景/).first()).toBeVisible();
  await expect(page.getByText(/道具/).first()).toBeVisible();
  await expect(page.getByText(/声线/).first()).toBeVisible();
  await expect(page.getByText(/模型策略|草稿快速|终稿质量/).first()).toBeVisible();
  await expect(page.getByText('Failed to fetch')).toHaveCount(0);

  await page.screenshot({ path: `${outputDir}/series-studio-overview.png`, fullPage: true });
  consoleHealth.assertHealthy();
});

test('production bible approval path works from studio', async ({ page }) => {
  await installSeriesStudioRoutes(page, { entityApproved: false, contractLocked: true });

  await page.goto(`/studio?workflow_id=${ids.workflowId}`);
  const panel = page.getByTestId('production-bible-panel');
  await expect(panel.getByText('林澈').first()).toBeVisible();
  await panel.getByRole('button', { name: '确认' }).first().click();

  await expect(page.getByText('实体已确认')).toBeVisible();
  await expect(panel.getByText('已确认').first()).toBeVisible();
});

test('episode contract can be locked from studio', async ({ page }) => {
  await installSeriesStudioRoutes(page, { entityApproved: true, contractLocked: false });

  await page.goto(`/studio?workflow_id=${ids.workflowId}`);
  const panel = page.getByTestId('episode-contract-panel');
  await expect(panel.getByText('未锁定').first()).toBeVisible();
  await panel.getByRole('button', { name: '锁定剧集合约' }).click();

  await expect(page.getByText('剧集合约已锁定')).toBeVisible();
  await expect(panel.getByText(/pb-hash-seri/)).toBeVisible();
});

test('shot review exposes fallback and reference package evidence', async ({ page }) => {
  await installSeriesStudioRoutes(page, { entityApproved: true, contractLocked: true, ledgerFinding: true });

  await page.goto(`/studio?workflow_id=${ids.workflowId}`);
  await page.getByTestId('consistency-ledger-panel').getByRole('button', { name: '绑定角色参考' }).click();

  await expect(page).toHaveURL(/\/studio\/shot-review\?workflow_id=wf-series-e2e/);
  await expect(page.getByRole('heading', { name: '镜头审阅' })).toBeVisible();
  await expect(page.getByText('draft_fast · visible_fallback')).toBeVisible();
  await expect(page.getByText('多角色参考包')).toBeVisible();
  await expect(page.getByTestId(`shot-review-reference-package-${ids.shotId}`)).toContainText('3图');
  await expect(page.getByTestId(`shot-review-reference-package-${ids.shotId}`)).toContainText('1视频');
  await expect(page.getByText('visible_fallback：参考包超出容量，裁剪后继续生成')).toBeVisible();
});

test('expert workflow page links back to studio', async ({ page }) => {
  await installSeriesStudioRoutes(page, { entityApproved: true, contractLocked: true });

  await page.goto(`/studio?workflow_id=${ids.workflowId}`);
  await page.getByRole('button', { name: /专家工具|更多/ }).click();
  await page.getByRole('menuitem', { name: '工作流' }).click();

  await expect(page).toHaveURL(/\/workflow/);
  await expect(page.getByText('这是专家工具。连续动漫制作建议从工作室统一管控。')).toBeVisible();
  await page.getByRole('button', { name: '回到工作室' }).click();
  await expect(page).toHaveURL(/\/studio/);
});

test('video generation history shows strategy and fallback badges', async ({ page }) => {
  await installSeriesStudioRoutes(page, { entityApproved: true, contractLocked: true });

  await page.goto(`/studio?workflow_id=${ids.workflowId}`);
  await page.getByRole('button', { name: /专家工具|更多/ }).click();
  await page.getByRole('menuitem', { name: '视频生成' }).click();
  await expect(page).toHaveURL(/\/video-generation/);

  await expect(page.getByRole('heading', { name: '生成历史' })).toBeVisible();
  await expect(page.getByText('draft_fast 策略兜底历史')).toBeVisible();
  await expect(page.getByTestId('history-preflight-video-history-series')).toContainText('visible_fallback');
  await expect(page.getByTestId('history-reference-package-video-history-series')).toContainText('参考包');
  await expect(page.getByTestId('history-reference-package-video-history-series')).toContainText('3图');
  await page.getByTitle('查看详情').first().click();
  await expect(page.getByText('API模型: seedance-fast')).toBeVisible();
});

test('mobile viewport keeps first screen usable', async ({ page }) => {
  await installSeriesStudioRoutes(page, { entityApproved: true, contractLocked: true });
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto(`/studio?workflow_id=${ids.workflowId}`);

  await expect(page.getByRole('heading', { name: '系列动漫工作室' })).toBeVisible();
  await expect(page.getByText(/连续性状态/).first()).toBeVisible();
  await expect(page.getByText(/模型策略|草稿快速/).first()).toBeVisible();
  await page.screenshot({ path: `${outputDir}/series-studio-mobile.png`, fullPage: true });
});

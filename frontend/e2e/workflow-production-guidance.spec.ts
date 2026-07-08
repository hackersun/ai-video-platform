import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `workflow-guidance-user-${Date.now()}`;
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

test('workflow page does not silently create a workflow without workflow_id', async ({ page }) => {
  let startWorkflowCalls = 0;
  await page.route('**/api/v1/workflow/start', async (route) => {
    startWorkflowCalls += 1;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ workflow_id: 'unexpected-auto-workflow' }),
    });
  });

  await page.goto('/workflow');
  await expect(page.getByText('选择或创建本集工程')).toBeVisible({ timeout: 10_000 });
  await page.waitForTimeout(1000);

  expect(startWorkflowCalls).toBe(0);
});

test('workflow next action posts the selected assistant action code', async ({ page }) => {
  const assistantRequests: Array<Record<string, unknown>> = [];

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === '/api/v1/llm/configs') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/workflow/status/wf-001') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow_id: 'wf-001',
          title: '逆天至尊 第一章',
          status: 'active',
          current_step: 6,
          completed_steps: [1, 2, 3, 4, 5, 6],
          novel_id: 'novel-001',
          chapter_id: 'chapter-001',
          script_id: 'script-001',
          storyboard_id: 'storyboard-001',
          video_jobs: [],
          tts_jobs: [],
          synthesis_jobs: [],
          metadata: { production_pack: { lock_count: 0 } },
        }),
      });
      return;
    }

    if (path === '/api/v1/short-video/workflow/wf-001/readiness') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          summary: { ready: false, score: 72, blocker_count: 0, warning_count: 1 },
          recommendations: ['先生成资产定稿包。'],
        }),
      });
      return;
    }

    if (path === '/api/v1/production-control/workflow/wf-001/producer-assistant') {
      const body = request.postData() ? JSON.parse(request.postData() || '{}') : {};
      assistantRequests.push(body);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow_id: 'wf-001',
          summary: {
            ready: false,
            next_action: {
              code: 'build_production_pack',
              label: '生成资产定稿包',
              detail: '锁定角色、场景、道具参考资产，避免多集生成漂移。',
              status: 'ready',
              priority: 'P0',
            },
            action_count: 1,
            executed_count: body.auto_fix ? 1 : 0,
          },
          actions: [{
            code: 'build_production_pack',
            label: '生成资产定稿包',
            detail: '锁定角色、场景、道具参考资产，避免多集生成漂移。',
            status: 'ready',
            priority: 'P0',
          }],
          executed: body.auto_fix ? [{ code: 'build_production_pack', result: { lock_count: 3 } }] : [],
          media_audit: { missing_count: 0 },
          quality: { average_score: 72 },
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: request.method() === 'GET' ? '[]' : '{}',
    });
  });

  await page.goto('/workflow?workflow_id=wf-001');
  await expect(page.getByText('下一步：生成资产定稿包')).toBeVisible();

  await page.getByRole('button', { name: /执行下一步/ }).click();

  await expect.poll(() => assistantRequests.some((body) => (
    body.auto_fix === true && body.action_code === 'build_production_pack'
  ))).toBeTruthy();
  expect(assistantRequests[0]).toEqual({ auto_fix: false });
});

test('workflow rerender button forces existing ffmpeg mp4 regeneration with burned subtitles', async ({ page }) => {
  let renderRequest: Record<string, unknown> | null = null;

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === '/api/v1/llm/configs') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/workflow/status/wf-render-force') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow_id: 'wf-render-force',
          title: '云灯邮局 第三集',
          status: 'active',
          current_step: 9,
          completed_steps: [1, 2, 3, 4, 5, 6, 7, 8],
          novel_id: 'novel-001',
          chapter_id: 'chapter-003',
          script_id: 'script-003',
          storyboard_id: 'storyboard-003',
          video_jobs: [{ id: 'video-001', status: 'succeeded', novel_id: 'novel-001', chapter_id: 'chapter-003', script_id: 'script-003', storyboard_id: 'storyboard-003' }],
          tts_jobs: [{ id: 'tts-001', status: 'succeeded', chapter_id: 'chapter-003', script_id: 'script-003', storyboard_id: 'storyboard-003' }],
          subtitle_tracks: [{ id: 'subtitle-001', novel_id: 'novel-001', chapter_id: 'chapter-003', script_id: 'script-003', storyboard_id: 'storyboard-003' }],
          synthesis_jobs: [{
            id: 'synthesis-001',
            manifest_url: '/static/exports/synthesis-001.json',
            output_url: '/static/exports/final-synthesis-001.mp4',
            segment_count: 1,
            duration_seconds: 7.596,
            extra_data: {
              render_status: 'rendered',
              render_backend: 'ffmpeg_local',
              render_source: 'editable_timeline',
              render_artifacts: {
                output_url: '/static/exports/final-synthesis-001.mp4',
                srt_url: '/static/exports/final-synthesis-001.srt',
                timeline_url: '/static/exports/synthesis-001-timeline.json',
                render_manifest_url: '/static/exports/synthesis-001-render.json',
              },
            },
          }],
          metadata: { latest_timeline_id: 'timeline-001' },
        }),
      });
      return;
    }

    if (path === '/api/v1/timelines/timeline-001/tracks') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/timelines/timeline-001/clips') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/workflow/wf-render-force/render' && request.method() === 'POST') {
      renderRequest = request.postData() ? JSON.parse(request.postData() || '{}') : {};
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow_id: 'wf-render-force',
          synthesis_job_id: 'synthesis-001',
          status: 'rendered',
          render_status: 'rendered',
          render_backend: 'ffmpeg_local',
          output_url: '/static/exports/final-synthesis-001-rerendered.mp4',
          srt_url: '/static/exports/final-synthesis-001-rerendered.srt',
          timeline_url: '/static/exports/synthesis-001-rerendered-timeline.json',
          render_manifest_url: '/static/exports/synthesis-001-rerendered-render.json',
          is_publishable: true,
          output_kind: 'final_video',
          publication_blockers: [],
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: request.method() === 'GET' ? '[]' : '{}',
    });
  });

  await page.goto('/workflow?workflow_id=wf-render-force');
  await expect(page.getByText('渲染预检与执行')).toBeVisible({ timeout: 10_000 });
  await page.locator('select[title="渲染执行器"]').selectOption('ffmpeg_local');
  await expect(page.getByLabel('烧录字幕')).toBeChecked();
  await page.getByRole('button', { name: /重新生成真实成片/ }).click();

  await expect.poll(() => renderRequest).not.toBeNull();
  expect(renderRequest).toMatchObject({
    render_backend: 'ffmpeg_local',
    burn_subtitles: true,
    force: true,
  });
});

test('workflow shows media sync health and per-shot consistency gaps', async ({ page }) => {
  const mediaSyncHealth = {
    status: 'warning',
    summary: { green: 1, yellow: 1, red: 0, segment_count: 2 },
    thresholds: { green_max_delta_seconds: 0.15, yellow_max_delta_seconds: 0.75 },
    segments: [
      {
        index: 1,
        shot_number: 1,
        status: 'ok',
        color: 'green',
        video_duration_seconds: 4,
        audio_duration_seconds: 4.05,
        subtitle_duration_seconds: 4,
        audio_video_delta_seconds: 0.05,
        subtitle_video_delta_seconds: 0,
        audio_subtitle_delta_seconds: 0.05,
        issues: [],
      },
      {
        index: 2,
        shot_number: 2,
        status: 'warning',
        color: 'yellow',
        video_duration_seconds: 4,
        audio_duration_seconds: 4.42,
        subtitle_duration_seconds: 4,
        audio_video_delta_seconds: 0.42,
        subtitle_video_delta_seconds: 0,
        audio_subtitle_delta_seconds: 0.42,
        issues: [{ code: 'dialogue_audio_tail_padding', message: '配音需复核' }],
      },
    ],
  };

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === '/api/v1/llm/configs') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/workflow/status/wf-health') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow_id: 'wf-health',
          title: '云灯邮局 第二集',
          status: 'active',
          current_step: 9,
          completed_steps: [1, 2, 3, 4, 5, 6, 7, 8],
          novel_id: 'novel-001',
          chapter_id: 'chapter-002',
          script_id: 'script-002',
          storyboard_id: 'storyboard-002',
          video_jobs: [{ id: 'video-001', status: 'succeeded', novel_id: 'novel-001', chapter_id: 'chapter-002', script_id: 'script-002', storyboard_id: 'storyboard-002' }],
          tts_jobs: [{ id: 'tts-001', status: 'succeeded', novel_id: 'novel-001', chapter_id: 'chapter-002', script_id: 'script-002', storyboard_id: 'storyboard-002' }],
          subtitle_tracks: [{ id: 'subtitle-001', novel_id: 'novel-001', chapter_id: 'chapter-002', script_id: 'script-002', storyboard_id: 'storyboard-002' }],
          synthesis_jobs: [{
            id: 'synthesis-001',
            manifest_url: '/static/exports/synthesis-001.json',
            output_url: '/static/exports/final-synthesis-001.mp4',
            segment_count: 2,
            duration_seconds: 8,
            extra_data: {
              render_status: 'rendered',
              render_backend: 'local_artifact_package',
              media_sync_health: mediaSyncHealth,
              render_artifacts: {
                preview_url: '/static/exports/synthesis-001-preview.html',
                srt_url: '/static/exports/synthesis-001.srt',
                timeline_url: '/static/exports/synthesis-001-timeline.json',
                render_manifest_url: '/static/exports/synthesis-001-render.json',
              },
            },
          }],
          metadata: {},
        }),
      });
      return;
    }

    if (path === '/api/v1/workflow/wf-health/render/preflight') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow_id: 'wf-health',
          synthesis_job_id: 'synthesis-001',
          ready: true,
          blocking_issue_count: 0,
          issue_count: 0,
          issues: [],
          segment_count: 2,
          duration_seconds: 8,
          media_sync_health: mediaSyncHealth,
        }),
      });
      return;
    }

    if (path === '/api/v1/shots/storyboard/storyboard-002') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'shot-001',
            shot_number: 1,
            duration: 4,
            prompt: '孙剑举起铜铃',
            dialogue: '孙剑：我来确认出口。',
            video_status: 'succeeded',
            audio_status: 'succeeded',
            extra_data: {
              consistency_gap_report: {
                required: {
                  character_reference: true,
                  visual_dna: true,
                  multi_view: true,
                  costume_lock: true,
                  prop_lock: true,
                },
                present: {
                  character_reference: true,
                  visual_dna: false,
                  multi_view_count: 1,
                  required_multi_view_count: 3,
                  costume_lock: false,
                  prop_lock: true,
                },
                missing: ['visual_dna', 'multi_view', 'costume_lock'],
              },
            },
          },
        ]),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: request.method() === 'GET' ? '[]' : '{}',
    });
  });

  await page.goto('/workflow?workflow_id=wf-health');
  await expect(page.getByText('音频/字幕/视频时长一致性体检')).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId('workflow-media-sync-health')).toContainText('黄 1');
  await expect(page.getByTestId('workflow-media-sync-health')).toContainText('镜头 2');
  await expect(page.getByTestId('workflow-media-sync-health')).toContainText('音频差 0.42s');

  await page.getByRole('button', { name: /6\. 镜头/ }).click();
  await expect(page.getByText('一致性缺口')).toBeVisible();
  await expect(page.getByTestId('shot-consistency-gaps-shot-001')).toContainText('视觉 DNA 缺');
  await expect(page.getByTestId('shot-consistency-gaps-shot-001')).toContainText('多视图 1/3');
  await expect(page.getByTestId('shot-consistency-gaps-shot-001')).toContainText('服装锁缺');
});

test('workflow synthesis only sends latest successful tts jobs per shot', async ({ page }) => {
  let concatRequest: Record<string, unknown> | null = null;

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === '/api/v1/llm/configs') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/workflow/status/wf-tts-filter') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow_id: 'wf-tts-filter',
          title: '雨巷铜铃 第一集',
          status: 'active',
          current_step: 9,
          completed_steps: [1, 2, 3, 4, 5, 6, 7, 8],
          novel_id: 'novel-001',
          chapter_id: 'chapter-001',
          script_id: 'script-001',
          storyboard_id: 'storyboard-001',
          video_jobs: [
            { id: 'video-001', status: 'succeeded', video_url: '/static/video-001.mp4', novel_id: 'novel-001', chapter_id: 'chapter-001', script_id: 'script-001', storyboard_id: 'storyboard-001', shot_id: 'shot-001' },
            { id: 'video-002', status: 'succeeded', video_url: '/static/video-002.mp4', novel_id: 'novel-001', chapter_id: 'chapter-001', script_id: 'script-001', storyboard_id: 'storyboard-001', shot_id: 'shot-002' },
          ],
          tts_jobs: [
            { id: 'tts-old-failed', status: 'failed', audio_url: null, created_at: '2026-07-08 06:57:35', chapter_id: 'chapter-001', script_id: 'script-001', storyboard_id: 'storyboard-001', shot_id: 'shot-001' },
            { id: 'tts-shot-001-ok', status: 'succeeded', audio_url: '/static/audio-001.mp3', created_at: '2026-07-08 07:20:52', chapter_id: 'chapter-001', script_id: 'script-001', storyboard_id: 'storyboard-001', shot_id: 'shot-001' },
            { id: 'tts-shot-002-ok', status: 'succeeded', audio_url: '/static/audio-002.mp3', created_at: '2026-07-08 07:20:54', chapter_id: 'chapter-001', script_id: 'script-001', storyboard_id: 'storyboard-001', shot_id: 'shot-002' },
            { id: 'tts-shot-002-failed-late', status: 'failed', audio_url: null, created_at: '2026-07-08 07:21:54', chapter_id: 'chapter-001', script_id: 'script-001', storyboard_id: 'storyboard-001', shot_id: 'shot-002' },
          ],
          subtitle_tracks: [],
          synthesis_jobs: [],
          metadata: {},
        }),
      });
      return;
    }

    if (path === '/api/v1/workflow/concatenate/wf-tts-filter' && request.method() === 'POST') {
      concatRequest = request.postData() ? JSON.parse(request.postData() || '{}') : {};
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: 'synthesis-001',
          manifest_url: '/static/exports/synthesis-001.json',
          output_url: '/static/dev/final-synthesis-001.mp4',
          segment_count: 2,
          duration_seconds: 8,
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: request.method() === 'GET' ? '[]' : '{}',
    });
  });

  await page.goto('/workflow?workflow_id=wf-tts-filter');
  await expect(page.getByText('生成连续成片')).toBeVisible({ timeout: 10_000 });
  await page.getByRole('button', { name: '生成连续成片' }).click();

  await expect.poll(() => concatRequest).not.toBeNull();
  expect(concatRequest?.tts_job_ids).toEqual(['tts-shot-001-ok', 'tts-shot-002-ok']);
});

test('workflow export step keeps final mp4 links and media sync health visible', async ({ page }) => {
  const mediaSyncHealth = {
    status: 'blocking',
    summary: { green: 0, yellow: 1, red: 1, segment_count: 2 },
    thresholds: { green_max_delta_seconds: 0.15, yellow_max_delta_seconds: 0.75 },
    segments: [
      {
        index: 1,
        shot_number: 7,
        status: 'blocking',
        color: 'red',
        video_duration_seconds: 4,
        audio_duration_seconds: 2.59,
        subtitle_duration_seconds: 4,
        audio_video_delta_seconds: 1.41,
        subtitle_video_delta_seconds: 0,
        audio_subtitle_delta_seconds: 1.41,
        issues: [],
      },
      {
        index: 2,
        shot_number: 8,
        status: 'warning',
        color: 'yellow',
        video_duration_seconds: 4,
        audio_duration_seconds: 3.49,
        subtitle_duration_seconds: 4,
        audio_video_delta_seconds: 0.51,
        subtitle_video_delta_seconds: 0,
        audio_subtitle_delta_seconds: 0.51,
        issues: [],
      },
    ],
  };

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === '/api/v1/llm/configs') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/workflow/status/wf-export-health') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow_id: 'wf-export-health',
          title: '雨巷铜铃 第一集',
          status: 'active',
          current_step: 10,
          completed_steps: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
          novel_id: 'novel-001',
          chapter_id: 'chapter-001',
          script_id: 'script-001',
          storyboard_id: 'storyboard-001',
          video_jobs: [
            { id: 'video-001', status: 'succeeded', video_url: '/static/video-001.mp4', novel_id: 'novel-001', chapter_id: 'chapter-001', script_id: 'script-001', storyboard_id: 'storyboard-001', shot_id: 'shot-001' },
            { id: 'video-002', status: 'succeeded', video_url: '/static/video-002.mp4', novel_id: 'novel-001', chapter_id: 'chapter-001', script_id: 'script-001', storyboard_id: 'storyboard-001', shot_id: 'shot-002' },
          ],
          tts_jobs: [
            { id: 'tts-001', status: 'succeeded', audio_url: '/static/audio-001.mp3', created_at: '2026-07-08 07:20:52', chapter_id: 'chapter-001', script_id: 'script-001', storyboard_id: 'storyboard-001', shot_id: 'shot-001' },
            { id: 'tts-002', status: 'succeeded', audio_url: '/static/audio-002.mp3', created_at: '2026-07-08 07:20:54', chapter_id: 'chapter-001', script_id: 'script-001', storyboard_id: 'storyboard-001', shot_id: 'shot-002' },
          ],
          subtitle_tracks: [],
          synthesis_jobs: [{
            id: 'synthesis-001',
            manifest_url: '/static/exports/synthesis-001.json',
            output_url: '/static/exports/final-synthesis-001.mp4',
            segment_count: 2,
            duration_seconds: 8,
            extra_data: {
              render_status: 'rendered',
              render_backend: 'ffmpeg_local',
              media_sync_health: mediaSyncHealth,
              render_artifacts: {
                output_url: '/static/exports/final-synthesis-001.mp4',
                srt_url: '/static/exports/final-synthesis-001.srt',
                timeline_url: '/static/exports/synthesis-001-timeline.json',
                render_manifest_url: '/static/exports/synthesis-001-render.json',
              },
            },
          }],
          metadata: {},
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: request.method() === 'GET' ? '[]' : '{}',
    });
  });

  await page.goto('/workflow?workflow_id=wf-export-health');
  await expect(page.getByRole('button', { name: '真实 MP4' })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole('link', { name: '打开真实 MP4' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'SRT 字幕' })).toBeVisible();
  await expect(page.getByText('音频/字幕/视频时长一致性体检')).toBeVisible();
  await expect(page.getByTestId('workflow-media-sync-health')).toContainText('红 1');
  await expect(page.getByTestId('workflow-media-sync-health')).toContainText('镜头 7');
  await expect(page.getByTestId('workflow-media-sync-health')).toContainText('音频差 1.41s');
});

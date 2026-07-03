import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `shot-review-user-${Date.now()}`;
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

test('studio shot review renders evidence and regenerates failed shots before concatenate', async ({ page }) => {
  const regenerateRequests: Array<Record<string, unknown>> = [];
  const concatenateRequests: Array<Record<string, unknown>> = [];
  const renderRequests: Array<Record<string, unknown>> = [];
  const calls: string[] = [];
  let shotReviewCalls = 0;

  const reviewPayload = {
    workflow_id: 'wf-review',
    latest_render_artifacts: {
      output_url: '/static/review/existing-output.mp4',
      source_manifest_url: '/static/review/existing-manifest.json',
      preview_url: '/static/review/existing-preview.html',
      srt_url: '/static/review/existing.srt',
      timeline_url: '/static/review/existing-timeline.json',
      render_manifest_url: '/static/review/existing-render.json',
    },
    shots: [
      {
        shot_id: 'shot-1',
        shot_number: 1,
        video_url: '/static/review/shot-1.mp4',
        status: 'succeeded',
        duration: 4,
        subtitle_text: '孙剑推开云上列车的舱门。',
        character_names: ['孙剑'],
        evidence: {
          strategy_routing: 'draft_fast',
          reference_package_mode: '角色参考包',
          reference_package: {
            mode: 'multimodal',
            image_count: 3,
            video_count: 1,
            dropped: [],
          },
          generation_preflight: '预检通过',
          visual_consistency: {
            score: 74,
            status: 'needs_review',
            reference_asset_id: 'asset-front-1',
            frame_count: 2,
            blocking: false,
          },
        },
        visual_consistency_score: 74,
        regeneration_count: 0,
      },
      {
        shot_id: 'shot-2',
        shot_number: 2,
        video_url: null,
        status: 'failed',
        duration: 4,
        subtitle_text: '阿月在雨幕里回头。',
        character_names: ['阿月'],
        evidence: {
          strategy_routing: 'draft_fast',
          reference_package_mode: '三视图参考包',
          generation_preflight: '视频生成超时',
        },
        regeneration_count: 1,
      },
    ],
  };

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === '/api/v1/workflow/wf-review/shot-review') {
      shotReviewCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(reviewPayload),
      });
      return;
    }

    if (path === '/api/v1/workflow/wf-review/regenerate-shots' && request.method() === 'POST') {
      calls.push('regenerate');
      regenerateRequests.push(request.postDataJSON());
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          regenerated_shot_ids: ['shot-2'],
          video_job_ids: ['video-shot-2-new'],
          tts_job_ids: ['tts-shot-2-new'],
          skipped: [],
          ready_for_concatenate: true,
        }),
      });
      return;
    }

    if (path === '/api/v1/workflow/concatenate/wf-review' && request.method() === 'POST') {
      calls.push('concatenate');
      concatenateRequests.push(request.postDataJSON());
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: 'synthesis-review',
          manifest_url: '/static/review/manifest-after-regenerate.json',
          output_url: '/static/review/output-after-regenerate.mp4',
          segment_count: 2,
        }),
      });
      return;
    }

    if (path === '/api/v1/workflow/wf-review/render/preflight') {
      calls.push('preflight');
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ready: true, issues: [], timeline_id: 'timeline-review' }),
      });
      return;
    }

    if (path === '/api/v1/workflow/wf-review/render' && request.method() === 'POST') {
      calls.push('render');
      renderRequests.push(request.postDataJSON());
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'succeeded',
          message: '镜头重生审阅包已生成',
          preview_url: '/static/review/preview-after-regenerate.html',
          srt_url: '/static/review/review-after-regenerate.srt',
          timeline_url: '/static/review/timeline-after-regenerate.json',
          render_manifest_url: '/static/review/render-after-regenerate.json',
        }),
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/studio/shot-review?workflow_id=wf-review');

  await expect(page.getByRole('heading', { name: '镜头审阅' })).toBeVisible();
  await expect(page.getByText('镜头 1')).toBeVisible();
  await expect(page.getByText('孙剑推开云上列车的舱门。')).toBeVisible();
  await expect(page.getByText('draft_fast').first()).toBeVisible();
  await expect(page.getByText('角色参考包')).toBeVisible();
  await expect(page.getByTestId('shot-review-reference-package-shot-1')).toContainText('3图');
  await expect(page.getByTestId('shot-review-reference-package-shot-1')).toContainText('1视频');
  await expect(page.getByText('预检通过')).toBeVisible();
  await expect(page.getByTestId('shot-review-visual-consistency-shot-1')).toContainText('74分');
  await expect(page.getByTestId('shot-review-visual-consistency-shot-1')).toContainText('待人审');
  await expect(page.getByTestId('shot-review-visual-consistency-shot-1')).toContainText('抽帧 2');
  await expect(page.getByText('阿月在雨幕里回头。')).toBeVisible();
  await expect(page.getByText('视频生成超时')).toBeVisible();
  await expect(page.getByText('重生 1 次')).toBeVisible();
  await expect(page.getByRole('link', { name: '打开审阅包' })).toHaveAttribute('href', /existing-preview\.html$/);
  await expect(page.getByRole('link', { name: '查看成片清单' })).toHaveAttribute('href', /existing-manifest\.json$/);
  await expect(page.getByRole('link', { name: '查看字幕' })).toHaveAttribute('href', /existing\.srt$/);
  await expect(page.getByRole('link', { name: '查看时间线' })).toHaveAttribute('href', /existing-timeline\.json$/);
  await expect(page.getByRole('link', { name: '查看渲染清单' })).toHaveAttribute('href', /existing-render\.json$/);
  await expect(page.getByRole('link', { name: '打开成片' })).toHaveAttribute('href', /existing-output\.mp4$/);

  await page.getByRole('button', { name: '仅重生失败' }).click();

  await expect.poll(() => regenerateRequests.length).toBe(1);
  expect(regenerateRequests[0]).toMatchObject({ filter: 'failed' });
  await expect.poll(() => concatenateRequests.length).toBe(1);
  expect(concatenateRequests[0]).toMatchObject({
    video_job_ids: ['video-shot-2-new'],
    tts_job_ids: ['tts-shot-2-new'],
    quality_profile: 'review',
  });
  await expect.poll(() => renderRequests.length).toBe(1);
  expect(renderRequests[0]).toMatchObject({
    synthesis_job_id: 'synthesis-review',
    render_backend: 'local_artifact_package',
    quality_profile: 'review',
    use_editable_timeline: true,
  });
  await expect.poll(() => shotReviewCalls).toBeGreaterThanOrEqual(2);
  expect(calls).toEqual(['regenerate', 'concatenate', 'preflight', 'render']);
  await expect(page.getByText('已刷新连续成片并生成审阅包')).toBeVisible();
  await expect(page.getByRole('link', { name: '打开审阅包' })).toHaveAttribute('href', /preview-after-regenerate\.html$/);
  await expect(page.getByRole('link', { name: '查看成片清单' })).toHaveAttribute('href', /manifest-after-regenerate\.json$/);
  await expect(page.getByRole('link', { name: '查看字幕' })).toHaveAttribute('href', /review-after-regenerate\.srt$/);
  await expect(page.getByRole('link', { name: '查看时间线' })).toHaveAttribute('href', /timeline-after-regenerate\.json$/);
  await expect(page.getByRole('link', { name: '查看渲染清单' })).toHaveAttribute('href', /render-after-regenerate\.json$/);
  await expect(page.getByRole('link', { name: '打开成片' })).toHaveAttribute('href', /output-after-regenerate\.mp4$/);
});

test('studio shot review shows waiting state when regenerated shots are still running', async ({ page }) => {
  const regenerateRequests: Array<Record<string, unknown>> = [];
  const calls: string[] = [];
  let shotReviewCalls = 0;

  const failedShot = {
    shot_id: 'shot-waiting',
    shot_number: 3,
    video_url: null,
    status: 'failed',
    duration: 4,
    subtitle_text: '雨停后，阿月重新点亮车灯。',
    character_names: ['阿月'],
    evidence: {
      strategy_routing: 'draft_fast',
      reference_package_mode: '角色参考包',
      generation_preflight: '视频生成失败',
    },
    regeneration_count: 1,
  };

  const runningShot = {
    ...failedShot,
    latest_video_job_id: 'video-shot-waiting-new',
    status: 'running',
    evidence: {
      ...failedShot.evidence,
      generation_preflight: '重生任务已提交',
    },
    regeneration_count: 2,
  };

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === '/api/v1/workflow/wf-waiting/shot-review') {
      shotReviewCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow_id: 'wf-waiting',
          shots: [shotReviewCalls === 1 ? failedShot : runningShot],
        }),
      });
      return;
    }

    if (path === '/api/v1/workflow/wf-waiting/regenerate-shots' && request.method() === 'POST') {
      calls.push('regenerate');
      regenerateRequests.push(request.postDataJSON());
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          regenerated_shot_ids: ['shot-waiting'],
          video_job_ids: ['video-shot-waiting-new'],
          tts_job_ids: [],
          skipped: [],
          ready_for_concatenate: false,
        }),
      });
      return;
    }

    if (path === '/api/v1/workflow/concatenate/wf-waiting' || path === '/api/v1/workflow/wf-waiting/render') {
      calls.push(path);
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/studio/shot-review?workflow_id=wf-waiting');

  await expect(page.getByText('雨停后，阿月重新点亮车灯。')).toBeVisible();
  await page.getByRole('button', { name: '仅重生失败' }).click();

  await expect.poll(() => regenerateRequests.length).toBe(1);
  expect(regenerateRequests[0]).toMatchObject({ filter: 'failed' });
  await expect.poll(() => shotReviewCalls).toBeGreaterThanOrEqual(2);
  await expect(page.getByTestId('shot-review-card-shot-waiting')).toContainText('生成中');
  await expect(page.getByTestId('shot-review-card-shot-waiting')).toContainText('等待视频/声音完成后再合成');
  await expect(page.getByText('重生任务已提交，等待视频/声音完成后再合成')).toBeVisible();
  expect(calls).toEqual(['regenerate']);
});

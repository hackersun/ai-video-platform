import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

async function installProducerRoutes(page: any, options: {
  configs?: any[];
  shots?: any[];
  onGenerateMediaBatch?: (body: any) => void;
} = {}) {
  const configs = options.configs ?? [];
  const shots = options.shots ?? [
    { id: 'shot-001', shot_number: 1, dialogue: '（旁白）少年推门踏入风雪。', image_url: null },
  ];

  await page.route('**/api/v1/**', async (route: any) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === '/api/v1/novels') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'novel-001', title: '逆天至尊', genre: '玄幻' }]),
      });
      return;
    }

    if (path === '/api/v1/llm/configs') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(configs) });
      return;
    }

    if (path === '/api/v1/workflow' && request.method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          workflow_id: 'wf-001',
          title: '第一章 制片工程',
          status: 'active',
          current_step: 6,
          completed_steps: [1, 2, 3, 4, 5, 6],
          novel_id: 'novel-001',
          chapter_id: 'chapter-001',
          script_id: 'script-001',
          storyboard_id: 'storyboard-001',
          video_job_ids: [],
          tts_job_ids: [],
          synthesis_job_ids: [],
        }]),
      });
      return;
    }

    if (path === '/api/v1/workflow/status/wf-001') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow_id: 'wf-001',
          title: '第一章 制片工程',
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
        }),
      });
      return;
    }

    if (path === '/api/v1/short-video/workflow/wf-001/readiness') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ summary: { ready: true, score: 90, blocker_count: 0, warning_count: 0, shot_count: shots.length }, recommendations: [] }),
      });
      return;
    }

    if (path === '/api/v1/chapters/novel/novel-001') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'chapter-001', title: '第一章 少年出山', chapter_number: 1 }]),
      });
      return;
    }

    if (path === '/api/v1/chapters/chapter-001/production-status') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ script_id: 'script-001', storyboard_id: 'storyboard-001', shot_count: shots.length, has_script: true, has_storyboard: true }),
      });
      return;
    }

    if (path === '/api/v1/story-bibles') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/batch/list') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ total: 0, jobs: [] }) });
      return;
    }

    if (path === '/api/v1/shots/storyboard/storyboard-001') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(shots) });
      return;
    }

    if (path === '/api/v1/workflow/wf-001/step') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
      return;
    }

    if (path === '/api/v1/production-control/workflow/wf-001/producer-assistant') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ summary: {}, actions: [] }) });
      return;
    }

    if (path === '/api/v1/production-control/workflow/wf-001/asset-locks') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ lock_count: 1 }) });
      return;
    }

    if (path === '/api/v1/short-video/workflow/wf-001/refresh-contracts') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ refreshed: true }) });
      return;
    }

    if (path === '/api/v1/workflow/wf-001/generate-media-batch') {
      options.onGenerateMediaBatch?.(request.postData() ? JSON.parse(request.postData() || '{}') : {});
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow_id: 'wf-001',
          strategy: 'separate_video_tts',
          created_count: 1,
          video_job_ids: ['video-001'],
          tts_job_ids: ['tts-001'],
          subtitle_track_ids: ['sub-001'],
          ready_for_concatenate: false,
          pending_video_job_ids: ['video-001'],
          pending_tts_job_ids: [],
        }),
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });
}

test.beforeEach(async ({ page }) => {
  const userId = `producer-preview-safety-user-${Date.now()}`;
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

test('producer blocks preview generation until current storyboard shots are loaded and selected', async ({ page }) => {
  const mediaBatchRequests: any[] = [];
  await installProducerRoutes(page, { onGenerateMediaBatch: (body) => mediaBatchRequests.push(body) });

  await page.goto('/producer?workflow_id=wf-001');
  await page.getByRole('button', { name: /一键生成本集草片/ }).click();

  await expect(page.getByText('请先加载镜头并选择关键镜头', { exact: true })).toBeVisible();
  await page.waitForTimeout(600);
  expect(mediaBatchRequests).toEqual([]);
});

test('producer exposes multi-speaker shot risk before submitting video and TTS', async ({ page }) => {
  await installProducerRoutes(page, {
    shots: [
      { id: 'shot-001', shot_number: 1, dialogue: '林岚：他们不记得了。\n许澈：连钟楼都忘了。', image_url: null },
    ],
  });

  await page.goto('/producer?workflow_id=wf-001');
  await page.getByRole('button', { name: /加载镜头/ }).click();

  const shotCard = page.getByTestId('producer-shot-card-shot-001');
  await expect(shotCard).toBeVisible();
  await expect(shotCard).toHaveAttribute('data-speaker-count', '2');
  await expect(shotCard).toContainText('双人对白');
  await expect(shotCard).toContainText('林岚');
  await expect(shotCard).toContainText('许澈');
});

test('producer warns when no Volcano or SD image reference model is configured', async ({ page }) => {
  await installProducerRoutes(page, {
    configs: [{
      id: 'minimax-image-config',
      model_id: 'image-01',
      config_model_id: 'minimax-image-01',
      api_model_id: 'image-01',
      model_type: 'image-generation',
      model_capabilities: ['text-to-image'],
      provider_id: 'minimax',
      provider_name: 'MiniMax',
      model_name: 'MiniMax图像生成',
      name: '默认 MiniMax 图像',
      is_default: true,
      test_status: 'success',
      key_available: true,
    }],
  });

  await page.goto('/producer?workflow_id=wf-001');

  await expect(page.getByText('未配置火山/SD1.5参考图模型')).toBeVisible();
  await expect(page.getByText('当前参考图会使用 MiniMax图像生成')).toBeVisible();
});

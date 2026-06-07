import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `video-history-backfill-user-${Date.now()}`;
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

test('succeeded history videos can be attached back to the current shot', async ({ page }) => {
  const shotUpdates: Array<Record<string, unknown>> = [];
  const videoHistoryRequests: string[] = [];
  const mediaHistoryRequests: string[] = [];
  let shotVideoUrl = '';

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === '/api/v1/llm/api-key/volcano' || path === '/api/v1/llm/api-key/volcano_agent_plan') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ configured: true, dev_mode: true }) });
      return;
    }

    if (path === '/api/v1/llm/models') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          id: 'video-model-001',
          model_id: 'doubao-seedance-test',
          model_name: '已验证视频模型',
          model_name_cn: '已验证视频模型',
          model_type: 'video',
          capabilities: ['video'],
        }]),
      });
      return;
    }

    if (path === '/api/v1/llm/configs') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          id: 'config-video-001',
          provider_id: 'volcano',
          config_model_id: 'video-model-001',
          api_model_id: 'doubao-seedance-test',
          model_id: 'doubao-seedance-test',
          model_type: 'video',
          is_default: true,
          test_status: 'success',
        }]),
      });
      return;
    }

    if (path === '/api/v1/external/configs') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/novels') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([{ id: 'novel-001', title: '逆天至尊' }]) });
      return;
    }

    if (path === '/api/v1/chapters/novel/novel-001') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'chapter-001', novel_id: 'novel-001', title: '第一章 少年醒来', chapter_number: 1 }]),
      });
      return;
    }

    if (path === '/api/v1/scripts' && request.method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'script-001', title: '第一章 剧本', novel_id: 'novel-001', chapter_id: 'chapter-001' }]),
      });
      return;
    }

    if (path === '/api/v1/storyboards/script/script-001') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'storyboard-001', title: '第一场', script_id: 'script-001', novel_id: 'novel-001', chapter_id: 'chapter-001', shot_count: 1 }]),
      });
      return;
    }

    if (path === '/api/v1/storyboards/storyboard-001') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'storyboard-001', title: '第一场', script_id: 'script-001', novel_id: 'novel-001', chapter_id: 'chapter-001', shot_count: 1 }),
      });
      return;
    }

    if (path === '/api/v1/shots/storyboard/storyboard-001') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'shot-001', storyboard_id: 'storyboard-001', shot_number: 1, duration: 4, prompt: '少年在宗门广场醒来', video_status: shotVideoUrl ? 'succeeded' : 'pending', video_url: shotVideoUrl }]),
      });
      return;
    }

    if (path === '/api/v1/shots/shot-001' && request.method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'shot-001',
          storyboard_id: 'storyboard-001',
          shot_number: 1,
          duration: 4,
          prompt: '少年在宗门广场醒来',
          dialogue: '少年：我还活着？',
          video_status: shotVideoUrl ? 'succeeded' : 'pending',
          video_url: shotVideoUrl,
          extra_data: { entity_refs: { characters: [], scenes: [], props: [] } },
        }),
      });
      return;
    }

    if (path === '/api/v1/shots/shot-001/production-context') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ production_context: {} }) });
      return;
    }

    if (path === '/api/v1/assets/view-presets') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ presets: [] }) });
      return;
    }

    if (path === '/api/v1/characters') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/video/jobs') {
      videoHistoryRequests.push(url.search);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'video-job-001',
            task_id: 'task-video-001',
            title: '镜头1 成片版本A',
            prompt: '少年在宗门广场醒来',
            status: 'succeeded',
            progress: 100,
            video_url: '/static/dev/video-from-history.mp4',
            shot_id: 'shot-001',
            duration: 4,
            resolution: '720p',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
          {
            id: 'video-job-failed',
            title: '失败版本',
            status: 'failed',
            progress: 0,
            video_url: '/static/dev/failed.mp4',
            shot_id: 'shot-001',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ]),
      });
      return;
    }

    if (path === '/api/v1/media/jobs') {
      mediaHistoryRequests.push(url.search);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'media-job-001',
            task_id: 'task-media-001',
            task_type: 'shot_audio_video',
            media_type: 'audio_video',
            title: '镜头1 音视频直生版本',
            prompt: '少年在宗门广场醒来并开口',
            status: 'succeeded',
            progress: 100,
            output_video_url: '/static/dev/media-direct.mp4',
            shot_id: 'shot-001',
            duration_seconds: 4,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            extra_data: {},
          },
          {
            id: 'media-job-pending',
            task_id: 'task-media-pending',
            task_type: 'shot_audio_video',
            media_type: 'audio_video',
            title: '等待版本',
            status: 'running',
            progress: 20,
            output_video_url: '/static/dev/pending.mp4',
            shot_id: 'shot-001',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            extra_data: {},
          },
        ]),
      });
      return;
    }

    if (path === '/api/v1/shots/shot-001' && request.method() === 'PUT') {
      const body = request.postData() ? JSON.parse(request.postData() || '{}') : {};
      shotUpdates.push(body);
      shotVideoUrl = String(body.video_url || '');
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'shot-001',
          storyboard_id: 'storyboard-001',
          shot_number: 1,
          duration: 4,
          prompt: '少年在宗门广场醒来',
          video_status: 'succeeded',
          video_url: shotVideoUrl,
          extra_data: {},
        }),
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/video-generation?novel_id=novel-001&chapter_id=chapter-001&script_id=script-001&storyboard_id=storyboard-001&shot_id=shot-001');

  await expect(page.getByText('镜头1 成片版本A')).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText('镜头1 音视频直生版本')).toBeVisible();

  await page.getByLabel('设为镜头视频：镜头1 成片版本A').click();
  await expect.poll(() => shotUpdates.length, { timeout: 3_000 }).toBe(1);
  expect(shotUpdates[0]).toMatchObject({
    video_url: '/static/dev/video-from-history.mp4',
    video_status: 'succeeded',
  });
  await expect.poll(() => videoHistoryRequests.length > 1).toBeTruthy();

  await page.getByLabel('设为镜头视频：镜头1 音视频直生版本').click();
  await expect.poll(() => shotUpdates.length, { timeout: 3_000 }).toBe(2);
  expect(shotUpdates[1]).toMatchObject({
    video_url: '/static/dev/media-direct.mp4',
    video_status: 'succeeded',
  });
  await expect.poll(() => mediaHistoryRequests.length > 1).toBeTruthy();

  await expect(page.getByLabel('设为镜头视频：失败版本')).toHaveCount(0);
  await expect(page.getByLabel('设为镜头视频：等待版本')).toHaveCount(0);
});

import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `producer-batch-evidence-user-${Date.now()}`;
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

test('producer shows batch item evidence with shot status outputs and failure reasons', async ({ page }) => {
  const itemRequests: string[] = [];

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === '/api/v1/novels') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'novel-001', title: '逆天至尊', genre: '玄幻', description: '少年逆境崛起。' }]),
      });
      return;
    }

    if (path === '/api/v1/llm/configs') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/workflow') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          workflow_id: 'wf-001',
          title: '逆天至尊 第一章',
          status: 'active',
          current_step: 6,
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
          recommendations: ['先处理失败镜头。'],
        }),
      });
      return;
    }

    if (path === '/api/v1/chapters/novel/novel-001') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'chapter-001', title: '第一章 少年出山', chapter_number: 1, content: '少年踏入风雪。' }]),
      });
      return;
    }

    if (path === '/api/v1/chapters/chapter-001/production-status') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ script_id: 'script-001', storyboard_id: 'storyboard-001', shot_count: 2 }),
      });
      return;
    }

    if (path === '/api/v1/story-bibles') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/batch/list') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total: 1,
          jobs: [{
            id: 'batch-001',
            job_type: 'video',
            title: '第一章批量视频',
            status: 'failed',
            total_count: 2,
            pending_count: 0,
            running_count: 0,
            succeeded_count: 1,
            failed_count: 1,
            skipped_count: 0,
            storyboard_id: 'storyboard-001',
            shot_ids: ['shot-001', 'shot-002'],
            workflow_id: 'wf-001',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          }],
        }),
      });
      return;
    }

    if (path === '/api/v1/batch/batch-001/progress') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: 'batch-001',
          status: 'failed',
          total_count: 2,
          pending_count: 0,
          running_count: 0,
          succeeded_count: 1,
          failed_count: 1,
          skipped_count: 0,
          progress_percent: 100,
          message: '已完成 1/2, 失败 1',
        }),
      });
      return;
    }

    if (path === '/api/v1/batch/batch-001/items') {
      itemRequests.push(url.search);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total: 2,
          items: [
            {
              id: 'item-001',
              batch_job_id: 'batch-001',
              shot_id: 'shot-001',
              status: 'succeeded',
              image_url: null,
              video_url: '/static/generated/videos/shot-001.mp4',
              audio_url: null,
              image_job_id: null,
              video_job_id: 'video-job-001',
              tts_job_id: null,
              error_message: null,
              sort_order: 1,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            },
            {
              id: 'item-002',
              batch_job_id: 'batch-001',
              shot_id: 'shot-002',
              status: 'failed',
              image_url: null,
              video_url: null,
              audio_url: null,
              image_job_id: null,
              video_job_id: null,
              tts_job_id: null,
              error_message: '参考图不是公网地址，云端视频模型无法读取',
              sort_order: 2,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            },
          ],
        }),
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/producer?workflow_id=wf-001');
  await page.getByText('第一章批量视频').click();

  await expect.poll(() => itemRequests.length).toBe(1);
  const panel = page.getByTestId('producer-batch-items');
  await expect(panel).toContainText('镜头 shot-001');
  await expect(panel).toContainText('已完成');
  await expect(panel).toContainText('video-job-001');
  await expect(panel).toContainText('镜头 shot-002');
  await expect(panel).toContainText('参考图不是公网地址');
});

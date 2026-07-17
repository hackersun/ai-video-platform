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

test('producer batch image action executes selected shot generation and records item result', async ({ page }) => {
  const generatedShotIds: string[] = [];
  const imageGenerateRequests: Array<Record<string, unknown>> = [];
  const itemUpdates: Array<{ url: string; body: any }> = [];

  await page.route('**/api/v1/**', async (route) => {
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
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          id: 'image-config-001',
          model_id: 'sd-1.5',
          model_type: 'image',
          model_capabilities: ['image-generation'],
          provider_id: 'volcano',
          provider_name: '火山方舟',
          model_name: 'SD1.5',
          name: '默认 SD1.5 参考图',
          is_default: true,
          test_status: 'success',
          key_available: true,
        }]),
      });
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
        body: JSON.stringify({ summary: { ready: true, score: 90, blocker_count: 0, warning_count: 0 }, recommendations: [] }),
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
        body: JSON.stringify({ script_id: 'script-001', storyboard_id: 'storyboard-001', shot_count: 2 }),
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
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'shot-001', shot_number: 1, image_url: null },
          { id: 'shot-002', shot_number: 2, image_url: null },
        ]),
      });
      return;
    }

    if (path === '/api/v1/batch/create') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'batch-002',
          job_type: 'image',
          title: '批量生成参考图 (1个)',
          status: 'pending',
          total_count: 1,
          pending_count: 1,
          running_count: 0,
          succeeded_count: 0,
          failed_count: 0,
          skipped_count: 0,
          storyboard_id: 'storyboard-001',
          shot_ids: ['shot-001'],
          workflow_id: 'wf-001',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }),
      });
      return;
    }

    if (path === '/api/v1/batch/batch-002/items') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total: 1,
          items: [{
            id: 'item-001',
            batch_job_id: 'batch-002',
            shot_id: 'shot-001',
            status: 'pending',
            image_url: null,
            video_url: null,
            audio_url: null,
            image_job_id: null,
            video_job_id: null,
            tts_job_id: null,
            error_message: null,
            sort_order: 0,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          }],
        }),
      });
      return;
    }

    if (path === '/api/v1/batch/batch-002/progress') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: 'batch-002',
          status: itemUpdates.length > 0 ? 'completed' : 'pending',
          total_count: 1,
          pending_count: itemUpdates.length > 0 ? 0 : 1,
          running_count: 0,
          succeeded_count: itemUpdates.length > 0 ? 1 : 0,
          failed_count: 0,
          skipped_count: 0,
          progress_percent: itemUpdates.length > 0 ? 100 : 0,
          message: itemUpdates.length > 0 ? '已完成 1/1' : '已完成 0/1',
        }),
      });
      return;
    }

    if (path === '/api/v1/shots/shot-001/generate-image') {
      generatedShotIds.push('shot-001');
      imageGenerateRequests.push(request.postData() ? JSON.parse(request.postData() || '{}') : {});
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          shot_id: 'shot-001',
          task_id: 'image-task-001',
          status: 'succeeded',
          image_url: '/static/generated/images/shot-001.jpg',
          image_asset_id: 'asset-001',
        }),
      });
      return;
    }

    if (path === '/api/v1/batch/batch-002/items/item-001' && request.method() === 'PUT') {
      const body = JSON.parse(request.postData() || '{}');
      itemUpdates.push({ url: request.url(), body });
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'item-001',
          batch_job_id: 'batch-002',
          shot_id: 'shot-001',
          status: body.status,
          image_url: body.image_url,
          video_url: null,
          audio_url: null,
          image_job_id: body.image_job_id,
          video_job_id: null,
          tts_job_id: null,
          error_message: body.error_message || null,
          sort_order: 0,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }),
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/producer?workflow_id=wf-001');
  await page.getByRole('button', { name: /加载镜头/ }).click();
  const shotCard = page.getByTestId('producer-shot-card-shot-001');
  await expect(shotCard).toBeVisible();
  await expect(shotCard).toHaveAttribute('aria-pressed', 'false');
  await shotCard.click();
  await expect(shotCard).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('button', { name: '批量生成参考图' })).toBeEnabled();
  await page.getByRole('button', { name: '批量生成参考图' }).click();

  await expect.poll(() => generatedShotIds).toEqual(['shot-001']);
  await expect.poll(() => imageGenerateRequests).toEqual([{ style: 'anime', model_config_id: 'image-config-001' }]);
  await expect.poll(() => itemUpdates.length).toBe(1);
  expect(itemUpdates[0].body).toMatchObject({
    status: 'succeeded',
    image_url: '/static/generated/images/shot-001.jpg',
    image_job_id: 'image-task-001',
  });
});

test('producer starts tts batch jobs after creating them', async ({ page }) => {
  const startedBatchIds: string[] = [];
  const batchCreateRequests: any[] = [];

  await page.route('**/api/v1/**', async (route) => {
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
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          id: 'voice-config-001',
          model_id: 'minimax-hd',
          model_type: 'tts',
          model_capabilities: ['text-to-speech'],
          provider_id: 'minimax',
          provider_name: 'MiniMax',
          model_name: 'MiniMax语音合成-HD',
          name: '默认 MiniMax HD',
          is_default: true,
          test_status: 'success',
          key_available: true,
        }]),
      });
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
        body: JSON.stringify({ summary: { ready: true, score: 90, blocker_count: 0, warning_count: 0 }, recommendations: [] }),
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
        body: JSON.stringify({ script_id: 'script-001', storyboard_id: 'storyboard-001', shot_count: 1 }),
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
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'shot-001', shot_number: 1, dialogue_text: '孙剑：我来确认出口。' }]),
      });
      return;
    }

    if (path === '/api/v1/batch/create') {
      batchCreateRequests.push(JSON.parse(request.postData() || '{}'));
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'batch-tts-001',
          job_type: 'tts',
          title: '批量生成配音 (1个)',
          status: 'pending',
          total_count: 1,
          pending_count: 1,
          running_count: 0,
          succeeded_count: 0,
          failed_count: 0,
          skipped_count: 0,
          storyboard_id: 'storyboard-001',
          shot_ids: ['shot-001'],
          workflow_id: 'wf-001',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }),
      });
      return;
    }

    if (path === '/api/v1/batch/batch-tts-001/start') {
      startedBatchIds.push('batch-tts-001');
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
      return;
    }

    if (path === '/api/v1/batch/batch-tts-001/progress') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: 'batch-tts-001',
          status: startedBatchIds.length > 0 ? 'running' : 'pending',
          total_count: 1,
          pending_count: startedBatchIds.length > 0 ? 0 : 1,
          running_count: startedBatchIds.length > 0 ? 1 : 0,
          succeeded_count: 0,
          failed_count: 0,
          skipped_count: 0,
          progress_percent: startedBatchIds.length > 0 ? 10 : 0,
          message: startedBatchIds.length > 0 ? '已启动' : '待启动',
        }),
      });
      return;
    }

    if (path === '/api/v1/batch/batch-tts-001/items') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total: 1,
          items: [{
            id: 'item-tts-001',
            batch_job_id: 'batch-tts-001',
            shot_id: 'shot-001',
            status: startedBatchIds.length > 0 ? 'running' : 'pending',
            image_url: null,
            video_url: null,
            audio_url: null,
            image_job_id: null,
            video_job_id: null,
            tts_job_id: null,
            error_message: null,
            sort_order: 0,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          }],
        }),
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/producer?workflow_id=wf-001');
  await page.getByRole('button', { name: /加载镜头/ }).click();
  await page.getByTestId('producer-shot-card-shot-001').click();
  await page.getByRole('button', { name: '批量生成配音' }).click();

  await expect.poll(() => batchCreateRequests).toEqual([
    expect.objectContaining({
      job_type: 'tts',
      extra_data: expect.objectContaining({
        model_config_id: 'voice-config-001',
        api_provider: 'minimax',
      }),
    }),
  ]);
  await expect.poll(() => startedBatchIds).toEqual(['batch-tts-001']);
});

test('producer sends selected video config when creating video batch jobs', async ({ page }) => {
  const batchCreateRequests: any[] = [];

  await page.route('**/api/v1/**', async (route) => {
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
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          id: 'video-config-001',
          model_id: 'seedance-1-5-pro',
          model_type: 'video',
          model_capabilities: ['image-to-video'],
          provider_id: 'volcano',
          provider_name: '火山引擎',
          model_name: '豆包Seedance-1.5-pro',
          name: '默认 Seedance 1.5 Pro',
          is_default: true,
          test_status: 'success',
          key_available: true,
        }]),
      });
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
        body: JSON.stringify({ summary: { ready: true, score: 90, blocker_count: 0, warning_count: 0 }, recommendations: [] }),
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
        body: JSON.stringify({ script_id: 'script-001', storyboard_id: 'storyboard-001', shot_count: 1 }),
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
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'shot-001', shot_number: 1, prompt: '少年踏入风雪。' }]),
      });
      return;
    }

    if (path === '/api/v1/batch/create') {
      batchCreateRequests.push(JSON.parse(request.postData() || '{}'));
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'batch-video-001',
          job_type: 'video',
          title: '批量生成视频 (1个)',
          status: 'pending',
          total_count: 1,
          pending_count: 1,
          running_count: 0,
          succeeded_count: 0,
          failed_count: 0,
          skipped_count: 0,
          storyboard_id: 'storyboard-001',
          shot_ids: ['shot-001'],
          workflow_id: 'wf-001',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }),
      });
      return;
    }

    if (path === '/api/v1/batch/batch-video-001/start') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
      return;
    }

    if (path === '/api/v1/batch/batch-video-001/progress') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: 'batch-video-001',
          status: 'running',
          total_count: 1,
          pending_count: 0,
          running_count: 1,
          succeeded_count: 0,
          failed_count: 0,
          skipped_count: 0,
          progress_percent: 10,
          message: '已启动',
        }),
      });
      return;
    }

    if (path === '/api/v1/batch/batch-video-001/items') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total: 1,
          items: [{
            id: 'item-video-001',
            batch_job_id: 'batch-video-001',
            shot_id: 'shot-001',
            status: 'running',
            image_url: null,
            video_url: null,
            audio_url: null,
            image_job_id: null,
            video_job_id: 'video-job-001',
            tts_job_id: null,
            error_message: null,
            sort_order: 0,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          }],
        }),
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/producer?workflow_id=wf-001');
  await page.getByRole('button', { name: /加载镜头/ }).click();
  await page.getByTestId('producer-shot-card-shot-001').click();
  await page.getByRole('button', { name: '批量生成视频' }).click();

  await expect.poll(() => batchCreateRequests).toEqual([
    expect.objectContaining({
      job_type: 'video',
      extra_data: expect.objectContaining({
        model_config_id: 'video-config-001',
      }),
    }),
  ]);
});

test('producer refreshes running video batch item status from item action', async ({ page }) => {
  const refreshRequests: string[] = [];
  let itemsCallCount = 0;

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === '/api/v1/novels') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([{ id: 'novel-001', title: '逆天至尊', genre: '玄幻' }]) });
      return;
    }
    if (path === '/api/v1/llm/configs') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }
    if (path === '/api/v1/workflow') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([{ workflow_id: 'wf-001', title: '逆天至尊 第一章', status: 'active', current_step: 6, novel_id: 'novel-001', chapter_id: 'chapter-001', script_id: 'script-001', storyboard_id: 'storyboard-001', video_job_ids: [], tts_job_ids: [], synthesis_job_ids: [] }]) });
      return;
    }
    if (path === '/api/v1/workflow/status/wf-001') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ workflow_id: 'wf-001', title: '逆天至尊 第一章', status: 'active', current_step: 6, completed_steps: [1, 2, 3, 4, 5, 6], novel_id: 'novel-001', chapter_id: 'chapter-001', script_id: 'script-001', storyboard_id: 'storyboard-001', video_jobs: [], tts_jobs: [], synthesis_jobs: [] }) });
      return;
    }
    if (path === '/api/v1/short-video/workflow/wf-001/readiness') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ summary: { ready: true, score: 90, blocker_count: 0, warning_count: 0 }, recommendations: [] }) });
      return;
    }
    if (path === '/api/v1/chapters/novel/novel-001') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([{ id: 'chapter-001', title: '第一章 少年出山', chapter_number: 1 }]) });
      return;
    }
    if (path === '/api/v1/chapters/chapter-001/production-status') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ script_id: 'script-001', storyboard_id: 'storyboard-001', shot_count: 1 }) });
      return;
    }
    if (path === '/api/v1/story-bibles') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }
    if (path === '/api/v1/batch/list') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ total: 1, jobs: [{ id: 'batch-video-001', job_type: 'video', title: '批量生成视频 (1个)', status: 'running', total_count: 1, pending_count: 0, running_count: 1, succeeded_count: 0, failed_count: 0, skipped_count: 0, storyboard_id: 'storyboard-001', shot_ids: ['shot-001'], workflow_id: 'wf-001', created_at: new Date().toISOString(), updated_at: new Date().toISOString() }] }) });
      return;
    }
    if (path === '/api/v1/batch/batch-video-001/progress') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ job_id: 'batch-video-001', status: itemsCallCount > 1 ? 'completed' : 'running', total_count: 1, pending_count: 0, running_count: itemsCallCount > 1 ? 0 : 1, succeeded_count: itemsCallCount > 1 ? 1 : 0, failed_count: 0, skipped_count: 0, progress_percent: itemsCallCount > 1 ? 100 : 0, message: itemsCallCount > 1 ? '已完成 1/1' : '已完成 0/1' }) });
      return;
    }
    if (path === '/api/v1/batch/batch-video-001/items') {
      itemsCallCount += 1;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total: 1,
          items: [{
            id: 'item-video-001',
            batch_job_id: 'batch-video-001',
            shot_id: 'shot-001',
            status: itemsCallCount > 1 ? 'succeeded' : 'running',
            image_url: null,
            video_url: itemsCallCount > 1 ? '/static/generated/videos/shot-001.mp4' : null,
            audio_url: null,
            image_job_id: null,
            video_job_id: 'video-job-001',
            tts_job_id: null,
            error_message: null,
            sort_order: 0,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          }],
        }),
      });
      return;
    }
    if (path === '/api/v1/video/jobs/video-job-001/refresh') {
      refreshRequests.push(path);
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 'video-job-001', status: 'succeeded', progress: 100, video_url: '/static/generated/videos/shot-001.mp4', message: '状态已更新' }) });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/producer?workflow_id=wf-001');
  await page.getByText('批量生成视频 (1个)').click();
  await expect(page.getByText('生成中')).toBeVisible();
  await page.getByRole('button', { name: '刷新视频状态' }).click();

  await expect.poll(() => refreshRequests).toEqual(['/api/v1/video/jobs/video-job-001/refresh']);
  await expect(page.getByText('已完成')).toBeVisible();
  await expect(page.getByText('/static/generated/videos/shot-001.mp4')).toBeVisible();
});

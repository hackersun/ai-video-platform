import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `video-preflight-block-user-${Date.now()}`;
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

test('video generation shows consistency preflight blockers before submitting', async ({ page }) => {
  const preflightRequests: Array<Record<string, unknown>> = [];
  let videoGenerateCalls = 0;

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
          model_id: 'doubao-seedance-2-0-fast-260128',
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
          api_model_id: 'doubao-seedance-2-0-fast-260128',
          model_id: 'doubao-seedance-2-0-fast-260128',
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
        body: JSON.stringify([{ id: 'shot-001', storyboard_id: 'storyboard-001', shot_number: 1, duration: 4, prompt: '少年在宗门广场醒来', video_status: 'pending', image_url: '/static/dev/local-ref.png' }]),
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
          video_status: 'pending',
          image_url: '/static/dev/local-ref.png',
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

    if (path === '/api/v1/video/jobs' || path === '/api/v1/media/jobs') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/consistency/preflight') {
      const body = request.postData() ? JSON.parse(request.postData() || '{}') : {};
      preflightRequests.push(body);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ready: false,
          blocking_issue_count: 1,
          warning_issue_count: 0,
          issues: [{
            code: 'reference_image_not_public',
            field: 'image_url',
            severity: 'blocking',
            message: '角色参考图不是公网地址，云端图生视频需要公网可访问对象存储/CDN地址',
          }],
          model_route: { provider_id: 'volcano', model_config_id: 'config-video-001' },
          entity_refs: {},
          asset_version_locks: [],
        }),
      });
      return;
    }

    if (path === '/api/v1/video/generate') {
      videoGenerateCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ task_id: 'task-should-not-start', job_id: 'job-should-not-start', status: 'running' }),
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/video-generation?novel_id=novel-001&chapter_id=chapter-001&script_id=script-001&storyboard_id=storyboard-001&shot_id=shot-001');

  await expect(page.getByRole('button', { name: '开始生成' })).toBeEnabled({ timeout: 10_000 });
  await page.getByRole('button', { name: '开始生成' }).click();

  await expect.poll(() => preflightRequests.length, { timeout: 3_000 }).toBe(1);
  expect(preflightRequests[0]).toMatchObject({
    task_type: 'shot_video',
    model_config_id: 'config-video-001',
    shot_id: 'shot-001',
    image_url: '/static/dev/local-ref.png',
    require_public_reference_image: true,
  });
  expect(videoGenerateCalls).toBe(0);
  await expect(page.getByTestId('video-generation-preflight')).toContainText('生成前预检未通过');
  await expect(page.getByText('角色参考图不是公网地址')).toBeVisible();
  await expect(page.getByTestId('video-generation-preflight')).toContainText('处理位置：生产适配');
  await expect(page.getByTestId('video-generation-preflight').locator('a[href="/production-adapters"]')).toContainText('去处理');
});

test('direct audio-video generation shows consistency preflight blockers before submitting', async ({ page }) => {
  const preflightRequests: Array<Record<string, unknown>> = [];
  let mediaGenerateCalls = 0;

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
          model_id: 'doubao-seedance-2-0-fast-260128',
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
          api_model_id: 'doubao-seedance-2-0-fast-260128',
          model_id: 'doubao-seedance-2-0-fast-260128',
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
        body: JSON.stringify([{ id: 'shot-001', storyboard_id: 'storyboard-001', shot_number: 1, duration: 4, prompt: '少年在宗门广场醒来', video_status: 'pending', image_url: '/static/dev/local-ref.png' }]),
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
          video_status: 'pending',
          image_url: '/static/dev/local-ref.png',
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

    if (path === '/api/v1/video/jobs' || path === '/api/v1/media/jobs') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/consistency/preflight') {
      const body = request.postData() ? JSON.parse(request.postData() || '{}') : {};
      preflightRequests.push(body);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ready: false,
          blocking_issue_count: 1,
          warning_issue_count: 0,
          issues: [{
            code: 'missing_asset_locks',
            field: 'asset_version_locks',
            severity: 'blocking',
            message: '镜头缺少角色/场景/道具定稿资产锁，可能导致跨镜头画风或人物漂移',
          }],
          model_route: { provider_id: 'audio_video_adapter' },
          entity_refs: {},
          asset_version_locks: [],
        }),
      });
      return;
    }

    if (path === '/api/v1/media/generate') {
      mediaGenerateCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'media-should-not-start', status: 'running' }),
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/video-generation?novel_id=novel-001&chapter_id=chapter-001&script_id=script-001&storyboard_id=storyboard-001&shot_id=shot-001');

  await page.getByRole('button', { name: '直生音视频' }).click();
  await expect(page.getByRole('button', { name: '生成音视频' })).toBeEnabled({ timeout: 10_000 });
  await page.getByRole('button', { name: '生成音视频' }).click();

  await expect.poll(() => preflightRequests.length, { timeout: 3_000 }).toBe(1);
  expect(preflightRequests[0]).toMatchObject({
    task_type: 'direct_audio_video',
    shot_id: 'shot-001',
    image_url: '/static/dev/local-ref.png',
    require_public_reference_image: true,
  });
  expect(mediaGenerateCalls).toBe(0);
  await expect(page.getByTestId('video-generation-preflight')).toContainText('生成前预检未通过');
  await expect(page.getByText('镜头缺少角色/场景/道具定稿资产锁')).toBeVisible();
  await expect(page.getByTestId('video-generation-preflight')).toContainText('处理位置：资产库');
  await expect(page.getByTestId('video-generation-preflight').locator('a[href="/assets"]')).toContainText('去锁定资产');
});

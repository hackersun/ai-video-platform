import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `history-preflight-user-${Date.now()}`;
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

test('video history shows persisted generation preflight evidence', async ({ page }) => {
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
        body: JSON.stringify([{ id: 'shot-001', storyboard_id: 'storyboard-001', shot_number: 1, duration: 4, prompt: '少年在宗门广场醒来', video_status: 'pending' }]),
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
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
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
          extra_data: {
            generation_preflight: {
              ready: true,
              blocking_issue_count: 0,
              issues: [],
            },
          },
        }]),
      });
      return;
    }

    if (path === '/api/v1/media/jobs') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          id: 'media-job-001',
          task_id: 'task-media-001',
          task_type: 'shot_audio_video',
          media_type: 'audio_video',
          title: '镜头1 音视频直生版本',
          prompt: '少年在宗门广场醒来并开口',
          status: 'failed',
          progress: 100,
          output_video_url: '',
          shot_id: 'shot-001',
          duration_seconds: 4,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          extra_data: {
            generation_preflight: {
              ready: false,
              blocking_issue_count: 1,
              issues: [{
                code: 'reference_image_not_public',
                field: 'image_url',
                severity: 'blocking',
                message: '角色参考图不是公网地址',
              }],
            },
          },
        }]),
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/video-generation?novel_id=novel-001&chapter_id=chapter-001&script_id=script-001&storyboard_id=storyboard-001&shot_id=shot-001');

  const videoEvidence = page.getByTestId('history-preflight-video-job-001');
  await expect(videoEvidence).toContainText('预检通过');

  const mediaEvidence = page.getByTestId('history-preflight-media-job-001');
  await expect(mediaEvidence).toContainText('预检未通过');
  await expect(mediaEvidence).toContainText('角色参考图不是公网地址');
});

test('tts history shows persisted generation preflight evidence', async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === '/api/v1/llm/configs') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          id: 'config-tts-001',
          provider_id: 'minimax',
          config_model_id: 'tts-model-001',
          api_model_id: 'speech-2.5-hd-preview',
          model_id: 'speech-2.5-hd-preview',
          model_type: 'tts',
          model_capabilities: ['text-to-speech'],
          model_name: '已验证语音模型',
          name: '已验证语音模型',
          is_default: true,
          test_status: 'success',
          key_available: true,
        }]),
      });
      return;
    }

    if (path === '/api/v1/tts/voices') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          voices: [{ id: 'female-shaonv', voice_id: 'female-shaonv', label: '少女音', gender: '女', provider: 'minimax' }],
        }),
      });
      return;
    }

    if (path === '/api/v1/tts/jobs') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          id: 'tts-job-001',
          title: '少年台词配音',
          text: '少年：我还活着？',
          voice: 'female-shaonv',
          status: 'succeeded',
          progress: 100,
          audio_url: '/static/dev/voice.mp3',
          duration_seconds: 3,
          shot_id: 'shot-001',
          created_at: new Date().toISOString(),
          extra_data: {
            generation_preflight: {
              ready: false,
              blocking_issue_count: 1,
              issues: [{
                code: 'missing_character_voice',
                field: 'voice_model',
                severity: 'blocking',
                message: '角色还没有锁定专属音色',
              }],
            },
          },
        }]),
      });
      return;
    }

    if (path === '/api/v1/novels') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([{ id: 'novel-001', title: '逆天至尊' }]) });
      return;
    }

    if (path === '/api/v1/story-bibles') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/scripts') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/tts');
  await expect(page.getByText('少年台词配音')).toBeVisible();

  const evidence = page.getByTestId('history-preflight-tts-job-001');
  await expect(evidence).toContainText('预检未通过');
  await expect(evidence).toContainText('角色还没有锁定专属音色');
});

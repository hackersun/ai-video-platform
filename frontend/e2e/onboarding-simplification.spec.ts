import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `onboarding-user-${Date.now()}`;
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

async function mockQuickStartBase(page: any) {
  await page.route('**/api/v1/llm/configs', async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { id: 'text-config', provider_id: 'volcano', model_type: 'text', capabilities: ['text'] },
        { id: 'video-config', provider_id: 'volcano', model_type: 'video', capabilities: ['text-to-video'] },
        { id: 'audio-config', provider_id: 'minimax', model_type: 'tts', capabilities: ['text-to-speech'] },
      ]),
    });
  });
  await page.route('**/api/v1/novels', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 'novel-1' }) });
  });
  await page.route('**/api/v1/chapters', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 'chapter-1' }) });
  });
  await page.route('**/api/v1/story-bibles/generate-from-novel', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 'bible-1' }) });
  });
  await page.route('**/api/v1/storyboards/generate-smart', async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ id: 'storyboard-1', script_id: 'script-1', shot_count: 4, shots: [{ id: 'shot-1' }] }),
    });
  });
  await page.route('**/api/v1/workflow/start', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ workflow_id: 'workflow-1' }) });
  });
  await page.route('**/api/v1/workflow/status/workflow-1', async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'workflow-1',
        novel_id: 'novel-1',
        chapter_id: 'chapter-1',
        script_id: 'script-1',
        storyboard_id: 'storyboard-1',
      }),
    });
  });
  await page.route('**/api/v1/workflow/workflow-1/step', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) });
  });
  await page.route('**/api/v1/production-control/workflow/workflow-1/producer-assistant', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) });
  });
  await page.route('**/api/v1/production-control/workflow/workflow-1/asset-locks', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) });
  });
  await page.route('**/api/v1/short-video/workflow/workflow-1/refresh-contracts', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) });
  });
}

test('quick start provides a sample story and beginner-ready checks', async ({ page }) => {
  await page.route('**/api/v1/llm/configs', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });

  await page.goto('/quick-start');
  await expect(page.getByRole('heading', { name: '连续动漫向导' })).toBeVisible();
  await page.getByRole('button', { name: '填入示例故事' }).click();

  await expect(page.getByPlaceholder('例如：星灯邮差')).toHaveValue('星灯邮差');
  await expect(page.getByPlaceholder(/写 2-5 句话即可/)).toHaveValue(/云上列车/);
  await expect(page.getByText('高级模型配置可先不管')).toBeVisible();
  await expect(page.getByText('就绪')).toHaveCount(4);
  await page.getByRole('button', { name: '保存草稿' }).click();
  await expect(page.getByText(/草稿已保存/)).toBeVisible();
});

test('quick start keeps partial work and can skip audio after MiniMax voice failure', async ({ page }) => {
  let mediaBatchCalls = 0;
  let skipAudioPayload: any = null;

  await mockQuickStartBase(page);
  await page.route('**/api/v1/workflow/workflow-1/generate-media-batch', async (route) => {
    mediaBatchCalls += 1;
    const payload = route.request().postDataJSON();
    if (mediaBatchCalls === 1) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'MiniMax TTS失败 [2054]: voice id not exist' }),
      });
      return;
    }
    skipAudioPayload = payload;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        workflow_id: 'workflow-1',
        strategy: 'separate_video_tts',
        created_count: 1,
        video_job_ids: ['video-1'],
        tts_job_ids: [],
        media_job_ids: [],
        subtitle_track_ids: ['subtitle-1'],
        pending_video_job_ids: [],
        pending_tts_job_ids: [],
        ready_for_concatenate: true,
        message: '视频任务已创建',
      }),
    });
  });
  await page.route('**/api/v1/workflow/concatenate/workflow-1', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ job_id: 'synthesis-1', segment_count: 1, output_url: '/static/dev/preview.mp4' }),
    });
  });
  await page.route('**/api/v1/workflow/workflow-1/render/preflight**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ready: true, issues: [] }) });
  });
  await page.route('**/api/v1/workflow/workflow-1/render', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'completed', message: '预览包已生成', preview_url: '/static/dev/preview.html' }),
    });
  });

  await page.goto('/quick-start');
  await page.getByRole('button', { name: '填入示例故事' }).click();
  await page.getByRole('button', { name: '生成第一集' }).click();

  await expect(page.getByText('配音音色不可用，已暂停在音视频草稿阶段')).toBeVisible();
  await expect(page.getByText('错误摘要：MiniMax TTS失败 [2054]: voice id not exist')).toBeVisible();
  await expect(page.getByText('已创建')).toBeVisible();
  await expect(page.getByRole('button', { name: /重试生产阶段/ })).toBeVisible();
  await expect(page.getByRole('link', { name: /进入工作室处理/ })).toBeVisible();
  await expect(page.getByText('视频任务 ID')).toHaveCount(0);

  const mediaStep = page.getByText('批量生成音视频草稿').locator('xpath=ancestor::div[contains(@class,"rounded")][1]');
  await mediaStep.getByRole('button', { name: '查看任务明细' }).click();
  await expect(mediaStep.getByText('环节状态')).toBeVisible();
  await expect(mediaStep.getByText('错误：MiniMax TTS失败 [2054]: voice id not exist')).toBeVisible();

  await page.reload();
  await expect(page.getByText(/已恢复上次执行记录/)).toBeVisible();
  await expect(page.getByText('配音音色不可用，已暂停在音视频草稿阶段')).toBeVisible();
  await expect(page.getByText('已创建')).toBeVisible();

  await page.getByRole('button', { name: /跳过配音继续生成/ }).click();

  await expect(page.getByText('首集预览草片、字幕和渲染包已生成')).toBeVisible();
  expect(skipAudioPayload?.audio_mode).toBe('none');
});

test('quick start treats pending cloud media as waiting instead of failed', async ({ page }) => {
  await mockQuickStartBase(page);
  await page.route('**/api/v1/workflow/workflow-1/generate-media-batch', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        workflow_id: 'workflow-1',
        strategy: 'separate_video_tts',
        created_count: 2,
        video_job_ids: ['video-pending-1', 'video-pending-2'],
        tts_job_ids: ['tts-pending-1'],
        media_job_ids: [],
        subtitle_track_ids: ['subtitle-1'],
        pending_video_job_ids: ['video-pending-1', 'video-pending-2'],
        pending_tts_job_ids: ['tts-pending-1'],
        ready_for_concatenate: false,
        message: '视频/声音任务已提交，需等待任务完成后再合成',
      }),
    });
  });

  await page.goto('/quick-start');
  await page.getByRole('button', { name: '填入示例故事' }).click();
  await page.getByRole('button', { name: '生成第一集' }).click();

  const concatenateStep = page.getByText('编排连续成片').locator('xpath=ancestor::div[contains(@class,"rounded")][1]');
  await expect(concatenateStep.getByText('等待云端')).toBeVisible();
  await expect(concatenateStep.getByText('失败')).toHaveCount(0);
  await concatenateStep.getByRole('button', { name: '查看任务明细' }).click();
  await expect(concatenateStep.getByText('等待视频/声音任务完成')).toBeVisible();

  const mediaStep = page.getByText('批量生成音视频草稿').locator('xpath=ancestor::div[contains(@class,"rounded")][1]');
  await mediaStep.getByRole('button', { name: '查看任务明细' }).click();
  await expect(mediaStep.getByText('video-pending-1、video-pending-2').first()).toBeVisible();
  await expect(mediaStep.getByText('tts-pending-1').first()).toBeVisible();
});

test('model config keeps test and noisy TTS models hidden until advanced mode is opened', async ({ page }) => {
  await page.route('**/api/v1/llm/providers', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'volcano',
          name: 'volcano',
          name_cn: '火山引擎',
          base_url: 'https://ark.cn-beijing.volces.com/api/v3',
          description: '测试用火山提供商',
        },
      ]),
    });
  });

  await page.route('**/api/v1/llm/models**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'volcano-seedance-recommended',
          provider_id: 'volcano',
          model_id: 'doubao-seedance-2-0-fast',
          model_name: 'Doubao Seedance 2.0 Fast',
          model_name_cn: '常用视频模型',
          model_type: 'video',
          capabilities: ['text-to-video', 'image-to-video'],
          context_window: 0,
          max_tokens: 0,
          input_cost_per_1k: 0,
          output_cost_per_1k: 0,
          is_recommended: true,
        },
        {
          id: 'test-video-chaos',
          provider_id: 'volcano',
          model_id: 'test-video-chaos',
          model_name: 'test-video-chaos',
          model_name_cn: '测试视频模型',
          model_type: 'video',
          capabilities: ['text-to-video'],
          context_window: 0,
          max_tokens: 0,
          input_cost_per_1k: 0,
          output_cost_per_1k: 0,
        },
        {
          id: 'tts-noisy-voice',
          provider_id: 'volcano',
          model_id: 'speech-voice-preview',
          model_name: 'speech-voice-preview',
          model_name_cn: '普通 TTS 声音模型',
          model_type: 'tts',
          capabilities: ['text-to-speech'],
          context_window: 0,
          max_tokens: 0,
          input_cost_per_1k: 0,
          output_cost_per_1k: 0,
        },
      ]),
    });
  });

  await page.route('**/api/v1/llm/configs', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });

  await page.goto('/llm-config');
  await expect(page.getByText('新手模式：只显示推荐和常用模型')).toBeVisible();
  await expect(page.getByText('常用视频模型').first()).toBeVisible();
  await expect(page.getByText('测试视频模型')).toHaveCount(0);
  await expect(page.getByText('普通 TTS 声音模型')).toHaveCount(0);

  await page.getByRole('button', { name: /显示测试\/高级模型/ }).click();
  await expect(page.getByText('测试视频模型').first()).toBeVisible();
  await expect(page.getByText('普通 TTS 声音模型').first()).toBeVisible();
});

test('top navigation keeps production path primary and expert tools grouped', async ({ page }) => {
  await page.route('**/api/v1/novels**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
  await page.route('**/api/v1/video/jobs**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
  await page.route('**/api/v1/tts/jobs**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
  await page.route('**/api/v1/scripts**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/dashboard');

  const navigation = page.getByRole('navigation').first();
  await expect(navigation.getByText('工作室')).toBeVisible();
  await expect(navigation.getByText('快速开始')).toBeVisible();
  await expect(navigation.getByText('小说')).toBeVisible();
  await expect(navigation.getByText('资产')).toBeVisible();

  await page.getByRole('button', { name: '专家工具' }).click();
  await expect(page.getByRole('menuitem', { name: 'Story Bible' })).toBeVisible();
  await expect(page.getByRole('menuitem', { name: '工作流' })).toBeVisible();
  await expect(page.getByRole('menuitem', { name: '视频生成' })).toBeVisible();
});

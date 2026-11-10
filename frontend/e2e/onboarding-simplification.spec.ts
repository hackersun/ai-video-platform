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
  await expect(page.getByRole('heading', { name: '专家向导' })).toBeVisible();
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

  await expect(page.getByText('配音音色不可用，已暂停在音视频草稿阶段').first()).toBeVisible();
  await expect(page.getByText('错误摘要：MiniMax TTS失败 [2054]: voice id not exist')).toBeVisible();
  await expect(page.getByText('已创建')).toBeVisible();
  await expect(page.locator('#quick-start-form').getByRole('button', { name: /重试生产阶段/ }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: /进入工作室处理/ })).toBeVisible();
  await expect(page.getByText('视频任务 ID')).toHaveCount(0);

  const mediaStep = page.getByTestId('quick-start-progress-step-media');
  await mediaStep.getByRole('button', { name: '查看任务明细' }).click();
  await expect(mediaStep.getByText('环节状态')).toBeVisible();
  await expect(mediaStep.getByText('错误：MiniMax TTS失败 [2054]: voice id not exist')).toBeVisible();

  await page.reload();
  await expect(page.getByText(/已恢复上次执行记录/)).toBeVisible();
  await expect(page.getByText('配音音色不可用，已暂停在音视频草稿阶段').first()).toBeVisible();
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

  await page.route('**/api/v1/video/jobs/*/refresh', async (route) => {
    const id = route.request().url().split('/video/jobs/')[1].split('/')[0];
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id, job_id: id, status: 'processing' }) });
  });
  await page.route('**/api/v1/tts/jobs/*', async (route) => {
    const id = route.request().url().split('/tts/jobs/')[1].split('?')[0];
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id, status: 'processing' }) });
  });
  await page.clock.install();

  await page.goto('/quick-start');
  await page.getByRole('button', { name: '填入示例故事' }).click();
  await page.getByRole('button', { name: '生成第一集' }).click();

  const concatenateStep = page.getByTestId('quick-start-progress-step-concatenate');
  await expect(concatenateStep.getByText('等待云端')).toBeVisible();
  // Fast-forward past the cloud-wait window so the run returns its waiting result.
  await page.clock.runFor(13 * 60 * 1000);
  await expect(concatenateStep.getByText('等待云端')).toBeVisible();
  await expect(concatenateStep.getByText('失败')).toHaveCount(0);
  await concatenateStep.getByRole('button', { name: '查看任务明细' }).click();
  await expect(concatenateStep.getByText('等待视频/声音任务完成')).toBeVisible();

  const mediaStep = page.getByTestId('quick-start-progress-step-media');
  await mediaStep.getByRole('button', { name: '查看任务明细' }).click();
  await expect(mediaStep.getByText('video-pending-1、video-pending-2').first()).toBeVisible();
  await expect(mediaStep.getByText('tts-pending-1').first()).toBeVisible();
});

const SECRET = 'sk-e2e-never-shown-123456';

function simpleCard(capability: string, label: string, configured: boolean) {
  return {
    capability, label,
    config_id: configured ? `cfg-${capability}` : null,
    provider_id: configured ? 'volcano' : null,
    provider_name: configured ? '火山引擎' : null,
    model_id: configured ? `m-${capability}` : null,
    model_name: configured ? `${label}推荐模型` : null,
    api_model_id: null, has_key: configured,
    test_status: configured ? 'pending' : null, test_message: null, tested_at: null, fresh: false,
    extra_params: {},
    options: [{ model_id: `m-${capability}`, api_model_id: capability, name: `${label}推荐模型`, provider_id: 'volcano', provider_name: '火山引擎' }],
  };
}

function simpleState(configured: boolean, verified = false) {
  const caps = { text: '文本', image: '图像', video: '视频', tts: '语音' } as const;
  const capabilities = Object.fromEntries(Object.entries(caps).map(([c, l]) => {
    const card = simpleCard(c, l, configured);
    if (verified) Object.assign(card, { test_status: 'success', fresh: true });
    return [c, card];
  }));
  return {
    providers: [{ id: 'volcano', code: 'volcano', name: '火山引擎', recommended: true,
      presets: { text: 'm-text', image: 'm-image', video: 'm-video', tts: 'm-tts' } }],
    capabilities, primary_provider_id: configured ? 'volcano' : null, configured, verified,
  };
}

test('model settings: one API key, save-and-check in one click, live calls on with default caps, secret never shown', async ({ page }) => {
  let saved: any = null;
  let configured = false;
  let verified = false;
  let billingPut: any = null;
  await page.route('**/api/v1/billing/settings', async (route) => {
    if (route.request().method() === 'PUT') billingPut = route.request().postDataJSON();
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      live_calls_opt_in: Boolean(billingPut?.live_calls_opt_in), opted_in_at: null,
      per_user_cap_rmb: billingPut?.per_user_cap_rmb || '100', per_pipeline_cap_rmb: billingPut?.per_pipeline_cap_rmb || '20', used_rmb: '0',
    }) });
  });
  await page.route('**/api/v1/model-center/simple-setup/test', async (route) => {
    verified = true;
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      results: Object.fromEntries(['text', 'image', 'video', 'tts'].map((c) => [c, { success: true, message: '连接成功', response_time_ms: 120 }])),
      state: simpleState(true, true),
    }) });
  });
  await page.route('**/api/v1/model-center/simple-setup', async (route) => {
    if (route.request().method() === 'PUT') {
      saved = route.request().postDataJSON();
      configured = true;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(simpleState(configured, verified)) });
  });

  await page.goto('/llm-config');
  await expect(page.getByRole('heading', { name: '模型设置' })).toBeVisible();
  await expect(page.getByText('尚未完成设置')).toBeVisible();
  // 四项模型默认折叠为一行摘要，「修改模型」展开后仍可逐项调整。
  await expect(page.getByTestId('model-setup-summary')).toContainText('文本：文本推荐模型');
  await expect(page.getByTestId('model-card-text')).toHaveCount(0);
  await page.getByRole('button', { name: '修改模型' }).click();
  for (const label of ['文本', '图像', '视频', '语音']) {
    await expect(page.getByRole('heading', { name: label, exact: true })).toBeVisible();
  }
  // 火山语音的 App ID 只在缺失导致检测失败时才要求。
  await expect(page.getByLabel('语音 App ID')).toHaveCount(0);
  await expect(page.getByRole('button', { name: '测试连接' })).toHaveCount(0);

  await page.getByLabel('API Key', { exact: true }).fill(SECRET);
  await page.getByRole('button', { name: '保存并检测' }).click();
  await expect(page.getByTestId('model-setup-notice')).toContainText('已保存并检测：4/4 项可用');
  await expect(page.getByTestId('model-setup-notice')).toContainText('已开启真实调用：每次生成最多 ¥50，账户累计最多 ¥200');
  expect(saved.provider_id).toBe('volcano');
  expect(saved.api_key).toBe(SECRET);
  expect(Object.keys(saved.capabilities).sort()).toEqual(['image', 'text', 'tts', 'video']);
  expect(billingPut).toEqual({ live_calls_opt_in: true, per_pipeline_cap_rmb: '50', per_user_cap_rmb: '200' });
  await expect(page.getByLabel('API Key', { exact: true })).toHaveValue('');
  await expect(page.getByLabel('API Key', { exact: true })).toHaveAttribute('placeholder', /已保存/);
  await expect(page.getByTestId('model-test-video')).toContainText('连接成功');
  await expect(page.getByText('全部就绪')).toBeVisible();
  expect(await page.content()).not.toContain(SECRET);

  await page.getByRole('button', { name: '费用上限（可选）' }).click();
  await expect(page.getByLabel('开启真实模型调用')).toBeChecked();
  await expect(page.getByLabel('账户费用上限')).toHaveValue('200');

  await page.getByRole('link', { name: '高级设置' }).click();
  await expect(page).toHaveURL(/section=overview/);
});

test('model settings: failed voice check asks for the missing App ID only then, live calls stay off', async ({ page }) => {
  let billingPut: any = null;
  await page.route('**/api/v1/billing/settings', async (route) => {
    if (route.request().method() === 'PUT') billingPut = route.request().postDataJSON();
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ live_calls_opt_in: false, per_user_cap_rmb: '100', per_pipeline_cap_rmb: '20', used_rmb: '0' }) });
  });
  await page.route('**/api/v1/model-center/simple-setup/test', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      results: {
        text: { success: true, message: '连接成功' }, image: { success: true, message: '连接成功' }, video: { success: true, message: '连接成功' },
        tts: { success: false, message: '语音接口缺少 App ID：请在火山语音控制台获取后填写' },
      },
      state: simpleState(true, false),
    }) });
  });
  await page.route('**/api/v1/model-center/simple-setup', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(simpleState(route.request().method() === 'PUT')) });
  });
  await page.goto('/llm-config');
  await expect(page.getByLabel('语音 App ID')).toHaveCount(0);
  await page.getByLabel('API Key', { exact: true }).fill(SECRET);
  await page.getByRole('button', { name: '保存并检测' }).click();
  await expect(page.getByTestId('model-setup-notice')).toContainText('已保存并检测：3/4 项可用');
  await expect(page.getByTestId('model-test-tts')).toContainText('缺少 App ID');
  await expect(page.getByLabel('语音 App ID')).toBeVisible();
  expect(billingPut).toBeNull();
});

test('welcome: only two choices; free trial saves, self-checks and jumps to novel import', async ({ page }) => {
  let simulationSaved = false;
  await page.route('**/api/v1/model-center/simple-setup/test', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      results: Object.fromEntries(['text', 'image', 'video', 'tts'].map((c) => [c, { success: true, message: '演示模式可用' }])),
      state: { ...simpleState(true, true), simulation_available: true, simulation_enabled: true },
    }) });
  });
  await page.route('**/api/v1/model-center/simple-setup', async (route) => {
    if (route.request().method() === 'PUT') simulationSaved = route.request().postDataJSON().simulation === true;
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...simpleState(simulationSaved, simulationSaved), simulation_available: true, simulation_enabled: simulationSaved }) });
  });
  await page.route('**/api/v1/novels**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
  await page.goto('/llm-config?welcome=1');
  const choice = page.getByTestId('onboarding-choice');
  await expect(choice.getByRole('button')).toHaveCount(2);
  await expect(choice.getByRole('button', { name: /演示模式/ })).toBeVisible();
  await expect(choice.getByRole('button', { name: /我有 API Key/ })).toBeVisible();
  await expect(page.getByLabel('API Key', { exact: true })).toHaveCount(0);
  await choice.getByRole('button', { name: /演示模式/ }).click();
  await expect(page).toHaveURL(/\/novels\?start=paste/);
  expect(simulationSaved).toBe(true);
});

test('welcome: "我有 API Key" reveals only the key form', async ({ page }) => {
  await page.route('**/api/v1/model-center/simple-setup', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...simpleState(false), simulation_available: true, simulation_enabled: false }) });
  });
  await page.goto('/llm-config?welcome=1');
  await page.getByTestId('onboarding-choice').getByRole('button', { name: /我有 API Key/ }).click();
  await expect(page.getByTestId('onboarding-choice')).toHaveCount(0);
  await expect(page.getByLabel('API Key', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '保存并检测' })).toBeVisible();
});

test('welcome without simulation: clear BYOK card, no free trial promise', async ({ page }) => {
  await page.route('**/api/v1/model-center/simple-setup', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...simpleState(false), simulation_available: false, simulation_enabled: false }) });
  });
  await page.goto('/llm-config?welcome=1');
  await expect(page.getByTestId('onboarding-choice')).toHaveCount(0);
  const byok = page.getByTestId('onboarding-byok');
  await expect(byok).toBeVisible();
  await expect(byok.getByRole('heading', { name: '填写 API Key 开始' })).toBeVisible();
  await expect(byok.getByText(/没有免费试用/)).toBeVisible();
  await expect(byok.getByText(/不赠送额度/)).toBeVisible();
  await page.getByTestId('onboarding-byok-start').click();
  await expect(page.getByTestId('onboarding-byok')).toHaveCount(0);
  await expect(page.getByLabel('API Key', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '保存并检测' })).toBeVisible();
});

test('demo (simulation) models are shown with plain names, never internal Deterministic ids', async ({ page }) => {
  const state = simpleState(true, true);
  for (const [cap, card] of Object.entries(state.capabilities) as [string, any][]) {
    Object.assign(card, { provider_id: 'deterministic-acceptance', provider_name: '模拟模式', model_id: `deterministic-${cap}`, model_name: `Deterministic ${cap}`, options: [] });
  }
  await page.route('**/api/v1/model-center/simple-setup', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...state, simulation_available: true, simulation_enabled: true }) });
  });
  await page.goto('/llm-config');
  await expect(page.getByTestId('model-setup-summary')).toContainText('文本：演示文本模型 · 图像：演示图片模型 · 视频：演示视频模型 · 语音：演示配音模型');
  await page.getByRole('button', { name: '修改模型' }).click();
  await expect(page.getByLabel('文本模型')).toContainText('演示文本模型 · 演示模式（不扣费）（当前）');
  expect(await page.locator('main').innerText()).not.toContain('Deterministic');
});

test('top navigation has one canonical entry per function and legacy entries redirect', async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/novels');

  const navigation = page.getByRole('navigation').first();
  for (const label of ['小说', '成片', '模型设置']) {
    await expect(navigation.getByRole('link', { name: label })).toBeVisible();
  }
  await expect(navigation.getByRole('link', { name: '模型设置' })).toHaveAttribute('href', '/llm-config');
  await expect(page.getByRole('link', { name: /AI视频平台/ }).first()).toHaveAttribute('href', '/novels');

  await page.getByRole('button', { name: '高级工具' }).click();
  await expect(page.getByRole('menuitem', { name: '工作流' })).toBeVisible();
  await expect(page.getByRole('menuitem', { name: '视频生成' })).toBeVisible();
  await expect(page.getByRole('menuitem', { name: '模型中心' })).toHaveCount(0);
  await page.keyboard.press('Escape');

  await page.goto('/teams');
  await expect(page).toHaveURL(/\/settings\/team$/);
  await page.goto('/prompt-skills');
  await expect(page).toHaveURL(/section=prompts/);
});

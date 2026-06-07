import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `workflow-media-preflight-user-${Date.now()}`;
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

test('workflow media batch shows preflight blockers returned by backend', async ({ page }) => {
  let mediaBatchCalls = 0;

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === '/api/v1/llm/configs') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'config-video-001',
            provider_id: 'volcano',
            config_model_id: 'video-model-001',
            api_model_id: 'doubao-seedance-2-0-fast-260128',
            model_id: 'doubao-seedance-2-0-fast-260128',
            model_type: 'video',
            model_capabilities: ['text-to-video', 'image-to-video'],
            model_name: '视频模型',
            name: '视频模型',
            is_default: true,
            test_status: 'success',
            key_available: true,
          },
          {
            id: 'config-audio-001',
            provider_id: 'minimax',
            config_model_id: 'audio-model-001',
            api_model_id: 'speech-2.5-hd-preview',
            model_id: 'speech-2.5-hd-preview',
            model_type: 'tts',
            model_capabilities: ['text-to-speech'],
            model_name: '声音模型',
            name: '声音模型',
            is_default: true,
            test_status: 'success',
            key_available: true,
          },
        ]),
      });
      return;
    }

    if (path === '/api/v1/workflow/status/wf-001') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow_id: 'wf-001',
          current_step: 7,
          novel_id: 'novel-001',
          chapter_id: 'chapter-001',
          script_id: 'script-001',
          storyboard_id: 'storyboard-001',
          video_jobs: [],
          tts_jobs: [],
          media_jobs: [],
          subtitle_tracks: [],
          synthesis_jobs: [],
          metadata: {},
        }),
      });
      return;
    }

    if (path === '/api/v1/story-bibles') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/workflow/wf-001/generate-media-batch' && request.method() === 'POST') {
      mediaBatchCalls += 1;
      await route.fulfill({
        status: 422,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: {
            code: 'generation_preflight_failed',
            message: '生成预检未通过，请先处理阻断项或明确选择降级策略。',
            blocking_issue_count: 2,
            issues: [
              {
                code: 'model_unverified',
                field: 'model_config_id',
                severity: 'blocking',
                message: '所选视频模型尚未验证通过，生产生成前需要先测试通过',
              },
              {
                code: 'missing_asset_locks',
                severity: 'blocking',
                message: '镜头缺少角色/场景/道具定稿资产锁，可能导致跨镜头画风或人物漂移',
              },
            ],
          },
        }),
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/workflow?workflow_id=wf-001');
  await expect(page.getByRole('button', { name: '批量生成视频和配音' })).toBeVisible({ timeout: 10_000 });
  await page.getByRole('button', { name: '批量生成视频和配音' }).click();

  await expect.poll(() => mediaBatchCalls, { timeout: 3_000 }).toBe(1);
  await expect(page.getByTestId('workflow-media-preflight')).toContainText('生成前预检未通过');
  await expect(page.getByText('所选视频模型尚未验证通过')).toBeVisible();
  await expect(page.getByText('镜头缺少角色/场景/道具定稿资产锁')).toBeVisible();
  await expect(page.getByTestId('workflow-media-preflight')).toContainText('处理位置：AI模型配置');
  await expect(page.getByTestId('workflow-media-preflight').locator('a[href="/llm-config"]')).toContainText('去验证模型');
  await expect(page.getByTestId('workflow-media-preflight')).toContainText('处理位置：资产库');
  await expect(page.getByTestId('workflow-media-preflight').locator('a[href="/assets"]')).toContainText('去锁定资产');
  await expect(page.getByText('批量视频和配音已生成')).toHaveCount(0);
});

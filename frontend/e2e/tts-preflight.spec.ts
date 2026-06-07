import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `tts-preflight-user-${Date.now()}`;
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

test('tts generation shows consistency preflight blockers before submitting', async ({ page }) => {
  const preflightRequests: Array<Record<string, unknown>> = [];
  let ttsGenerateCalls = 0;

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
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/novels') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'novel-001', title: '逆天至尊' }]),
      });
      return;
    }

    if (path === '/api/v1/chapters/novel/novel-001') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'chapter-001', novel_id: 'novel-001', title: '第一章 少年醒来' }]),
      });
      return;
    }

    if (path === '/api/v1/story-bibles') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'bible-001', title: '逆天至尊设定', character_rules: [{ name: '少年' }] }]),
      });
      return;
    }

    if (path === '/api/v1/scripts') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'script-001', title: '第一章剧本', novel_id: 'novel-001', chapter_id: 'chapter-001' }]),
      });
      return;
    }

    if (path === '/api/v1/storyboards/script/script-001') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'storyboard-001', title: '第一场', script_id: 'script-001' }]),
      });
      return;
    }

    if (path === '/api/v1/shots/storyboard/storyboard-001') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          id: 'shot-001',
          storyboard_id: 'storyboard-001',
          shot_number: 1,
          prompt: '少年在宗门广场醒来',
          dialogue: '少年：我还活着？',
        }]),
      });
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
            code: 'missing_character_voice',
            field: 'voice_model',
            severity: 'blocking',
            message: '角色还没有锁定专属音色，无法保证连续章节配音一致',
          }],
          model_route: { provider_id: 'minimax', model_config_id: 'config-tts-001' },
          entity_refs: {},
        }),
      });
      return;
    }

    if (path === '/api/v1/tts/generate') {
      ttsGenerateCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'tts-should-not-start', status: 'running', progress: 1 }),
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/tts');
  await expect(page.getByRole('heading', { name: /语音合成/ })).toBeVisible();

  await page.locator('select').filter({ has: page.locator('option[value="novel-001"]') }).selectOption('novel-001');
  await page.locator('select').filter({ has: page.locator('option[value="chapter-001"]') }).selectOption('chapter-001');
  await page.locator('select').filter({ has: page.locator('option[value="script-001"]') }).selectOption('script-001');
  await page.locator('select').filter({ has: page.locator('option[value="storyboard-001"]') }).selectOption('storyboard-001');
  await page.locator('select').filter({ has: page.locator('option[value="shot-001"]') }).selectOption('shot-001');

  await expect(page.getByRole('button', { name: '生成语音' })).toBeEnabled({ timeout: 10_000 });
  await page.getByRole('button', { name: '生成语音' }).click();

  await expect.poll(() => preflightRequests.length, { timeout: 3_000 }).toBe(1);
  expect(preflightRequests[0]).toMatchObject({
    task_type: 'tts_dialogue',
    model_config_id: 'config-tts-001',
    novel_id: 'novel-001',
    chapter_id: 'chapter-001',
    script_id: 'script-001',
    storyboard_id: 'storyboard-001',
    shot_id: 'shot-001',
  });
  expect(ttsGenerateCalls).toBe(0);
  await expect(page.getByTestId('tts-generation-preflight')).toContainText('生成前预检未通过');
  await expect(page.getByText('角色还没有锁定专属音色')).toBeVisible();
});

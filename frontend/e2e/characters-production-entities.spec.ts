import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `characters-production-entities-user-${Date.now()}`;
  await page.addInitScript(({ authToken, authUserId }) => {
    localStorage.setItem('auth_token', authToken);
    localStorage.setItem('user', JSON.stringify({
      id: authUserId,
      username: authUserId,
      email: `${authUserId}@example.test`,
    }));
  }, { authToken: devToken(userId), authUserId: userId });
});

test('角色管理页在 legacy Character 为空时展示 StoryEntity 生产角色', async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === '/api/v1/novels') {
      await route.fulfill({ json: [{ id: 'novel-prod', title: '雾港星锚' }] });
      return;
    }
    if (path === '/api/v1/llm/configs') {
      await route.fulfill({ json: [] });
      return;
    }
    if (path === '/api/v1/assets/style-templates') {
      await route.fulfill({ json: { templates: [] } });
      return;
    }
    if (path === '/api/v1/characters') {
      await route.fulfill({ json: [] });
      return;
    }
    if (path === '/api/v1/story-bibles/entities') {
      await route.fulfill({
        json: [{
          id: 'entity-xulan',
          entity_type: 'character',
          name: '许澜',
          description: '修表师，负责追查星锚异常。',
          appearance: '灰蓝外套，红围巾。',
          attributes: {
            visual_dna: { costume: '灰蓝外套', accessory: '红围巾' },
            voice: 'sunqinyue-default',
          },
          tags: ['主角'],
          novel_id: 'novel-prod',
          chapter_id: null,
          aliases: [],
          relations: [],
          state_changes: [],
          confidence: 96,
          source: 'deterministic',
          is_approved: true,
          consistency_score: 1,
          version: 1,
        }],
      });
      return;
    }

    await route.fulfill({ json: [] });
  });

  await page.goto('/characters?novel_id=novel-prod');

  await expect(page.getByTestId('character-source-summary')).toContainText('角色总数 1');
  await expect(page.getByTestId('character-source-summary')).toContainText('手工角色 0');
  await expect(page.getByTestId('character-source-summary')).toContainText('生产实体 1');
  await expect(page.getByText('许澜')).toBeVisible();
  await expect(page.getByText('StoryEntity').first()).toBeVisible();
});

import { expect, test } from '@playwright/test';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `shots-multiview-user-${Date.now()}`;
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

async function apiPost(page: any, endpoint: string, body: any) {
  return page.evaluate(async ({ url, payload }) => {
    const token = localStorage.getItem('auth_token');
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(`${url} failed: HTTP ${response.status} ${JSON.stringify(data)}`);
    }
    return data;
  }, { url: `${API_BASE}${endpoint}`, payload: body });
}

test('镜头编辑弹窗展示出镜实体的多视图完整度提醒', async ({ page }) => {
  const stamp = Date.now();
  await page.goto('/shots');

  const novel = await apiPost(page, '/novels', {
    title: `镜头多视图小说-${stamp}`,
    genre: '玄幻',
    description: '黑衣剑修进入秘境。',
  });
  const chapter = await apiPost(page, '/chapters', {
    novel_id: novel.id,
    title: '第一章 秘境初临',
    content: '顾寒霜踏入秘境，古剑发出微光。',
    chapter_number: 1,
  });
  const script = await apiPost(page, '/scripts', {
    novel_id: novel.id,
    chapter_id: chapter.id,
    title: `镜头多视图剧本-${stamp}`,
    content: '顾寒霜踏入秘境，拔出古剑。',
    genre: 'fantasy',
    style: 'anime',
  });
  const storyboard = await apiPost(page, '/storyboards', {
    script_id: script.id,
    title: `镜头多视图分镜-${stamp}`,
    description: '角色进入秘境',
    content: { novel_id: novel.id, chapter_id: chapter.id, style: 'anime' },
  });
  const entity = await apiPost(page, '/story-bibles/entities', {
    novel_id: novel.id,
    chapter_id: chapter.id,
    entity_type: 'character',
    name: `顾寒霜-${stamp}`,
    description: '黑衣少年剑修，银色发带，背负古剑。',
    attributes: { appearance: '黑衣，古剑，冷峻眉眼' },
  });
  const front = await apiPost(page, '/assets', {
    category: 'character',
    asset_type: 'image',
    name: `顾寒霜 正面-${stamp}`,
    url: '/static/dev/front.png',
    thumbnail_url: '/static/dev/front.png',
    novel_id: novel.id,
    entity_id: entity.id,
    entity_type: 'character',
    generation_params: { source: 'entity_multiview', view_key: 'front', view_label: '正面' },
  });
  await apiPost(page, `/assets/${front.id}/lock`, {});

  await apiPost(page, '/shots', {
    storyboard_id: storyboard.id,
    shot_number: 1,
    duration: 4,
    prompt: '顾寒霜踏入秘境，古剑微光亮起。',
    dialogue: '顾寒霜：这里，就是古遗迹？',
    visual_description: '黑衣剑修站在秘境入口，背后雾气翻涌。',
    camera_angle: 'medium',
    character_refs: [{ id: entity.id, entity_id: entity.id, name: entity.name, entity_type: 'character' }],
    extra_data: {
      entity_refs: {
        characters: [{ id: entity.id, entity_id: entity.id, name: entity.name, entity_type: 'character' }],
      },
    },
  });

  await page.goto(`/shots?storyboard_id=${storyboard.id}`);
  await expect(page.getByText('顾寒霜踏入秘境，古剑微光亮起。')).toBeVisible({ timeout: 10_000 });
  await page.getByTitle('选择镜头').first().click();
  await expect(page.getByText('批量参考图风格（已选 1 个镜头）')).toBeVisible();
  await page.getByTestId('image-style-template').filter({ hasText: '修仙仙侠' }).click();
  await expect(page.getByTestId('image-style-template').filter({ hasText: '修仙仙侠' })).toHaveAttribute('aria-pressed', 'true');
  await page.getByTitle('编辑镜头').first().click();

  await expect(page.getByText('镜头编辑工作台')).toBeVisible();
  await expect(page.getByText('基础镜头')).toBeVisible();
  await expect(page.getByText('画面与运镜')).toBeVisible();
  await expect(page.getByText('台词与声音')).toBeVisible();

  const statusPanel = page.getByTestId('shot-edit-multiview-status');
  await expect(statusPanel.getByText('参考资产完整度')).toBeVisible();
  await expect(statusPanel.getByText(entity.name)).toBeVisible();
  await expect(statusPanel.getByText('角色三视图')).toBeVisible();
  await expect(statusPanel.getByText('1/3 已定稿')).toBeVisible();
  await expect(statusPanel.getByText('待补齐：侧面、背面')).toBeVisible();
});

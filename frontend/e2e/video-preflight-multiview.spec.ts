import { expect, test } from '@playwright/test';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `video-preflight-user-${Date.now()}`;
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

test('视频生成页在生成前提示镜头参考资产完整度', async ({ page }) => {
  const stamp = Date.now();
  await page.goto('/video-generation');

  const novel = await apiPost(page, '/novels', {
    title: `视频预检小说-${stamp}`,
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
    title: `视频预检剧本-${stamp}`,
    content: '顾寒霜踏入秘境，拔出古剑。',
    genre: 'fantasy',
    style: 'anime',
  });
  const storyboard = await apiPost(page, '/storyboards', {
    script_id: script.id,
    title: `视频预检分镜-${stamp}`,
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

  const shot = await apiPost(page, '/shots', {
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

  await page.goto(`/video-generation?novel_id=${novel.id}&chapter_id=${chapter.id}&script_id=${script.id}&storyboard_id=${storyboard.id}&shot_id=${shot.id}`);

  const preflight = page.getByTestId('video-reference-preflight');
  await expect(preflight.getByText('生成前参考资产预检')).toBeVisible({ timeout: 10_000 });
  await expect(preflight.getByText(entity.name)).toBeVisible();
  await expect(preflight.getByText('角色三视图')).toBeVisible();
  await expect(preflight.getByText('1/3 已定稿')).toBeVisible();
  await expect(preflight.getByText('待补齐：侧面、背面')).toBeVisible();
  await expect(preflight.locator(`a[href*="entity_id=${entity.id}"]`)).toContainText('去补齐参考图');
});

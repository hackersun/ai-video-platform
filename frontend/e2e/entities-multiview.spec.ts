import { expect, test } from '@playwright/test';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `entities-e2e-user-${Date.now()}`;
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

test('实体页展示小说角色的多视图定稿包并可跳转补齐', async ({ page }) => {
  const stamp = Date.now();
  await page.goto('/entities');

  const novel = await apiPost(page, '/novels', {
    title: `实体多视图小说-${stamp}`,
    genre: '玄幻',
    description: '少年剑修进入古遗迹秘境。',
  });
  const entity = await apiPost(page, '/story-bibles/entities', {
    novel_id: novel.id,
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
    generation_params: {
      source: 'entity_multiview',
      view_key: 'front',
      view_label: '正面',
    },
  });
  await apiPost(page, `/assets/${front.id}/lock`, {});
  await apiPost(page, '/assets', {
    category: 'character',
    asset_type: 'image',
    name: `顾寒霜 侧面-${stamp}`,
    url: '/static/dev/side.png',
    thumbnail_url: '/static/dev/side.png',
    novel_id: novel.id,
    entity_id: entity.id,
    entity_type: 'character',
    generation_params: {
      source: 'entity_multiview',
      view_key: 'side',
      view_label: '侧面',
    },
  });

  await page.goto('/entities');
  await expect(page.getByRole('heading', { name: '实体审阅台' })).toBeVisible();
  const card = page.getByTestId(`entity-card-${entity.id}`);
  await expect(card.getByText(entity.name)).toBeVisible();
  await expect(card.getByText('多视图定稿包')).toBeVisible();
  await expect(card.getByText('角色三视图')).toBeVisible();
  await expect(card.getByTestId(`entity-view-${entity.id}-front`).getByText('正面')).toBeVisible();
  await expect(card.getByTestId(`entity-view-${entity.id}-front`).getByText('已定稿')).toBeVisible();
  await expect(card.getByTestId(`entity-view-${entity.id}-side`).getByText('侧面')).toBeVisible();
  await expect(card.getByTestId(`entity-view-${entity.id}-side`).getByText('已生成')).toBeVisible();
  await expect(card.getByTestId(`entity-view-${entity.id}-back`).getByText('背面')).toBeVisible();
  await expect(card.getByTestId(`entity-view-${entity.id}-back`).getByText('待补齐')).toBeVisible();

  await card.getByRole('link', { name: '补齐多视图' }).click();
  await expect(page).toHaveURL(new RegExp(`/assets\\?.*entity_id=${entity.id}`));
  await expect(page.getByTestId('asset-wizard')).toContainText(entity.name);
});

test('实体页选中实体后展示批量作用域、标签和重抽模式入口', async ({ page }) => {
  const stamp = Date.now();
  await page.goto('/entities');

  const novel = await apiPost(page, '/novels', {
    title: `实体批量维护小说-${stamp}`,
    genre: '玄幻',
    description: '用于实体批量维护入口验证。',
  });
  const entity = await apiPost(page, '/story-bibles/entities', {
    novel_id: novel.id,
    entity_type: 'prop',
    name: `星砂罗盘-${stamp}`,
    description: '用于定位秘境的罗盘。',
    tags: ['旧标签'],
  });

  await page.goto('/entities');
  const card = page.getByTestId(`entity-card-${entity.id}`);
  await expect(card.getByText(entity.name)).toBeVisible();
  await card.getByRole('checkbox').check();

  await expect(page.getByRole('button', { name: '批量作用域' })).toBeVisible();
  await expect(page.getByRole('button', { name: '批量标签' })).toBeVisible();
  await expect(page.getByRole('button', { name: '重抽模式' })).toBeVisible();
});

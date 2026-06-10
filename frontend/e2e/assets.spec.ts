import { expect, test } from '@playwright/test';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `asset-e2e-user-${Date.now()}`;
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

test('资产库页面可创建、编辑和归档资产', async ({ page }) => {
  const stamp = Date.now();
  const name = `资产库验证角色-${stamp}`;
  const editedName = `${name}-更新`;

  await page.goto('/assets');
  await expect(page.getByRole('heading', { name: '资产库' })).toBeVisible();

  await page.getByRole('textbox', { name: '搜索资产名称、描述、标签' }).fill(name);
  await page.getByRole('button', { name: '搜索' }).click();
  await page.getByRole('button', { name: '新建资产' }).click();
  await expect(page.getByPlaceholder(/变量配置 JSON/)).toBeHidden();
  await expect(page.getByPlaceholder(/生成参数 JSON/)).toBeHidden();
  await page.getByRole('button', { name: /高级设置/ }).click();
  await expect(page.getByPlaceholder(/变量配置 JSON/)).toBeVisible();
  await expect(page.getByPlaceholder(/生成参数 JSON/)).toBeVisible();
  await page.getByRole('textbox', { name: '资产名称', exact: true }).fill(name);
  await page.getByPlaceholder('资源 URL 或 /static/... 路径').fill('/static/dev/reference.png');
  await page.getByPlaceholder('业务标签，例如：主角，夜景，法器').fill('主角,多视图');
  await page.getByPlaceholder('资产用途、视觉 DNA、适用镜头或一致性说明').fill('黑发蓝衣，正面角色参考图。');
  await page.getByRole('button', { name: '保存资产' }).click();

  await expect(page.getByText('资产已保存')).toBeVisible();
  await expect(page.getByText(name)).toBeVisible();

  await page.getByTitle('编辑资产').filter({ hasText: '编辑' }).first().click();
  await page.getByRole('textbox', { name: '资产名称', exact: true }).fill(editedName);
  await page.getByRole('button', { name: '保存资产' }).click();

  await expect(page.getByText('资产已更新')).toBeVisible();
  await expect(page.getByText(editedName)).toBeVisible();

  await page.getByTitle('归档资产').filter({ hasText: '归档' }).first().click();
  await expect(page.getByText('资产已归档')).toBeVisible();
});

test('资产库选中资产后展示批量范围和标签入口', async ({ page }) => {
  const stamp = Date.now();
  const name = `批量维护资产-${stamp}`;

  await page.goto('/assets');
  await apiPost(page, '/assets', {
    category: 'prop',
    asset_type: 'image',
    name,
    url: '/static/dev/reference.png',
    tags: ['旧标签'],
  });

  await page.goto('/assets');
  const card = page.getByTestId('asset-card').filter({ hasText: name });
  await expect(card).toBeVisible();
  await card.locator('input[type="checkbox"]').check();

  await expect(page.getByRole('button', { name: '批量设为当前范围' })).toBeVisible();
  await expect(page.getByRole('button', { name: '批量标签' })).toBeVisible();
  await expect(page.getByRole('button', { name: '重建资产包', exact: true })).toBeVisible();
});

test('资产库可按选中资产绑定实体重建资产包', async ({ page }) => {
  const stamp = Date.now();
  await page.goto('/assets');
  const novel = await apiPost(page, '/novels', {
    title: `资产重建小说-${stamp}`,
    genre: '玄幻',
    description: '用于资产包重建。',
  });
  const entity = await apiPost(page, '/story-bibles/entities', {
    novel_id: novel.id,
    entity_type: 'prop',
    name: `青铜铃-${stamp}`,
    description: '带裂纹的青铜铃关键道具。',
  });
  const asset = await apiPost(page, '/assets', {
    category: 'prop',
    asset_type: 'image',
    name: `青铜铃旧主视图-${stamp}`,
    url: '/static/dev/reference.png',
    novel_id: novel.id,
    entity_id: entity.id,
    entity_type: 'prop',
    generation_params: { source: 'entity_multiview', view_key: 'main' },
  });

  let receivedPayload: any = null;
  await page.route('**/api/v1/assets/reextract', async (route) => {
    receivedPayload = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        updated_count: 1,
        deleted_count: 1,
        created_count: 1,
        skipped: [],
        warnings: [],
        assets: [],
      }),
    });
  });

  await page.goto('/assets');
  const card = page.getByTestId('asset-card').filter({ hasText: asset.name });
  await expect(card).toBeVisible();
  await card.locator('input[type="checkbox"]').check();

  page.once('dialog', async (dialog) => {
    expect(dialog.type()).toBe('prompt');
    await dialog.accept('overwrite');
  });
  await page.getByRole('button', { name: '重建资产包', exact: true }).click();

  await expect(page.getByText(/资产包重建完成：新建 1 个/)).toBeVisible();
  expect(receivedPayload).toMatchObject({
    entity_ids: [entity.id],
    entity_types: ['prop'],
    mode: 'overwrite',
  });
});

test('资产库提供小说实体多视图 AI 制片向导', async ({ page }) => {
  const stamp = Date.now();
  await page.goto('/assets');
  const novel = await apiPost(page, '/novels', {
    title: `资产向导小说-${stamp}`,
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

  await page.reload();
  await expect(page.getByRole('heading', { name: '资产库' })).toBeVisible();
  await expect(page.getByText('AI 资产制片向导')).toBeVisible();

  await page.getByLabel('向导小说').selectOption(novel.id);
  await page.getByLabel('资产对象类型').selectOption('character');
  await page.getByLabel('小说对象').selectOption(entity.id);

  const wizard = page.getByTestId('asset-wizard');
  await expect(wizard.getByRole('heading', { name: '角色三视图' })).toBeVisible();
  await expect(wizard.getByText('画面风格样例')).toBeVisible();
  await wizard.getByTestId('image-style-template').filter({ hasText: '修仙仙侠' }).click();
  await expect(wizard.getByTestId('image-style-template').filter({ hasText: '修仙仙侠' })).toHaveAttribute('aria-pressed', 'true');
  expect(await wizard.getByTestId('image-style-template').locator('img').evaluateAll((imgs) => (
    imgs.length > 0 && imgs.every((img) => {
      const element = img as HTMLImageElement;
      return element.complete && element.naturalWidth > 0;
    })
  ))).toBeTruthy();
  await expect(wizard.getByText('题材模板示例')).toBeVisible();
  await expect(wizard.getByTestId('asset-style-example').filter({ hasText: '修仙仙侠' })).toBeVisible();
  expect(await wizard.getByTestId('asset-style-example').locator('img').evaluateAll((imgs) => (
    imgs.length > 0 && imgs.every((img) => {
      const element = img as HTMLImageElement;
      return element.complete && element.naturalWidth > 0;
    })
  ))).toBeTruthy();
  await expect(wizard.getByText('推荐比例：9:16')).toBeVisible();
  await expect(page.getByTestId('asset-wizard-view-front').getByText('正面', { exact: true })).toBeVisible();
  await expect(page.getByTestId('asset-wizard-view-side').getByText('侧面', { exact: true })).toBeVisible();
  await expect(page.getByTestId('asset-wizard-view-back').getByText('背面', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '生成缺失视图' })).toBeVisible();
});

test('资产向导多视图卡片使用紧凑图标操作栏', async ({ page }) => {
  const stamp = Date.now();
  await page.goto('/assets');
  const novel = await apiPost(page, '/novels', {
    title: `资产紧凑操作小说-${stamp}`,
    genre: '玄幻',
    description: '女主需要稳定三视图。',
  });
  const entity = await apiPost(page, '/story-bibles/entities', {
    novel_id: novel.id,
    entity_type: 'character',
    name: `沈清辞-${stamp}`,
    description: '青衣女修，束发，玉簪，长剑。',
    attributes: { appearance: '青衣，玉簪，长剑，清冷气质' },
  });
  await apiPost(page, '/assets', {
    category: 'character',
    asset_type: 'image',
    name: `沈清辞正面参考-${stamp}`,
    url: '/static/dev/shenqingci-front.png',
    thumbnail_url: '/static/dev/shenqingci-front.png',
    novel_id: novel.id,
    entity_id: entity.id,
    entity_type: 'character',
    generation_params: { source: 'entity_multiview', view_key: 'front', view_label: '正面' },
  });

  await page.reload();
  await page.getByLabel('向导小说').selectOption(novel.id);
  await page.getByLabel('资产对象类型').selectOption('character');
  await page.getByLabel('小说对象').selectOption(entity.id);

  const frontCard = page.getByTestId('asset-wizard-view-front');
  await expect(frontCard.getByRole('img', { name: `沈清辞正面参考-${stamp}` })).toBeVisible();

  for (const name of ['预览', '编辑', '锁定']) {
    const button = frontCard.getByRole('button', { name });
    await expect(button).toBeVisible();
    const box = await button.boundingBox();
    expect(box?.width).toBeLessThanOrEqual(44);
    expect(box?.height).toBeLessThanOrEqual(36);
  }
});

test('资产页通过 URL 参数自动选中实体并展示多视图资产', async ({ page }) => {
  const stamp = Date.now();
  await page.goto('/assets');
  const novel = await apiPost(page, '/novels', {
    title: `资产直达小说-${stamp}`,
    genre: '玄幻',
    description: '从其他工作台直达资产库时要展示已绑定三视图。',
  });
  const entity = await apiPost(page, '/story-bibles/entities', {
    novel_id: novel.id,
    entity_type: 'character',
    name: `苏明月-${stamp}`,
    description: '白衣女修，银冠，长剑。',
    attributes: { appearance: '白衣，银冠，长剑，清冷气质' },
  });
  await apiPost(page, '/assets', {
    category: 'character',
    asset_type: 'image',
    name: `苏明月正面参考-${stamp}`,
    url: '/static/dev/sumingyue-front.png',
    thumbnail_url: '/static/dev/sumingyue-front.png',
    novel_id: novel.id,
    entity_id: entity.id,
    entity_type: 'character',
    generation_params: { source: 'entity_multiview', view_key: 'front', view_label: '正面' },
  });

  await page.goto(`/assets?novel_id=${novel.id}&entity_type=character&entity_id=${entity.id}`);
  await expect(page.getByRole('heading', { name: '资产库' })).toBeVisible();
  await expect(page.locator('#asset-wizard-entity')).toHaveValue(entity.id);
  await expect(page.getByTestId('asset-wizard-view-front').getByRole('img', { name: `苏明月正面参考-${stamp}` })).toBeVisible();
});

test('资产制片向导阻止复合角色生成单角色三视图并精确过滤实体资产', async ({ page }) => {
  const stamp = Date.now();
  await page.goto('/assets');
  const novel = await apiPost(page, '/novels', {
    title: `复合角色过滤小说-${stamp}`,
    genre: '玄幻',
    description: '少年剑修被外门弟子围堵。',
  });
  const composite = await apiPost(page, '/story-bibles/entities', {
    novel_id: novel.id,
    entity_type: 'character',
    name: `孙剑（逆天至尊）、外门弟子们-${stamp}`,
    description: '孙剑与一群外门弟子同时出现的群体标签，不是单一角色。',
    attributes: { appearance: '多人群体，不应用于单角色设定图' },
  });
  const single = await apiPost(page, '/story-bibles/entities', {
    novel_id: novel.id,
    entity_type: 'character',
    name: `孙剑-${stamp}`,
    description: '黑衣少年剑修，银色发带，背负古剑。',
    attributes: { appearance: '黑衣，银色发带，古剑，少年男性' },
  });
  await apiPost(page, '/assets', {
    category: 'character',
    asset_type: 'image',
    name: `全局角色参考-${stamp}`,
    url: '/static/dev/global-character.png',
    thumbnail_url: '/static/dev/global-character.png',
    generation_params: { source: 'global-reference' },
  });
  await apiPost(page, '/assets', {
    category: 'character',
    asset_type: 'image',
    name: `孙剑正面参考-${stamp}`,
    url: '/static/dev/sunjian-front.png',
    thumbnail_url: '/static/dev/sunjian-front.png',
    novel_id: novel.id,
    entity_id: single.id,
    entity_type: 'character',
    generation_params: { source: 'entity_multiview', view_key: 'front', view_label: '正面' },
  });

  await page.reload();
  await expect(page.getByRole('heading', { name: '资产库' })).toBeVisible();
  await page.getByLabel('向导小说').selectOption(novel.id);
  await page.getByLabel('资产对象类型').selectOption('character');

  const entitySelect = page.locator('#asset-wizard-entity');
  const compositeOption = entitySelect.locator(`option[value="${composite.id}"]`);
  await expect(compositeOption).toHaveAttribute('disabled', '');
  await expect(compositeOption).toHaveText(/群体\/复合角色/);
  await expect(page.getByText('角色三视图只能用于单一角色')).toBeVisible();

  await entitySelect.selectOption(single.id);
  await expect(page.getByRole('button', { name: '生成缺失视图' })).toBeEnabled();
  await expect(page.getByText(`孙剑正面参考-${stamp}`)).toBeVisible();
  await expect(page.getByText(`全局角色参考-${stamp}`)).toHaveCount(0);

  const singleCard = page.getByTestId('asset-card').filter({ hasText: `孙剑正面参考-${stamp}` });
  await singleCard.getByRole('button', { name: '编辑' }).click();
  await expect(page.getByText('AI 重新生成当前视图')).toBeVisible();
  await expect(page.getByText('重新生成风格')).toBeVisible();
  await expect(page.getByRole('button', { name: 'AI重新生成' })).toBeVisible();
});

test('资产库展示多视图失败记录、重试入口和视觉一致性分数', async ({ page }) => {
  const stamp = Date.now();
  await page.goto('/assets');
  const novel = await apiPost(page, '/novels', {
    title: `资产失败重试小说-${stamp}`,
    genre: '玄幻',
    description: '女剑修在秘境中追踪灵印。',
  });
  const entity = await apiPost(page, '/story-bibles/entities', {
    novel_id: novel.id,
    entity_type: 'character',
    name: `洛云-${stamp}`,
    description: '白衣女剑修，青色发带，手持长剑。',
    attributes: { appearance: '白衣，青色发带，长剑' },
  });
  await apiPost(page, '/assets', {
    category: 'character',
    asset_type: 'text',
    name: `洛云 正面生成失败-${stamp}`,
    novel_id: novel.id,
    entity_id: entity.id,
    entity_type: 'character',
    source_prompt: '白衣女剑修正面三视图',
    generation_params: {
      source: 'entity_multiview',
      status: 'failed',
      view_key: 'front',
      view_label: '正面',
      error_message: '图像模型超时',
      retryable: true,
    },
  });
  await apiPost(page, '/assets', {
    category: 'character',
    asset_type: 'image',
    name: `洛云 侧面-${stamp}`,
    url: '/static/dev/luoyun-side.png',
    thumbnail_url: '/static/dev/luoyun-side.png',
    novel_id: novel.id,
    entity_id: entity.id,
    entity_type: 'character',
    generation_params: {
      source: 'entity_multiview',
      view_key: 'side',
      view_label: '侧面',
      reference_view_key: 'front',
      visual_contract: {
        id: `contract-${stamp}`,
        name: `洛云-${stamp}`,
      },
      visual_consistency: {
        score: 88,
        model: 'manual-review',
        issues: ['服装纹样略简化'],
      },
    },
  });

  await page.goto(`/assets?novel_id=${novel.id}&entity_type=character&entity_id=${entity.id}`);
  await expect(page.getByRole('heading', { name: '资产库' })).toBeVisible();
  const failedCard = page.getByTestId('asset-card').filter({ hasText: `洛云 正面生成失败-${stamp}` });
  await expect(failedCard.getByText('生成失败', { exact: true }).first()).toBeVisible();
  await expect(failedCard.getByText('图像模型超时')).toBeVisible();
  await expect(failedCard.getByRole('button', { name: '重试生成' })).toBeVisible();
  const imageCard = page.getByTestId('asset-card').filter({ hasText: `洛云 侧面-${stamp}` });
  await expect(imageCard.getByText('一致性 88')).toBeVisible();
  await expect(imageCard.getByText(`视觉契约 contract-${stamp}`)).toBeVisible();
  await expect(imageCard.getByText('继承正面参考')).toBeVisible();
});

test('资产图片默认显示缩略图并在当前页预览', async ({ page }) => {
  const stamp = Date.now();
  await page.goto('/assets');
  const novel = await apiPost(page, '/novels', {
    title: `资产预览小说-${stamp}`,
    genre: '玄幻',
    description: '少年剑修需要稳定角色参考图。',
  });
  await apiPost(page, '/assets', {
    category: 'character',
    asset_type: 'image',
    name: `孙剑背面参考-${stamp}`,
    url: '/static/dev/sunjian-back.png',
    novel_id: novel.id,
    entity_type: 'character',
    generation_params: { source: 'entity_multiview', view_key: 'back', view_label: '背面' },
  });

  await page.goto(`/assets?novel_id=${novel.id}&category=character`);
  await expect(page.getByRole('heading', { name: '资产库' })).toBeVisible();
  const card = page.getByTestId('asset-card').filter({ hasText: `孙剑背面参考-${stamp}` });
  await expect(card.getByRole('img', { name: `孙剑背面参考-${stamp}` })).toBeVisible();

  await card.getByRole('button', { name: '预览' }).click();
  const dialog = page.getByRole('dialog', { name: '资产预览' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText(`孙剑背面参考-${stamp}`)).toBeVisible();
  await expect(dialog.getByRole('img', { name: `孙剑背面参考-${stamp}` })).toBeVisible();
});

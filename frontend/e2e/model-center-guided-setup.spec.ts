import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(JSON.stringify({
    sub: userId,
    exp: Math.floor(Date.now() / 1000) + 86400,
  })).toString('base64url');
  return `dev.${payload}.sig`;
}

const pageMeta = { page: 1, page_size: 100, total: 1 };
const provider = {
  id: 'provider-qwen', code: 'qwen', display_name: '阿里千问', provider_family: 'dashscope',
  is_builtin: true, enabled: true, revision: 1,
};
const catalogModel = {
  provider_id: provider.id, provider_name: provider.display_name, provider_code: provider.code,
  model_name: 'Qwen Plus', api_model_id: 'qwen-plus', profile_version_id: 'profile-text-v1',
  profile_version: 1, driver_key: 'legacy_text_v1', legacy_model_id: null, legacy_config_id: null,
  certification_status: 'connection_verified', capabilities: ['text_generation'],
};
const connection = {
  id: 'connection-qwen', provider_id: provider.id, provider_name: provider.display_name,
  provider_code: provider.code, name: '生产套餐', base_url: null, has_secret: true,
  secret_hint: '****ef09', secret_updated_at: null, enabled: true, revision: 1,
};
const binding = {
  id: 'binding-text', scope_type: 'user', scope_id: 'user-1', task: 'script_generation',
  capability: 'text_generation', profile_version_id: catalogModel.profile_version_id,
  profile_name: catalogModel.model_name, api_model_id: catalogModel.api_model_id,
  connection_id: connection.id, connection_name: connection.name, provider_name: provider.display_name,
  priority: 100, route_policy: 'single', fallback_profile_version_ids: [],
  certification_status: 'connection_verified', affected_recipes: 2, version: 1,
  is_active: true, revision: 1,
};

test.beforeEach(async ({ page }) => {
  const userId = `guided-model-center-${Date.now()}`;
  await page.addInitScript(({ token, id }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({ id, username: id }));
  }, { token: devToken(userId), id: userId });
  await page.route('**/api/v1/model-center/**', async (route) => {
    const url = route.request().url();
    const body = url.includes('/providers') ? { items: [provider], meta: pageMeta }
      : url.includes('/drivers') ? {
        items: [
          { key: 'legacy_text_v1', capabilities: ['text_generation'], parameter_schema: {}, contract_version: 'v1' },
          { key: 'dashscope_video_v1', capabilities: ['video_generation'], parameter_schema: {}, contract_version: 'v1' },
        ], meta: { ...pageMeta, total: 2 },
      }
        : url.includes('/catalog') ? { items: [catalogModel], meta: pageMeta }
          : url.includes('/connections') ? { items: [connection], meta: pageMeta }
            : url.includes('/bindings') ? { items: [binding], meta: pageMeta }
              : { blocking_issues: [], connections: [connection], recipes: [] };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
});

test('概览用四个业务步骤解释模型接入与默认设置', async ({ page }) => {
  await page.goto('/llm-config?section=overview');

  await expect(page.getByRole('heading', { name: '四步完成模型接入' })).toBeVisible();
  await expect(page.getByText('1. 保存供应商账号')).toBeVisible();
  await expect(page.getByText('4. 设为默认模型')).toBeVisible();
  await expect(page.getByRole('navigation', { name: '模型中心功能' }).getByRole('link', { name: /供应商账号/ })).toBeVisible();
  await expect(page.getByRole('navigation', { name: '模型中心功能' }).getByRole('link', { name: /默认模型/ })).toBeVisible();
});

test('供应商账号解释账号名称且保留原连接契约', async ({ page }) => {
  await page.goto('/llm-config?section=connections');

  await expect(page.getByRole('heading', { name: '供应商账号', level: 1 })).toBeVisible();
  await expect(page.getByText('用于区分同一供应商的不同账号、套餐或环境')).toBeVisible();
  await expect(page.getByLabel('账号名称')).toHaveAttribute('placeholder', '例如：火山生产套餐');
  await expect(page.getByRole('button', { name: '新增账号' })).toBeEnabled();
});

test('新增文本模型只展示文本兼容适配器', async ({ page }) => {
  await page.goto('/llm-config?section=catalog&capability=text_generation');
  await page.getByRole('button', { name: '新增模型' }).click();

  await expect(page.getByRole('dialog', { name: '新增模型' })).toBeVisible();
  await expect(page.getByLabel('模型用途')).toHaveValue('text_generation');
  await expect(page.getByLabel('兼容适配器')).toHaveValue('legacy_text_v1');
  await expect(page.getByLabel('兼容适配器').locator('option')).toHaveCount(2);
  await expect(page.getByLabel('兼容适配器').locator('option[value="dashscope_video_v1"]')).toHaveCount(0);
  await expect(page.getByText('配置标识会根据 Model ID 自动生成')).toBeVisible();
});

test('新增 Seedance 2.5 未来兼容草稿可配置动态参考与时长能力', async ({ page }) => {
  let submittedVersion: Record<string, unknown> | null = null;
  await page.route('**/api/v1/model-center/profiles', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback();
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        id: 'profile-seedance-25', provider_id: provider.id, profile_key: 'seedance-25',
        display_name: 'Seedance 2.5 实验', enabled: true, revision: 1,
      }),
    });
  });
  await page.route('**/api/v1/model-center/profiles/profile-seedance-25/versions', async (route) => {
    submittedVersion = route.request().postDataJSON();
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        id: 'profile-seedance-25-v1', model_id: 'profile-seedance-25', version: 1,
        api_model_id: 'seedance-2.5-account-model', driver_key: 'dashscope_video_v1',
        capabilities: ['video_generation'], input_contract: (submittedVersion as any).input_contract,
        output_contract: {}, parameter_schema: {}, default_params: {},
        limits: (submittedVersion as any).limits, contract_version: 'seedance-2.5-configurable-v1',
        status: 'draft', revision: 1,
      }),
    });
  });

  await page.goto('/llm-config?section=catalog&capability=video_generation');
  await page.getByRole('button', { name: '新增模型' }).click();
  await page.getByRole('button', { name: '未来 Seedance 2.5 兼容模板' }).click();
  await expect(page.getByText('当前不能实模验证、发布或设为默认')).toBeVisible();

  await expect(page.getByText('视频模型能力')).toBeVisible();
  await page.getByLabel('模型显示名称').fill('Seedance 2.5 实验');
  await page.getByLabel('供应商 Model ID').fill('seedance-2.5-account-model');
  await page.getByLabel('最小时长（秒）').fill('4');
  await page.getByLabel('最大时长（秒）').fill('30');
  await page.getByLabel('参考图片上限').fill('20');
  await page.getByLabel('参考视频上限').fill('10');
  await page.getByLabel('参考音频上限').fill('10');
  await page.getByLabel('输出分辨率').fill('720p,1080p');
  await page.getByLabel('支持原生音频').check();
  await page.getByLabel('支持上一段视频参考').check();
  await page.getByRole('button', { name: '保存模型草稿' }).click();
  await expect(page.getByText('草稿 v1 已保存')).toBeVisible();

  expect(submittedVersion).toMatchObject({
    input_contract: {
      family: 'seedance_2_5', verification_status: 'experimental',
      modes: expect.arrayContaining(['multimodal_reference', 'video_continuation']),
    },
    limits: {
      duration_min: 4, duration_max: 30, reference_images: 20,
      reference_videos: 10, reference_audios: 10, native_audio: true,
      supports_previous_video: true, resolutions: ['720p', '1080p'],
    },
    contract_version: 'seedance-2.5-configurable-v1',
  });
});

test('视频模型详情展示已保存能力与实验状态', async ({ page }) => {
  await page.route('**/api/v1/model-center/catalog**', async (route) => {
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ items: [{
        ...catalogModel, model_name: 'Seedance 2.5 实验', api_model_id: 'seedance-2.5-account-model',
        capabilities: ['video_generation'], driver_key: 'dashscope_video_v1',
        input_contract: { family: 'seedance_2_5', verification_status: 'experimental' },
        limits: { duration_min: 4, duration_max: 30, reference_images: 20, reference_videos: 10, reference_audios: 10, native_audio: true },
      }], meta: pageMeta }),
    });
  });

  await page.goto('/llm-config?section=catalog&capability=video_generation');
  await page.getByRole('button', { name: '查看 Seedance 2.5 实验' }).click();

  await expect(page.getByText('实验能力契约')).toBeVisible();
  await expect(page.getByText('4–30 秒')).toBeVisible();
  await expect(page.getByText('图片 20 · 视频 10 · 音频 10')).toBeVisible();
});

test('默认模型页直接说明当前生产选择并可更换', async ({ page }) => {
  await page.goto('/llm-config?section=bindings');

  await expect(page.getByRole('heading', { name: '默认模型', level: 1 })).toBeVisible();
  await expect(page.getByText('小说理解与分镜')).toBeVisible();
  await expect(page.getByText('Qwen Plus · qwen-plus')).toBeVisible();
  await expect(page.getByRole('button', { name: '更换小说理解与分镜默认模型' })).toBeEnabled();
  await expect(page.getByRole('button', { name: '设置默认模型' })).toBeEnabled();
});

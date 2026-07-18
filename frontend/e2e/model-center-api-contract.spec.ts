import { expect, test } from '@playwright/test';

import { modelCenterApi } from '../src/features/model-center/api';
import {
  createModelCenterRequestGeneration,
} from '../src/features/model-center/hooks/use-model-center-query';
import {
  modelCenterMutationInvalidations,
  subscribeModelCenterQuery,
} from '../src/features/model-center/hooks/model-center-query-store';
import { runModelCenterMutation } from '../src/features/model-center/hooks/run-model-center-mutation';
import type {
  ModelBindingUpdateInput,
  ModelConnectionUpdateInput,
  ModelProfileVersionUpdateInput,
  ModelProviderUpdateInput,
} from '../src/features/model-center/types';

// Task 15 owns the rendered shell. This contract instead proves that no raw
// credential can cross the typed client boundary for a future shell to expose.

type FetchCall = { url: string; init: RequestInit | undefined };

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function recordFetch(respond: (url: string) => Response) {
  const calls: FetchCall[] = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    const url = typeof input === 'string' ? input : input.toString();
    calls.push({ url, init });
    return respond(url);
  };
  return {
    calls,
    restore() {
      globalThis.fetch = originalFetch;
    },
  };
}

const connectionPage = {
  items: [{
    id: 'connection-1', provider_id: 'volcengine', provider_name: '火山引擎', provider_code: 'volcengine',
    name: '主连接', base_url: null,
    has_secret: true, secret_hint: '****ef09', secret_updated_at: '2026-07-17T09:00:00Z',
    enabled: true, revision: 3,
  }],
  meta: { page: 1, page_size: 20, total: 1 },
};

const validConnectionUpdate = {
  name: '主连接',
  expected_revision: 3,
} satisfies ModelConnectionUpdateInput;
const validSecretReplacement = {
  api_key: 'replacement-key',
  expected_revision: 3,
  reason: '轮换已过期密钥',
} satisfies ModelConnectionUpdateInput;
const validProviderUpdate = { enabled: false, expected_revision: 2 } satisfies ModelProviderUpdateInput;
const validProfileUpdate = {
  api_model_id: 'seed-1.8', driver_key: 'ark', capabilities: ['text_generation'],
  contract_version: 'v1', expected_revision: 2,
} satisfies ModelProfileVersionUpdateInput;
const validBindingUpdate = {
  scope_type: 'user', task: 'text.storyboard', capability: 'text_generation',
  profile_version_id: 'profile-1', connection_id: 'connection-1', expected_revision: 2,
} satisfies ModelBindingUpdateInput;
void [validConnectionUpdate, validSecretReplacement, validProviderUpdate, validProfileUpdate, validBindingUpdate];

// @ts-expect-error update envelopes require optimistic-concurrency revisions
const missingConnectionRevision: ModelConnectionUpdateInput = { name: '主连接' };
// @ts-expect-error replacing a secret requires an audit reason
const missingSecretReplacementReason: ModelConnectionUpdateInput = { api_key: 'replacement-key', expected_revision: 3 };
// @ts-expect-error every update envelope requires an optimistic-concurrency revision
const missingProviderRevision: ModelProviderUpdateInput = { enabled: false };
// @ts-expect-error profile-version updates require an optimistic-concurrency revision
const missingProfileRevision: ModelProfileVersionUpdateInput = {
  api_model_id: 'seed-1.8', driver_key: 'ark', capabilities: ['text_generation'], contract_version: 'v1',
};
// @ts-expect-error binding updates require an optimistic-concurrency revision
const missingBindingRevision: ModelBindingUpdateInput = {
  scope_type: 'user', task: 'text.storyboard', capability: 'text_generation',
  profile_version_id: 'profile-1', connection_id: 'connection-1',
};
void [
  missingConnectionRevision,
  missingSecretReplacementReason,
  missingProviderRevision,
  missingProfileRevision,
  missingBindingRevision,
];

test('uses bounded versioned Model Center URLs and publish envelopes through the shared transport', async () => {
  const requests = recordFetch((url) => {
    if (url.includes('/connections?')) return jsonResponse(connectionPage);
    if (url.endsWith('/test')) return jsonResponse({ id: 'run-1' });
    return jsonResponse({ published_version_id: 'profile-version-1', previous_version_id: null, impact: {}, audit_event_id: 'audit-1' });
  });
  try {
    await modelCenterApi.listConnections(2, 50);
    await modelCenterApi.testConnection('connection-1');
    await modelCenterApi.publishProfileVersion('profile-version-1', {
      expected_revision: 3,
      reason: '认证通过',
    });

    expect(requests.calls).toEqual([
      {
        url: 'http://localhost:8000/api/v1/model-center/connections?page=2&page_size=50',
        init: { headers: { 'Content-Type': 'application/json' } },
      },
      {
        url: 'http://localhost:8000/api/v1/model-center/connections/connection-1/test',
        init: { method: 'POST', headers: { 'Content-Type': 'application/json' } },
      },
      {
        url: 'http://localhost:8000/api/v1/model-center/profile-versions/profile-version-1/publish',
        init: {
          method: 'POST',
          body: JSON.stringify({ expected_revision: 3, reason: '认证通过' }),
          headers: { 'Content-Type': 'application/json' },
        },
      },
    ]);
  } finally {
    requests.restore();
  }
});

test('redacts an unexpected raw secret at the Model Center response boundary', async () => {
  const requests = recordFetch(() => jsonResponse({
    ...connectionPage,
    items: [{ ...connectionPage.items[0], api_key: 'raw-secret-value', encrypted_secret: 'ciphertext' }],
  }));
  try {
    const response = await modelCenterApi.listConnections();
    expect(response.items[0]).toEqual(connectionPage.items[0]);
    expect(JSON.stringify(response)).not.toContain('raw-secret-value');
    expect(JSON.stringify(response)).not.toContain('ciphertext');
  } finally {
    requests.restore();
  }
});

test('redacts raw secrets from overview and connection write responses', async () => {
  const rawConnection = {
    ...connectionPage.items[0],
    api_key: 'raw-secret-value',
    encrypted_secret: 'ciphertext',
  };
  const requests = recordFetch((url) => {
    if (url.endsWith('/overview')) {
      return jsonResponse({ blocking_issues: [], connections: [rawConnection], recipes: [] });
    }
    return jsonResponse(rawConnection);
  });
  try {
    const overview = await modelCenterApi.getOverview();
    const created = await modelCenterApi.createConnection({
      provider_id: 'volcengine', name: '主连接', reason: '创建主连接', api_key: 'replacement-key',
    });
    const updated = await modelCenterApi.updateConnection('connection-1', {
      name: '主连接', expected_revision: 3,
    });
    const values = [overview.connections[0], created, updated];

    values.forEach((connection) => {
      expect(connection).toEqual(connectionPage.items[0]);
      expect(JSON.stringify(connection)).not.toContain('raw-secret-value');
      expect(JSON.stringify(connection)).not.toContain('ciphertext');
    });
  } finally {
    requests.restore();
  }
});

test('preserves the shared transport error mapping', async () => {
  const requests = recordFetch(() => jsonResponse({
    detail: { code: 'revision_conflict', message: '配置已被其他操作更新，请刷新后重新提交。' },
  }, 409));
  const originalConsoleError = console.error;
  console.error = () => undefined;
  try {
    await expect(modelCenterApi.listConnections()).rejects.toMatchObject({
      message: 'revision_conflict · 配置已被其他操作更新，请刷新后重新提交。',
      status: 409,
      detail: { code: 'revision_conflict' },
    });
  } finally {
    console.error = originalConsoleError;
    requests.restore();
  }
});

test('profile publish invalidates subscribed catalog, binding, recipe, impact, and overview queries', async () => {
  const refreshed: string[] = [];
  const unsubscribe = [
    subscribeModelCenterQuery('overview', () => refreshed.push('overview')),
    subscribeModelCenterQuery('catalog', () => refreshed.push('catalog')),
    subscribeModelCenterQuery('bindings', () => refreshed.push('bindings')),
    subscribeModelCenterQuery('recipes', () => refreshed.push('recipes')),
    subscribeModelCenterQuery('impact', () => refreshed.push('impact')),
    subscribeModelCenterQuery('prompt-profiles', () => refreshed.push('prompt-profiles')),
  ];
  try {
    await runModelCenterMutation(
      () => Promise.resolve('published'),
      modelCenterMutationInvalidations.profilePublish,
    );
    expect(refreshed).toEqual(['overview', 'catalog', 'bindings', 'recipes', 'impact']);
  } finally {
    unsubscribe.forEach((stop) => stop());
  }
});

test('bounds collection pagination before issuing a drivers URL', async () => {
  const requests = recordFetch(() => jsonResponse({ items: [], meta: { page: 1, page_size: 100, total: 0 } }));
  try {
    await modelCenterApi.listDrivers(0, 999);
    expect(requests.calls[0]?.url).toBe('http://localhost:8000/api/v1/model-center/drivers?page=1&page_size=100');
  } finally {
    requests.restore();
  }
});

test('catalog filters are encoded before server pagination', async () => {
  const requests = recordFetch(() => jsonResponse({
    items: [], meta: { page: 2, page_size: 10, total: 23 },
  }));
  try {
    await modelCenterApi.listCatalog(2, 10, {
      capability: 'video_generation',
      providerId: 'volcengine',
      status: 'unverified',
      query: 'seedance 1.5',
    });
    expect(requests.calls[0]?.url).toBe(
      'http://localhost:8000/api/v1/model-center/catalog?page=2&page_size=10&capability=video_generation&provider_id=volcengine&status=unverified&q=seedance+1.5',
    );
  } finally {
    requests.restore();
  }
});

test('a slow stale request cannot overwrite the latest generation or update after unmount', () => {
  const generations = createModelCenterRequestGeneration();
  const pageOne = generations.begin();
  const pageTwo = generations.begin();
  const accepted: string[] = [];

  if (pageTwo.isCurrent()) accepted.push('page-2');
  if (pageOne.isCurrent()) accepted.push('page-1');
  generations.unmount();
  if (pageTwo.isCurrent()) accepted.push('after-unmount');
  generations.mount();
  if (generations.begin().isCurrent()) accepted.push('remounted');

  expect(accepted).toEqual(['page-2', 'remounted']);
});

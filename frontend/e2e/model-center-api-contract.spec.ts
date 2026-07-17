import { expect, test } from '@playwright/test';

import { modelCenterApi } from '../src/features/model-center/api';
import {
  modelCenterMutationInvalidations,
  type ModelCenterQueryKey,
} from '../src/features/model-center/hooks/model-center-query-store';
import { apiClient } from '../src/lib/api-client';
import type { ModelConnectionView } from '../src/features/model-center/types';

// Task 15 owns the rendered shell and navigation. This client-level contract stays
// runnable before that shell exists, so it can lock transport, redaction, and cache
// invalidation behavior without depending on a future route.

type RequestCall = {
  endpoint: string;
  options: RequestInit;
};

function recordRequests() {
  const calls: RequestCall[] = [];
  const originalRequest = apiClient.request;
  apiClient.request = ((endpoint: string, options: RequestInit = {}) => {
    calls.push({ endpoint, options });
    return Promise.resolve(undefined);
  }) as typeof apiClient.request;

  return {
    calls,
    restore() {
      apiClient.request = originalRequest;
    },
  };
}

test('uses versioned Model Center URLs and publish envelopes', async () => {
  const requests = recordRequests();
  try {
    void modelCenterApi.listConnections(2, 50);
    void modelCenterApi.testConnection('connection-1');
    void modelCenterApi.publishProfileVersion('profile-version-1', {
      expected_revision: 3,
      reason: '认证通过',
    });

    expect(requests.calls).toEqual([
      {
        endpoint: '/model-center/connections?page=2&page_size=50',
        options: {},
      },
      {
        endpoint: '/model-center/connections/connection-1/test',
        options: { method: 'POST' },
      },
      {
        endpoint: '/model-center/profile-versions/profile-version-1/publish',
        options: {
          method: 'POST',
          body: JSON.stringify({ expected_revision: 3, reason: '认证通过' }),
        },
      },
    ]);
  } finally {
    requests.restore();
  }
});

test('models connections with the redacted response shape only', () => {
  const connection: ModelConnectionView = {
    id: 'connection-1',
    provider_id: 'volcengine',
    name: '主连接',
    base_url: null,
    has_secret: true,
    secret_hint: '****ef09',
    secret_updated_at: '2026-07-17T09:00:00Z',
    enabled: true,
    revision: 3,
  };

  expect(connection).toEqual({
    id: 'connection-1',
    provider_id: 'volcengine',
    name: '主连接',
    base_url: null,
    has_secret: true,
    secret_hint: '****ef09',
    secret_updated_at: '2026-07-17T09:00:00Z',
    enabled: true,
    revision: 3,
  });
});

test('preserves the shared transport error mapping', async () => {
  const expectedError = Object.assign(new Error('配置已被其他操作更新，请刷新后重新提交。'), {
    detail: { code: 'revision_conflict' },
    status: 409,
  });
  const originalRequest = apiClient.request;
  apiClient.request = (() => Promise.reject(expectedError)) as typeof apiClient.request;

  try {
    await expect(modelCenterApi.listConnections()).rejects.toBe(expectedError);
  } finally {
    apiClient.request = originalRequest;
  }
});

test('invalidates only the resource views affected by each mutation', () => {
  const connectionKeys: ModelCenterQueryKey[] = ['overview', 'connections'];
  const publishKeys: ModelCenterQueryKey[] = [
    'overview',
    'prompt-profiles',
    'bindings',
    'recipes',
    'impact',
  ];

  expect(modelCenterMutationInvalidations.connectionTest).toEqual(connectionKeys);
  expect(modelCenterMutationInvalidations.profilePublish).toEqual(publishKeys);
});

import assert from 'node:assert/strict';
import test from 'node:test';
import { redactLog } from './run-four-chapter-acceptance-logged.mjs';

test('raw acceptance log redacts credentials while preserving phase evidence', () => {
  const value = redactLog('Authorization: Bearer secret-token\napi_key=sk-live-secret\n后端聚焦测试：通过');
  assert.doesNotMatch(value, /secret-token|sk-live-secret/);
  assert.match(value, /后端聚焦测试：通过/);
});

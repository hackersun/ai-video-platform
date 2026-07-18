import { expect, test } from '@playwright/test';

import { legacyModelCenterHref, modelCenterHref, modelCenterSectionHref } from '../src/features/model-center/navigation';

test('model center links preserve exact task context without leaking external return URLs', () => {
  expect(modelCenterHref({
    section: 'test-lab',
    capability: 'speech_generation',
    runId: 'run-17',
    returnTo: '/studio/cards?novelId=novel-1',
  })).toBe('/llm-config?section=test-lab&capability=speech_generation&runId=run-17&returnTo=%2Fstudio%2Fcards%3FnovelId%3Dnovel-1');

  expect(modelCenterHref({ section: 'connections', returnTo: 'https://untrusted.example' }))
    .toBe('/llm-config?section=connections');

  expect(modelCenterSectionHref('bindings', {
    capability: 'video_generation',
    runId: 'run-17',
    returnTo: '/studio',
  })).toBe('/llm-config?section=bindings&capability=video_generation&runId=run-17&returnTo=%2Fstudio');

  expect(legacyModelCenterHref('connections', new URLSearchParams('capability=audio')))
    .toBe('/llm-config?section=connections&capability=speech_generation');
});

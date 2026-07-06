import { expect, request, test } from '@playwright/test';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';
const AUTH_TOKEN = process.env.REAL_CONTEXT_E2E_TOKEN || '';
const SKIP_MESSAGE = 'Set REAL_CONTEXT_E2E=1 after seeding the acceptance fixture.';

test.skip(process.env.REAL_CONTEXT_E2E !== '1', SKIP_MESSAGE);

async function api(path: string) {
  const context = await request.newContext({
    extraHTTPHeaders: {
      Authorization: `Bearer ${AUTH_TOKEN}`,
    },
  });

  try {
    const response = await context.get(`${API_BASE}${path}`);
    expect(response.ok(), `${response.status()} ${response.statusText()} for ${path}`).toBeTruthy();
    return response.json();
  } finally {
    await context.dispose();
  }
}

test('Series Studio loads a workflow with novel and chapter context', async ({ page }) => {
  const workflowId = process.env.REAL_CONTEXT_WORKFLOW_ID?.trim() || '';
  const novelId = process.env.REAL_CONTEXT_NOVEL_ID?.trim() || '';
  const chapterId = process.env.REAL_CONTEXT_CHAPTER_ID?.trim() || '';
  const userId = process.env.REAL_CONTEXT_E2E_USER_ID?.trim() || 'real-context-e2e-user';

  expect(workflowId, 'REAL_CONTEXT_WORKFLOW_ID must be set').not.toEqual('');
  expect(novelId, 'REAL_CONTEXT_NOVEL_ID must be set').not.toEqual('');
  expect(chapterId, 'REAL_CONTEXT_CHAPTER_ID must be set').not.toEqual('');

  const snapshot = await api(`/studio/workflows/${workflowId}/snapshot`);
  expect(snapshot.workflow.novel_id).toBe(novelId);
  expect(snapshot.workflow.chapter_id).toBe(chapterId);

  await page.addInitScript(({ authToken, authUserId }) => {
    localStorage.setItem('auth_token', authToken);
    localStorage.setItem('user', JSON.stringify({
      id: authUserId,
      username: authUserId,
      email: `${authUserId}@example.test`,
    }));
  }, { authToken: AUTH_TOKEN, authUserId: userId });

  const params = new URLSearchParams({
    workflow_id: workflowId,
    novel_id: novelId,
    chapter_id: chapterId,
  });

  await page.goto(`/studio?${params.toString()}`);
  await expect(page.getByTestId('studio-command-bar')).toBeVisible();
  await expect(page.getByTestId('studio-stage-flow')).toBeVisible();
  await expect(page.getByText('Production Bible').first()).toBeVisible();

  await page.goto(`/studio/cards?novel_id=${encodeURIComponent(novelId)}`);
  await expect(page.getByText(/定稿卡/).first()).toBeVisible();

  await page.goto(`/studio/shot-review?${params.toString()}`);
  await expect(page.getByText(/镜头|复审|重生/).first()).toBeVisible();
});

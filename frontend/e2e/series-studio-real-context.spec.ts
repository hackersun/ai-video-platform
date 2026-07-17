import { expect, request, test } from '@playwright/test';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';
const AUTH_TOKEN = process.env.REAL_CONTEXT_E2E_TOKEN || '';
const SKIP_MESSAGE = 'Set REAL_CONTEXT_E2E=1 after seeding the acceptance fixture.';

test.skip(process.env.REAL_CONTEXT_E2E !== '1', SKIP_MESSAGE);
test.use({ trace: 'off', screenshot: 'off', video: 'off' });

type AnyRecord = Record<string, any>;

function textValue(value: unknown) {
  return typeof value === 'string' ? value.trim() : '';
}

function firstText(...values: unknown[]) {
  for (const value of values) {
    const text = textValue(value);
    if (text) return text;
  }
  return '';
}

function cardVisibleLabel(card: AnyRecord) {
  return firstText(
    card.entity_name,
    card.name,
    card.title,
    card.character_name,
    card.entity?.name,
    card.profile?.name
  );
}

function shotVisibleLabel(shot: AnyRecord) {
  const label = firstText(shot.shot_title, shot.title, shot.prompt, shot.dialogue, shot.subtitle_text);
  if (label) return label;
  return shot.shot_number == null ? '' : `镜头 ${shot.shot_number}`;
}

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

  expect(AUTH_TOKEN, 'REAL_CONTEXT_E2E_TOKEN must be set').not.toEqual('');
  expect(workflowId, 'REAL_CONTEXT_WORKFLOW_ID must be set').not.toEqual('');
  expect(novelId, 'REAL_CONTEXT_NOVEL_ID must be set').not.toEqual('');
  expect(chapterId, 'REAL_CONTEXT_CHAPTER_ID must be set').not.toEqual('');

  const snapshot = await api(`/studio/workflows/${workflowId}/snapshot`);
  expect(snapshot.workflow.novel_id).toBe(novelId);
  expect(snapshot.workflow.chapter_id).toBe(chapterId);

  const productionCards = await api(`/production-cards/novel/${novelId}`);
  expect(Array.isArray(productionCards.cards), 'production cards response must include cards').toBeTruthy();
  expect(productionCards.cards.length, 'seeded novel must include at least one production card').toBeGreaterThan(0);
  const cardLabel = cardVisibleLabel(productionCards.cards[0]);
  expect(cardLabel, 'first production card must include a visible label').not.toEqual('');

  const shotReview = await api(`/workflow/${workflowId}/shot-review`);
  expect(Array.isArray(shotReview.shots), 'shot review response must include shots').toBeTruthy();
  expect(shotReview.shots.length, 'seeded workflow must include at least one shot-review item').toBeGreaterThan(0);
  const firstShot = shotReview.shots[0];
  const shotId = textValue(firstShot.shot_id);
  const shotLabel = shotVisibleLabel(firstShot);
  expect(shotId || shotLabel, 'first shot-review item must include a shot id or visible label').not.toEqual('');

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

  await page.goto(`/studio/cards?${params.toString()}`);
  await expect(page.getByText(/定稿卡/).first()).toBeVisible();
  await expect(page.getByText(cardLabel).first()).toBeVisible();

  await page.goto(`/studio/shot-review?${params.toString()}`);
  await expect(page.getByText(/镜头|复审|重生/).first()).toBeVisible();
  if (shotId) {
    await expect(page.getByTestId(`shot-review-card-${shotId}`)).toBeVisible();
  }
  if (shotLabel) {
    await expect(page.getByText(shotLabel).first()).toBeVisible();
  }
});

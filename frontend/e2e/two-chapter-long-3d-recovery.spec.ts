import { expect, test } from '@playwright/test';
import { writeFile } from 'node:fs/promises';

import { devToken } from './helpers/production-os-fixture';

const userId = process.env.TWO_CHAPTER_LIVE_USER_ID || '';
const novelId = process.env.TWO_CHAPTER_LIVE_NOVEL_ID || '';
const priorRunId = process.env.TWO_CHAPTER_LIVE_RUN_ID || '';
const badEntityGroups = [
  {
    chapterId: 'fb673790-2bae-4e98-9964-c1cf96f1b3b1',
    entityIds: ['9c544ba4-1567-4d0b-a696-bbcd493eea52'],
  },
  {
    chapterId: 'c4ec966d-3dc9-4859-a102-f8c94bcdc4e0',
    entityIds: [
      '1dcc817b-6d8c-4a88-8f02-d98b3b8742f3',
      'd17cabc0-09af-4d30-8990-25458c23cf18',
    ],
  },
];
const badEntityIds = badEntityGroups.flatMap((group) => group.entityIds);

test.describe.configure({ retries: 0 });

test('remove false narration entities and rebuild the two-chapter series run from UI', async ({ page }, testInfo) => {
  test.setTimeout(20 * 60_000);
  expect(testInfo.retry).toBe(0);
  expect(userId).toBeTruthy();
  expect(novelId).toBeTruthy();
  expect(priorRunId).toBeTruthy();

  const token = devToken(userId);
  await page.addInitScript(({ id, tokenValue }) => {
    localStorage.setItem('auth_token', tokenValue);
    localStorage.setItem('user', JSON.stringify({ id, username: 'sunqy' }));
  }, { id: userId, tokenValue: token });

  for (const group of badEntityGroups) {
    await page.goto(`/entities?novel_id=${novelId}&chapter_id=${group.chapterId}`);
    await expect(page.getByRole('heading', { name: '实体审阅台' })).toBeVisible();
    let selectedCount = 0;
    for (const entityId of group.entityIds) {
      if (entityId === '1dcc817b-6d8c-4a88-8f02-d98b3b8742f3') continue;
      const card = page.getByTestId(`entity-card-${entityId}`);
      if (await card.count()) {
        await card.getByRole('checkbox').click();
        selectedCount += 1;
      }
    }
    if (selectedCount > 0) {
      page.once('dialog', (dialog) => dialog.accept());
      await page.getByRole('button', { name: '批量删除' }).click();
      await page.waitForTimeout(1_000);
    }
  }

  const retainedEntityId = '1dcc817b-6d8c-4a88-8f02-d98b3b8742f3';
  await page.goto(`/entities?novel_id=${novelId}&chapter_id=c4ec966d-3dc9-4859-a102-f8c94bcdc4e0`);
  const retainedCard = page.getByTestId(`entity-card-${retainedEntityId}`);
  await expect(retainedCard).toBeVisible({ timeout: 30_000 });
  await retainedCard.getByRole('button', { name: /编辑(?:她睁眼|顾清霜)/ }).click();
  const dialog = page.getByRole('dialog', { name: '编辑实体' });
  await dialog.locator('input').nth(0).fill('顾清霜');
  await dialog.locator('input').nth(1).fill('顾清霜');
  await dialog.locator('textarea').nth(0).fill('二十四岁女剑修，坠星古墟两章唯一主角。');
  await dialog.locator('textarea').nth(1).fill(
    '清瘦女性面容，冷白肤色，黑发束成银环高马尾；靛青窄袖长袍绣银色星轨纹，暗红束带；左腕青铜星盘，背负霜衡细长银剑。',
  );
  const savedEntity = page.waitForResponse(
    (response) => response.url().endsWith(`/story-bibles/entities/${retainedEntityId}`)
      && response.request().method() === 'PUT',
  );
  await dialog.getByRole('button', { name: '保存' }).click();
  expect((await savedEntity).status()).toBe(200);
  await expect(retainedCard.getByText('顾清霜', { exact: true })).toBeVisible({ timeout: 30_000 });

  await page.goto(`/novels/${novelId}?tab=series-plan`);
  await page.getByRole('tab', { name: '整书计划 (2)', exact: true }).click();
  const rebuiltPlanResponse = page.waitForResponse(
    (response) => response.url().endsWith(`/novels/${novelId}/series-plan`)
      && response.request().method() === 'POST',
  );
  await page.getByRole('button', { name: '生成多集计划', exact: true }).click();
  const rebuiltPlan = await rebuiltPlanResponse;
  expect(rebuiltPlan.status()).toBe(200);
  expect((await rebuiltPlan.json()).style).toBe('xianxia-3d');
  await expect(page.getByText('xianxia-3d · 9:16')).toBeVisible({ timeout: 120_000 });
  await page.evaluate((id) => localStorage.removeItem(`series-run:${id}`), novelId);
  await page.reload();
  await page.getByRole('tab', { name: '整书计划 (2)', exact: true }).click();
  const panel = page.getByTestId('series-run-panel');
  await panel.getByRole('button', { name: '整书自动制作', exact: true }).click();
  await page.waitForFunction(
    ({ id, previous }) => {
      const current = localStorage.getItem(`series-run:${id}`);
      return Boolean(current && current !== previous);
    },
    { id: novelId, previous: priorRunId },
  );
  await expect(panel.getByTestId('series-run-episodes').getByText('镜头就绪')).toHaveCount(2, { timeout: 12 * 60_000 });
  for (const skill of ['剧本 Skill', '实体抽取 Skill', '分镜 Skill', '镜头提示词 Skill']) {
    await expect(panel.getByTestId('series-run-skill-evidence')).toContainText(skill);
  }

  const runId = await page.evaluate((id) => localStorage.getItem(`series-run:${id}`), novelId);
  expect(runId).toBeTruthy();
  await writeFile(testInfo.outputPath('recovery-run.json'), JSON.stringify({
    novel_id: novelId,
    run_id: runId,
    removed_false_entity_ids: badEntityIds,
  }, null, 2));
  await page.screenshot({ path: testInfo.outputPath('01-rebuilt-two-chapter-run.png'), fullPage: true });
});

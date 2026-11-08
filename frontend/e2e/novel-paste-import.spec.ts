import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `novel-import-user-${Date.now()}`;
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


test('paste novel text: recognizes chapters, auto-names an untitled paste, imports and opens detail', async ({ page }) => {
  let previewBody = '';
  let confirmPayload: any = null;
  const chapters = [
    { title: '第一章 雾港来客', chapter_number: 1, word_count: 20, preview: '沈砚抵达雾港。' },
    { title: '第二章 铜铃示警', chapter_number: 2, word_count: 18, preview: '铜铃响起。' },
  ];
  await page.route('**/api/v1/**', async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname.split('/api/v1')[1];
    if (req.method() === 'POST' && path === '/novels/import/preview') {
      previewBody = req.postDataBuffer()?.toString('utf-8') || '';
      await route.fulfill({ status: 201, json: { id: 'job-paste', title: '未命名小说', chapter_count: 2, chapters } });
      return;
    }
    if (req.method() === 'POST' && path === '/novels/import/confirm') {
      confirmPayload = req.postDataJSON();
      await route.fulfill({ status: 201, json: { id: 'novel-pasted', title: confirmPayload.title, chapters: [] } });
      return;
    }
    await route.fulfill({ json: path?.startsWith('/novels/novel-pasted') ? { id: 'novel-pasted', title: 'x', status: 'draft' } : [] });
  });

  await page.goto('/novels?start=paste');
  const box = page.getByTestId('novel-paste-input');
  await expect(box).toBeFocused();
  await expect(page.getByTestId('novel-paste-parse')).toBeDisabled();
  await box.fill('第一章 雾港来客\n沈砚抵达雾港。\n第二章 铜铃示警\n铜铃响起。');
  await page.getByTestId('novel-paste-parse').click();

  await expect(page.getByText('预览：2 章 · 首章《第一章 雾港来客》')).toBeVisible();
  expect(previewBody).toContain('filename="pasted.txt"');
  expect(previewBody).toContain('第二章 铜铃示警');
  await expect(page.getByPlaceholder('导入后小说标题')).toHaveValue(/^未命名小说 \d{1,2}-\d{2} \d{2}:\d{2}$/);

  await page.getByRole('button', { name: '确认导入' }).click();
  await expect(page).toHaveURL(/\/novels\/novel-pasted/);
  expect(confirmPayload.job_id).toBe('job-paste');
  expect(confirmPayload.title).toMatch(/^未命名小说 /);
});

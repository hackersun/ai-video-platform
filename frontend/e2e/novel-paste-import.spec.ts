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

  // 成功路径：不展开预览，直接进入详情
  await expect(page.getByTestId('novel-import-preview')).toHaveCount(0);
  expect(previewBody).toContain('filename="pasted.txt"');
  expect(previewBody).toContain('第二章 铜铃示警');
  await expect(page).toHaveURL(/\/novels\/novel-pasted/);
  expect(confirmPayload.job_id).toBe('job-paste');
  expect(confirmPayload.title).toMatch(/^未命名小说 /);
});

test('导入失败才展开预览，可改标题后确认导入', async ({ page }) => {
  let confirmPayload: any = null;
  const chapters = [
    { title: '第一章', chapter_number: 1, word_count: 10, preview: 'a' },
    { title: '第二章', chapter_number: 2, word_count: 10, preview: 'b' },
  ];
  let confirmCalls = 0;
  await page.route('**/api/v1/**', async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname.split('/api/v1')[1];
    if (req.method() === 'POST' && path === '/novels/import/preview') {
      await route.fulfill({ status: 201, json: { id: 'job-fail', title: '坏标题', chapter_count: 2, chapters } });
      return;
    }
    if (req.method() === 'POST' && path === '/novels/import/confirm') {
      confirmCalls += 1;
      confirmPayload = req.postDataJSON();
      if (confirmCalls === 1) {
        await route.fulfill({ status: 400, json: { detail: '标题冲突，请换一个名字' } });
        return;
      }
      await route.fulfill({ status: 201, json: { id: 'novel-retry', title: confirmPayload.title, chapters: [] } });
      return;
    }
    await route.fulfill({ json: path?.startsWith('/novels/novel-retry') ? { id: 'novel-retry', title: 'x', status: 'draft' } : [] });
  });

  await page.goto('/novels?start=paste');
  await page.getByTestId('novel-paste-input').fill('第一章\na\n第二章\nb');
  await page.getByTestId('novel-paste-parse').click();
  await expect(page.getByTestId('novel-import-preview')).toBeVisible();
  await expect(page.getByTestId('novel-import-preview')).toBeVisible();
  await expect(page.getByRole('main').getByText('标题冲突，请换一个名字')).toBeVisible();
  await page.getByPlaceholder('导入后小说标题').fill('修好的书名');
  await page.getByRole('button', { name: '确认导入' }).click();
  await expect(page).toHaveURL(/\/novels\/novel-retry/);
  expect(confirmPayload.title).toBe('修好的书名');
});

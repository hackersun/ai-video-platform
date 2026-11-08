import { expect, test } from './helpers/synthetic-media';

function devToken(userId: string) {
  const payload = Buffer.from(JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 86400 })).toString('base64url');
  return `dev.${payload}.sig`;
}

test('演示模式一键生成不弹确认、连点只提交一次，排队无人处理时给出明确提示', async ({ page }) => {
  test.setTimeout(60_000);
  const userId = `one-click-user-${Date.now()}`;
  await page.addInitScript(({ token, uid }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({ id: uid, username: uid, email: `${uid}@example.test` }));
  }, { token: devToken(userId), uid: userId });
  const nativeDialogs: string[] = [];
  page.on('dialog', async (dialog) => { nativeDialogs.push(dialog.message()); await dialog.dismiss(); });

  const novel = { id: 'novel-q', user_id: userId, title: '排队测试', description: '', genre: '悬疑', status: 'draft', word_count: 20, tags: [], source: 'manual', created_at: '2026-11-08T00:00:00', updated_at: '2026-11-08T00:00:00' };
  const chapters = [1, 2].map((n) => ({ id: `ch-${n}`, novel_id: novel.id, title: `第${n}章`, chapter_number: n, content: '沈砚说：“走。”', word_count: 10, status: 'completed', created_at: '2026-11-08T00:00:00', updated_at: '2026-11-08T00:00:00' }));
  const queued = { pipeline_id: 'pl-1', novel_id: novel.id, status: 'queued', stage: 'accepted', episodes: [], updated_at: '2026-11-08T00:00:00' };
  let pipelines: unknown[] = [];
  let posts = 0;

  await page.route('**/*', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (!url.pathname.includes('/api/v1')) return route.continue();
    const path = url.pathname.slice(url.pathname.indexOf('/api/v1') + 7);
    const method = request.method();
    if (method === 'GET' && path === `/novels/${novel.id}`) return route.fulfill({ json: novel });
    if (method === 'GET' && path === `/chapters/novel/${novel.id}`) return route.fulfill({ json: chapters });
    if (method === 'GET' && path === '/billing/settings') return route.fulfill({ json: { live_calls_opt_in: false, per_user_cap_rmb: '200.00', used_rmb: '0.00', opted_in_at: null } });
    if (method === 'GET' && path === '/model-center/simple-setup') return route.fulfill({ json: { providers: [], capabilities: {}, configured: true, verified: true, simulation_enabled: true } });
    if (method === 'GET' && path === `/novels/${novel.id}/publication-pipelines`) return route.fulfill({ json: pipelines });
    if (method === 'POST' && path === `/novels/${novel.id}/publication-pipelines`) {
      posts += 1;
      pipelines = [queued];
      return route.fulfill({ json: queued });
    }
    if (method === 'GET' && path === `/novels/${novel.id}/series-plan`) return route.fulfill({ status: 404, json: { detail: 'not found' } });
    return route.fulfill({ json: [] });
  });

  await page.goto(`/novels/${novel.id}`);
  const button = page.getByTestId('one-click-generate');
  await expect(button).toBeEnabled();
  await button.dblclick();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(button).toBeDisabled();

  const card = page.getByTestId('pipeline-status-card');
  await expect(card).toContainText('排队中，等待处理');
  await expect(page.getByTestId('pipeline-wait-hint')).toHaveCount(0);
  await expect(page.getByTestId('pipeline-wait-hint')).toContainText('处理节点繁忙或暂未启动', { timeout: 35_000 });
  expect(posts).toBe(1);
  expect(nativeDialogs).toEqual([]);

  await card.getByRole('button', { name: '取消' }).click();
  await expect(page.getByRole('dialog')).toContainText('取消本次生成？');
  expect(nativeDialogs).toEqual([]);
});

test('真实模式一键生成：站内确认框写明本次与账户花费上限，连点只弹一次', async ({ page }) => {
  const userId = `one-click-live-${Date.now()}`;
  await page.addInitScript(({ token, uid }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({ id: uid, username: uid, email: `${uid}@example.test` }));
  }, { token: devToken(userId), uid: userId });
  const nativeDialogs: string[] = [];
  page.on('dialog', async (dialog) => { nativeDialogs.push(dialog.message()); await dialog.dismiss(); });
  const novel = { id: 'novel-live', user_id: userId, title: '真实测试', description: '', genre: '悬疑', status: 'draft', word_count: 20, tags: [], source: 'manual', created_at: '2026-11-08T00:00:00', updated_at: '2026-11-08T00:00:00' };
  const chapters = [1, 2].map((n) => ({ id: `ch-${n}`, novel_id: novel.id, title: `第${n}章`, chapter_number: n, content: '沈砚说：“走。”', word_count: 10, status: 'completed', created_at: '2026-11-08T00:00:00', updated_at: '2026-11-08T00:00:00' }));
  let posts = 0;
  await page.route('**/*', async (route) => {
    const url = new URL(route.request().url());
    if (!url.pathname.includes('/api/v1')) return route.continue();
    const path = url.pathname.slice(url.pathname.indexOf('/api/v1') + 7);
    const method = route.request().method();
    if (method === 'GET' && path === `/novels/${novel.id}`) return route.fulfill({ json: novel });
    if (method === 'GET' && path === `/chapters/novel/${novel.id}`) return route.fulfill({ json: chapters });
    if (method === 'GET' && path === '/billing/settings') return route.fulfill({ json: { live_calls_opt_in: true, per_user_cap_rmb: '200.00', per_pipeline_cap_rmb: '50.00', used_rmb: '12.00', opted_in_at: '2026-11-08T00:00:00' } });
    if (method === 'GET' && path === '/model-center/simple-setup') return route.fulfill({ json: { providers: [], capabilities: {}, configured: true, verified: true, simulation_enabled: false } });
    if (method === 'POST' && path === `/novels/${novel.id}/publication-pipelines`) { posts += 1; return route.fulfill({ json: { pipeline_id: 'pl-live', novel_id: novel.id, status: 'queued', stage: 'accepted', episodes: [] } }); }
    if (method === 'GET' && path === `/novels/${novel.id}/series-plan`) return route.fulfill({ status: 404, json: { detail: 'not found' } });
    return route.fulfill({ json: [] });
  });
  await page.goto(`/novels/${novel.id}`);
  await page.getByTestId('one-click-generate').dblclick();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toHaveCount(1);
  await expect(dialog).toContainText('确认开始生成');
  await expect(dialog).toContainText('本次最多花费 ¥50.00，账户累计上限 ¥200.00（已用 ¥12.00）');
  expect(posts).toBe(0);
  await dialog.getByRole('button', { name: '开始生成' }).click();
  await expect(dialog).toHaveCount(0);
  await expect.poll(() => posts).toBe(1);
  expect(nativeDialogs).toEqual([]);
});

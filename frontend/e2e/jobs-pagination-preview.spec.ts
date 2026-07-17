import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

function makeVideoJobs(count: number) {
  const baseTime = new Date('2026-07-08T10:00:00.000Z').getTime();

  return Array.from({ length: count }, (_, index) => {
    const sequence = index + 1;
    const id = `video-${String(sequence).padStart(3, '0')}`;
    return {
      id,
      title: `镜头任务 ${String(sequence).padStart(2, '0')}`,
      status: sequence % 5 === 0 ? 'failed' : 'completed',
      progress: sequence % 5 === 0 ? 64 : 100,
      video_url: sequence % 5 === 0 ? undefined : `/outputs/${id}.mp4`,
      error_message: sequence % 5 === 0 ? '模型返回超时，请重新生成' : undefined,
      duration_seconds: 45 + sequence,
      created_at: new Date(baseTime - index * 60 * 1000).toISOString(),
      completed_at: sequence % 5 === 0 ? undefined : new Date(baseTime - index * 60 * 1000 + 55 * 1000).toISOString(),
    };
  });
}

test.beforeEach(async ({ page }) => {
  const userId = `jobs-user-${Date.now()}`;
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

test('jobs page paginates merged tasks and opens a task preview', async ({ page }) => {
  await page.route('**/api/v1/video/jobs**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(makeVideoJobs(26)) });
  });
  await page.route('**/api/v1/tts/jobs**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });
  await page.route('**/api/v1/images/jobs**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });
  await page.route('**/api/v1/synthesis/jobs**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });
  await page.route('**/api/v1/media/jobs**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });
  await page.route('**/api/v1/batch/list**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ total: 0, jobs: [] }) });
  });

  await page.goto('/jobs');

  await expect(page.getByRole('heading', { name: '任务队列' })).toBeVisible();
  await expect(page.getByText('显示 1-12 / 26').first()).toBeVisible();
  await expect(page.getByRole('button', { name: /查看镜头任务 01详情/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /查看镜头任务 12详情/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /查看镜头任务 13详情/ })).not.toBeVisible();

  await page.getByRole('button', { name: '下一页' }).click();

  await expect(page.getByText('显示 13-24 / 26').first()).toBeVisible();
  await expect(page.getByRole('button', { name: /查看镜头任务 13详情/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /查看镜头任务 01详情/ })).not.toBeVisible();

  await page.getByRole('button', { name: /查看镜头任务 13详情/ }).click();

  await expect(page.getByRole('heading', { name: '任务预览' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '镜头任务 13' })).toBeVisible();
  await expect(page.getByText('输出预览')).toBeVisible();
});

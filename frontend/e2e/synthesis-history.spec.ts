import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `synthesis-history-user-${Date.now()}`;
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

test('synthesis history can filter and preview render artifacts inline', async ({ page }) => {
  const synthesisRequests: string[] = [];

  await page.route('**/api/v1/video/jobs**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
  await page.route('**/api/v1/tts/jobs**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
  await page.route('**/api/v1/synthesis/publications**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
  await page.route('**/api/v1/synthesis/jobs**', async (route) => {
    const url = new URL(route.request().url());
    synthesisRequests.push(url.search);
    const novelId = url.searchParams.get('novel_id');
    const body = novelId && novelId !== 'novel-001'
      ? []
      : [
          {
            id: 'syn-render-001',
            job_id: 'syn-render-001',
            user_id: 'user-1',
            title: '第一章可播放渲染包',
            status: 'succeeded',
            progress: 100,
            output_url: '/static/exports/render-001-preview.html',
            manifest_url: '/static/exports/sequence-001.json',
            preview_url: '/static/exports/render-001-preview.html',
            srt_url: '/static/exports/render-001.srt',
            timeline_url: '/static/exports/render-001-timeline.json',
            render_manifest_url: '/static/exports/render-001.json',
            render_status: 'rendered',
            segment_count: 2,
            novel_id: 'novel-001',
            chapter_id: 'chapter-001',
            script_id: 'script-001',
            storyboard_id: 'storyboard-001',
            shot_id: 'shot-001',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ];
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });

  await page.goto('/synthesis');

  await expect(page.getByText('合成历史筛选')).toBeVisible();
  await page.getByLabel('小说ID').fill('novel-001');
  await page.getByLabel('章节ID').fill('chapter-001');
  await page.getByLabel('渲染状态').selectOption('rendered');
  await page.getByRole('button', { name: '筛选历史' }).click();

  await expect.poll(() => synthesisRequests.some((query) => query.includes('novel_id=novel-001'))).toBeTruthy();
  await expect(page.getByText('第一章可播放渲染包')).toBeVisible();

  await page.getByRole('button', { name: '预览 第一章可播放渲染包' }).click();

  await expect(page.getByTestId('synthesis-history-preview')).toBeVisible();
  await expect(page.getByText('历史预览：第一章可播放渲染包')).toBeVisible();
  await expect(page.getByRole('link', { name: '字幕 SRT' })).toBeVisible();
  await expect(page.getByRole('link', { name: '时间线' })).toBeVisible();
  await expect(page.getByRole('link', { name: '渲染清单' })).toBeVisible();
});

test('publication history exposes published render artifacts', async ({ page }) => {
  await page.route('**/api/v1/video/jobs**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
  await page.route('**/api/v1/tts/jobs**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
  await page.route('**/api/v1/synthesis/jobs**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
  await page.route('**/api/v1/synthesis/publications**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'pub-render-001',
          title: '第一章正式发布包',
          status: 'succeeded',
          export_url: '/static/exports/pub-render-001.json',
          provider: 'local',
          synthesis_job_id: 'syn-render-001',
          created_at: new Date().toISOString(),
          metadata: {
            source_output_url: '/static/exports/render-001-preview.html',
            render_artifacts: {
              preview_url: '/static/exports/render-001-preview.html',
              srt_url: '/static/exports/render-001.srt',
              timeline_url: '/static/exports/render-001-timeline.json',
              render_manifest_url: '/static/exports/render-001.json',
            },
          },
        },
      ]),
    });
  });

  await page.goto('/synthesis');

  const publicationRow = page.getByTestId('publication-row-pub-render-001');
  await expect(publicationRow).toBeVisible();
  await expect(publicationRow.getByRole('link', { name: '发布预览' })).toHaveAttribute('href', /render-001-preview\.html$/);
  await expect(publicationRow.getByRole('link', { name: '发布字幕 SRT' })).toHaveAttribute('href', /render-001\.srt$/);
  await expect(publicationRow.getByRole('link', { name: '发布时间线' })).toHaveAttribute('href', /render-001-timeline\.json$/);
  await expect(publicationRow.getByRole('link', { name: '发布渲染清单' })).toHaveAttribute('href', /render-001\.json$/);
});

test('synthesis history hides publish actions for review-only and unfinished jobs with reasons', async ({ page }) => {
  let publishAttempts = 0;
  let exportAttempts = 0;

  await page.route('**/api/v1/video/jobs**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
  await page.route('**/api/v1/tts/jobs**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
  await page.route('**/api/v1/synthesis/publications**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
  await page.route('**/api/v1/synthesis/publish', async (route) => {
    publishAttempts += 1;
    await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: '不可发布 job 不应请求发布' }) });
  });
  await page.route('**/api/v1/synthesis/export', async (route) => {
    exportAttempts += 1;
    await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: '不可发布 job 不应请求导出' }) });
  });
  await page.route('**/api/v1/synthesis/jobs**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'syn-review-only',
          job_id: 'syn-review-only',
          title: '第一章本地审阅包',
          status: 'succeeded',
          progress: 100,
          output_kind: 'preview_package',
          is_publishable: false,
          publish_block_reason: '当前只有本地预览包',
          output_url: '/static/exports/review-only-preview.html',
          preview_url: '/static/exports/review-only-preview.html',
          srt_url: '/static/exports/review-only.srt',
          timeline_url: '/static/exports/review-only-timeline.json',
          render_manifest_url: '/static/exports/review-only-render.json',
          render_status: 'rendered',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
        {
          id: 'syn-cloud-pending',
          job_id: 'syn-cloud-pending',
          title: '第一章云渲染等待中',
          status: 'processing',
          progress: 60,
          output_kind: 'final_video',
          is_publishable: false,
          publish_block_reason: '等待云渲染完成',
          manifest_url: '/static/exports/cloud-pending.json',
          render_status: 'rendering',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ]),
    });
  });

  await page.goto('/synthesis');

  const reviewRow = page.getByTestId('synthesis-job-row-syn-review-only');
  const pendingRow = page.getByTestId('synthesis-job-row-syn-cloud-pending');
  await expect(reviewRow).toBeVisible();
  await expect(pendingRow).toBeVisible();
  await expect(reviewRow).toContainText('当前只有本地预览包');
  await expect(pendingRow).toContainText('等待云渲染完成');
  await expect(reviewRow.getByRole('button', { name: '发布' })).toHaveCount(0);
  await expect(reviewRow.getByRole('button', { name: '导出' })).toHaveCount(0);
  await expect(pendingRow.getByRole('button', { name: '发布' })).toHaveCount(0);
  await expect(pendingRow.getByRole('button', { name: '导出' })).toHaveCount(0);
  expect(publishAttempts).toBe(0);
  expect(exportAttempts).toBe(0);
});

test('synthesis history publishes final video jobs and refreshes publication records', async ({ page }) => {
  let publicationsReadCount = 0;
  const publishBodies: Array<Record<string, unknown>> = [];

  await page.route('**/api/v1/video/jobs**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
  await page.route('**/api/v1/tts/jobs**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
  await page.route('**/api/v1/synthesis/jobs**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'syn-final-video',
          job_id: 'syn-final-video',
          title: '第一章正式成片',
          status: 'succeeded',
          progress: 100,
          output_kind: 'final_video',
          is_publishable: true,
          output_url: '/static/exports/final-video.mp4',
          video_url: '/static/exports/final-video.mp4',
          manifest_url: '/static/exports/final-video.json',
          render_status: 'rendered',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ]),
    });
  });
  await page.route('**/api/v1/synthesis/publications', async (route) => {
    if (route.request().method() === 'GET') {
      publicationsReadCount += 1;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(publicationsReadCount > 1 ? [
          {
            id: 'pub-final-video',
            title: '第一章正式成片',
            status: 'succeeded',
            export_url: '/static/exports/final-video.mp4',
            provider: 'local',
            synthesis_job_id: 'syn-final-video',
            created_at: new Date().toISOString(),
            metadata: {},
          },
        ] : []),
      });
      return;
    }
    await route.fallback();
  });
  await page.route('**/api/v1/synthesis/publish', async (route) => {
    publishBodies.push(route.request().postDataJSON());
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'pub-final-video',
        title: '第一章正式成片',
        status: 'succeeded',
        export_url: '/static/exports/final-video.mp4',
        synthesis_job_id: 'syn-final-video',
      }),
    });
  });

  await page.goto('/synthesis');

  const finalRow = page.getByTestId('synthesis-job-row-syn-final-video');
  await expect(finalRow).toBeVisible();
  await finalRow.getByRole('button', { name: '发布' }).click();

  await expect.poll(() => publishBodies.length).toBe(1);
  expect(publishBodies[0]).toMatchObject({ synthesis_job_id: 'syn-final-video', title: '第一章正式成片' });
  await expect.poll(() => publicationsReadCount).toBeGreaterThan(1);
  await expect(page.getByTestId('publication-row-pub-final-video')).toBeVisible();
});

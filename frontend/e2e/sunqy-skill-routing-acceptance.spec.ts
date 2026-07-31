import { expect, test } from '@playwright/test';

const userId = '56ae84de-951f-4e74-ac79-3550d6f6f3b2';
const apiBase = 'http://127.0.0.1:8000/api/v1';

test('sunqy starts a four-chapter Skill-routed production from the workbench', async ({ page }) => {
  await page.addInitScript(({ id }) => {
    localStorage.setItem('auth_token', id);
    localStorage.setItem('user', JSON.stringify({ id, username: 'sunqy' }));
  }, { id: userId });

  const title = `星渊遗钥-3D-Skill验收-${Date.now()}`;
  const chapters = [
    ['第一章 星门苏醒', '角色：林澈。场景：蓝晶车站。道具：黄铜星钥。事件：星门苏醒。林澈说：“必须在天亮前关闭星门。”'],
    ['第二章 追踪回声', '角色：林澈。场景：悬浮档案馆。道具：黄铜星钥。事件：追踪回声。林澈说：“回声指向档案馆深处。”'],
    ['第三章 守门人', '角色：林澈。角色：季衡。场景：星门控制厅。道具：黄铜星钥。事件：守门人现身。季衡说：“钥匙不能交给星门。”'],
    ['第四章 遗钥抉择', '角色：林澈。角色：季衡。场景：星门核心。道具：黄铜星钥。事件：关闭星门。林澈说：“这一次由我决定它的去向。”'],
  ];

  await page.goto('/novels/new');
  await page.getByPlaceholder('输入小说标题').fill(title);
  await page.getByPlaceholder('简要介绍小说内容').fill('电影级 3D 科幻悬疑连续短片，验证角色、场景、道具、事件和对白一致性。');
  await page.locator('select').first().selectOption('mystery');
  await page.getByRole('button', { name: '保存草稿' }).click();
  await page.waitForURL(/\/novels$/);
  const href = await page.getByRole('link', { name: new RegExp(title) }).first().getAttribute('href');
  expect(href).toBeTruthy();
  const novelId = href!.split('/').pop()!;
  await page.goto(`${href}?tab=chapters`);

  for (const [chapterTitle, content] of chapters) {
    await page.getByRole('button', { name: '新建章节' }).click();
    await page.getByPlaceholder(/章节标题，可留空/).fill(chapterTitle);
    await page.getByPlaceholder(/章节内容或创作方向/).fill(content);
    await page.getByRole('button', { name: '手动创建' }).click();
    await expect.poll(async () => {
      const response = await page.request.get(`${apiBase}/chapters/novel/${novelId}`, {
        headers: { Authorization: `Bearer ${userId}` },
      });
      return (await response.json()).length;
    }).toBe(chapters.indexOf(chapters.find((item) => item[0] === chapterTitle)!) + 1);
    await page.reload();
  }

  await page.getByRole('tab', { name: /整书计划/ }).click();
  await page.getByRole('button', { name: '生成多集计划', exact: true }).click();
  await page.getByRole('button', { name: '整书自动制作', exact: true }).click();
  await page.waitForFunction((id) => Boolean(localStorage.getItem(`series-run:${id}`)), novelId);
  const runId = await page.evaluate((id) => localStorage.getItem(`series-run:${id}`), novelId);
  await page.getByRole('button', { name: '继续推进' }).click();
  await expect(page.getByTestId('series-run-episodes').getByText('镜头就绪')).toHaveCount(4, { timeout: 180_000 });
  await expect(page.getByTestId('series-run-skill-evidence')).toContainText('标准剧本创建技能');
  await expect(page.getByTestId('series-run-skill-evidence')).toContainText('标准实体/资产抽取技能');
  await expect(page.getByTestId('series-run-skill-evidence')).toContainText('标准分镜创建技能');
  await expect(page.getByTestId('series-run-skill-evidence')).toContainText('标准镜头创建技能');
  await expect(page.getByTestId('series-run-skill-evidence')).toContainText('Skill 约束执行（确定性阶段）');

  const response = await page.request.get(`${apiBase}/series-runs/${runId}`, {
    headers: { Authorization: `Bearer ${userId}` },
  });
  expect(response.ok()).toBeTruthy();
  const run = await response.json();
  expect(run.episodes).toHaveLength(4);
  expect(run.episodes.every((episode: any) => episode.stage === 'shots_ready')).toBeTruthy();
  expect(run.run_metadata.skill_evidence.entity_extraction.runs).toHaveLength(4);
});

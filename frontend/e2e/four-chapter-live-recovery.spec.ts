import { expect, test } from '@playwright/test';
import { writeFile } from 'node:fs/promises';

import { devToken } from './helpers/production-os-fixture';

const userId = process.env.FOUR_CHAPTER_RECOVERY_USER_ID || '';
const novelId = process.env.FOUR_CHAPTER_RECOVERY_NOVEL_ID || '';
const runId = process.env.FOUR_CHAPTER_RECOVERY_RUN_ID || '';
const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';

test.describe.configure({ retries: 0 });

test('frontend resumes an existing Doubao TTS run without resubmitting providers', async ({ page }, testInfo) => {
  expect(userId).toBeTruthy();
  expect(novelId).toBeTruthy();
  expect(runId).toBeTruthy();
  const token = devToken(userId);
  const headers = { Authorization: `Bearer ${token}` };
  await page.addInitScript(({ id, novel, run, tokenValue }) => {
    localStorage.setItem('auth_token', tokenValue);
    localStorage.setItem('user', JSON.stringify({ id, username: 'live-recovery' }));
    localStorage.setItem(`series-run:${novel}`, run);
  }, { id: userId, novel: novelId, run: runId, tokenValue: token });

  const requests: string[] = [];
  let completedReconciliations = 0;
  page.on('request', (request) => {
    if (request.url().includes(`/series-runs/${runId}/`)) requests.push(request.url());
  });
  page.on('response', async (response) => {
    if (response.url().endsWith('/reconcile-selected') && response.ok()) {
      const payload = await response.json();
      if (payload.status === 'completed') completedReconciliations += 1;
    }
  });

  await page.goto(`/novels/${novelId}?tab=series-plan`);
  await expect.poll(() => completedReconciliations, { timeout: 120_000 }).toBeGreaterThan(0);
  await expect(page.getByText(/待可信多模态评估/)).toBeVisible({ timeout: 120_000 });
  expect(requests.some((url) => url.endsWith('/generate-selected'))).toBe(false);
  expect(requests.some((url) => /\/video\/jobs\/[^/]+\/refresh$/.test(url))).toBe(false);

  const run = await (await page.request.get(`${apiBase}/series-runs/${runId}`, { headers })).json();
  const recovery = await (await page.request.get(`${apiBase}/series-runs/${runId}/recovery`, { headers })).json();
  const selectedIds = run.run_metadata?.selected_anchor_shot_ids || [];
  const jobs = (await (await page.request.get(`${apiBase}/media/jobs?novel_id=${novelId}`, { headers })).json())
    .filter((job: any) => selectedIds.includes(job.shot_id));
  expect(selectedIds).toHaveLength(2);
  expect(jobs).toHaveLength(2);
  expect(jobs.every((job: any) => ['completed', 'succeeded'].includes(job.status))).toBe(true);
  expect(run.cost_summary).toMatchObject({ spent_rmb: '9.00', reserved_rmb: '0.00' });
  expect(recovery.operations).toEqual([]);
  expect(run.model_bindings.capabilities.tts).toMatchObject({
    config_id: 'sunqy-volcano-seed-tts-2-0',
    provider_id: 'volcano',
    api_model_id: 'seed-tts-2.0',
    contract_version: 'volcano.seed_tts.v3.v1',
    verification_status: 'verified',
  });

  const evidence = {
    run_id: run.id,
    novel_id: novelId,
    selected_count: selectedIds.length,
    cost_summary: {
      spent_rmb: run.cost_summary.spent_rmb,
      reserved_rmb: run.cost_summary.reserved_rmb,
    },
    tts_binding: run.model_bindings.capabilities.tts,
    jobs: jobs.map((job: any) => ({
      id: job.id,
      shot_id: job.shot_id,
      status: job.status,
      provider_id: job.provider_id,
      task_id: job.task_id,
      has_artifact: Boolean(job.output_manifest_url || job.output_video_url || job.output_audio_url),
    })),
    frontend_reconciliations: completedReconciliations,
    provider_resubmissions: 0,
  };
  expect(JSON.stringify(evidence)).not.toMatch(/"(?:api[_-]?key|api[_-]?secret|secret|password|prompt)"\s*:/i);
  await writeFile(testInfo.outputPath('doubao-recovery-evidence.json'), JSON.stringify(evidence, null, 2), { mode: 0o600 });
  await page.screenshot({ path: testInfo.outputPath('doubao-recovery-workbench.png'), fullPage: true });
});

import { expect, test } from '@playwright/test';

const dimensions = ['narrative_truth', 'character_visual', 'scene_prop_state', 'motion_camera', 'voice_lipsync', 'delivery_integrity'];

function qualityGate(issueCode: 'wrong_speaker' | 'wrong_prop_owner', artifactId: string) {
  const issueDimension = issueCode === 'wrong_speaker' ? 'voice_lipsync' : 'scene_prop_state';
  return {
    ready: false,
    overall_readiness: 'blocked',
    blockers: [{ code: issueCode, dimension: issueDimension }],
    warnings: [],
    dimensions: dimensions.map((dimension) => ({
      id: `${artifactId}-${dimension}`,
      dimension,
      expected_state: issueCode === 'wrong_speaker' ? { speaker_id: 'character-lin' } : { prop_owners: { key: 'character-su' } },
      observed_state: dimension === issueDimension ? { mismatch: true } : {},
      evidence: { source: 'server_deterministic' },
      score: dimension === issueDimension ? 0 : 100,
      confidence: 1,
      severity: dimension === issueDimension ? 'blocking' : 'pass',
      blocking: dimension === issueDimension,
      artifact_id: artifactId,
    })),
    suggested_repair: {
      issue_code: issueCode,
      actions: issueCode === 'wrong_speaker'
        ? ['regenerate_tts', 'rerun_lipsync', 'rerender_audio']
        : ['regenerate_shot_video', 'rerun_visual_review'],
      affected_artifact_ids: [artifactId],
      cost_risk: { cost: 'low', risk: 'low', scope: issueCode === 'wrong_speaker' ? 'audio_only' : 'shot_video_only' },
      available: true,
    },
  };
}

test('shot review triggers server evaluation and repairs wrong voice and wrong prop independently', async ({ page }) => {
  const evaluateRequests: any[] = [];
  const repairRequests: any[] = [];
  const repairResponses: any[] = [];
  const evaluated = new Set<string>();
  const repaired = new Set<string>();
  await page.addInitScript(() => {
    localStorage.setItem('auth_token', 'dev.mock.sig');
    localStorage.setItem('user', JSON.stringify({ id: 'quality-user' }));
  });
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === '/api/v1/workflow/wf-quality/shot-review') {
      const shot = (id: string, number: number, issue: 'wrong_speaker' | 'wrong_prop_owner', artifact: string) => ({
        shot_id: id, shot_number: number, latest_video_job_id: `video-${number}`, latest_tts_job_id: `tts-${number}`,
        status: 'succeeded', duration: 4, subtitle_text: '对白', character_names: ['角色'], evidence: {}, regeneration_count: 0,
        quality_gate: repaired.has(id) ? { ready: true, overall_readiness: 'ready', blockers: [], warnings: [], dimensions: qualityGate(issue, artifact).dimensions.map((item: any) => ({ ...item, score: 100, severity: 'pass', blocking: false })), suggested_repair: null }
          : evaluated.has(id) ? qualityGate(issue, artifact) : null,
      });
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ workflow_id: 'wf-quality', shots: [shot('shot-1', 1, 'wrong_speaker', 'tts-1'), shot('shot-2', 2, 'wrong_prop_owner', 'video-2')] }) });
      return;
    }
    if (path.endsWith('/quality/evaluate') && request.method() === 'POST') {
      const body = request.postDataJSON(); evaluateRequests.push(body); evaluated.add(body.shot_id);
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ready: false, blockers: [{ code: body.shot_id === 'shot-1' ? 'wrong_speaker' : 'wrong_prop_owner' }] }) });
      return;
    }
    if (path.endsWith('/quality/repair') && request.method() === 'POST') {
      const body = request.postDataJSON(); repairRequests.push(body); repaired.add(body.shot_id);
      const payload = { unchanged_artifact_ids: body.shot_id === 'shot-1' ? ['video-1', 'video-2', 'tts-2'] : ['video-1', 'tts-1-repaired', 'tts-2'], evaluation_ready: true, overall_readiness: 'ready' };
      repairResponses.push(payload);
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/studio/shot-review?workflow_id=wf-quality');
  await page.getByRole('button', { name: '开始检查镜头 1' }).click();
  await expect.poll(() => evaluateRequests).toContainEqual({ shot_id: 'shot-1' });
  const voiceGate = page.getByTestId('quality-gate-shot-1');
  await expect(voiceGate).toContainText('交付检查（6 项）');
  await expect(voiceGate).toContainText('1 项需要处理');
  await expect(voiceGate.getByTestId('quality-dimension-shot-1-voice_lipsync')).toContainText('说话人与锁定角色不一致或无法确认');
  await expect(voiceGate.locator('pre')).toHaveCount(0);
  await voiceGate.getByRole('button', { name: '重新生成镜头 1 配音并重跑口型' }).click();
  await expect.poll(() => repairRequests).toContainEqual({ shot_id: 'shot-1', issue_code: 'wrong_speaker' });
  expect(repairResponses[0].unchanged_artifact_ids).toEqual(['video-1', 'video-2', 'tts-2']);
  await expect(page.getByText('已完成最小返修；未改动 3 个无关任务')).toBeVisible();
  await expect(page.getByTestId('quality-gate-shot-1')).toContainText('全部通过，可以进入成片复审');
  await expect(page.getByRole('button', { name: '开始检查镜头 2' })).toBeVisible();

  await page.getByRole('button', { name: '开始检查镜头 2' }).click();
  await expect.poll(() => evaluateRequests).toContainEqual({ shot_id: 'shot-2' });
  const propGate = page.getByTestId('quality-gate-shot-2');
  await expect(propGate.getByTestId('quality-dimension-shot-2-scene_prop_state')).toContainText('道具归属与故事设定不一致');
  await propGate.getByRole('button', { name: '重新生成镜头 2 视频并复审画面' }).click();
  await expect.poll(() => repairRequests).toContainEqual({ shot_id: 'shot-2', issue_code: 'wrong_prop_owner' });
  expect(repairResponses[1].unchanged_artifact_ids).toEqual(['video-1', 'tts-1-repaired', 'tts-2']);
  await expect(page.getByText('已完成最小返修；未改动 3 个无关任务')).toBeVisible();
  await expect(page.getByTestId('quality-gate-shot-2')).toContainText('全部通过，可以进入成片复审');
  await expect(page.getByTestId('quality-gate-shot-1')).toContainText('全部通过，可以进入成片复审');
  await expect(page.getByRole('button', { name: /重试全部/ })).toHaveCount(0);
});

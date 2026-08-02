'use client';

import { useState } from 'react';

import { apiClient } from '@/lib/api-client';
import { previousSelectedShotId } from './first-frame-continuity';

type FirstFrameFailure = { shotId: string; message: string };

const isRealFirstFrame = (url?: string | null) => Boolean(url && !url.includes('/static/dev/'));

const waitForShotImage = async (shotId: string) => {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    const shot = await apiClient.getShot(shotId);
    if (shot.image_status === 'succeeded' && isRealFirstFrame(shot.image_url)) return shot;
    if (shot.image_status === 'succeeded' && !isRealFirstFrame(shot.image_url)) {
      throw new Error('实模首帧不能使用开发占位图，请点击“只重试失败项”重新调用真实图像模型');
    }
    if (shot.image_status === 'failed') {
      throw new Error(shot.extra_data?.image_generation_error || '镜头首帧生成失败');
    }
    await new Promise((resolve) => window.setTimeout(resolve, 2000));
  }
  throw new Error('镜头首帧仍在生成，可稍后刷新状态或只重试失败项');
};

export function useSelectedFirstFrames({
  runId,
  selected,
  style,
  imageConfigId,
  refreshPreflight,
}: {
  runId?: string;
  selected: string[];
  style: string;
  imageConfigId?: string;
  refreshPreflight: () => Promise<unknown>;
}) {
  const [busy, setBusy] = useState(false);
  const [regeneratingShotId, setRegeneratingShotId] = useState('');
  const [failures, setFailures] = useState<FirstFrameFailure[]>([]);
  const [message, setMessage] = useState('');

  const generate = async (retryFailures = false) => {
    if (!runId || !imageConfigId) return;
    const targetIds = retryFailures && failures.length ? failures.map((item) => item.shotId) : selected;
    setBusy(true);
    setFailures([]);
    setMessage(`正在检查 ${targetIds.length} 个镜头首帧…`);
    const nextFailures: FirstFrameFailure[] = [];
    let succeeded = 0;
    for (const shotId of targetIds) {
      try {
        const current = await apiClient.getShot(shotId);
        if (!isRealFirstFrame(current.image_url) || current.image_status !== 'succeeded') {
          const previousId = previousSelectedShotId(selected, shotId);
          const previous = previousId ? await apiClient.getShot(previousId) : null;
          const continuityId = previous?.image_status === 'succeeded' && isRealFirstFrame(previous.image_url)
            ? previous.id
            : undefined;
          const result = await apiClient.generateShotImage(shotId, {
            style,
            model_config_id: imageConfigId,
            continuity_reference_shot_id: continuityId,
          });
          if (result.status !== 'succeeded' || !isRealFirstFrame(result.image_url)) await waitForShotImage(shotId);
        }
        succeeded += 1;
        setMessage(`镜头首帧处理中：${succeeded}/${targetIds.length} 已完成`);
      } catch (reason: any) {
        nextFailures.push({ shotId, message: reason?.message || '镜头首帧生成失败' });
      }
    }
    setFailures(nextFailures);
    setMessage(nextFailures.length
      ? `${succeeded} 个首帧已完成，${nextFailures.length} 个失败；已保留成功结果，可只重试失败项。`
      : `${targetIds.length} 个镜头首帧已全部完成。`);
    await refreshPreflight().catch(() => null);
    setBusy(false);
  };

  const regenerateShot = async (shotId: string) => {
    if (!runId || !imageConfigId || regeneratingShotId) return;
    setRegeneratingShotId(shotId);
    setFailures((items) => items.filter((item) => item.shotId !== shotId));
    setMessage('正在仅重做当前镜头参考；系列角色三视图不会被替换…');
    try {
      const previousId = previousSelectedShotId(selected, shotId);
      const identityReference = previousId ? await apiClient.getShot(previousId) : null;
      const result = await apiClient.generateShotImage(shotId, {
        style,
        model_config_id: imageConfigId,
        continuity_reference_shot_id: identityReference?.image_status === 'succeeded'
          && isRealFirstFrame(identityReference.image_url) ? identityReference.id : undefined,
      });
      if (result.status !== 'succeeded' || !isRealFirstFrame(result.image_url)) {
        await waitForShotImage(shotId);
      }
      setMessage('当前镜头参考已更新；其他章节继续复用原有角色三视图。');
    } catch (reason: any) {
      const failure = { shotId, message: reason?.message || '当前镜头参考生成失败' };
      setFailures((items) => [...items.filter((item) => item.shotId !== shotId), failure]);
      setMessage('当前镜头参考重做失败；其他章节及已成功结果未受影响，可再次单独重试。');
    } finally {
      await refreshPreflight().catch(() => null);
      setRegeneratingShotId('');
    }
  };

  return {
    busy: busy || Boolean(regeneratingShotId),
    regeneratingShotId,
    failures,
    message,
    generate,
    regenerateShot,
  };
}

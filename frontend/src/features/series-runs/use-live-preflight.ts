import { useState } from 'react';

import { apiClient, type LivePreflightPlan } from '@/lib/api-client';

export function useLivePreflight() {
  const [preflightPlan, setPreflightPlan] = useState<LivePreflightPlan | null>(null);
  const [preflightLoading, setPreflightLoading] = useState(false);
  const [preflightError, setPreflightError] = useState('');
  const [selectedVoiceId, setSelectedVoiceId] = useState('');

  const refreshPreflightPlan = async (runId: string, nativeAudio = false) => {
    setPreflightLoading(true);
    setPreflightError('');
    try {
      for (let attempt = 0; attempt < 3; attempt += 1) {
        try {
          const plan = await apiClient.getSeriesRunLivePreflightPlan(runId, nativeAudio);
          setPreflightPlan(plan);
          setSelectedVoiceId((current) => plan.blocker_codes.includes('voice_selection_stale')
            ? ''
            : plan.voice_options?.selection?.voice_id || current || plan.voice_options?.options[0]?.voice_id || '');
          return plan;
        } catch (reason: any) {
          if (reason?.status !== 500 || attempt === 2) throw reason;
          await new Promise((resolve) => setTimeout(resolve, 250 * (attempt + 1)));
        }
      }
      throw new Error('前置状态读取失败');
    } catch (reason: any) {
      setPreflightError(reason?.message || '前置状态读取失败，请手动刷新。');
      throw reason;
    } finally {
      setPreflightLoading(false);
    }
  };

  return { preflightPlan, preflightLoading, preflightError, selectedVoiceId,
    setSelectedVoiceId, refreshPreflightPlan };
}

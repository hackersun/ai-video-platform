'use client';

import { useState } from 'react';

import { modelCenterApi } from '../api';
import { usePromptProfiles } from '../hooks/use-prompt-profiles';
import type { PromptProfileView, ResourceImpact } from '../types';
import { ImpactDialog } from './impact-dialog';
import { PromptProfileEditor } from './prompt-profile-editor';
import { ModelCenterEmpty, ModelCenterError, ModelCenterLoading } from './model-center-state';

type ImpactAction = { profile: PromptProfileView; kind: 'publish' | 'rollback'; impact: ResourceImpact };

export function PromptProfileList() {
  const query = usePromptProfiles();
  const [selected, setSelected] = useState<PromptProfileView | null>(null);
  const [action, setAction] = useState<ImpactAction | null>(null);
  const [reason, setReason] = useState('');
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  if (query.loading && !query.data) return <ModelCenterLoading label="正在读取提示词版本…" />;
  if (query.error && !query.data) return <ModelCenterError error={query.error} onRetry={() => void query.reload()} />;
  const profiles = query.data?.items || [];
  const active = selected || profiles[0] || null;
  const openImpact = async (profile: PromptProfileView, kind: ImpactAction['kind']) => {
    setMessage(null);
    try {
      const impact = await modelCenterApi.getImpact();
      setReason('');
      setAction({ profile, kind, impact });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '无法读取发布影响，请稍后重试。');
    }
  };
  const confirm = async () => {
    if (!action) return;
    if (action.kind === 'rollback') return setMessage('回滚 API 尚未启用；历史版本保持不变，待服务端接口启用后可重新提交。');
    setPending(true);
    try {
      await query.publishPromptProfileVersion(action.profile.id, { expected_revision: action.profile.revision, reason });
      setAction(null);
      setMessage('发布请求已提交。');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '发布请求失败');
    } finally {
      setPending(false);
    }
  };
  return <div className="p-4"><header><h2 className="text-sm font-semibold text-white">不可变提示词版本</h2><p className="mt-1 text-xs text-slate-500">编辑产生新版本；发布前必须核对影响范围与确定性样例。</p></header>{message && <p className="mt-4 rounded-md bg-amber-500/10 px-3 py-2 text-xs text-amber-100">{message}</p>}{profiles.length ? <div className="mt-4 grid gap-4 xl:grid-cols-[16rem_minmax(0,1fr)]"><nav aria-label="提示词版本" className="space-y-2">{profiles.map((profile) => <button type="button" key={profile.id} onClick={() => setSelected(profile)} className={`w-full rounded-lg border p-3 text-left ${active?.id === profile.id ? 'border-violet-400/50 bg-violet-500/10' : 'border-white/10 bg-black/10'}`}><span className="block text-sm font-medium text-white">{profile.profile_key}</span><span className="mt-1 block text-xs text-slate-500">v{profile.version} · {profile.status}</span></button>)}</nav>{active && <PromptProfileEditor profile={active} onPublish={() => void openImpact(active, 'publish')} onRollback={() => void openImpact(active, 'rollback')} />}</div> : <ModelCenterEmpty title="还没有提示词版本" description="提示词版本会在后端写入接口启用后统一维护。" />}{action && <ImpactDialog title={action.kind === 'publish' ? '发布影响确认' : '回滚影响确认'} description={action.kind === 'publish' ? '发布会让受影响的模型版本和生产方案在后续任务中解析到此提示词版本。' : '将创建新的头版本，不会改写任何历史版本。'} impact={action.impact} reason={reason} confirmLabel={action.kind === 'publish' ? '确认发布' : '确认回滚'} pending={pending} onReasonChange={setReason} onCancel={() => setAction(null)} onConfirm={() => void confirm()} />}</div>;
}

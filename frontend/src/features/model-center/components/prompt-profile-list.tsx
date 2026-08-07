'use client';

import { FormEvent, useState } from 'react';
import { Plus, X } from 'lucide-react';
import Link from 'next/link';

import { modelCenterApi } from '../api';
import { usePromptProfiles } from '../hooks/use-prompt-profiles';
import type { ModelCenterLocation } from '../navigation';
import type { PromptProfileInput, PromptProfileView, ResourceImpact } from '../types';
import { ImpactDialog } from './impact-dialog';
import { emptyPromptDraft, PromptFields, promptVersionInput } from './prompt-profile-editor';
import { PromptProfileWorkbench } from './prompt-profile-workbench';
import { ModelCenterEmpty, ModelCenterError, ModelCenterLoading } from './model-center-state';

type ImpactAction = { profile: PromptProfileView; kind: 'publish' | 'rollback'; impact: ResourceImpact };

function CreatePromptDialog({ onClose, onSave }: { onClose: () => void; onSave: (input: PromptProfileInput) => Promise<void> }) {
  const [key, setKey] = useState('');
  const [name, setName] = useState('');
  const [task, setTask] = useState('');
  const [stage, setStage] = useState('');
  const [draft, setDraft] = useState(emptyPromptDraft);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const update = (field: keyof typeof draft, value: string) => setDraft((current) => ({ ...current, [field]: value }));
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      setPending(true);
      setError(null);
      const version = promptVersionInput(draft, 1);
      await onSave({ key: key.trim(), name: name.trim(), task: task.trim(), stage: stage.trim() || null, system_contract: version.system_contract || '', task_template: version.task_template || '', input_mapping: version.input_mapping || {}, output_schema: version.output_schema || {}, negative_constraints: version.negative_constraints || [], model_family_overrides: version.model_family_overrides || {}, validation_fixtures: version.validation_fixtures || [], release_notes: version.release_notes || '' });
      onClose();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '提示词草稿保存失败');
    } finally {
      setPending(false);
    }
  };
  return <div role="dialog" aria-modal="true" aria-label="新建提示词模板" className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/80 p-4 sm:p-8"><form onSubmit={submit} className="mx-auto max-w-4xl rounded-xl border border-white/15 bg-slate-900 p-5 shadow-2xl"><header className="flex items-start justify-between gap-4"><div><h2 className="text-xl font-semibold text-white">新建提示词模板</h2><p className="mt-1 text-sm text-slate-400">创建不可变草稿版本；结构化字段会随版本持久化。</p></div><button type="button" aria-label="关闭提示词编辑器" onClick={onClose} className="model-center-quiet"><X className="h-4 w-4" /></button></header><div className="mt-4 grid gap-3 sm:grid-cols-2"><label className="text-xs text-slate-400">模板键<input aria-label="模板键" required value={key} onChange={(event) => setKey(event.target.value)} className="model-center-input mt-1 w-full" /></label><label className="text-xs text-slate-400">模板名称<input aria-label="模板名称" required value={name} onChange={(event) => setName(event.target.value)} className="model-center-input mt-1 w-full" /></label><label className="text-xs text-slate-400">任务类型<input aria-label="任务类型" required value={task} onChange={(event) => setTask(event.target.value)} className="model-center-input mt-1 w-full" placeholder="例如 shot_video" /></label><label className="text-xs text-slate-400">阶段（可选）<input aria-label="阶段" value={stage} onChange={(event) => setStage(event.target.value)} className="model-center-input mt-1 w-full" /></label></div><PromptFields draft={draft} onChange={update} /><footer className="mt-5 flex justify-end gap-2"><button type="button" onClick={onClose} className="model-center-quiet">取消</button><button type="submit" disabled={pending || !key.trim() || !name.trim() || !task.trim()} className="model-center-primary">{pending ? '保存中' : '保存提示词草稿'}</button></footer>{error && <p className="mt-3 rounded-md bg-rose-500/10 px-3 py-2 text-xs text-rose-100">{error}</p>}</form></div>;
}

export function PromptProfileList({ location, initialSelectedId = null }: { location: ModelCenterLocation; initialSelectedId?: string | null }) {
  const query = usePromptProfiles();
  const [selectedId, setSelectedId] = useState<string | null>(initialSelectedId);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('all');
  const [action, setAction] = useState<ImpactAction | null>(null);
  const [reason, setReason] = useState('');
  const [pending, setPending] = useState(false);
  const [creating, setCreating] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  if (query.loading && !query.data) return <ModelCenterLoading label="正在读取提示词版本…" />;
  if (query.error && !query.data) return <ModelCenterError error={query.error} onRetry={() => void query.reload()} />;
  const profiles = query.data?.items || [];
  const filtered = profiles.filter((profile) => {
    const keyword = search.trim().toLowerCase();
    const matchesKeyword = !keyword || `${profile.name} ${profile.key} ${profile.task}`.toLowerCase().includes(keyword);
    return matchesKeyword && (status === 'all' || profile.status === status);
  });
  const active = filtered.find((profile) => profile.id === selectedId) || filtered[0] || null;
  const openImpact = async (profile: PromptProfileView, kind: ImpactAction['kind']) => {
    try {
      setMessage(null);
      const impact = await modelCenterApi.getImpact('prompt_profile', profile.id);
      setReason('');
      setAction({ profile, kind, impact });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '无法读取发布影响，请稍后重试。');
    }
  };
  const confirm = async () => {
    if (!action || action.profile.head_version === null || !action.profile.head_version_id) return;
    try {
      setPending(true);
      if (action.kind === 'publish') await query.publishPromptProfileVersion(action.profile.head_version_id, { expected_revision: action.profile.head_version, reason });
      else await query.rollbackPromptProfile(action.profile.id, { expected_revision: action.profile.head_version, target_version_id: action.profile.head_version_id, reason });
      setAction(null);
      setMessage(action.kind === 'publish' ? '发布请求已提交。' : '已创建新的回滚草稿版本。');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '提示词版本操作失败');
    } finally {
      setPending(false);
    }
  };
  return <div className="p-4"><header className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-sm font-semibold text-white">提示词版本工作台</h2><p className="mt-1 text-xs text-slate-500">正文、历史、AI 优化和预览已统一到同一个版本工作区。</p></div><div className="flex flex-wrap gap-2">{location.returnTo && <Link href={location.returnTo} className="model-center-quiet">返回工作台</Link>}<button type="button" onClick={() => setCreating(true)} className="model-center-primary"><Plus className="h-4 w-4" />新建提示词模板</button></div></header><div className="mt-4 flex flex-wrap gap-2"><input aria-label="搜索提示词" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索名称、键或任务" className="model-center-input min-w-56 flex-1" /><select aria-label="提示词状态" value={status} onChange={(event) => setStatus(event.target.value)} className="model-center-input"><option value="all">全部状态</option><option value="draft">草稿</option><option value="published">已发布</option><option value="disabled">已停用</option></select></div>{message && <p className="mt-4 rounded-md bg-amber-500/10 px-3 py-2 text-xs text-amber-100">{message}</p>}{profiles.length ? <div className="mt-4 grid gap-4 xl:grid-cols-[16rem_minmax(0,1fr)]"><nav aria-label="提示词版本" className="space-y-2">{filtered.map((profile) => <button type="button" key={profile.id} onClick={() => setSelectedId(profile.id)} className={`w-full rounded-lg border p-3 text-left ${active?.id === profile.id ? 'border-violet-400/50 bg-violet-500/10' : 'border-white/10 bg-black/10'}`}><span className="block text-sm font-medium text-white">{profile.name}</span><span className="mt-1 block text-xs text-slate-500">{profile.key} · v{profile.head_version ?? '—'} · {profile.status || '未创建'}</span></button>)}</nav>{active && <PromptProfileWorkbench profile={active} onSaveVersion={async (input) => { await query.createPromptProfileVersion(active.id, input); setMessage('新草稿版本已保存。'); }} onPublish={() => void openImpact(active, 'publish')} onRollback={() => void openImpact(active, 'rollback')} onLegacyChanged={async () => { await query.reload(); }} />}</div> : <ModelCenterEmpty title="还没有提示词版本" description="从新建模板开始，后续编辑将创建不可变草稿版本。" />}{creating && <CreatePromptDialog onClose={() => setCreating(false)} onSave={async (input) => { await query.createPromptProfile(input); setMessage('提示词草稿已保存。'); }} />}{action && <ImpactDialog title={action.kind === 'publish' ? '发布影响确认' : '回滚影响确认'} description={action.kind === 'publish' ? '发布会让受影响模型版本和生产方案在后续任务中解析到此提示词版本。' : '将创建新的头版本，不会改写任何历史版本。'} impact={action.impact} reason={reason} confirmLabel={action.kind === 'publish' ? '确认发布' : '确认回滚'} pending={pending} onReasonChange={setReason} onCancel={() => setAction(null)} onConfirm={() => void confirm()} />}</div>;
}

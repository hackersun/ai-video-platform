'use client';

import { History, Save } from 'lucide-react';
import { useEffect, useState } from 'react';

import type {
  PromptProfileDetail,
  PromptProfileVersionDetail,
  PromptProfileVersionInput,
  PromptProfileView,
} from '../types';

export type PromptDraft = {
  systemContract: string;
  taskTemplate: string;
  inputMapping: string;
  outputSchema: string;
  negativeConstraints: string;
  modelFamilyOverrides: string;
  validationFixtures: string;
  releaseNotes: string;
};

export const emptyPromptDraft: PromptDraft = {
  systemContract: '', taskTemplate: '', inputMapping: '{}', outputSchema: '{}',
  negativeConstraints: '', modelFamilyOverrides: '{}', validationFixtures: '[]', releaseNotes: '',
};

export function promptDraftFromVersion(
  version: PromptProfileVersionDetail,
): PromptDraft {
  return {
    systemContract: version.system_contract,
    taskTemplate: version.task_template,
    inputMapping: JSON.stringify(version.input_mapping || {}, null, 2),
    outputSchema: JSON.stringify(version.output_schema || {}, null, 2),
    negativeConstraints: (version.negative_constraints || []).join('\n'),
    modelFamilyOverrides: JSON.stringify(version.model_family_overrides || {}, null, 2),
    validationFixtures: JSON.stringify(version.validation_fixtures || [], null, 2),
    releaseNotes: version.release_notes || '',
  };
}

function parseObject(value: string, label: string) {
  const parsed = JSON.parse(value);
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error(`${label}必须是 JSON 对象。`);
  return parsed as Record<string, unknown>;
}

function parseFixtures(value: string) {
  const parsed = JSON.parse(value);
  if (!Array.isArray(parsed) || parsed.some((item) => !item || typeof item !== 'object' || Array.isArray(item))) throw new Error('验证样例必须是 JSON 对象数组。');
  return parsed as Array<Record<string, unknown>>;
}

export function promptVersionInput(draft: PromptDraft, expectedRevision: number): PromptProfileVersionInput {
  const input: PromptProfileVersionInput = { expected_revision: expectedRevision };
  if (draft.systemContract.trim()) input.system_contract = draft.systemContract.trim();
  if (draft.taskTemplate.trim()) input.task_template = draft.taskTemplate.trim();
  if (draft.inputMapping.trim() && draft.inputMapping.trim() !== '{}') input.input_mapping = parseObject(draft.inputMapping, '输入映射');
  if (draft.outputSchema.trim() && draft.outputSchema.trim() !== '{}') input.output_schema = parseObject(draft.outputSchema, '输出结构');
  if (draft.negativeConstraints.trim()) input.negative_constraints = draft.negativeConstraints.split('\n').map((item) => item.trim()).filter(Boolean);
  if (draft.modelFamilyOverrides.trim() && draft.modelFamilyOverrides.trim() !== '{}') input.model_family_overrides = parseObject(draft.modelFamilyOverrides, '模型家族覆盖');
  if (draft.validationFixtures.trim() && draft.validationFixtures.trim() !== '[]') input.validation_fixtures = parseFixtures(draft.validationFixtures);
  if (draft.releaseNotes.trim()) input.release_notes = draft.releaseNotes.trim();
  return input;
}

type PromptProfileEditorProps = {
  profile: PromptProfileView;
  detail: PromptProfileDetail;
  appliedTaskTemplate?: string | null;
  onTaskTemplateChange?: (value: string) => void;
  onSaveVersion: (input: PromptProfileVersionInput) => Promise<void>;
  onPublish: (versionId: string, revision: number) => void;
  onRollback: (versionId: string, revision: number) => void;
};

export function PromptProfileEditor({
  profile,
  detail,
  appliedTaskTemplate,
  onTaskTemplateChange,
  onSaveVersion,
  onPublish,
  onRollback,
}: PromptProfileEditorProps) {
  const [draft, setDraft] = useState(emptyPromptDraft);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const restored = promptDraftFromVersion(detail.head);
    setDraft(restored);
    onTaskTemplateChange?.(restored.taskTemplate);
  }, [detail.head.id, onTaskTemplateChange]);
  useEffect(() => {
    if (appliedTaskTemplate === null || appliedTaskTemplate === undefined) return;
    setDraft((current) => ({ ...current, taskTemplate: appliedTaskTemplate }));
    onTaskTemplateChange?.(appliedTaskTemplate);
  }, [appliedTaskTemplate, onTaskTemplateChange]);
  const update = (key: keyof PromptDraft, value: string) => {
    setDraft((current) => ({ ...current, [key]: value }));
    if (key === 'taskTemplate') onTaskTemplateChange?.(value);
  };
  const save = async () => {
    try {
      setPending(true);
      setError(null);
      await onSaveVersion(promptVersionInput(draft, detail.head.version));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '提示词草稿保存失败');
    } finally {
      setPending(false);
    }
  };
  const publishable = detail.head.status === 'draft';
  return <section className="rounded-lg border border-white/10 bg-slate-950/20 p-4"><header className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-sm font-semibold text-white">{profile.name} · {profile.key}</h3><p className="mt-1 text-xs text-slate-500">已恢复服务端头版本正文：v{detail.head.version} · {detail.head.status}。修改会保存为新草稿，不会覆盖历史版本。</p></div><div className="flex flex-wrap gap-2"><button type="button" onClick={() => onRollback(detail.head.id, detail.head.version)} className="model-center-quiet"><History className="h-3.5 w-3.5" />回滚为新版本</button><button type="button" onClick={() => onPublish(detail.head.id, detail.head.version)} disabled={!publishable} className="model-center-primary">{publishable ? '发布此版本' : '当前版本已发布'}</button></div></header><PromptFields draft={draft} onChange={update} /><button type="button" onClick={() => void save()} disabled={pending} className="model-center-quiet mt-4"><Save className="h-3.5 w-3.5" />{pending ? '保存中' : '保存为新草稿版本'}</button>{error && <p className="mt-3 rounded-md bg-rose-500/10 px-3 py-2 text-xs text-rose-100">{error}</p>}</section>;
}

export function PromptFields({ draft, onChange, optional = false }: { draft: PromptDraft; onChange: (key: keyof PromptDraft, value: string) => void; optional?: boolean }) {
  const required = optional ? undefined : true;
  return <div className="mt-4 grid gap-3 lg:grid-cols-2"><label className="text-xs text-slate-400">系统约束<textarea aria-label="系统约束" required={required} value={draft.systemContract} onChange={(event) => onChange('systemContract', event.target.value)} className="model-center-input mt-1 h-24 w-full py-2" /></label><label className="text-xs text-slate-400">任务模板<textarea aria-label="任务模板" required={required} value={draft.taskTemplate} onChange={(event) => onChange('taskTemplate', event.target.value)} className="model-center-input mt-1 h-24 w-full py-2" /></label><label className="text-xs text-slate-400">输入映射 JSON<textarea aria-label="输入映射 JSON" required={required} value={draft.inputMapping} onChange={(event) => onChange('inputMapping', event.target.value)} className="model-center-input mt-1 h-20 w-full py-2" /></label><label className="text-xs text-slate-400">输出结构 JSON<textarea aria-label="输出结构 JSON" required={required} value={draft.outputSchema} onChange={(event) => onChange('outputSchema', event.target.value)} className="model-center-input mt-1 h-20 w-full py-2" /></label><label className="text-xs text-slate-400">负向约束（每行一条）<textarea aria-label="负向约束" value={draft.negativeConstraints} onChange={(event) => onChange('negativeConstraints', event.target.value)} className="model-center-input mt-1 h-20 w-full py-2" /></label><label className="text-xs text-slate-400">模型家族覆盖 JSON<textarea aria-label="模型家族覆盖 JSON" value={draft.modelFamilyOverrides} onChange={(event) => onChange('modelFamilyOverrides', event.target.value)} className="model-center-input mt-1 h-20 w-full py-2" /></label><label className="text-xs text-slate-400">验证样例 JSON<textarea aria-label="验证样例 JSON" required={required} value={draft.validationFixtures} onChange={(event) => onChange('validationFixtures', event.target.value)} className="model-center-input mt-1 h-20 w-full py-2" /></label><label className="text-xs text-slate-400">发布说明<textarea aria-label="发布说明" value={draft.releaseNotes} onChange={(event) => onChange('releaseNotes', event.target.value)} className="model-center-input mt-1 h-20 w-full py-2" /></label></div>;
}

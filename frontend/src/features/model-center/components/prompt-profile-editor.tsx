'use client';

import { useEffect, useState } from 'react';
import { History, Save } from 'lucide-react';

import type { PromptProfileView } from '../types';
import { PromptProfileDiff } from './prompt-profile-diff';

type PromptProfileEditorProps = {
  profile: PromptProfileView;
  onPublish: () => void;
  onRollback: () => void;
};

function contentText(value: unknown) {
  return typeof value === 'string' ? value : JSON.stringify(value ?? {}, null, 2);
}

export function PromptProfileEditor({ profile, onPublish, onRollback }: PromptProfileEditorProps) {
  const [draft, setDraft] = useState({ system: '', template: '', releaseNotes: '' });
  useEffect(() => setDraft({ system: contentText(profile.content.system_contract), template: contentText(profile.content.task_template), releaseNotes: contentText(profile.content.release_notes) }), [profile]);
  return <section className="mt-4 rounded-lg border border-white/10 bg-slate-950/20 p-4"><header className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-sm font-semibold text-white">{profile.profile_key} · v{profile.version}</h3><p className="mt-1 text-xs text-slate-500">当前版本不可直接改写；保存会产生新的草稿版本，发布与回滚均保留完整历史。</p></div><div className="flex flex-wrap gap-2"><button type="button" onClick={onRollback} className="model-center-quiet"><History className="h-3.5 w-3.5" />回滚为新版本</button><button type="button" onClick={onPublish} className="model-center-primary">发布此版本</button></div></header><div className="mt-4 grid gap-3 lg:grid-cols-2"><label className="text-xs text-slate-400">系统约束<textarea aria-label="系统约束" value={draft.system} onChange={(event) => setDraft({ ...draft, system: event.target.value })} className="model-center-input mt-1 h-28 w-full py-2" /></label><label className="text-xs text-slate-400">任务模板<textarea aria-label="任务模板" value={draft.template} onChange={(event) => setDraft({ ...draft, template: event.target.value })} className="model-center-input mt-1 h-28 w-full py-2" /></label><label className="text-xs text-slate-400">发布说明<textarea aria-label="发布说明" value={draft.releaseNotes} onChange={(event) => setDraft({ ...draft, releaseNotes: event.target.value })} className="model-center-input mt-1 h-20 w-full py-2" /></label><div className="rounded-lg border border-dashed border-white/15 p-3 text-xs leading-5 text-slate-400">发布前会校验 JSON 结构、每个目标能力/模型家族的覆盖，以及至少一个确定性样例通过。当前后端未启用新版本写入接口，因此此处不会伪造保存结果。</div></div><button type="button" disabled className="model-center-quiet mt-4"><Save className="h-3.5 w-3.5" />保存为新草稿版本（接口待启用）</button><div className="mt-5"><h4 className="mb-2 text-sm font-medium text-slate-200">当前版本结构</h4><PromptProfileDiff profile={profile} /></div></section>;
}

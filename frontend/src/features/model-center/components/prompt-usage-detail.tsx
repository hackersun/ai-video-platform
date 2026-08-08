'use client';

import { BookOpen, Code2, Cpu, ExternalLink, RefreshCw, Route } from 'lucide-react';

import type { PromptUsageStage } from '../prompt-usage-types';

export function PromptUsageDetail({
  stage,
  onOpenLibrary,
  onChangeTemplate,
}: {
  stage: PromptUsageStage;
  onOpenLibrary: (profileId?: string) => void;
  onChangeTemplate: () => void;
}) {
  return <article className="min-w-0 border-l border-white/10 p-5">
    <header className="flex flex-wrap items-start justify-between gap-3 border-b border-white/10 pb-5">
      <div><p className="text-xs text-slate-500">当前生产环节</p><h2 className="mt-1 text-xl font-semibold text-white">{stage.name}</h2></div>
      <span className="rounded-full border border-violet-400/25 bg-violet-500/10 px-3 py-1 text-xs text-violet-300">{stage.routing.source_label}</span>
    </header>
    <div className="mt-5 grid gap-3 sm:grid-cols-2">
      <section className="rounded-xl border border-white/10 bg-slate-950/25 p-4 sm:col-span-2">
        <div className="flex items-center gap-2 text-xs text-slate-500"><BookOpen className="h-4 w-4" />当前使用的模板</div>
        <p className="mt-2 text-base font-semibold text-white">{stage.template ? `${stage.template.name} · v${stage.template.version}` : '未配置可发布模板'}</p>
        <p className="mt-2 text-sm leading-6 text-slate-400">{stage.message}</p>
      </section>
      <section className="rounded-xl border border-white/10 bg-slate-950/25 p-4">
        <div className="flex items-center gap-2 text-xs text-slate-500"><Cpu className="h-4 w-4" />当前默认模型</div>
        <p className="mt-2 text-sm font-medium text-white">{stage.model?.name || '此环节无需模型'}</p>
        {stage.model && <p className="mt-1 break-all text-xs text-slate-500">{stage.model.provider_name} · {stage.model.api_model_id}</p>}
      </section>
      <section className="rounded-xl border border-white/10 bg-slate-950/25 p-4">
        <div className="flex items-center gap-2 text-xs text-slate-500"><Route className="h-4 w-4" />生效来源</div>
        <p className="mt-2 text-sm font-medium text-white">{stage.routing.source_label}</p>
        <p className="mt-1 text-xs text-slate-500">只影响后续新任务，不改写历史结果。</p>
      </section>
    </div>
    {stage.template && <details className="mt-4 rounded-xl border border-white/10 bg-slate-950/20 p-4">
      <summary className="cursor-pointer text-sm font-medium text-white">高级设置</summary>
      <div className="mt-4 space-y-3 text-xs text-slate-400">
        <div className="flex items-start gap-2"><Code2 className="mt-0.5 h-4 w-4 shrink-0" /><div><p className="text-slate-500">模板版本标识</p><p className="mt-1 break-all">{stage.template.profile_version_id}</p></div></div>
        <div><p className="text-slate-500">模型版本标识</p><p className="mt-1 break-all">{stage.model?.profile_version_id || '—'}</p></div>
        <p className="leading-5">模板正文、输入映射和历史版本请在模板库中查看和维护。</p>
      </div>
    </details>}
    <div className="mt-5 flex flex-wrap gap-2">
      {stage.uses_prompt && <button type="button" onClick={onChangeTemplate} className="model-center-primary"><RefreshCw className="h-4 w-4" />更换模板</button>}
      <button type="button" onClick={() => onOpenLibrary(stage.template?.id)} className="model-center-quiet"><ExternalLink className="h-4 w-4" />{stage.template ? '在模板库编辑' : '打开模板库'}</button>
    </div>
  </article>;
}

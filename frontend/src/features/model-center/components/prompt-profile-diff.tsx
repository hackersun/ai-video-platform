import type { PromptProfileDetail } from '../types';

export function PromptProfileDiff({ detail }: { detail: PromptProfileDetail }) {
  return <dl className="grid gap-3 sm:grid-cols-2"><div className="rounded-lg border border-white/10 bg-black/10 p-3"><dt className="text-xs text-slate-500">任务类型</dt><dd className="mt-2 text-xs leading-5 text-slate-300">{detail.task}</dd></div><div className="rounded-lg border border-white/10 bg-black/10 p-3"><dt className="text-xs text-slate-500">当前头版本</dt><dd className="mt-2 text-xs leading-5 text-slate-300">v{detail.head.version} · {detail.head.status}</dd></div><div className="rounded-lg border border-white/10 bg-black/10 p-3 sm:col-span-2"><dt className="text-xs text-slate-500">版本正文摘要</dt><dd className="mt-2 whitespace-pre-wrap text-xs leading-5 text-slate-300">{detail.head.task_template.slice(0, 360)}</dd></div></dl>;
}

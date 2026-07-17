import type { PromptProfileView } from '../types';

export function PromptProfileDiff({ profile }: { profile: PromptProfileView }) {
  return <dl className="grid gap-3 sm:grid-cols-2"><div className="rounded-lg border border-white/10 bg-black/10 p-3"><dt className="text-xs text-slate-500">任务类型</dt><dd className="mt-2 text-xs leading-5 text-slate-300">{profile.task}</dd></div><div className="rounded-lg border border-white/10 bg-black/10 p-3"><dt className="text-xs text-slate-500">当前头版本</dt><dd className="mt-2 text-xs leading-5 text-slate-300">v{profile.head_version ?? '—'} · {profile.status || '未创建'}</dd></div><div className="rounded-lg border border-white/10 bg-black/10 p-3 sm:col-span-2"><dt className="text-xs text-slate-500">版本正文</dt><dd className="mt-2 text-xs leading-5 text-slate-400">目录接口不返回历史提示词正文。编辑器仅提交本次明确变更的结构化字段，其余字段由服务端继承父版本。</dd></div></dl>;
}

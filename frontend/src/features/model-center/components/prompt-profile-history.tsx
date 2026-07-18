import type { PromptProfileVersionDetail } from '../types';

export function PromptProfileHistory({
  versions,
}: {
  versions: PromptProfileVersionDetail[];
}) {
  return <section className="rounded-lg border border-white/10 bg-black/10 p-4"><h3 className="text-sm font-semibold text-white">版本历史</h3><p className="mt-1 text-xs text-slate-500">历史版本只读；回滚会创建新的头版本。</p><ol className="mt-3 space-y-2">{versions.map((version) => <li key={version.id} className="rounded-md border border-white/10 px-3 py-2"><div className="flex items-center justify-between gap-3 text-xs"><span className="font-medium text-slate-200">v{version.version} · {version.status}</span><span className="text-slate-500">{version.published_at ? new Date(version.published_at).toLocaleString('zh-CN') : '未发布'}</span></div><p className="mt-1 line-clamp-2 text-xs text-slate-400">{version.release_notes || '没有发布说明'}</p><p className="mt-1 font-mono text-[10px] text-slate-600">{version.checksum.slice(0, 12)}</p></li>)}</ol></section>;
}

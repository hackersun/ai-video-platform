'use client';

export type LiveCertificationContext = {
  userScope: string;
  recipeVersion: string;
  chapterId: string;
  runId: string;
  selectedShots: string;
  budgetCeiling: string;
  retryPolicy: 'never' | 'manual';
  storagePolicy: 'qiniu_public' | 'private';
};

export function AdvancedParametersDrawer({ value, onChange }: { value: LiveCertificationContext; onChange: (value: LiveCertificationContext) => void }) {
  const update = (key: keyof LiveCertificationContext, next: string) => onChange({ ...value, [key]: next });
  return <details open className="mt-4 rounded-lg border border-white/10 bg-black/10 p-4"><summary className="cursor-pointer text-sm font-medium text-slate-200">高级参数与真实费用范围</summary><div className="mt-4 grid gap-3 sm:grid-cols-2"><label className="text-xs text-slate-400">用户作用域<input aria-label="用户作用域" value={value.userScope} onChange={(event) => update('userScope', event.target.value)} className="model-center-input mt-1 w-full" /></label><label className="text-xs text-slate-400">生产方案版本<input aria-label="生产方案版本" value={value.recipeVersion} onChange={(event) => update('recipeVersion', event.target.value)} className="model-center-input mt-1 w-full" /></label><label className="text-xs text-slate-400">章节 ID<input aria-label="章节 ID" value={value.chapterId} onChange={(event) => update('chapterId', event.target.value)} className="model-center-input mt-1 w-full" /></label><label className="text-xs text-slate-400">运行 ID<input aria-label="运行 ID" value={value.runId} onChange={(event) => update('runId', event.target.value)} className="model-center-input mt-1 w-full" /></label><label className="text-xs text-slate-400">选定镜头<input aria-label="选定镜头" value={value.selectedShots} onChange={(event) => update('selectedShots', event.target.value)} className="model-center-input mt-1 w-full" placeholder="shot-03, shot-07" /></label><label className="text-xs text-slate-400">预算上限（元）<input aria-label="预算上限" inputMode="decimal" value={value.budgetCeiling} onChange={(event) => update('budgetCeiling', event.target.value)} className="model-center-input mt-1 w-full" /></label><label className="text-xs text-slate-400">重试策略<select aria-label="重试策略" value={value.retryPolicy} onChange={(event) => update('retryPolicy', event.target.value)} className="model-center-input mt-1 w-full"><option value="never">失败不重试</option><option value="manual">仅允许人工重试</option></select></label><label className="text-xs text-slate-400">存储策略<select aria-label="存储策略" value={value.storagePolicy} onChange={(event) => update('storagePolicy', event.target.value)} className="model-center-input mt-1 w-full"><option value="qiniu_public">七牛公网映射</option><option value="private">私有存储</option></select></label></div></details>;
}

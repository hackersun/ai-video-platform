'use client';

import { AlertCircle, RotateCcw, Send, X } from 'lucide-react';
import { useMemo, useState } from 'react';

import type { ProductionRecipeView } from '../types';

type Validation = { valid: boolean; errors: Array<{ code: string; message: string }> };
type RecipeDetailProps = {
  recipe: ProductionRecipeView;
  versions: ProductionRecipeView[];
  onClose: () => void;
  onValidate: (id: string) => Promise<Validation>;
  onPublish: (id: string, revision: number, reason: string) => Promise<void>;
  onRollback: (recipeKey: string, targetId: string, revision: number, reason: string) => Promise<void>;
};

const statusLabel = { draft: '草稿', published: '已发布', disabled: '已停用' } as const;

export function RecipeDetail({ recipe, versions, onClose, onValidate, onPublish, onRollback }: RecipeDetailProps) {
  const [action, setAction] = useState<'publish' | 'rollback' | null>(null);
  const [reason, setReason] = useState('');
  const [targetId, setTargetId] = useState('');
  const [errors, setErrors] = useState<Array<{ code: string; message: string }>>([]);
  const [operationError, setOperationError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const sameRecipe = useMemo(
    () => versions.filter((item) => item.recipe_key === recipe.recipe_key).sort((a, b) => b.version - a.version),
    [recipe.recipe_key, versions],
  );
  const isHead = sameRecipe[0]?.id === recipe.id;
  const rollbackTargets = sameRecipe.filter((item) => item.id !== recipe.id && item.version < recipe.version);
  const stageRows = Object.entries(recipe.stages || recipe.spec || {}) as Array<[string, Record<string, unknown>]>;

  const preparePublish = async () => {
    setPending(true);
    setErrors([]);
    setOperationError(null);
    try {
      const result = await onValidate(recipe.id);
      if (!result.valid) setErrors(result.errors);
      else setAction('publish');
    } catch (failure) {
      setOperationError(failure instanceof Error ? failure.message : '发布前校验失败，请修改后重试。');
    } finally {
      setPending(false);
    }
  };
  const submit = async () => {
    setPending(true);
    setOperationError(null);
    try {
      if (action === 'publish') await onPublish(recipe.id, recipe.revision, reason);
      if (action === 'rollback') await onRollback(recipe.recipe_key, targetId, recipe.revision, reason);
      setAction(null);
      setReason('');
    } catch (failure) {
      setOperationError(failure instanceof Error ? failure.message : '操作失败，请按提示修改后重试。');
    } finally {
      setPending(false);
    }
  };

  return <div role="dialog" aria-modal="true" aria-label="生产方案详情" className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/80 p-4 sm:p-8">
    <section className="mx-auto max-w-3xl rounded-xl border border-white/15 bg-slate-900 p-5 shadow-2xl">
      <header className="flex items-start justify-between gap-4"><div><h2 className="text-xl font-semibold text-white">{recipe.name}</h2><p className="mt-1 text-sm text-slate-400">{recipe.recipe_key} · v{recipe.version} · {statusLabel[recipe.status]}</p></div><button type="button" aria-label="关闭方案详情" onClick={onClose} className="model-center-quiet"><X className="h-4 w-4" /></button></header>
      <div className="mt-4 grid gap-3 sm:grid-cols-3"><div className="rounded-lg border border-white/10 p-3"><p className="text-xs text-slate-500">生产策略</p><p className="mt-1 text-sm text-white">{recipe.strategy || '未声明'}</p></div><div className="rounded-lg border border-white/10 p-3"><p className="text-xs text-slate-500">版本状态</p><p className="mt-1 text-sm text-white">{statusLabel[recipe.status]}{isHead && recipe.status === 'published' ? '（当前）' : ''}</p></div><div className="rounded-lg border border-white/10 p-3"><p className="text-xs text-slate-500">绑定阶段</p><p className="mt-1 text-sm text-white">{stageRows.filter(([, value]) => value.binding_id).length} 个</p></div></div>
      <div className="mt-4 overflow-hidden rounded-lg border border-white/10"><table className="min-w-full text-left text-sm"><thead className="bg-white/[0.035] text-xs text-slate-500"><tr><th>阶段</th><th>绑定/策略</th><th>是否必需</th></tr></thead><tbody>{stageRows.map(([stage, values]) => <tr key={stage} className="border-t border-white/[0.07] text-slate-300"><td>{stage}</td><td>{String(values.binding_id || values.mode || values.source || '未绑定')}</td><td>{values.required === true ? '必需' : '可选'}</td></tr>)}</tbody></table></div>
      {errors.length > 0 && <div className="mt-4 rounded-lg bg-rose-500/10 p-3 text-sm text-rose-100"><p className="flex items-center gap-2 font-medium"><AlertCircle className="h-4 w-4" />发布前校验未通过</p>{errors.map((error) => <p key={`${error.code}-${error.message}`} className="mt-1 text-xs">{error.code}：{error.message}</p>)}</div>}
      {operationError && <p className="mt-4 rounded-lg bg-rose-500/10 p-3 text-sm text-rose-100">{operationError} 可修改配置后再次点击当前操作。</p>}
      {action && <div className="mt-4 rounded-lg border border-violet-400/20 bg-violet-500/[0.06] p-4">{action === 'rollback' && <label className="block text-xs text-slate-300">目标版本<select aria-label="回滚目标版本" value={targetId} onChange={(event) => setTargetId(event.target.value)} className="model-center-input mt-1 w-full"><option value="">请选择历史版本</option>{rollbackTargets.map((item) => <option key={item.id} value={item.id}>v{item.version} · {item.name}</option>)}</select></label>}<label className="mt-3 block text-xs text-slate-300">{action === 'publish' ? '发布原因' : '回滚原因'}<input aria-label={action === 'publish' ? '发布原因' : '回滚原因'} value={reason} onChange={(event) => setReason(event.target.value)} className="model-center-input mt-1 w-full" /></label><div className="mt-3 flex justify-end gap-2"><button type="button" onClick={() => setAction(null)} className="model-center-quiet">取消</button><button type="button" disabled={pending || reason.trim().length < 2 || (action === 'rollback' && !targetId)} onClick={() => void submit()} className="model-center-primary">{action === 'publish' ? '确认发布' : '确认回滚'}</button></div></div>}
      {!action && <footer className="mt-5 flex justify-end gap-2">{isHead && recipe.status === 'published' && rollbackTargets.length > 0 && <button type="button" onClick={() => setAction('rollback')} className="model-center-quiet"><RotateCcw className="h-4 w-4" />回滚方案</button>}{recipe.status === 'draft' && <button type="button" disabled={pending} onClick={() => void preparePublish()} className="model-center-primary"><Send className="h-4 w-4" />发布方案</button>}</footer>}
    </section>
  </div>;
}

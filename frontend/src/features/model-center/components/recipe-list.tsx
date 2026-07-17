'use client';

import { useState } from 'react';
import { Plus } from 'lucide-react';

import { useModelBindings } from '../hooks/use-model-bindings';
import { useProductionRecipes } from '../hooks/use-production-recipes';
import { ModelCenterEmpty, ModelCenterError, ModelCenterLoading } from './model-center-state';
import { RecipeEditor } from './recipe-editor';

export function RecipeList() {
  const recipes = useProductionRecipes();
  const bindings = useModelBindings();
  const [editing, setEditing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  if ((recipes.loading || bindings.loading) && !recipes.data) return <ModelCenterLoading label="正在读取组合预设与能力绑定…" />;
  if (recipes.error && !recipes.data) return <ModelCenterError error={recipes.error} onRetry={() => void recipes.reload()} />;
  return <div className="p-4"><header className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-sm font-semibold text-white">版本化生产方案</h2><p className="mt-1 text-xs text-slate-500">使用已认证的能力绑定组合生产链。</p></div><button type="button" onClick={() => setEditing(true)} className="model-center-primary"><Plus className="h-4 w-4" />新建生产方案</button></header>{message && <p className="mt-4 rounded-md bg-rose-500/10 px-3 py-2 text-xs text-rose-100">{message}</p>}{recipes.data?.items.length ? <div className="mt-4 overflow-x-auto rounded-lg border border-white/10"><table className="min-w-full text-left text-sm"><thead className="bg-white/[0.035] text-xs text-slate-500"><tr><th>名称</th><th>策略</th><th>版本</th><th>状态</th></tr></thead><tbody>{recipes.data.items.map((recipe) => <tr key={recipe.id} className="border-t border-white/[0.07] text-slate-300"><td className="font-medium text-white">{recipe.name}</td><td>{typeof recipe.spec.strategy === 'string' ? recipe.spec.strategy : '未声明'}</td><td>v{recipe.version}</td><td>{recipe.status}</td></tr>)}</tbody></table></div> : <ModelCenterEmpty title="还没有生产方案" description="新建方案后，按发布版本供工作台选择。" />}{editing && <RecipeEditor bindings={bindings.data?.items || []} onClose={() => setEditing(false)} onSave={async (input) => { try { const created = await recipes.createRecipe(input); const validation = await recipes.validateRecipeVersion(created.id); if (!validation.valid) throw new Error(validation.errors.map((item) => item.message).join('；') || '生产方案校验未通过'); setMessage('草稿已保存并通过生产方案校验。'); } catch (reason) { setMessage(reason instanceof Error ? reason.message : '生产方案保存失败'); throw reason; } }} />}</div>;
}

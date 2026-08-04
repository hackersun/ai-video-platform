'use client';

import { Eye, Plus } from 'lucide-react';
import { useState } from 'react';

import { useModelBindings } from '../hooks/use-model-bindings';
import { useProductionRecipes } from '../hooks/use-production-recipes';
import { ModelCenterEmpty, ModelCenterError, ModelCenterLoading } from './model-center-state';
import { RecipeDetail } from './recipe-detail';
import { RecipeEditor } from './recipe-editor';
import { PRODUCTION_STRATEGY_COPY, type ProductionStrategy } from '@/lib/production-strategy';

const statusLabel = { draft: '草稿', published: '已发布', disabled: '已停用' } as const;

export function RecipeList() {
  const recipes = useProductionRecipes();
  const bindings = useModelBindings();
  const [editing, setEditing] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [message, setMessage] = useState<{ text: string; error?: boolean } | null>(null);
  if ((recipes.loading || bindings.loading) && !recipes.data) return <ModelCenterLoading label="正在读取生产方案与默认模型…" />;
  if (recipes.error && !recipes.data) return <ModelCenterError error={recipes.error} onRetry={() => void recipes.reload()} />;
  const rows = recipes.data?.items || [];
  const selected = rows.find((recipe) => recipe.id === selectedId);

  return <div className="p-4">
    <header className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-sm font-semibold text-white">版本化生产方案</h2><p className="mt-1 text-xs text-slate-500">选择生产目标，并为每个步骤使用已验证的默认模型。</p></div><button type="button" onClick={() => setEditing(true)} className="model-center-primary"><Plus className="h-4 w-4" />新建生产方案</button></header>
    {message && <p className={`mt-4 rounded-md px-3 py-2 text-xs ${message.error ? 'bg-rose-500/10 text-rose-100' : 'bg-emerald-500/10 text-emerald-100'}`}>{message.text}</p>}
    {rows.length ? <div className="mt-4 overflow-x-auto rounded-lg border border-white/10"><table className="min-w-[760px] text-left text-sm"><thead className="bg-white/[0.035] text-xs text-slate-500"><tr><th>名称</th><th>生产目标</th><th>版本</th><th>状态</th><th>操作</th></tr></thead><tbody>{rows.map((recipe) => { const strategyCopy = PRODUCTION_STRATEGY_COPY[recipe.strategy as ProductionStrategy]; return <tr key={recipe.id} className="border-t border-white/[0.07] text-slate-300"><td className="font-medium text-white">{recipe.name}</td><td><span className="font-medium text-slate-200">{strategyCopy?.label || '自定义目标'}</span>{strategyCopy && <span className="mt-0.5 block max-w-md text-xs leading-5 text-slate-500">{strategyCopy.description}</span>}</td><td className="whitespace-nowrap">v{recipe.version}</td><td className="whitespace-nowrap">{statusLabel[recipe.status]}</td><td><button type="button" aria-label={`查看${recipe.name}`} onClick={() => setSelectedId(recipe.id)} className="model-center-quiet whitespace-nowrap"><Eye className="h-3.5 w-3.5 shrink-0" />查看</button></td></tr>; })}</tbody></table></div> : <ModelCenterEmpty title="还没有生产方案" description="新建方案后，按发布版本供工作台选择。" />}
    {editing && <RecipeEditor bindings={bindings.data?.items || []} onClose={() => setEditing(false)} onSave={async (input) => { try { const created = await recipes.createRecipe(input); const validation = await recipes.validateRecipeVersion(created.id); if (!validation.valid) throw new Error(validation.errors.map((item) => item.message).join('；') || '生产方案校验未通过'); setMessage({ text: '草稿已保存并通过生产方案校验。' }); } catch (reason) { setMessage({ text: reason instanceof Error ? reason.message : '生产方案保存失败', error: true }); throw reason; } }} />}
    {selected && <RecipeDetail recipe={selected} versions={rows} onClose={() => setSelectedId(null)} onValidate={recipes.validateRecipeVersion} onPublish={async (id, revision, reason) => { await recipes.publishRecipeVersion(id, { expected_revision: revision, reason }); setMessage({ text: '生产方案已发布。' }); }} onRollback={async (key, target, revision, reason) => { await recipes.rollbackRecipe(key, { target_version_id: target, expected_revision: revision, reason }); setMessage({ text: '生产方案已回滚并生成新的发布版本。' }); setSelectedId(null); }} />}
  </div>;
}

'use client';

import { Pencil, Plus } from 'lucide-react';
import { useState } from 'react';

import { useModelBindings } from '../hooks/use-model-bindings';
import { capabilityLabels, certificationLabel, connectionDisplayName, taskLabel } from '../model-center-labels';
import type { ModelBindingView, ModelCenterSection } from '../types';
import type { ModelCenterLocation } from '../navigation';
import { PromptProfileList } from './prompt-profile-list';
import { RecipeList } from './recipe-list';
import { ModelCenterEmpty, ModelCenterError, ModelCenterLoading } from './model-center-state';
import { TestLab } from './test-lab';
import { BindingEditor } from './binding-editor';

function BindingsTable({ rows, onEdit }: { rows: ModelBindingView[]; onEdit: (row: ModelBindingView) => void }) {
  return <div className="overflow-x-auto rounded-lg border border-white/10"><table className="min-w-full text-left text-sm">
    <thead className="bg-white/[0.035] text-xs text-slate-500"><tr><th>使用场景</th><th>当前默认模型</th><th>供应商账号</th><th>验证状态</th><th>使用状态</th><th className="text-right">操作</th></tr></thead>
    <tbody>{rows.map((item) => <tr key={item.id} className="border-t border-white/[0.07] text-slate-300">
      <td><span className="block font-medium text-white">{taskLabel(item.task)}</span><span className="text-xs text-slate-500">{capabilityLabels[item.capability]} · {item.affected_recipes} 个组合使用</span></td>
      <td><span className="block">{item.profile_name} · {item.api_model_id}</span><span className="text-xs text-slate-500">高级路由：{item.route_policy} · P{item.priority}</span></td>
      <td><span className="block">{connectionDisplayName(item.connection_name, item.provider_name)}</span><span className="text-xs text-slate-500">{item.provider_name}</span></td>
      <td>{certificationLabel(item.certification_status)}</td>
      <td>{item.is_active ? '生产中使用' : '已停用'}</td>
      <td className="text-right"><button type="button" aria-label={`更换${taskLabel(item.task)}默认模型`} onClick={() => onEdit(item)} className="model-center-quiet"><Pencil className="h-3.5 w-3.5" />更换</button></td>
    </tr>)}</tbody>
  </table></div>;
}

function BindingsPanel() {
  const query = useModelBindings();
  const [editor, setEditor] = useState<ModelBindingView | 'new' | null>(null);
  if (query.loading && !query.data) return <ModelCenterLoading label="正在读取默认模型…" />;
  if (query.error && !query.data) return <ModelCenterError error={query.error} onRetry={() => void query.reload()} />;
  const rows = query.data?.items || [];
  const current = editor === 'new' ? undefined : editor || undefined;
  return <div className="p-4">
    <div className="mb-4 flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><p className="max-w-2xl text-sm text-slate-400">这里决定生产任务实际调用哪个模型。更换后会影响后续新任务，已生成的资产不会被修改。</p><button type="button" onClick={() => setEditor('new')} className="model-center-primary"><Plus className="h-4 w-4" />设置默认模型</button></div>
    {rows.length ? <BindingsTable rows={rows} onEdit={setEditor} /> : <ModelCenterEmpty title="还没有默认模型" description="先添加并验证模型，再为一个生产场景设置默认模型。" />}
    {editor && <BindingEditor binding={current} onClose={() => setEditor(null)} onSave={async (input) => {
      if (current) await query.updateBinding(current.id, { ...input, expected_revision: current.revision });
      else await query.createBinding(input);
    }} />}
  </div>;
}

export function ModelCenterManagementPanel({ section, location }: { section: Exclude<ModelCenterSection, 'overview' | 'connections' | 'catalog'>; location: ModelCenterLocation }) {
  if (section === 'bindings') return <BindingsPanel />;
  if (section === 'recipes') return <RecipeList />;
  if (section === 'prompts') return <PromptProfileList location={location} />;
  return <TestLab runId={location.runId} location={location} />;
}

'use client';

import { Pencil, Plus } from 'lucide-react';
import { useState } from 'react';

import { useModelBindings } from '../hooks/use-model-bindings';
import type { ModelBindingView, ModelCenterSection } from '../types';
import type { ModelCenterLocation } from '../navigation';
import { PromptProfileList } from './prompt-profile-list';
import { RecipeList } from './recipe-list';
import { ModelCenterEmpty, ModelCenterError, ModelCenterLoading } from './model-center-state';
import { TestLab } from './test-lab';
import { BindingEditor } from './binding-editor';

function BindingsTable({ rows, onEdit }: { rows: ModelBindingView[]; onEdit: (row: ModelBindingView) => void }) {
  return <div className="overflow-x-auto rounded-lg border border-white/10"><table className="min-w-full text-left text-sm">
    <thead className="bg-white/[0.035] text-xs text-slate-500"><tr><th>任务与能力</th><th>模型与连接</th><th>路由策略</th><th>认证</th><th>影响</th><th>状态</th><th>操作</th></tr></thead>
    <tbody>{rows.map((item) => <tr key={item.id} className="border-t border-white/[0.07] text-slate-300">
      <td><span className="block font-medium text-white">{item.task}</span><span className="text-xs text-slate-500">{item.capability} · {item.scope_type}</span></td>
      <td><span className="block">{item.profile_name} · {item.api_model_id}</span><span className="text-xs text-slate-500">{item.connection_name} · {item.provider_name}</span></td>
      <td>{item.route_policy}<span className="ml-1 text-xs text-slate-500">P{item.priority}</span></td>
      <td>{item.certification_status}</td><td>{item.affected_recipes} 个方案</td>
      <td>{item.is_active ? '已启用' : '已停用'}</td>
      <td><button type="button" aria-label={`编辑${item.task === 'shot_video' ? '镜头视频' : item.task}绑定`} onClick={() => onEdit(item)} className="model-center-quiet"><Pencil className="h-3.5 w-3.5" />编辑</button></td>
    </tr>)}</tbody>
  </table></div>;
}

function BindingsPanel() {
  const query = useModelBindings();
  const [editor, setEditor] = useState<ModelBindingView | 'new' | null>(null);
  if (query.loading && !query.data) return <ModelCenterLoading label="正在读取能力绑定…" />;
  if (query.error && !query.data) return <ModelCenterError error={query.error} onRetry={() => void query.reload()} />;
  const rows = query.data?.items || [];
  const current = editor === 'new' ? undefined : editor || undefined;
  return <div className="p-4">
    <div className="mb-4 flex justify-end"><button type="button" onClick={() => setEditor('new')} className="model-center-primary"><Plus className="h-4 w-4" />新建能力绑定</button></div>
    {rows.length ? <BindingsTable rows={rows} onEdit={setEditor} /> : <ModelCenterEmpty title="能力绑定" description="尚未建立任务能力绑定。配置连接和模型版本后可在此绑定。" />}
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

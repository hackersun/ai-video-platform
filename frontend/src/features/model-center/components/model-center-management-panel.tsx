'use client';

import { useModelBindings } from '../hooks/use-model-bindings';
import type { ModelCenterSection } from '../types';
import type { ModelCenterLocation } from '../navigation';
import { PromptProfileList } from './prompt-profile-list';
import { RecipeList } from './recipe-list';
import { ModelCenterEmpty, ModelCenterError, ModelCenterLoading } from './model-center-state';
import { TestLab } from './test-lab';

function BindingsPanel() {
  const query = useModelBindings();
  if (query.loading && !query.data) return <ModelCenterLoading label="正在读取能力绑定…" />;
  if (query.error && !query.data) return <ModelCenterError error={query.error} onRetry={() => void query.reload()} />;
  const rows = query.data?.items || [];
  return <div className="p-4">{rows.length ? <div className="overflow-x-auto rounded-lg border border-white/10"><table className="min-w-full text-left text-sm"><thead className="bg-white/[0.035] text-xs text-slate-500"><tr><th>任务</th><th>能力</th><th>作用域</th><th>路由策略</th><th>状态</th></tr></thead><tbody>{rows.map((item) => <tr key={item.id} className="border-t border-white/[0.07] text-slate-300"><td className="font-medium text-white">{item.task}</td><td>{item.capability}</td><td>{item.scope_type}</td><td>{item.route_policy}</td><td>{item.is_active ? '已启用' : '已停用'}</td></tr>)}</tbody></table></div> : <ModelCenterEmpty title="能力绑定" description="尚未建立任务能力绑定。配置连接和模型版本后可在此绑定。" />}</div>;
}

export function ModelCenterManagementPanel({ section, location }: { section: Exclude<ModelCenterSection, 'overview' | 'connections' | 'catalog'>; location: ModelCenterLocation }) {
  if (section === 'bindings') return <BindingsPanel />;
  if (section === 'recipes') return <RecipeList />;
  if (section === 'prompts') return <PromptProfileList />;
  return <TestLab runId={location.runId} location={location} />;
}

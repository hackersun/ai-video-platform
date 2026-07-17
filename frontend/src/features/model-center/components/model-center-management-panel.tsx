'use client';

import { useModelBindings } from '../hooks/use-model-bindings';
import { useProductionRecipes } from '../hooks/use-production-recipes';
import { usePromptProfiles } from '../hooks/use-prompt-profiles';
import { useCertificationRun } from '../hooks/use-certification-run';
import type { ModelCenterSection } from '../types';
import { ModelCenterEmpty, ModelCenterError, ModelCenterLoading } from './model-center-state';

function SimpleTable({ columns, rows }: { columns: string[]; rows: Array<Array<string | number>> }) {
  return <div className="overflow-x-auto rounded-lg border border-white/10"><table className="min-w-full text-left text-sm"><thead className="bg-white/[0.035] text-xs text-slate-500"><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index} className="border-t border-white/[0.07] text-slate-300">{row.map((value, cell) => <td key={cell} className={cell === 0 ? 'font-medium text-white' : ''}>{value}</td>)}</tr>)}</tbody></table></div>;
}

function BindingsPanel() {
  const query = useModelBindings();
  if (query.loading && !query.data) return <ModelCenterLoading label="正在读取能力绑定…" />;
  if (query.error && !query.data) return <ModelCenterError error={query.error} onRetry={() => void query.reload()} />;
  const rows = (query.data?.items || []).map((item) => [item.task, item.capability, item.scope_type, item.route_policy, item.is_active ? '已启用' : '已停用']);
  return <div className="p-4">{rows.length ? <SimpleTable columns={['任务', '能力', '作用域', '路由策略', '状态']} rows={rows} /> : <ModelCenterEmpty title="能力绑定" description="尚未建立任务能力绑定。配置连接和模型版本后可在此绑定。" />}</div>;
}

function RecipesPanel() {
  const query = useProductionRecipes();
  if (query.loading && !query.data) return <ModelCenterLoading label="正在读取组合预设…" />;
  if (query.error && !query.data) return <ModelCenterError error={query.error} onRetry={() => void query.reload()} />;
  const rows = (query.data?.items || []).map((item) => [item.name, item.recipe_key, `v${item.version}`, item.status]);
  return <div className="p-4">{rows.length ? <SimpleTable columns={['组合名称', '组合键', '版本', '状态']} rows={rows} /> : <ModelCenterEmpty title="组合预设" description="尚无生产组合预设。组合会版本化保存，避免影响已提交任务。" />}</div>;
}

function PromptsPanel() {
  const query = usePromptProfiles();
  if (query.loading && !query.data) return <ModelCenterLoading label="正在读取提示词模板…" />;
  if (query.error && !query.data) return <ModelCenterError error={query.error} onRetry={() => void query.reload()} />;
  const rows = (query.data?.items || []).map((item) => [item.profile_key, `v${item.version}`, item.status]);
  return <div className="p-4">{rows.length ? <SimpleTable columns={['模板键', '版本', '状态']} rows={rows} /> : <ModelCenterEmpty title="提示词模板" description="尚无版本化提示词模板。" />}</div>;
}

function TestLabPanel({ runId }: { runId?: string }) {
  const query = useCertificationRun(runId);
  if (!runId) return <ModelCenterEmpty title="测试实验室" description="从连接测试跳转后，可在此查看认证运行。" />;
  if (query.loading && !query.data) return <ModelCenterLoading label="正在读取认证证据…" />;
  if (query.error && !query.data) return <ModelCenterError error={query.error} onRetry={() => void query.reload()} />;
  const run = query.data;
  if (!run) return <ModelCenterEmpty title="测试实验室" description="尚未找到该认证运行，请确认运行 ID。" />;
  return <div className="p-4"><div className="rounded-lg border border-white/10 bg-slate-950/25 p-5 text-sm"><dl className="grid gap-4 sm:grid-cols-2"><div><dt>运行 ID</dt><dd>{run.id}</dd></div><div><dt>认证等级</dt><dd>{run.level}</dd></div><div><dt>状态</dt><dd>{run.status}</dd></div><div><dt>实际成本</dt><dd>¥{run.actual_cost_rmb}</dd></div></dl><div className="mt-5 border-t border-white/10 pt-4"><p className="mb-2 text-xs text-slate-500">已脱敏证据</p><pre className="max-h-64 overflow-auto rounded bg-black/20 p-3 text-xs text-slate-300">{JSON.stringify(run.sanitized_evidence, null, 2)}</pre></div></div></div>;
}

export function ModelCenterManagementPanel({ section, runId }: { section: Exclude<ModelCenterSection, 'overview' | 'connections' | 'catalog'>; runId?: string }) {
  if (section === 'bindings') return <BindingsPanel />;
  if (section === 'recipes') return <RecipesPanel />;
  if (section === 'prompts') return <PromptsPanel />;
  return <TestLabPanel runId={runId} />;
}

import type { PromptProfileView } from '../types';

const labels: Record<string, string> = {
  system_contract: '系统约束', task_template: '任务模板', input_mapping: '输入映射', output_schema: '输出结构',
  negative_constraints: '负向约束', model_family_overrides: '模型家族覆盖', validation_fixtures: '验证样例', release_notes: '发布说明',
};

export function PromptProfileDiff({ profile }: { profile: PromptProfileView }) {
  return <dl className="grid gap-3 sm:grid-cols-2">{Object.entries(labels).map(([key, label]) => <div key={key} className="rounded-lg border border-white/10 bg-black/10 p-3"><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-2 whitespace-pre-wrap break-words text-xs leading-5 text-slate-300">{typeof profile.content[key] === 'string' ? profile.content[key] : JSON.stringify(profile.content[key] ?? {}, null, 2)}</dd></div>)}</dl>;
}

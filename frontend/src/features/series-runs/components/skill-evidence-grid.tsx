import { CheckCircle2, CircleDashed } from 'lucide-react';

type Evidence = {
  id?: string;
  name?: string;
  version?: number;
  execution_mode?: string;
  artifact_type?: string;
  artifact_id?: string;
  task?: string;
  model_execution?: {
    execution_mode?: string;
    validation_status?: string;
    fallback_reason?: string | null;
    provider_id?: string | null;
    api_model_id?: string | null;
  };
};

function firstEvidence(value: unknown): Evidence | undefined {
  if (!value || typeof value !== 'object') return undefined;
  const record = value as Record<string, unknown>;
  if (typeof record.id === 'string') return record as Evidence;
  for (const child of Object.values(record)) {
    const found = firstEvidence(child);
    if (found) return found;
  }
  return undefined;
}

function modeLabel(mode?: string) {
  if (mode === 'provider_model') return '模型输出已通过确定性校验';
  if (mode === 'deterministic_fallback') return '模型不可用或结果未通过，已使用确定性兜底';
  if (mode === 'supplied_candidates') return '已校验调用方提供的候选结果';
  if (mode === 'deterministic_skill_contract') return 'Skill 约束执行（确定性阶段）';
  return mode || '已绑定，等待执行';
}

const fallbackLabels: Record<string, string> = {
  model_unavailable: '未找到可用文本模型配置',
  model_execution_failed: '模型调用失败',
  model_output_invalid: '模型返回格式无效',
  model_output_rejected: '模型结果未通过一致性校验',
};

export function SkillEvidenceGrid({ runMetadata, nativeAudio }: {
  runMetadata: Record<string, any> | undefined;
  nativeAudio: boolean;
}) {
  const skills = runMetadata?.skill_evidence || {};
  const video = firstEvidence(skills[nativeAudio ? 'shot_audio_video' : 'shot_video'])
    || firstEvidence(skills.shot_audio_video)
    || firstEvidence(skills.shot_video);
  const items = [
    ['剧本', firstEvidence(skills.script_generation), '推进到剧本阶段后生成'],
    ['实体抽取', firstEvidence(skills.entity_extraction), '准备故事锁后生成'],
    ['分镜', firstEvidence(skills.storyboard_generation), '推进到分镜阶段后生成'],
    ['镜头提示词', firstEvidence(skills.shot_prompt), '推进到镜头阶段后生成'],
    ['复合参考设定板', firstEvidence(runMetadata?.reference_preparation?.prompt_skill), '生成并锁定参考图后生成'],
    [nativeAudio ? '原生有声视频' : '镜头视频', video, '提交关键镜头视频后生成'],
  ] as const;

  return <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3" data-testid="series-run-skill-evidence">
    {items.map(([label, evidence, pending]) => <div key={label} className="rounded-md border border-white/10 bg-black/15 p-3 text-sm">
      <div className="flex items-center gap-2 text-white/40">
        {evidence ? <CheckCircle2 className="h-4 w-4 text-emerald-300" /> : <CircleDashed className="h-4 w-4" />}
        {label} Skill
      </div>
      <div className="mt-1 text-white">{evidence?.name ? `${evidence.name} · v${evidence.version}` : '尚无执行证据'}</div>
      <div className="text-xs text-white/40">{evidence ? modeLabel(evidence.execution_mode) : pending}</div>
      {evidence?.model_execution?.fallback_reason && <div className="mt-1 text-xs text-amber-300/80">
        兜底原因：{fallbackLabels[evidence.model_execution.fallback_reason] || evidence.model_execution.fallback_reason}
      </div>}
      {evidence?.model_execution?.execution_mode === 'provider_model' && <div className="mt-1 truncate text-[11px] text-emerald-300/70">
        {evidence.model_execution.provider_id} · {evidence.model_execution.api_model_id}
      </div>}
      {evidence?.artifact_id && <div className="mt-1 truncate text-[11px] text-white/30">{evidence.artifact_type} · {evidence.artifact_id}</div>}
    </div>)}
  </div>;
}

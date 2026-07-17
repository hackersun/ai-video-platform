'use client';

import { Button } from '@/components/ui/button';
import type { QualityGateSummary } from '@/lib/studio-types';

const DIMENSION_LABELS: Record<string, string> = {
  narrative_truth: '叙事事实',
  character_visual: '角色视觉',
  scene_prop_state: '场景与道具状态',
  motion_camera: '运镜与动作',
  voice_lipsync: '声音与口型',
  delivery_integrity: '交付完整性',
};

const VALUE_LABELS: Record<string, string> = { low: '低', medium: '中', high: '高' };

function stateText(value?: Record<string, any>) {
  if (!value || !Object.keys(value).length) return '暂无';
  return JSON.stringify(value, null, 2);
}

function severityText(value?: string) {
  if (value === 'blocking') return '阻断';
  if (value === 'warning') return '警告';
  return '通过';
}

function repairLabel(issueCode: string, shotNumber: number) {
  if (issueCode === 'wrong_speaker' || issueCode === 'wrong_voice') {
    return `重新生成镜头 ${shotNumber} 配音并重跑口型`;
  }
  if (issueCode === 'wrong_prop_owner' || issueCode === 'wrong_prop_state') {
    return `重新生成镜头 ${shotNumber} 视频并复审画面`;
  }
  if (issueCode === 'missing_subtitle' || issueCode === 'subtitle_timing') {
    return `修复镜头 ${shotNumber} 字幕并重新渲染字幕`;
  }
  if (issueCode === 'future_episode_leakage') {
    return `修订镜头 ${shotNumber} 提示词并重新生成视频`;
  }
  if (issueCode === 'corrupt_mp4') {
    return `重新渲染镜头 ${shotNumber} 视频并校验 MP4`;
  }
  if (issueCode === 'main_character_identity_mismatch') {
    return `重新生成镜头 ${shotNumber} 视频并复审角色形象`;
  }
  return `修复镜头 ${shotNumber} 的受影响资产`;
}

export function QualityGatePanel({
  qualityGate,
  shotId,
  shotNumber,
  loading,
  onRepair,
  onEvaluate,
}: {
  qualityGate?: QualityGateSummary | null;
  shotId: string;
  shotNumber: number;
  loading?: boolean;
  onRepair: (shotId: string, issueCode: string) => void;
  onEvaluate: (shotId: string) => void;
}) {
  if (!qualityGate) {
    return (
      <section className="rounded-md border border-white/10 bg-slate-950/55 p-3" data-testid={`quality-gate-${shotId}`}>
        <Button type="button" size="sm" disabled={loading} onClick={() => onEvaluate(shotId)}>
          评估镜头 {shotNumber} 六维质量
        </Button>
      </section>
    );
  }
  const repair = qualityGate.suggested_repair;
  const costRisk = repair?.cost_risk;
  return (
    <section
      className="space-y-3 rounded-md border border-white/10 bg-slate-950/55 p-3"
      data-testid={`quality-gate-${shotId}`}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-semibold text-white">六维质量门禁</div>
        <span className={qualityGate.ready ? 'text-xs text-emerald-300' : 'text-xs text-red-300'}>
          {qualityGate.ready ? '可交付' : '存在阻断'}
        </span>
      </div>
      <Button type="button" size="sm" variant="outline" disabled={loading} onClick={() => onEvaluate(shotId)}>
        重新评估镜头 {shotNumber}
      </Button>
      <div className="space-y-2">
        {qualityGate.dimensions.map((item) => (
          <div key={item.id || item.dimension} className="rounded-md bg-white/[0.05] p-2 text-xs text-white/70">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium text-white">{DIMENSION_LABELS[item.dimension] || item.dimension}</span>
              <span className={item.blocking ? 'text-red-300' : item.severity === 'warning' ? 'text-amber-300' : 'text-emerald-300'}>
                {severityText(item.severity)} · {Math.round(item.score ?? 0)}分
              </span>
            </div>
            <div className="mt-2 grid gap-2 sm:grid-cols-3">
              <div><div className="text-white/40">期望</div><pre className="mt-1 whitespace-pre-wrap break-all">{stateText(item.expected_state)}</pre></div>
              <div><div className="text-white/40">实际</div><pre className="mt-1 whitespace-pre-wrap break-all">{stateText(item.observed_state)}</pre></div>
              <div><div className="text-white/40">证据</div><pre className="mt-1 whitespace-pre-wrap break-all">{stateText(item.evidence)}</pre></div>
            </div>
          </div>
        ))}
      </div>
      {repair ? (
        <div className="space-y-2 rounded-md border border-red-300/20 bg-red-400/5 p-3 text-xs text-white/70">
          <div className="flex flex-wrap gap-3">
            <span>成本：{VALUE_LABELS[costRisk?.cost || ''] || costRisk?.cost || '未知'}</span>
            <span>风险：{VALUE_LABELS[costRisk?.risk || ''] || costRisk?.risk || '未知'}</span>
            <span>范围：{costRisk?.scope || '受影响资产'}</span>
          </div>
          <div>动作：{repair.actions.join(' → ')}</div>
          {repair.available === false ? (
            <a href={repair.navigation_url || '#'} className="inline-flex text-amber-200 underline underline-offset-4">
              当前动作不可自动执行，打开人工复审
            </a>
          ) : (
            <Button
              type="button"
              size="sm"
              disabled={loading}
              onClick={() => onRepair(shotId, repair.issue_code)}
              className="bg-red-600 text-white hover:bg-red-700"
            >
              {repairLabel(repair.issue_code, shotNumber)}
            </Button>
          )}
        </div>
      ) : null}
    </section>
  );
}

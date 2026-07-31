'use client';

import { AlertTriangle, CheckCircle2, HelpCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { QualityGateDimension, QualityGateSummary } from '@/lib/studio-types';

const DIMENSIONS: Record<string, { label: string; description: string; passed: string }> = {
  narrative_truth: { label: '故事事实', description: '人物、事件和章节信息是否串章或冲突', passed: '与当前章节设定一致' },
  character_visual: { label: '角色形象', description: '角色身份、外观和锁定造型是否一致', passed: '角色身份与锁定设定一致' },
  scene_prop_state: { label: '场景与道具', description: '场景状态、道具归属和前后关系是否正确', passed: '场景与道具状态一致' },
  motion_camera: { label: '动作与运镜', description: '动作、镜头运动和画面表现是否符合分镜', passed: '动作与运镜符合分镜' },
  voice_lipsync: { label: '声音与对白', description: '说话人、对白、配音和口型是否对应', passed: '声音、对白与角色对应' },
  delivery_integrity: { label: '成片完整性', description: '视频、字幕和交付文件是否完整可用', passed: '成片和字幕文件完整' },
};

const ISSUE_TEXT: Record<string, string> = {
  main_character_identity_mismatch: '成片没有确认到已锁定的主角，角色形象可能不一致',
  future_episode_leakage: '画面或对白出现了后续章节才应出现的信息',
  wrong_prop_owner: '道具归属与故事设定不一致',
  wrong_prop_state: '道具状态与当前章节设定不一致',
  wrong_speaker: '说话人与锁定角色不一致或无法确认',
  wrong_voice: '角色音色与锁定声音不一致',
  missing_subtitle: '有对白，但成片缺少对应字幕',
  subtitle_timing: '字幕出现时间与对白不同步',
  corrupt_mp4: '成片文件损坏或无法正常播放',
  background_unverified: '当前证据不足，暂时无法确认场景背景',
  ambient_audio_unverified: '当前证据不足，暂时无法确认环境音',
  unknown_blocking_quality_issue: '系统发现阻断项，需要人工复核',
};

const ACTION_TEXT: Record<string, string> = {
  regenerate_shot_video: '重新生成本镜头视频',
  rerun_visual_review: '重新检查角色和画面',
  regenerate_tts: '重新生成本镜头配音',
  rerun_lipsync: '重新匹配口型',
  rerender_audio: '重新合成声音',
  generate_subtitles: '补齐字幕',
  rerender_subtitles: '重新渲染字幕',
  revise_shot_prompt: '修正镜头提示词',
  rerender_video: '重新渲染视频',
};

const VALUE_LABELS: Record<string, string> = { low: '低', medium: '中', high: '高' };
const SCOPE_LABELS: Record<string, string> = {
  audio_only: '只处理本镜头声音',
  shot_video_only: '只处理本镜头视频',
  affected_assets: '只处理受影响资产',
};

function evidenceIssueCodes(item: QualityGateDimension) {
  const values = item.evidence?.issue_codes;
  return Array.isArray(values) ? values.map(String) : [];
}

function resultText(item: QualityGateDimension, fallbackCodes: string[]) {
  const dimension = DIMENSIONS[item.dimension];
  const codes = evidenceIssueCodes(item).length ? evidenceIssueCodes(item) : fallbackCodes;
  if (codes.length) return codes.map((code) => ISSUE_TEXT[code] || `检查项：${code}`).join('；');
  if (item.blocking) return '这项检查未通过，需要处理后重新检查';
  if (item.severity === 'warning') return '暂未发现冲突，但证据不足，建议人工看一眼';
  return dimension?.passed || '检查通过';
}

function repairLabel(issueCode: string, shotNumber: number) {
  if (issueCode === 'wrong_speaker' || issueCode === 'wrong_voice') return `重新生成镜头 ${shotNumber} 配音并重跑口型`;
  if (issueCode === 'wrong_prop_owner' || issueCode === 'wrong_prop_state') return `重新生成镜头 ${shotNumber} 视频并复审画面`;
  if (issueCode === 'missing_subtitle' || issueCode === 'subtitle_timing') return `修复镜头 ${shotNumber} 字幕并重新渲染字幕`;
  if (issueCode === 'future_episode_leakage') return `修订镜头 ${shotNumber} 提示词并重新生成视频`;
  if (issueCode === 'corrupt_mp4') return `重新渲染镜头 ${shotNumber} 视频并校验 MP4`;
  if (issueCode === 'main_character_identity_mismatch') return `重新生成镜头 ${shotNumber} 视频并复审角色形象`;
  return `修复镜头 ${shotNumber} 的受影响资产`;
}

function DimensionCard({ item, shotId, fallbackCodes }: { item: QualityGateDimension; shotId: string; fallbackCodes: string[] }) {
  const meta = DIMENSIONS[item.dimension] || { label: item.dimension, description: '检查当前镜头的交付质量', passed: '检查通过' };
  const failed = Boolean(item.blocking);
  const warning = !failed && item.severity === 'warning';
  const Icon = failed ? AlertTriangle : warning ? HelpCircle : CheckCircle2;
  return (
    <article
      data-testid={`quality-dimension-${shotId}-${item.dimension}`}
      className={`rounded-lg border p-3 ${failed ? 'border-red-400/30 bg-red-500/10' : warning ? 'border-amber-300/25 bg-amber-400/10' : 'border-emerald-300/15 bg-emerald-400/[0.06]'}`}
    >
      <div className="flex items-start gap-2.5">
        <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${failed ? 'text-red-300' : warning ? 'text-amber-200' : 'text-emerald-300'}`} aria-hidden="true" />
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="font-medium text-white">{meta.label}</span>
            <span className={`text-xs ${failed ? 'text-red-200' : warning ? 'text-amber-100' : 'text-emerald-200'}`}>
              {failed ? '需处理' : warning ? '建议复核' : '已通过'} · {Math.round(item.score ?? 0)} 分
            </span>
          </div>
          <p className="mt-1 text-xs leading-5 text-white/45">{meta.description}</p>
          <p className="mt-2 text-sm leading-5 text-white/78">{resultText(item, fallbackCodes)}</p>
          {(failed || warning) ? (
            <details className="mt-2 text-xs text-white/50">
              <summary className="cursor-pointer text-cyan-100/80">查看检查依据</summary>
              <div className="mt-2 space-y-1 rounded bg-black/20 p-2">
                <div>检查方式：{item.evidence?.source === 'server_deterministic' ? '系统确定性校验' : '系统质量检查'}</div>
                {item.artifact_id ? <div>关联任务：{item.artifact_id}</div> : null}
                {item.evidence?.evaluation_generation_id ? <div>检查批次：{item.evidence.evaluation_generation_id}</div> : null}
              </div>
            </details>
          ) : null}
        </div>
      </div>
    </article>
  );
}

export function QualityGatePanel({ qualityGate, shotId, shotNumber, loading, onRepair, onEvaluate }: {
  qualityGate?: QualityGateSummary | null;
  shotId: string;
  shotNumber: number;
  loading?: boolean;
  onRepair: (shotId: string, issueCode: string) => void;
  onEvaluate: (shotId: string) => void;
}) {
  if (!qualityGate) {
    return (
      <section className="rounded-xl border border-white/10 bg-slate-950/55 p-4" data-testid={`quality-gate-${shotId}`}>
        <div className="text-sm font-semibold text-white">交付检查（6 项）</div>
        <p className="mt-1 text-xs leading-5 text-white/50">检查故事、角色、场景道具、动作运镜、声音对白和成片完整性。</p>
        <Button className="mt-3" type="button" size="sm" disabled={loading} onClick={() => onEvaluate(shotId)}>开始检查镜头 {shotNumber}</Button>
      </section>
    );
  }
  const repair = qualityGate.suggested_repair;
  const blockerCount = qualityGate.blockers?.length || qualityGate.dimensions.filter((item) => item.blocking).length;
  const warningCount = qualityGate.warnings?.length || qualityGate.dimensions.filter((item) => item.severity === 'warning').length;
  const status = qualityGate.ready ? '全部通过，可以进入成片复审' : blockerCount ? `${blockerCount} 项需要处理` : `${warningCount} 项建议复核`;
  return (
    <section className="space-y-4 rounded-xl border border-white/10 bg-slate-950/55 p-4" data-testid={`quality-gate-${shotId}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-white">交付检查（6 项）</div>
          <p className="mt-1 text-xs leading-5 text-white/50">系统会告诉你哪一项有问题、为什么，以及下一步怎么处理。</p>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-xs ${qualityGate.ready ? 'bg-emerald-400/10 text-emerald-200' : 'bg-red-400/10 text-red-200'}`}>{status}</span>
      </div>
      <div className="grid gap-2 md:grid-cols-2">{qualityGate.dimensions.map((item) => (
        <DimensionCard
          key={item.id || item.dimension}
          item={item}
          shotId={shotId}
          fallbackCodes={[...(qualityGate.blockers || []), ...(qualityGate.warnings || [])].filter((issue) => issue.dimension === item.dimension).map((issue) => issue.code)}
        />
      ))}</div>
      <div className="flex flex-wrap gap-2">
        <Button type="button" size="sm" variant="outline" disabled={loading} onClick={() => onEvaluate(shotId)}>重新检查镜头 {shotNumber}</Button>
      </div>
      {repair ? (
        <div className="rounded-lg border border-red-300/20 bg-red-400/[0.07] p-4 text-sm text-white/75">
          <div className="font-medium text-white">现在怎么做</div>
          <p className="mt-1 text-xs leading-5 text-white/55">只返修当前阻断项，不会重做已经通过的其他镜头。</p>
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs">
            <span>预计成本：{VALUE_LABELS[repair.cost_risk?.cost || ''] || '未知'}</span>
            <span>改动风险：{VALUE_LABELS[repair.cost_risk?.risk || ''] || '未知'}</span>
            <span>处理范围：{SCOPE_LABELS[repair.cost_risk?.scope || ''] || repair.cost_risk?.scope || '受影响资产'}</span>
          </div>
          <p className="mt-2 text-xs text-white/55">处理步骤：{repair.actions.map((action) => ACTION_TEXT[action] || action).join(' → ')}</p>
          {repair.available === false ? (
            <a href={repair.navigation_url || '#'} className="mt-3 inline-flex text-amber-200 underline underline-offset-4">打开人工复审</a>
          ) : (
            <Button type="button" size="sm" disabled={loading} onClick={() => onRepair(shotId, repair.issue_code)} className="mt-3 bg-red-600 text-white hover:bg-red-700">{repairLabel(repair.issue_code, shotNumber)}</Button>
          )}
        </div>
      ) : null}
    </section>
  );
}

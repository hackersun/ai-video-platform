'use client';

import Link from 'next/link';
import { Film, ImageOff, Link2, Wrench } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { HistoryReferencePackageEvidence } from '@/components/production/history-preflight-evidence';
import { QualityGatePanel } from '@/components/studio/quality-gate-panel';
import type { WorkflowShotReviewItem } from '@/lib/api-client';
import type { QualityGateSummary } from '@/lib/studio-types';

type ShotReferenceReviewItem = WorkflowShotReviewItem & {
  episode_shot_number?: number | null;
  scene_index?: number | null;
  scene_count?: number | null;
  scene_title?: string | null;
  reference_image_url?: string | null;
  reference_image_status?: string | null;
  reference_asset_id?: string | null;
  reference_entities?: {
    characters?: Array<{ id?: string; name: string }>;
    scenes?: Array<{ id?: string; name: string }>;
    props?: Array<{ id?: string; name: string }>;
  };
};

function statusLabel(status?: string) {
  if (status === 'succeeded' || status === 'completed') return '成功';
  if (status === 'failed') return '失败';
  if (status === 'running' || status === 'processing') return '生成中';
  if (status === 'queued' || status === 'pending') return '等待中';
  return status || '待生成';
}

function isWaiting(status?: string) {
  return ['queued', 'pending', 'running', 'processing'].includes(status || '');
}

function evidenceText(value: any) {
  if (value == null || value === '') return '暂无';
  if (typeof value === 'string') return value;
  if (typeof value === 'boolean') return value ? '是' : '否';
  if (typeof value === 'number') return String(value);
  if (typeof value === 'object') {
    if (typeof value.message === 'string') return value.message;
    if (typeof value.reason === 'string') return value.reason;
    if (value.ready === true) return '预检通过';
    if (value.ready === false) return '预检未通过';
  }
  return '已有检查记录';
}

function visualConsistencyText(shot: WorkflowShotReviewItem) {
  const evidence = shot.evidence?.visual_consistency;
  const score = shot.visual_consistency_score ?? evidence?.score;
  if (score == null) return '未检测';
  const value = Math.round(Number(score));
  const status = evidence?.status === 'passed' ? '通过' : evidence?.status === 'needs_review' ? '待人工确认' : evidence?.status === 'skipped' ? '已跳过' : '已检测';
  return `${Number.isFinite(value) ? value : score} 分 · ${status}`;
}

function ReferenceMedia({ shot, referenceImageUrl, videoUrl, assetHref }: {
  shot: ShotReferenceReviewItem;
  referenceImageUrl: string;
  videoUrl: string;
  assetHref: string;
}) {
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <figure className="overflow-hidden rounded-xl border border-cyan-300/20 bg-slate-950">
        <figcaption className="flex items-center justify-between border-b border-white/10 px-3 py-2 text-xs text-white/55">
          <span>生成使用的参考图</span><span>{shot.reference_image_status === 'succeeded' ? '已绑定' : '待补齐'}</span>
        </figcaption>
        <div className="aspect-video">
          {referenceImageUrl ? (
            <img src={referenceImageUrl} alt={`镜头 ${shot.shot_number} 生成使用的参考图`} className="h-full w-full object-contain" />
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center text-sm text-white/45">
              <ImageOff className="h-8 w-8" aria-hidden="true" />
              <span>未找到可展示的参考图</span>
              <Button asChild size="sm" variant="outline"><Link href={assetHref}>去资产工作台补齐</Link></Button>
            </div>
          )}
        </div>
      </figure>
      <figure className="overflow-hidden rounded-xl border border-violet-300/20 bg-slate-950">
        <figcaption className="flex items-center justify-between border-b border-white/10 px-3 py-2 text-xs text-white/55">
          <span>当前生成视频</span><span>{statusLabel(shot.status)}</span>
        </figcaption>
        <div className="aspect-video">
          {videoUrl ? <video src={videoUrl} className="h-full w-full object-contain" controls muted playsInline /> : (
            <div className="flex h-full items-center justify-center text-white/35"><Film className="h-10 w-10" aria-hidden="true" /></div>
          )}
        </div>
      </figure>
    </div>
  );
}

function ReferenceEntities({ shot, assetHref }: { shot: ShotReferenceReviewItem; assetHref: string }) {
  const groups = [
    { key: 'characters', label: '角色', values: shot.reference_entities?.characters || [] },
    { key: 'scenes', label: '场景', values: shot.reference_entities?.scenes || [] },
    { key: 'props', label: '道具', values: shot.reference_entities?.props || [] },
  ];
  return (
    <section className="rounded-xl border border-white/10 bg-white/[0.035] p-4" data-testid={`shot-reference-entities-${shot.shot_id}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><div className="flex items-center gap-2 text-sm font-medium text-white"><Link2 className="h-4 w-4 text-cyan-300" />本镜头引用</div><p className="mt-1 text-xs text-white/45">确认名字、场景和道具是否与小说设定一致。</p></div>
        <Button asChild size="sm" variant="outline"><Link href={assetHref}><Wrench className="mr-1.5 h-3.5 w-3.5" />修复角色、场景与道具引用</Link></Button>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        {groups.map((group) => (
          <div key={group.key} className="rounded-lg bg-black/20 px-3 py-2 text-xs">
            <div className="text-white/40">{group.label}</div>
            <div className="mt-1 leading-5 text-white/80">{group.values.length ? `${group.label}：${group.values.map((item) => item.name).join('、')}` : `未绑定${group.label}`}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

export function ShotReviewCard({ shot, referenceImageUrl, videoUrl, assetHref, selected, target, repairLoading, onSelectedChange, onQualityRepair, onQualityEvaluate }: {
  shot: ShotReferenceReviewItem;
  referenceImageUrl: string;
  videoUrl: string;
  assetHref: string;
  selected: boolean;
  target: boolean;
  repairLoading?: boolean;
  onSelectedChange: (checked: boolean) => void;
  onQualityRepair: (shotId: string, issueCode: string) => void;
  onQualityEvaluate: (shotId: string) => void;
}) {
  const qualityGate = (shot as WorkflowShotReviewItem & { quality_gate?: QualityGateSummary }).quality_gate;
  return (
    <Card id={`shot-review-${shot.shot_id}`} data-testid={`shot-review-card-${shot.shot_id}`} data-shot-id={shot.shot_id} data-target-shot={target ? 'true' : undefined} className={`overflow-hidden bg-white/[0.035] text-white shadow-none ${target ? 'border-cyan-300/40 ring-1 ring-cyan-300/20' : 'border-white/10'}`}>
      <CardHeader className="border-b border-white/10 p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <Checkbox checked={selected} onCheckedChange={(value) => onSelectedChange(value === true)} aria-label={`选择镜头 ${shot.shot_number}`} />
            <div>
              <CardTitle className="text-lg">镜头 {shot.shot_number}</CardTitle>
              {(shot.scene_index || shot.episode_shot_number) ? (
                <p data-testid={`shot-sequence-${shot.shot_id}`} className="mt-1 text-xs text-cyan-200/80">
                  {shot.scene_index ? `场景 ${shot.scene_index}${shot.scene_count ? `/${shot.scene_count}` : ''}${shot.scene_title ? ` · ${shot.scene_title}` : ''}` : ''}
                  {shot.scene_index && shot.episode_shot_number ? ' · ' : ''}
                  {shot.episode_shot_number ? `本集镜头 ${shot.episode_shot_number}` : ''}
                </p>
              ) : null}
              <p className="mt-1 text-xs text-white/45">{shot.duration || 0} 秒 · 重生 {shot.regeneration_count || 0} 次</p>
            </div>
          </div>
          <Badge variant={shot.status === 'failed' ? 'danger' : 'secondary'}>{statusLabel(shot.status)}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 p-4 sm:p-5">
        {isWaiting(shot.status) ? <div className="rounded-lg border border-cyan-300/25 bg-cyan-400/10 px-3 py-2 text-xs text-cyan-50">重生进行中，等待视频/声音完成后再合成</div> : null}
        <ReferenceMedia shot={shot} referenceImageUrl={referenceImageUrl} videoUrl={videoUrl} assetHref={assetHref} />
        <div className="rounded-xl bg-white/[0.035] p-4"><div className="text-xs text-white/40">字幕 / 对白</div><p className="mt-1 text-sm leading-6 text-white/80">{shot.subtitle_text || '暂无字幕/对白'}</p></div>
        <ReferenceEntities shot={shot} assetHref={assetHref} />
        <div className="grid gap-2 text-xs text-white/70 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-lg bg-white/[0.04] px-3 py-2"><div className="text-white/40">生成策略</div><div className="mt-1 font-medium text-white">{evidenceText(shot.evidence?.strategy_routing)}</div></div>
          <div className="rounded-lg bg-white/[0.04] px-3 py-2"><div className="text-white/40">参考包</div><div className="mt-1 font-medium text-white">{evidenceText(shot.evidence?.reference_package_mode)}</div><HistoryReferencePackageEvidence referencePackage={shot.evidence?.reference_package} testId={`shot-review-reference-package-${shot.shot_id}`} /></div>
          <div className="rounded-lg bg-white/[0.04] px-3 py-2"><div className="text-white/40">生成前检查</div><div className="mt-1 font-medium text-white">{evidenceText(shot.evidence?.generation_preflight)}</div></div>
          <div className="rounded-lg bg-white/[0.04] px-3 py-2" data-testid={`shot-review-visual-consistency-${shot.shot_id}`}><div className="text-white/40">视觉一致性</div><div className="mt-1 font-medium text-white">{visualConsistencyText(shot)}</div>{shot.evidence?.visual_consistency?.frame_count != null ? <div className="mt-1 text-white/45">抽帧 {shot.evidence.visual_consistency.frame_count}</div> : null}</div>
        </div>
        <QualityGatePanel qualityGate={qualityGate} shotId={shot.shot_id} shotNumber={shot.shot_number} loading={repairLoading} onRepair={onQualityRepair} onEvaluate={onQualityEvaluate} />
      </CardContent>
    </Card>
  );
}

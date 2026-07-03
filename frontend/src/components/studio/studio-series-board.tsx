'use client';

import Link from 'next/link';
import { BookMarked, CheckCircle2, Film, Lock, PlayCircle, ShieldAlert } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { StudioIssue, StudioSnapshot } from '@/lib/studio-types';

type StageTone = 'ready' | 'working' | 'blocked';
type Requirement = {
  label: string;
  ready: boolean;
  value: string;
};

function hasIssue(issues: StudioIssue[], needles: string[]) {
  return issues.some((issue) => {
    const haystack = `${issue.code || ''} ${issue.message || ''}`.toLowerCase();
    return needles.some((needle) => haystack.includes(needle));
  });
}

function toneClass(tone: StageTone) {
  if (tone === 'ready') return 'border-emerald-400/25 bg-emerald-500/10 text-emerald-50';
  if (tone === 'blocked') return 'border-red-400/25 bg-red-500/10 text-red-50';
  return 'border-cyan-400/25 bg-cyan-500/10 text-cyan-50';
}

function statusLabel(tone: StageTone) {
  if (tone === 'ready') return '已就绪';
  if (tone === 'blocked') return '需补齐';
  return '进行中';
}

function requirementClass(ready: boolean) {
  return ready ? 'border-emerald-300/20 bg-emerald-400/10 text-emerald-50' : 'border-red-300/25 bg-red-400/10 text-red-50';
}

function SeriesStage({
  icon: Icon,
  title,
  description,
  detail,
  requirements,
  tone,
  href,
  actionLabel,
}: {
  icon: any;
  title: string;
  description: string;
  detail: string;
  requirements?: Requirement[];
  tone: StageTone;
  href: string;
  actionLabel: string;
}) {
  return (
    <div className={`rounded-xl border p-4 ${toneClass(tone)}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <Icon className="mt-0.5 h-5 w-5 shrink-0" />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <div className="font-medium text-white">{title}</div>
              <Badge variant="outline" className="border-current text-current">
                {statusLabel(tone)}
              </Badge>
            </div>
            <div className="mt-1 text-sm leading-6 text-white/70">{description}</div>
            <div className="mt-2 text-xs text-white/50">{detail}</div>
            {requirements && requirements.length > 0 ? (
              <div className="mt-3 grid gap-2 sm:grid-cols-3">
                {requirements.map((item) => (
                  <div key={item.label} className={`rounded-lg border px-3 py-2 text-xs ${requirementClass(item.ready)}`}>
                    <div className="font-medium">{item.ready ? '已满足' : '缺失'} · {item.label}</div>
                    <div className="mt-1 text-white/55">{item.value}</div>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </div>
        <Button asChild size="sm" variant="outline" className="shrink-0 border-white/20 text-white">
          <Link href={href}>{actionLabel}</Link>
        </Button>
      </div>
    </div>
  );
}

export function StudioSeriesBoard({
  snapshot,
  workflowId,
}: {
  snapshot: StudioSnapshot | null;
  workflowId?: string;
}) {
  const issues = snapshot?.issues || [];
  const bible = snapshot?.story_bible;
  const productionBible = snapshot?.production_bible_summary;
  const production = snapshot?.production || {};
  const assets = snapshot?.assets || {};
  const jobs = snapshot?.jobs?.summary || {};
  const strategy = snapshot?.workflow?.latest_production_strategy;
  const blockingCount = snapshot?.mode_policy?.blocking_issue_count || 0;
  const mediaCount = (jobs.video_count || 0) + (jobs.tts_count || 0) + (jobs.media_count || 0) + (jobs.synthesis_count || 0);
  const bibleRuleCount =
    ((productionBible?.counts?.characters || 0) +
      (productionBible?.counts?.scenes || 0) +
      (productionBible?.counts?.props || 0) +
      (productionBible?.counts?.events || 0)) ||
    (bible?.character_rule_count || 0) +
    (bible?.scene_rule_count || 0) +
    (bible?.prop_rule_count || 0) +
    (bible?.event_count || 0);
  const bibleReady = Boolean(productionBible?.story_bible_id || bible?.id || bibleRuleCount > 0);
  const draftReady = Boolean(snapshot?.timeline?.preview_url || (snapshot?.timeline?.clip_count || 0) > 0);
  const hasShots = (production.shot_count || 0) > 0;
  const assetCoverage = production.asset_lock_coverage || 0;
  const assetCoverageLabel = assetCoverage >= 1 ? '全量覆盖' : assetCoverage > 0 ? '部分覆盖' : '未覆盖';
  const missingAssetCount = productionBible?.asset_readiness?.missing_asset_count;
  const voiceCount = productionBible?.voices?.length || 0;
  const hasFinalReference = (assets.final_count || 0) > 0;
  const hasAssetLocks = Boolean(productionBible?.asset_readiness?.ready || assetCoverage >= 1);
  const hasVoiceProfiles = voiceCount > 0;
  const missingFinalGateLocks = !hasFinalReference || !hasAssetLocks || !hasVoiceProfiles;
  const assetIssue = hasIssue(issues, ['asset', '资产', 'lock', 'voice', '声音', 'tts']);
  const qualityBlocked = blockingCount > 0 || hasIssue(issues, ['model', 'preflight', 'gate', '门禁', '验证']);
  const isFinalQuality = strategy === 'final_quality';
  const isDraftFast = strategy === 'draft_fast' || !strategy;
  const finalGateTone: StageTone = missingFinalGateLocks || assetIssue ? 'blocked' : 'ready';
  const strategyLabel = snapshot?.workflow?.latest_production_strategy_label || (isFinalQuality ? '高质量终稿' : '快速草稿');
  const strategyGateCopy = isFinalQuality
    ? missingFinalGateLocks
      ? '终稿门禁：缺少定稿参考图、资产锁覆盖或角色声线时会阻断终稿生产。'
      : '终稿门禁：定稿参考图、资产锁覆盖和角色声线已满足，可进入终稿生产。'
    : isDraftFast
      ? '草稿模式：草片可先跑；进入终稿前必须补齐定稿参考图、资产锁覆盖和角色声线。'
      : `${strategyLabel}：终稿导出前仍会校验定稿参考图、资产锁覆盖和角色声线。`;
  const assetLockDetail = [
    strategyGateCopy,
    `资产锁${assetCoverageLabel} · 已锁定 ${assets.locked_count || 0} · 定稿 ${assets.final_count || 0} · 声线 ${voiceCount} · 缺资产 ${missingAssetCount ?? '未知'}`,
  ].join(' ');
  const producerHref = workflowId ? `/producer?workflow_id=${workflowId}` : '/producer';
  const shotReviewHref = workflowId ? `/studio/shot-review?workflow_id=${workflowId}` : '/studio/shot-review';
  const quickStartHref = '/quick-start';

  return (
    <Card className="border-cyan-400/15 bg-cyan-500/[0.06]">
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-white">
              <BookMarked className="h-4 w-4 text-cyan-300" />
              本集生产 P0 看板
            </CardTitle>
            <div className="mt-1 max-w-3xl text-sm leading-6 text-white/55">
              从小说/章节生成本集工程后，这里跟踪 Production Bible、草片、资产/声音锁和质量门禁，不需要先理解底层 workflow。
            </div>
          </div>
          <div className="flex shrink-0 flex-col gap-2 sm:flex-row">
            <Button asChild size="sm" className="bg-cyan-600 hover:bg-cyan-700">
              <Link href={producerHref}>生成本集草片</Link>
            </Button>
            <Button asChild size="sm" variant="outline" className="border-white/20 text-white">
              <Link href={shotReviewHref}>
                <Film className="mr-1.5 h-3.5 w-3.5" />
                镜头审阅
              </Link>
            </Button>
            <Button asChild size="sm" variant="outline" className="border-white/20 text-white">
              <Link href={quickStartHref}>从小说创建本集工程</Link>
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="grid gap-3 xl:grid-cols-2">
        <SeriesStage
          icon={BookMarked}
          title="Production Bible"
          description="锁定系列风格、角色、场景、道具和事件，作为本集生产的一致性来源。"
          detail={bibleReady ? `已读取 ${bibleRuleCount} 条角色/场景/道具/事件锚点` : '尚未绑定小说级设定，建议先从小说分析生成。'}
          tone={bibleReady ? 'ready' : 'blocked'}
          href={quickStartHref}
          actionLabel={bibleReady ? '查看小说入口' : '生成设定'}
        />
        <SeriesStage
          icon={PlayCircle}
          title="一键本集草片"
          description="复用当前本集工程的剧本、分镜、镜头、媒体任务和时间线，推进到可审阅草片。"
          detail={draftReady ? `时间线 ${snapshot?.timeline?.clip_count || 0} 个片段` : hasShots ? `已有 ${production.shot_count || 0} 个镜头，可进入制片生成草片` : '还没有镜头，先创建本集工程或生成分镜。'}
          tone={draftReady ? 'ready' : hasShots || mediaCount > 0 ? 'working' : 'blocked'}
          href={producerHref}
          actionLabel="去制片"
        />
        <SeriesStage
          icon={Lock}
          title="资产/声音锁"
          description="终稿模式需要定稿参考图、资产锁覆盖和角色 voice profile；缺任一项都会阻断终稿出片。"
          detail={assetLockDetail}
          requirements={[
            { label: '定稿参考图', ready: hasFinalReference, value: hasFinalReference ? `${assets.final_count || 0} 个定稿资产` : '缺定稿参考图，先在资产页补齐。' },
            { label: '资产锁覆盖', ready: hasAssetLocks, value: hasAssetLocks ? assetCoverageLabel : `缺资产 ${missingAssetCount ?? '未知'}，进入 Producer 应用锁。` },
            { label: '角色声线', ready: hasVoiceProfiles, value: hasVoiceProfiles ? `${voiceCount} 个 voice profile` : '缺角色声线，回 Story Bible/角色设定绑定。' },
          ]}
          tone={finalGateTone}
          href="/assets"
          actionLabel={missingFinalGateLocks ? '补齐资产/声线' : '查看资产'}
        />
        <SeriesStage
          icon={qualityBlocked ? ShieldAlert : CheckCircle2}
          title={isFinalQuality ? '终稿门禁' : '质量门禁'}
          description={isFinalQuality ? '高质量终稿会强制执行资产/声音锁、模型验证、公开素材地址和一致性要求。' : '生产模式下汇总资产锁、模型验证、公开素材地址和一致性风险，防止带病出片。'}
          detail={qualityBlocked || (isFinalQuality && missingFinalGateLocks) ? `${blockingCount || issues.length || 1} 个阻断/风险项需要处理；缺锁会阻断终稿。` : isDraftFast ? '草稿可继续生成和审阅；终稿前需要完成资产/声音锁。' : '当前没有阻断项，可继续草片审阅或终稿生产。'}
          tone={qualityBlocked || (isFinalQuality && missingFinalGateLocks) ? 'blocked' : 'ready'}
          href="#studio-agent-panel"
          actionLabel="查看门禁"
        />
      </CardContent>
    </Card>
  );
}

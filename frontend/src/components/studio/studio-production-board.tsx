'use client';

import Link from 'next/link';
import { Boxes, CheckCircle2, Download, Film, ListChecks, Lock, Timer, Video } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { StudioSnapshot } from '@/lib/studio-types';

const percent = (value?: number) => `${Math.round((value || 0) * 100)}%`;

const statusLabel = (status?: string) => {
  const labels: Record<string, string> = {
    pending: '等待',
    running: '生成中',
    succeeded: '完成',
    completed: '完成',
    failed: '失败',
    cancelled: '取消',
  };
  return status ? labels[status] || status : '未知';
};

const droppedReasonText = (reason?: string) => {
  const labels: Record<string, string> = {
    exceeds_model_reference_image_limit: '超出模型参考图上限',
    unsupported_reference_media: '不支持的参考素材',
    reference_image_not_public: '参考图不是公网地址',
  };
  return reason ? labels[reason] || reason : '参考素材被丢弃';
};

function Metric({ label, value, detail, icon: Icon }: any) {
  return (
    <div className="rounded-lg border border-white/10 bg-black/20 p-3">
      <div className="flex items-center gap-2 text-xs text-white/45">
        <Icon className="h-4 w-4" />
        {label}
      </div>
      <div className="mt-1 text-2xl font-semibold text-white">{value}</div>
      <div className="mt-1 text-xs text-white/45">{detail}</div>
    </div>
  );
}

export function StudioProductionBoard({ snapshot, workflowId }: { snapshot: StudioSnapshot | null; workflowId?: string }) {
  const production = snapshot?.production || {};
  const jobs = snapshot?.jobs?.summary || {};
  const referenceJobs = (snapshot?.jobs?.video_jobs || [])
    .filter((job) => job.reference_package)
    .slice(0, 3);
  const assets = snapshot?.assets || {};
  const shots = snapshot?.shots || [];
  const activeWorkflowId = workflowId || snapshot?.workflow?.id || '';
  const shotReviewHref = activeWorkflowId ? `/studio/shot-review?workflow_id=${activeWorkflowId}` : '/studio/shot-review';
  const renderHref = activeWorkflowId ? `/workflow?workflow_id=${activeWorkflowId}` : '/workflow';
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
      <Card className="border-white/10 bg-white/5">
        <CardHeader className="pb-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <CardTitle className="flex items-center gap-2 text-white">
              <ListChecks className="h-4 w-4 text-cyan-300" />
              生产看板
            </CardTitle>
            <div className="flex flex-wrap gap-2">
              <Button asChild size="sm" variant="outline" className="shrink-0 border-white/20 text-white">
                <Link href={shotReviewHref}>
                  <Film className="mr-1.5 h-3.5 w-3.5" />
                  镜头审阅
                </Link>
              </Button>
              <Button asChild size="sm" variant="outline" className="shrink-0 border-white/20 text-white">
                <Link href={renderHref}>
                  <Download className="mr-1.5 h-3.5 w-3.5" />
                  真实成片
                </Link>
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Metric icon={Film} label="镜头" value={production.shot_count || 0} detail="当前本集全部场景镜头" />
            <Metric icon={Lock} label="资产锁" value={percent(production.asset_lock_coverage)} detail="角色/场景/道具锁覆盖" />
            <Metric icon={CheckCircle2} label="实体引用" value={percent(production.entity_ref_coverage)} detail="镜头上下文覆盖" />
            <Metric icon={Video} label="媒体任务" value={(jobs.video_count || 0) + (jobs.media_count || 0)} detail="视频与直生音视频" />
          </div>

          <div className="overflow-hidden rounded-lg border border-white/10">
            <div className="grid grid-cols-[72px_1fr_96px_96px] bg-white/5 px-3 py-2 text-xs text-white/45">
              <div>镜头</div>
              <div>内容</div>
              <div>实体</div>
              <div>资产锁</div>
            </div>
            {shots.length ? (
              shots.slice(0, 20).map((shot) => (
                <div key={shot.id} className="grid grid-cols-[72px_1fr_96px_96px] border-t border-white/10 px-3 py-2 text-sm">
                  <div className="text-white/70">
                    #{shot.episode_shot_number || shot.shot_number || '-'}
                    {shot.scene_index ? <span className="ml-1 text-[10px] text-white/40">场{shot.scene_index}</span> : null}
                  </div>
                  <div className="min-w-0 truncate text-white">{shot.prompt || shot.dialogue || '未填写镜头描述'}</div>
                  <div>
                    <Badge variant="outline" className="border-white/20 text-white/70">{shot.entity_ref_count || 0}</Badge>
                  </div>
                  <div>
                    <Badge
                      variant="outline"
                      className={shot.asset_lock_count ? 'border-emerald-400/30 text-emerald-200' : 'border-red-400/30 text-red-200'}
                    >
                      {shot.asset_lock_count || 0}
                    </Badge>
                  </div>
                </div>
              ))
            ) : (
              <div className="border-t border-white/10 px-3 py-6 text-center text-sm text-white/50">还没有镜头，先生成或选择分镜。</div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="border-white/10 bg-white/5">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-white">
            <Boxes className="h-4 w-4 text-cyan-300" />
            资产与时间线
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <Metric icon={Boxes} label="资产总数" value={assets.total_count || 0} detail={`已锁定 ${assets.locked_count || 0} · 定稿 ${assets.final_count || 0}`} />
          <Metric icon={Timer} label="时间线片段" value={snapshot?.timeline?.clip_count || 0} detail={snapshot?.timeline?.name || '尚未同步时间线'} />
          <div className="rounded-lg border border-white/10 bg-black/20 p-3">
            <div className="text-xs text-white/45">任务分布</div>
            <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-white/65">
              <div>视频：{jobs.video_count || 0}</div>
              <div>TTS：{jobs.tts_count || 0}</div>
              <div>直生：{jobs.media_count || 0}</div>
              <div>合成：{jobs.synthesis_count || 0}</div>
            </div>
          </div>
          {referenceJobs.length ? (
            <div className="rounded-lg border border-white/10 bg-black/20 p-3">
              <div className="text-xs font-medium text-white/70">最近参考包</div>
              <div className="mt-2 space-y-2">
                {referenceJobs.map((job, index) => {
                  const pkg = job.reference_package;
                  const droppedCount = pkg?.dropped_count ?? pkg?.dropped?.length ?? 0;
                  const croppedCount = pkg?.cropped_count || 0;
                  const trimCount = droppedCount + croppedCount;
                  const reason = pkg?.dropped?.[0]?.reason;

                  return (
                    <div key={job.id || job.task_id || index} className="border-t border-white/10 pt-2 first:border-t-0 first:pt-0">
                      <div className="flex items-center justify-between gap-2 text-xs">
                        <span className="truncate text-white/70">{statusLabel(job.status)}</span>
                        <span className="truncate text-white/45">{job.reference_package_mode || pkg?.mode || '参考包'}</span>
                      </div>
                      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-white/60">
                        <span>图片 {pkg?.image_count || 0}</span>
                        <span>视频 {pkg?.video_count || 0}</span>
                        <span>裁剪 {trimCount}</span>
                      </div>
                      {reason ? <div className="mt-1 truncate text-xs text-amber-200/75">丢弃：{droppedReasonText(reason)}</div> : null}
                    </div>
                  );
                })}
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

'use client';

import Link from 'next/link';
import { GitBranch, History, Route } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import type { ProductionGraphEvent, StudioSnapshot } from '@/lib/studio-types';

const eventLabels: Record<string, string> = {
  costume_changed: '服装变化',
  injury_changed: '伤势变化',
  prop_owner_changed: '道具持有人变化',
  weather_changed: '场景天气变化',
  relationship_changed: '人物关系变化',
  restore_version: '恢复生产版本',
};

function shortHash(value?: string | null) {
  return value ? value.slice(0, 10) : '-';
}

function numericValue(value: unknown) {
  return typeof value === 'number' || typeof value === 'string' ? value : '-';
}

function textValue(value: unknown) {
  return typeof value === 'string' ? value : '未标注';
}

function EventRow({ item, workflowId }: { item: ProductionGraphEvent; workflowId?: string }) {
  const episodes = Array.isArray(item.affected_episode_indices) ? item.affected_episode_indices : [];
  const shotReviewUrl = item.affected_shots?.[0]?.review_url
    || (workflowId ? `/studio/shot-review?workflow_id=${workflowId}` : null);
  return (
    <div className="rounded-lg border border-white/10 bg-black/20 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-medium text-white">{eventLabels[item.event_type] || item.event_type || '状态变化'}</div>
        <Badge variant="outline" className="border-cyan-400/30 text-cyan-100">修订 v{item.production_version || '-'}</Badge>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5 text-xs text-white/55">
        <span>剧情：第 {numericValue(item.story_time?.episode_index || item.episode_index)} 集 / 顺序 {numericValue(item.story_time?.sequence)}</span>
        <span>·</span>
        <span>制作：{textValue(item.production_time?.stage)}</span>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <span className="text-xs text-white/45">影响集数</span>
        {episodes.length ? episodes.map((episode: number) => (
          <Badge key={episode} variant="outline" className="border-amber-400/35 text-amber-100">第 {episode} 集</Badge>
        )) : <span className="text-xs text-white/40">无下游影响</span>}
      </div>
      {shotReviewUrl && episodes.length ? (
        <Link
          className="mt-2 inline-flex text-xs text-cyan-200 hover:text-cyan-100"
          href={shotReviewUrl}
        >
          查看受影响镜头
        </Link>
      ) : null}
    </div>
  );
}

export function ProductionGraphPanel({ snapshot }: { snapshot: StudioSnapshot | null }) {
  const graph = snapshot?.production_graph || {};
  const storyOrder = Array.isArray(graph.story_order) ? graph.story_order : [];
  const revisions = Array.isArray(graph.production_revisions) ? graph.production_revisions : [];
  const workflowId = snapshot?.workflow?.id;

  return (
    <Card data-testid="production-graph-panel" className="border-white/10 bg-white/[0.035]">
      <CardContent className="p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex items-center gap-2 text-white">
              <GitBranch className="h-5 w-5 text-cyan-200" aria-hidden />
              <h2 className="text-lg font-semibold">Production Graph</h2>
            </div>
            <p className="mt-1 text-sm leading-6 text-white/50">剧情发生顺序与制作修订顺序独立展示，避免回改覆盖历史事实。</p>
          </div>
          <div className="flex gap-2">
            <Badge variant="outline" className="border-white/15 text-white/65">版本 {graph.version || 0}</Badge>
            <Badge variant="outline" className="border-white/15 text-white/65">Hash {shortHash(graph.hash)}</Badge>
          </div>
        </div>

        {storyOrder.length || revisions.length ? (
          <div className="mt-5 grid gap-4 xl:grid-cols-2">
            <section aria-label="剧情顺序">
              <div className="mb-2 flex items-center gap-2 text-sm font-medium text-white/80">
                <Route className="h-4 w-4 text-emerald-200" aria-hidden />
                剧情顺序
              </div>
              <div className="space-y-2">{storyOrder.map((item) => <EventRow key={item.id} item={item} workflowId={workflowId} />)}</div>
            </section>
            <section aria-label="制作修订顺序">
              <div className="mb-2 flex items-center gap-2 text-sm font-medium text-white/80">
                <History className="h-4 w-4 text-amber-200" aria-hidden />
                制作修订顺序
              </div>
              <div className="space-y-2">{revisions.map((item) => <EventRow key={item.id} item={item} workflowId={workflowId} />)}</div>
            </section>
          </div>
        ) : (
          <div className="mt-5 rounded-lg border border-dashed border-white/15 p-6 text-center text-sm text-white/45">
            尚无已记录的生产状态事件。
          </div>
        )}
      </CardContent>
    </Card>
  );
}

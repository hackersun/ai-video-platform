'use client';

import Link from 'next/link';
import { Layers3, PlayCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { SeriesPlanEpisode, StudioSnapshot } from '@/lib/studio-types';

function chapterRangeLabel(episode: SeriesPlanEpisode) {
  const range = episode.chapter_range;
  if (range && !Array.isArray(range) && typeof range === 'object') {
    return range.label || [range.start_number, range.end_number].filter(Boolean).join('-');
  }
  if (Array.isArray(range)) return range.filter(Boolean).join('-');
  return episode.chapter_ids?.length ? `${episode.chapter_ids.length} 章` : '未绑定章节';
}

function carryOverLabel(episode: SeriesPlanEpisode) {
  const state = episode.carry_over_state || {};
  const characters = Array.isArray(state.characters) ? state.characters.length : 0;
  const props = Array.isArray(state.props) ? state.props.length : 0;
  const events = Array.isArray(state.events) ? state.events.length : 0;
  return `承接 角色 ${characters} · 道具 ${props} · 事件 ${events}`;
}

export function EpisodePlanPanel({ snapshot }: { snapshot: StudioSnapshot | null }) {
  const plan = snapshot?.series_plan;
  const episodes = plan?.episodes || [];

  return (
    <Card data-testid="episode-plan-panel" className="border-white/10 bg-white/5">
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-white">
              <Layers3 className="h-4 w-4 text-cyan-300" />
              多集计划
            </CardTitle>
            <div className="mt-1 text-sm text-white/55">从整本小说拆分剧集，追踪每集继承状态和生产入口。</div>
          </div>
          <Badge variant="outline" className="w-fit border-white/15 text-white/70">
            {episodes.length || 0} 集
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {episodes.length ? (
          episodes.map((episode, index) => {
            const episodeIndex = episode.episode_index || episode.episode_number || index + 1;
            const workflowHref = episode.workflow_id ? `/studio?workflow_id=${episode.workflow_id}` : '#studio-agent-panel';
            return (
              <div key={`${episodeIndex}-${episode.title || index}`} className="grid gap-3 border-t border-white/10 py-3 first:border-t-0 first:pt-0 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="text-sm font-medium text-white">第 {episodeIndex} 集 · {episode.title || '未命名'}</div>
                    <Badge variant="outline" className="border-cyan-300/25 text-cyan-100">{episode.status || 'planned'}</Badge>
                  </div>
                  <div className="mt-1 break-words text-xs leading-5 text-white/50">
                    章节 {chapterRangeLabel(episode)} · {carryOverLabel(episode)}
                  </div>
                  {episode.summary ? (
                    <div className="mt-1 line-clamp-2 break-words text-xs leading-5 text-white/45">{episode.summary}</div>
                  ) : null}
                </div>
                <Button asChild size="sm" variant="outline" className="w-fit border-white/15 text-white">
                  <Link href={workflowHref}>
                    <PlayCircle className="mr-1.5 h-3.5 w-3.5" />
                    打开本集
                  </Link>
                </Button>
              </div>
            );
          })
        ) : (
          <div className="border-t border-white/10 py-4 text-sm text-white/50">暂无多集计划</div>
        )}
      </CardContent>
    </Card>
  );
}

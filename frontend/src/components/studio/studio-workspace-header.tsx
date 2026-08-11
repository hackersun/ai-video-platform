'use client';

import { useEffect, useMemo, useState } from 'react';
import { BookOpen, CheckCircle2, ChevronDown, Plus, Settings2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import apiClient from '@/lib/api-client';
import { toMediaUrl } from '@/lib/media-url';
import type { StudioSnapshot, StudioWorkflowOption } from '@/lib/studio-types';

type ExpertLink = { href: string; label: string };
type NovelDetail = { cover_url?: string | null; chapter_count?: number; total_chapters?: number; updated_at?: string };
type ChapterDetail = { id: string; title?: string; chapter_number?: number };
type EpisodeOption = { id: string; chapterId: string; workflowId?: string; label: string; title: string; progress: string; status: string; completed: boolean };

function workflowIdOf(item: StudioWorkflowOption) {
  return item.workflow_id || item.id || '';
}

function relatedWorkflows(snapshot: StudioSnapshot, workflows: StudioWorkflowOption[], chapters: ChapterDetail[]) {
  const novelId = snapshot.workflow?.novel_id || snapshot.story_context?.novel?.id || '';
  const order = new Map(chapters.map((chapter) => [chapter.id, chapter.chapter_number || Number.MAX_SAFE_INTEGER]));
  const byWorkflowId = new Map<string, StudioWorkflowOption>();
  workflows
    .filter((workflow) => !novelId || workflow.novel_id === novelId || workflowIdOf(workflow) === snapshot.workflow?.id)
    .forEach((workflow) => {
      const id = workflowIdOf(workflow);
      const existing = byWorkflowId.get(id);
      if (id && (!existing || (!existing.chapter_id && workflow.chapter_id))) byWorkflowId.set(id, workflow);
    });
  const currentWorkflow: StudioWorkflowOption = {
    ...snapshot.workflow,
    workflow_id: snapshot.workflow?.id,
    chapter_id: snapshot.workflow?.chapter_id || snapshot.story_context?.chapter?.id,
  };
  if (currentWorkflow.workflow_id && !byWorkflowId.has(currentWorkflow.workflow_id)) {
    byWorkflowId.set(currentWorkflow.workflow_id, currentWorkflow);
  }
  const seenChapterIds = new Set<string>();
  return Array.from(byWorkflowId.values())
    .filter((workflow) => {
      if (!workflow.chapter_id) return true;
      if (seenChapterIds.has(workflow.chapter_id)) return false;
      seenChapterIds.add(workflow.chapter_id);
      return true;
    })
    .sort((a, b) => (order.get(a.chapter_id || '') || 999) - (order.get(b.chapter_id || '') || 999));
}

function episodeOptions(snapshot: StudioSnapshot, workflows: StudioWorkflowOption[], chapters: ChapterDetail[]): EpisodeOption[] {
  const chapterMap = new Map(chapters.map((chapter) => [chapter.id, chapter]));
  const related = relatedWorkflows(snapshot, workflows, chapters);
  const workflowMap = new Map(related.filter((workflow) => workflow.chapter_id).map((workflow) => [workflow.chapter_id, workflow]));
  const episodeRows = chapters.length
    ? chapters.map((chapter) => ({ chapter, workflow: workflowMap.get(chapter.id) }))
    : related.map((workflow) => ({ chapter: chapterMap.get(workflow.chapter_id || ''), workflow }));
  const knownChapterIds = new Set(chapters.map((chapter) => chapter.id));
  if (chapters.length) related.filter((workflow) => !workflow.chapter_id || !knownChapterIds.has(workflow.chapter_id)).forEach((workflow) => episodeRows.push({ chapter: undefined, workflow }));
  return episodeRows.map(({ chapter, workflow }, index) => {
    if (!workflow) return {
      id: `chapter:${chapter?.id || index}`,
      chapterId: chapter?.id || '',
      label: `第 ${chapter?.chapter_number || index + 1} 集`, title: chapter?.title || '未命名本集',
      progress: '未创建工程 · 点击创建', status: 'planned', completed: false,
    };
    const id = workflowIdOf(workflow);
    const shotTotal = workflow.metadata?.production_quality_report?.shot_count || 8;
    const generated = Math.min(workflow.video_job_ids?.length || 0, shotTotal);
    const completed = Boolean(workflow.synthesis_job_ids?.length || workflow.status === 'completed');
    const active = id === snapshot.workflow?.id;
    return {
      id,
      chapterId: workflow.chapter_id || chapter?.id || '', workflowId: id,
      label: `第 ${chapter?.chapter_number || index + 1} 集`,
      title: chapter?.title || workflow.title || '未命名本集',
      progress: `${generated}/${shotTotal} · ${active ? '当前制作' : completed ? '已完成' : '计划中'}`,
      status: active ? 'active' : completed ? 'completed' : 'planned',
      completed,
    };
  });
}

function formatDate(value?: string) {
  return value ? value.slice(0, 10) : '暂无记录';
}

export function StudioWorkspaceHeader({
  snapshot, workflows, workflowId, loading, expertLinks, onWorkflowChange, onOpenExpert,
}: {
  snapshot: StudioSnapshot;
  workflows: StudioWorkflowOption[];
  workflowId: string;
  loading?: boolean;
  expertLinks: ExpertLink[];
  onWorkflowChange: (workflowId: string) => void;
  onOpenExpert: (href: string) => void;
}) {
  const [novel, setNovel] = useState<NovelDetail>({});
  const [chapters, setChapters] = useState<ChapterDetail[] | null>(null);
  const [creatingEpisodeId, setCreatingEpisodeId] = useState('');
  const [episodeError, setEpisodeError] = useState('');
  const novelId = snapshot.workflow?.novel_id || snapshot.story_context?.novel?.id || '';
  useEffect(() => {
    let cancelled = false;
    if (!novelId) { setNovel({}); setChapters([]); return; }
    setChapters(null);
    Promise.all([apiClient.getNovel(novelId), apiClient.getChapters(novelId)])
      .then(([novelData, chapterData]) => {
        if (!cancelled) { setNovel(novelData || {}); setChapters(Array.isArray(chapterData) ? chapterData : []); }
      })
      .catch(() => { if (!cancelled) { setNovel({}); setChapters([]); } });
    return () => { cancelled = true; };
  }, [novelId]);

  const episodes = useMemo(() => chapters === null ? [] : episodeOptions(snapshot, workflows, chapters), [chapters, snapshot, workflows]);
  const completed = episodes.filter((episode) => episode.completed).length;
  const total = novel.total_chapters || novel.chapter_count || episodes.length || 1;
  const progress = Math.round(completed / total * 100);
  const novelTitle = snapshot.story_context?.novel?.title || snapshot.workflow?.title || '未命名小说';
  const assetsReady = Boolean(snapshot.production_bible_summary?.asset_readiness?.ready);

  const openEpisode = async (episode: EpisodeOption) => {
    if (episode.workflowId) { onWorkflowChange(episode.workflowId); return; }
    if (!novelId || !episode.chapterId) return;
    setCreatingEpisodeId(episode.id); setEpisodeError('');
    try {
      const result = await apiClient.startWorkflow({ title: `${novelTitle} · ${episode.title}`, novel_id: novelId, chapter_id: episode.chapterId });
      onWorkflowChange(result.workflow_id);
    } catch (err: any) {
      setEpisodeError(err?.message || '创建本集工程失败，请检查后重试');
    } finally { setCreatingEpisodeId(''); }
  };

  return (
    <div className="space-y-3">
      <Card className="overflow-hidden border-white/10 bg-white/[0.045]" data-testid="studio-series-summary">
        <CardContent className="grid gap-4 p-4 md:grid-cols-[190px_minmax(0,1fr)_190px] md:items-center">
          {novel.cover_url ? (
            <img src={toMediaUrl(novel.cover_url)} alt={`${novelTitle} 系列封面`} className="h-24 w-[190px] rounded-lg border border-white/10 object-cover" />
          ) : (
            <div className="flex h-24 w-[190px] flex-col items-center justify-center rounded-lg border border-dashed border-white/15 bg-black/20 text-center text-[11px] text-white/40">
              <BookOpen aria-hidden className="mb-1 h-5 w-5" />尚未设置系列封面
            </div>
          )}
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2"><h2 className="truncate text-xl font-semibold tracking-tight text-white">小说《{novelTitle}》</h2><Badge variant="outline" className="border-violet-300/25 text-violet-100">多季连载</Badge></div>
            <div className="mt-4 grid gap-3 text-xs text-white/50 sm:grid-cols-[minmax(140px,1fr)_auto_auto_auto] sm:items-end">
              <div><div>整体进度</div><div className="mt-2 flex items-center gap-2"><div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/10"><div className="h-full bg-violet-500" style={{ width: `${progress}%` }} /></div><span className="text-white/75">{progress}%</span></div></div>
              <div><span className="block">已完成</span><strong className="mt-1 block text-sm text-white"> {completed} 集</strong></div>
              <div><span className="block">总集数</span><strong className="mt-1 block text-sm text-white"> {total} 集</strong></div>
              <div><span className="block">更新时间</span><strong className="mt-1 block text-sm text-white">{formatDate(novel.updated_at || snapshot.workflow?.updated_at)}</strong></div>
            </div>
          </div>
          <Button type="button" variant="ghost" className="h-auto justify-between border-l border-white/10 px-4 py-3 text-left text-white" onClick={() => onOpenExpert('/studio/cards')}>
            <span><span className="block text-xs text-white/45">系列设定与资产</span><span className={`mt-1 flex items-center gap-1.5 text-sm ${assetsReady ? 'text-emerald-300' : 'text-amber-200'}`}><CheckCircle2 className="h-4 w-4" />{assetsReady ? '已就绪' : '待补齐'}</span></span><ChevronDown className="h-4 w-4 -rotate-90" />
          </Button>
        </CardContent>
      </Card>

      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <div className="contents" aria-label="剧集工程">
          {chapters === null ? <div className="flex min-h-[76px] items-center rounded-lg border border-white/10 bg-white/[0.025] px-3 text-sm text-white/45">正在加载剧集…</div> : null}
          {episodes.map((episode) => <button key={episode.chapterId || episode.id} data-testid={`studio-episode-${episode.chapterId}`} type="button" aria-current={episode.workflowId === workflowId ? 'page' : undefined} disabled={loading || Boolean(creatingEpisodeId)} onClick={() => void openEpisode(episode)} className={`min-w-0 rounded-lg border px-3 py-2.5 text-left transition-colors ${episode.workflowId === workflowId ? 'border-violet-400 bg-violet-500/15 text-white' : episode.workflowId ? 'border-white/10 bg-white/[0.035] text-white/65 hover:border-white/20' : 'border-amber-300/20 bg-amber-500/[0.06] text-amber-50 hover:border-amber-300/40'}`}><div className="text-xs font-medium">{episode.label}</div><div className="mt-1 truncate text-sm">{episode.title}</div><div className="mt-1.5 text-[11px] text-white/45">{creatingEpisodeId === episode.id ? '正在创建工程…' : episode.progress}</div></button>)}
        </div>
        <Button type="button" variant="outline" className="h-auto min-h-[76px] border-white/15 text-white/70" onClick={() => onOpenExpert(`/quick-start?novel_id=${novelId}`)}><Plus className="mr-1 h-4 w-4" />新建集数</Button>
        <DropdownMenu modal={false}><DropdownMenuTrigger asChild><Button type="button" variant="outline" className="h-auto min-h-[76px] border-white/15 text-white"><Settings2 className="mr-1 h-4 w-4" />系列管理</Button></DropdownMenuTrigger><DropdownMenuContent align="end" className="w-52 border-white/10 bg-slate-950 text-white">{expertLinks.map((link) => <DropdownMenuItem key={link.href} onSelect={() => onOpenExpert(link.href)} className="text-white/75 focus:bg-white/10 focus:text-white">{link.label}</DropdownMenuItem>)}</DropdownMenuContent></DropdownMenu>
      </div>
      {episodeError ? <div role="alert" className="rounded-lg border border-red-300/25 bg-red-500/10 px-3 py-2 text-sm text-red-100">{episodeError}</div> : null}
    </div>
  );
}

'use client';

import { Library, Map } from 'lucide-react';
import { useState } from 'react';

import { usePromptUsageMap } from '../hooks/use-prompt-usage-map';
import type { ModelCenterLocation } from '../navigation';
import { ModelCenterError, ModelCenterLoading } from './model-center-state';
import { PromptProfileList } from './prompt-profile-list';
import { PromptUsageAssignmentDialog } from './prompt-usage-assignment-dialog';
import { PromptUsageDetail } from './prompt-usage-detail';
import { PromptUsageStageList } from './prompt-usage-stage-list';
import { PromptUsageSummary } from './prompt-usage-summary';

export function PromptUsageMap({ location }: { location: ModelCenterLocation }) {
  const query = usePromptUsageMap();
  const [view, setView] = useState<'map' | 'library'>('map');
  const [initialProfileId, setInitialProfileId] = useState<string | null>(null);
  const [assigningStageId, setAssigningStageId] = useState<string | null>(null);
  if (view === 'library') return <div><div className="flex justify-end border-b border-white/10 p-3"><button type="button" onClick={() => setView('map')} className="model-center-quiet"><Map className="h-4 w-4" />返回使用地图</button></div><PromptProfileList location={location} initialSelectedId={initialProfileId} onPublished={initialProfileId ? () => { setView('map'); void query.refresh(); } : undefined} /></div>;
  if (query.loading && !query.data) return <ModelCenterLoading label="正在核对各生产环节实际使用的提示词…" />;
  if (query.error && !query.data) return <ModelCenterError error={query.error} onRetry={() => void query.refresh()} />;
  if (!query.data || !query.selectedStage) return null;
  const openLibrary = (profileId?: string) => {
    setInitialProfileId(profileId || null);
    setView('library');
  };
  return <div>
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-4 py-3">
      <p className="text-xs text-slate-400">按真实默认模型和生产路由展示；不是手工维护的说明表。</p>
      <button type="button" onClick={() => openLibrary()} className="model-center-quiet"><Library className="h-4 w-4" />模板库</button>
    </div>
    <PromptUsageSummary summary={query.data.summary} problemsOnly={query.problemsOnly} onToggleProblems={query.toggleProblemsOnly} />
    <p className="border-b border-white/10 px-4 py-2 text-xs text-slate-500">字幕、成片合成：此环节不使用提示词模板。</p>
    <div className="grid min-h-[620px] lg:grid-cols-[20rem_minmax(0,1fr)]">
      <PromptUsageStageList groups={query.visibleGroups} selectedStageId={query.selectedStageId} onSelect={query.selectStage} />
      <PromptUsageDetail stage={query.selectedStage} onOpenLibrary={openLibrary} onChangeTemplate={() => setAssigningStageId(query.selectedStage?.id || null)} />
    </div>
    {assigningStageId && <PromptUsageAssignmentDialog stage={query.data.groups.flatMap((group) => group.stages).find((stage) => stage.id === assigningStageId) || query.selectedStage} onClose={() => setAssigningStageId(null)} onCreated={(result) => { setAssigningStageId(null); openLibrary(result.profile_id); }} />}
  </div>;
}

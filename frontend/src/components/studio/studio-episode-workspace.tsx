'use client';

import type {
  StudioActionResult,
  StudioGuidedAction,
  StudioRunMode,
  StudioSnapshot,
  StudioWorkflowOption,
} from '@/lib/studio-types';
import { StudioActionProgress } from './studio-action-progress';
import { StudioCommandBar } from './studio-command-bar';
import { StudioEpisodeSidebar } from './studio-episode-sidebar';
import { StudioEpisodeStageBoard } from './studio-episode-stage-board';
import { StudioStageFlow } from './studio-stage-flow';
import { StudioWorkspaceHeader } from './studio-workspace-header';

export function StudioEpisodeWorkspace({
  snapshot,
  workflows,
  workflowId,
  expertLinks,
  mode,
  loading,
  lastAction,
  retryMessage,
  onModeChange,
  onWorkflowChange,
  onOpenExpert,
  onPrimaryAction,
}: {
  snapshot: StudioSnapshot;
  workflows: StudioWorkflowOption[];
  workflowId: string;
  expertLinks: Array<{ href: string; label: string }>;
  mode: StudioRunMode;
  loading?: boolean;
  lastAction: StudioActionResult | null;
  retryMessage?: string;
  onModeChange: (mode: StudioRunMode) => void;
  onWorkflowChange: (workflowId: string) => void;
  onOpenExpert: (href: string) => void;
  onPrimaryAction: (action: StudioGuidedAction) => void;
}) {
  return (
    <section className="space-y-4" data-testid="studio-episode-workspace">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_230px]">
        <div className="min-w-0 space-y-4">
          <StudioWorkspaceHeader
            snapshot={snapshot}
            workflows={workflows}
            workflowId={workflowId}
            loading={loading}
            expertLinks={expertLinks}
            onWorkflowChange={onWorkflowChange}
            onOpenExpert={onOpenExpert}
          />
          <StudioEpisodeStageBoard snapshot={snapshot} />
        </div>
        <StudioEpisodeSidebar snapshot={snapshot} />
      </div>
      <StudioCommandBar snapshot={snapshot} mode={mode} loading={loading} onModeChange={onModeChange} onPrimaryAction={onPrimaryAction} />
      <StudioActionProgress
        action={lastAction}
        loading={loading}
        retryMessage={retryMessage}
        resume={snapshot.guidance?.orchestration_resume}
      />
      <StudioStageFlow snapshot={snapshot} />
    </section>
  );
}

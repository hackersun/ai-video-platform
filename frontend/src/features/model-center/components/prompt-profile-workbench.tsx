'use client';

import { useCallback, useState } from 'react';

import { usePromptProfileDetail } from '../hooks/use-prompt-profile-detail';
import type { PromptProfileVersionInput, PromptProfileView } from '../types';
import { ModelCenterError, ModelCenterLoading } from './model-center-state';
import { PromptAssistantPanel } from './prompt-assistant-panel';
import { PromptLegacyActions } from './prompt-legacy-actions';
import { PromptProfileDiff } from './prompt-profile-diff';
import { PromptProfileEditor } from './prompt-profile-editor';
import { PromptProfileHistory } from './prompt-profile-history';

export function PromptProfileWorkbench({
  profile,
  onSaveVersion,
  onPublish,
  onRollback,
  onLegacyChanged,
}: {
  profile: PromptProfileView;
  onSaveVersion: (input: PromptProfileVersionInput) => Promise<void>;
  onPublish: (versionId: string, revision: number) => void;
  onRollback: (versionId: string, revision: number) => void;
  onLegacyChanged: () => Promise<void>;
}) {
  const query = usePromptProfileDetail(profile.id);
  const [taskTemplate, setTaskTemplate] = useState('');
  const [appliedTemplate, setAppliedTemplate] = useState<string | null>(null);
  const handleTemplateChange = useCallback((value: string) => setTaskTemplate(value), []);
  if (query.loading && !query.data) return <ModelCenterLoading label="正在读取提示词正文与版本历史…" />;
  if (query.error && !query.data) return <ModelCenterError error={query.error} onRetry={() => void query.reload()} />;
  if (!query.data) return null;
  const detail = query.data;
  return <div className="space-y-4"><PromptProfileEditor profile={profile} detail={detail} appliedTaskTemplate={appliedTemplate} onTaskTemplateChange={handleTemplateChange} onSaveVersion={async (input) => { await onSaveVersion(input); await query.reload(); }} onPublish={onPublish} onRollback={onRollback} /><div className="grid gap-4 2xl:grid-cols-2"><PromptAssistantPanel profileId={profile.id} task={detail.task} version={detail.head} taskTemplate={taskTemplate || detail.head.task_template} onApply={setAppliedTemplate} /><PromptProfileHistory versions={detail.versions} /></div><PromptLegacyActions detail={detail} onChanged={async () => { await onLegacyChanged(); await query.reload(); }} /><PromptProfileDiff detail={detail} /></div>;
}

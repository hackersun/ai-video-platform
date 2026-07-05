import type { StudioSnapshot } from './studio-types';

export function studioContextParams(
  snapshot: StudioSnapshot | null,
  extra: Record<string, string | undefined | null> = {}
) {
  const params = new URLSearchParams();
  const workflowId = snapshot?.workflow?.id || snapshot?.guidance?.breadcrumbs?.workflow_id || '';
  const novelId =
    snapshot?.workflow?.novel_id ||
    snapshot?.story_context?.novel?.id ||
    snapshot?.guidance?.breadcrumbs?.novel_id ||
    '';
  const chapterId =
    snapshot?.workflow?.chapter_id ||
    snapshot?.story_context?.chapter?.id ||
    snapshot?.guidance?.breadcrumbs?.chapter_id ||
    '';

  if (workflowId) params.set('workflow_id', workflowId);
  if (novelId) params.set('novel_id', novelId);
  if (chapterId) params.set('chapter_id', chapterId);

  Object.entries(extra).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });

  return params;
}

export function withStudioContext(
  path: string,
  snapshot: StudioSnapshot | null,
  extra: Record<string, string | undefined | null> = {}
) {
  const params = studioContextParams(snapshot, extra);
  const qs = params.toString();
  if (!qs) return path;
  return `${path}${path.includes('?') ? '&' : '?'}${qs}`;
}

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
  const scriptId = snapshot?.workflow?.script_id || snapshot?.story_context?.script?.id || '';
  const storyboardId = snapshot?.workflow?.storyboard_id || snapshot?.story_context?.storyboard?.id || '';

  if (workflowId) params.set('workflow_id', workflowId);
  if (novelId) params.set('novel_id', novelId);
  if (chapterId) params.set('chapter_id', chapterId);
  if (scriptId) params.set('script_id', scriptId);
  if (storyboardId) params.set('storyboard_id', storyboardId);

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
  const hashIndex = path.indexOf('#');
  const pathWithoutHash = hashIndex >= 0 ? path.slice(0, hashIndex) : path;
  const hash = hashIndex >= 0 ? path.slice(hashIndex) : '';
  const queryIndex = pathWithoutHash.indexOf('?');
  const basePath = queryIndex >= 0 ? pathWithoutHash.slice(0, queryIndex) : pathWithoutHash;
  const existingQuery = queryIndex >= 0 ? pathWithoutHash.slice(queryIndex + 1) : '';
  const params = new URLSearchParams(existingQuery);

  studioContextParams(snapshot).forEach((value, key) => {
    if (!params.has(key)) params.set(key, value);
  });
  Object.entries(extra).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });

  const qs = params.toString();
  return `${basePath}${qs ? `?${qs}` : ''}${hash}`;
}

export function withStudioQuickAction(
  path: string,
  snapshot: StudioSnapshot | null,
  extra: Record<string, string | undefined | null> = {}
) {
  const returnTo = withStudioContext('/studio', snapshot);
  return withStudioContext(path, snapshot, { source: 'studio', return_to: returnTo, ...extra });
}

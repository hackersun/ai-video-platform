export function subtitleQueryContext(search: string) {
  const params = new URLSearchParams(search);
  return {
    workflow_id: params.get('workflow_id') || undefined,
    novel_id: params.get('novel_id') || undefined,
    chapter_id: params.get('chapter_id') || undefined,
    storyboard_id: params.get('storyboard_id') || undefined,
    include_segments: true,
  };
}

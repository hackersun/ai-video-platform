export function stableChapterSnapshot(chapters, expectedTitles) {
  if (!Array.isArray(chapters) || chapters.length !== expectedTitles.length) return null;
  const byTitle = new Map(chapters.map((chapter) => [chapter?.title, chapter]));
  const ordered = expectedTitles.map((title) => byTitle.get(title));
  if (ordered.some((chapter) => !chapter?.id)) return null;
  const ids = ordered.map((chapter) => String(chapter.id));
  if (new Set(ids).size !== ids.length) return null;
  return ordered.map((chapter) => ({ id: String(chapter.id), title: String(chapter.title) }));
}

export function isRecoverableReadonlyPreflight(status, body) {
  if (Number(status) !== 500) return false;
  const text = JSON.stringify(body || {});
  return text.includes('StaleDataError') || text.includes('expected to update 1 row(s); 0 were matched');
}

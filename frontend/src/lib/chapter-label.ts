export type ChapterLabelInput = {
  title?: string | null;
  chapter_number?: number | null;
};

export function formatChapterLabel(chapter?: ChapterLabelInput | null) {
  if (!chapter) return '未绑定章节';
  const title = (chapter.title || '').trim();
  let remaining = title;
  let explicitNumber = '';
  const chapterPrefixPattern = /^\s*第\s*([一二三四五六七八九十百千万两\d\s]+?)\s*[章节卷集回]\s*[：:、.\s-]*/;
  while (remaining) {
    const match = remaining.match(chapterPrefixPattern);
    if (!match) break;
    explicitNumber = match[1].replace(/\s+/g, '');
    remaining = remaining.slice(match[0].length).trim();
  }
  if (explicitNumber) {
    return `第${explicitNumber}章${remaining ? ` ${remaining}` : ''}`;
  }
  return chapter.chapter_number ? `第${chapter.chapter_number}章${title ? ` ${title}` : ''}` : title || '未命名章节';
}

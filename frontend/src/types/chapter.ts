/**
 * 章节类型定义
 */

// 章节状态
export type ChapterStatus = 'draft' | 'published' | 'archived';

// 章节内容类型
export type ContentType = 'plain' | 'rich' | 'markdown';

// 章节基本信息
export interface Chapter {
  id: string;
  novel_id: string;
  title: string;
  content: string;
  chapter_number: number;
  status: ChapterStatus;
  word_count: number;
  content_type: ContentType;
  created_at: string;
  updated_at: string;
  published_at?: string;
  // 扩展字段
  summary?: string;
  tags?: string[];
  parent_id?: string; // 用于分卷/章节嵌套
  children?: Chapter[]; // 子章节
}

// 创建章节输入
export interface CreateChapterInput {
  title: string;
  content?: string;
  chapter_number?: number;
  status?: ChapterStatus;
  content_type?: ContentType;
  summary?: string;
  tags?: string[];
  parent_id?: string;
}

// 更新章节输入
export interface UpdateChapterInput {
  title?: string;
  content?: string;
  chapter_number?: number;
  status?: ChapterStatus;
  content_type?: ContentType;
  summary?: string;
  tags?: string[];
}

// 章节排序输入
export interface ReorderChaptersInput {
  chapter_ids: string[]; // 按顺序排列的章节ID数组
}

// 自动保存草稿输入
export interface SaveDraftInput {
  novel_id: string;
  chapter_id?: string; // 现有章节ID，空表示新建
  title?: string;
  content: string;
  auto_save_key?: string; // 用于标识同一章节的多次草稿
}

// 导出配置
export interface ExportOptions {
  format: 'txt' | 'markdown' | 'html' | 'pdf' | 'epub';
  include_metadata?: boolean;
  include_chapter_titles?: boolean;
  start_chapter?: number;
  end_chapter?: number;
}

// 导出响应
export interface ExportResponse {
  download_url: string;
  file_name: string;
  file_size: number;
  expires_at: string;
}

// 章节列表响应
export interface ChapterListResponse {
  items: Chapter[];
  total: number;
  page: number;
  limit: number;
}

// 章节筛选参数
export interface ChapterFilters {
  status?: ChapterStatus;
  content_type?: ContentType;
  page?: number;
  limit?: number;
  search?: string; // 标题搜索
}

// 批量操作
export interface BatchChapterOperation {
  chapter_ids: string[];
  operation: 'delete' | 'publish' | 'unpublish' | 'archive';
}

// 章节统计
export interface ChapterStats {
  total_chapters: number;
  published_chapters: number;
  draft_chapters: number;
  total_words: number;
  average_words_per_chapter: number;
}
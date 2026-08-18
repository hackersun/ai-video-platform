import { withStudioQuickAction } from './studio-context-links';
import type { StudioIssue, StudioSnapshot } from './studio-types';

export type StudioRepairOption = {
  key: string;
  title: string;
  description: string;
  buttonLabel: string;
  href: string;
};

const repairCopy: Record<string, Omit<StudioRepairOption, 'key' | 'href'>> = {
  select_novel: {
    title: '当前本集没有关联小说',
    description: '先选择小说，后续章节、分镜和设定才能对应到同一部作品。',
    buttonLabel: '去关联小说',
  },
  select_chapter: {
    title: '当前本集没有关联章节',
    description: '先选择本集使用的章节，避免剧本和分镜串到其他内容。',
    buttonLabel: '去关联章节',
  },
  select_storyboard: {
    title: '当前本集没有关联分镜',
    description: '先关联或创建本集分镜，工作室才能检查镜头。',
    buttonLabel: '补齐工作流分镜',
  },
  missing_story_bible: {
    title: '当前小说缺少统一设定',
    description: '为当前小说建立角色、场景、道具和事件设定。',
    buttonLabel: '为当前小说生成设定',
  },
  missing_shots: {
    title: '当前分镜还没有镜头',
    description: '分镜建立后生成镜头，才能继续视频和合成。',
    buttonLabel: '生成分镜镜头',
  },
};

function targetForIssue(issue: StudioIssue) {
  if (issue.code === 'missing_story_bible') {
    return { path: '/story-bibles?action=create', focus: 'story-bible' };
  }
  if (issue.code === 'select_storyboard' || issue.code === 'missing_shots') {
    return { path: '/storyboards', focus: 'storyboard' };
  }
  if (issue.code === 'select_novel' || issue.code === 'select_chapter') {
    return { path: '/workflow', focus: 'episode-setup' };
  }
  return { path: issue.repair_action?.href || '/jobs', focus: 'jobs' };
}

export function buildStudioRepairOption(issue: StudioIssue, snapshot: StudioSnapshot): StudioRepairOption {
  const copy = repairCopy[issue.code || ''] || {
    title: issue.message || '当前有一项需要人工处理',
    description: '打开对应页面，根据页面提示补齐后返回工作室刷新。',
    buttonLabel: issue.repair_action?.label || '打开处理页面',
  };
  const target = targetForIssue(issue);
  return {
    key: issue.code || issue.message || target.path,
    ...copy,
    href: withStudioQuickAction(target.path, snapshot, {
      focus: target.focus,
      source_issue_code: issue.code,
    }),
  };
}

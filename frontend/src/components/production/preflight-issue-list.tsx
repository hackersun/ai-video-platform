'use client';

import { AlertCircle, CheckCircle2, ExternalLink, Info } from 'lucide-react';

type PreflightIssue = {
  code?: string;
  message?: string;
  severity?: string;
  field?: string;
};

type PreflightFixTarget = {
  label: string;
  href: string;
  action: string;
  hint: string;
};

const FIX_TARGET_BY_CODE: Record<string, PreflightFixTarget> = {
  reference_image_not_public: {
    label: '生产适配',
    href: '/production-adapters',
    action: '去处理',
    hint: '配置公网对象存储/CDN，或在资产库重新生成公网参考图。',
  },
  model_unverified: {
    label: 'AI模型配置',
    href: '/llm-config',
    action: '去验证模型',
    hint: '测试通过当前模型配置，并按能力类型设为默认或重新选择已验证模型。',
  },
  model_config_missing: {
    label: 'AI模型配置',
    href: '/llm-config',
    action: '去配置模型',
    hint: '补齐对应的视频、图像或声音模型配置后再生成。',
  },
  model_api_key_missing: {
    label: 'AI模型配置',
    href: '/llm-config',
    action: '去补齐密钥',
    hint: '重新保存 API Key 并完成模型测试。',
  },
  external_config_missing: {
    label: '生产适配',
    href: '/production-adapters',
    action: '去配置',
    hint: '补齐云渲染、对象存储或第三方生产服务配置。',
  },
  external_config_unverified: {
    label: '生产适配',
    href: '/production-adapters',
    action: '去验证',
    hint: '先测试通过外部生产服务配置，再提交生成。',
  },
  missing_asset_locks: {
    label: '资产库',
    href: '/assets',
    action: '去锁定资产',
    hint: '补齐并锁定角色、场景、道具的定稿参考图，避免跨镜头漂移。',
  },
  missing_entity_refs: {
    label: '实体库',
    href: '/entities',
    action: '去补齐实体',
    hint: '为镜头补齐人物、场景、道具或事件引用。',
  },
  lineage_mismatch: {
    label: '制作链路',
    href: '/workflow',
    action: '去重新选择',
    hint: '重新选择同一小说、章节、剧本、分镜和镜头，保持链路一致。',
  },
  shot_missing: {
    label: '镜头管理',
    href: '/shots',
    action: '去选择镜头',
    hint: '确认镜头存在且属于当前作品链路。',
  },
  storyboard_missing: {
    label: '分镜管理',
    href: '/storyboards',
    action: '去选择分镜',
    hint: '确认分镜存在且与当前镜头、剧本一致。',
  },
  script_missing: {
    label: '剧本管理',
    href: '/scripts',
    action: '去选择剧本',
    hint: '确认剧本存在且属于当前小说章节。',
  },
  chapter_missing: {
    label: '小说章节',
    href: '/novels',
    action: '去选择章节',
    hint: '确认章节存在且属于当前小说。',
  },
  novel_missing: {
    label: '小说管理',
    href: '/novels',
    action: '去选择小说',
    hint: '确认小说存在且当前账号有权限访问。',
  },
  missing_story_bible: {
    label: '故事设定',
    href: '/story-bibles',
    action: '去同步设定',
    hint: '先同步人物、场景、道具和世界观设定，再进入生成。',
  },
  story_bible_missing: {
    label: '故事设定',
    href: '/story-bibles',
    action: '去同步设定',
    hint: '先同步人物、场景、道具和世界观设定，再进入生成。',
  },
};

const FIX_TARGET_BY_FIELD: Record<string, PreflightFixTarget> = {
  image_url: FIX_TARGET_BY_CODE.reference_image_not_public,
  model_config_id: FIX_TARGET_BY_CODE.model_unverified,
  external_config_id: FIX_TARGET_BY_CODE.external_config_unverified,
  shot_id: FIX_TARGET_BY_CODE.shot_missing,
  storyboard_id: FIX_TARGET_BY_CODE.storyboard_missing,
  script_id: FIX_TARGET_BY_CODE.script_missing,
  chapter_id: FIX_TARGET_BY_CODE.chapter_missing,
  novel_id: FIX_TARGET_BY_CODE.novel_missing,
};

function getPreflightFixTarget(issue: PreflightIssue): PreflightFixTarget | null {
  const code = issue.code || '';
  const field = issue.field || '';

  if (code && FIX_TARGET_BY_CODE[code]) return FIX_TARGET_BY_CODE[code];
  if (field && FIX_TARGET_BY_FIELD[field]) return FIX_TARGET_BY_FIELD[field];
  if (code.startsWith('model_')) return FIX_TARGET_BY_CODE.model_unverified;
  if (code.startsWith('external_')) return FIX_TARGET_BY_CODE.external_config_unverified;
  if (code.includes('asset')) return FIX_TARGET_BY_CODE.missing_asset_locks;
  if (code.includes('entity')) return FIX_TARGET_BY_CODE.missing_entity_refs;
  if (code.includes('story_bible')) return FIX_TARGET_BY_CODE.story_bible_missing;
  return null;
}

interface PreflightIssueListProps {
  issues?: PreflightIssue[];
  emptyText?: string;
}

export function PreflightIssueList({ issues = [], emptyText = '暂无阻断问题' }: PreflightIssueListProps) {
  if (!issues.length) {
    return (
      <div className="flex items-center gap-2 rounded border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100">
        <CheckCircle2 className="h-4 w-4" />
        {emptyText}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {issues.map((issue, index) => {
        const blocking = issue.severity !== 'warning';
        const Icon = blocking ? AlertCircle : Info;
        const fixTarget = getPreflightFixTarget(issue);
        return (
          <div
            key={`${issue.code || 'issue'}-${index}`}
            className={`rounded border px-3 py-2 text-sm leading-5 ${
              blocking
                ? 'border-red-500/25 bg-red-500/10 text-red-50'
                : 'border-amber-500/25 bg-amber-500/10 text-amber-50'
            }`}
          >
            <div className="flex items-start gap-2">
              <Icon className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <div className="min-w-0 flex-1">
                <div>{issue.message || issue.code || '预检问题'}</div>
                {fixTarget && (
                  <div className="mt-2 rounded border border-white/10 bg-black/15 px-3 py-2 text-xs text-white/80">
                    <div className="font-medium text-white">处理位置：{fixTarget.label}</div>
                    <div className="mt-1">{fixTarget.hint}</div>
                    <a
                      href={fixTarget.href}
                      className="mt-2 inline-flex items-center gap-1 rounded border border-white/15 px-2 py-1 text-white hover:bg-white/10"
                    >
                      {fixTarget.action}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  </div>
                )}
                {(issue.field || issue.code) && (
                  <div className="mt-1 text-xs opacity-65">
                    {issue.field ? `字段：${issue.field}` : null}
                    {issue.field && issue.code ? ' · ' : null}
                    {issue.code ? `规则：${issue.code}` : null}
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

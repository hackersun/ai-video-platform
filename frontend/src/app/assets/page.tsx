'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Archive,
  Boxes,
  Edit3,
  Eye,
  ExternalLink,
  FileUp,
  Image as ImageIcon,
  Loader2,
  Lock,
  Unlock,
  Music,
  Plus,
  RefreshCw,
  Save,
  Search,
  Shield,
  Trash2,
  Video,
  Volume2,
  X,
  History,
  Palette,
  PanelsTopLeft,
  Smile,
  Sparkles,
  PersonStanding,
} from 'lucide-react';
import { MainLayout } from '@/components/layout/main-layout';
import {
  DEFAULT_IMAGE_STYLE_TEMPLATES,
  ImageStyleTemplatePicker,
  type ImageStyleTemplate,
} from '@/components/media/image-style-template-picker';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { apiClient } from '@/lib/api-client';
import { formatChapterLabel } from '@/lib/chapter-label';

type AssetCategory = {
  id: string;
  name: string;
  name_cn?: string;
  asset_count?: number;
};

type Project = {
  id: string;
  name: string;
};

type Novel = {
  id: string;
  title: string;
};

type Chapter = {
  id: string;
  title: string;
  chapter_number?: number;
};

type ScriptItem = {
  id: string;
  title: string;
};

type StoryEntity = {
  id: string;
  name: string;
  entity_type: string;
  description?: string;
  appearance?: string;
  visual_prompt?: string;
};

type Asset = {
  id: string;
  category: string;
  name: string;
  description?: string;
  asset_type?: string;
  url?: string;
  thumbnail_url?: string;
  source_url?: string;
  project_id?: string;
  novel_id?: string;
  chapter_id?: string;
  script_id?: string;
  entity_id?: string;
  entity_type?: string;
  tags?: string[];
  style_tags?: string[];
  prompt_template?: string;
  source_prompt?: string;
  variables?: any[];
  shot_template?: any;
  generation_params?: Record<string, any>;
  is_public?: boolean;
  likes?: number;
  usage_count?: number;
  version?: number;
  is_locked?: boolean;
  is_final?: boolean;
  status?: string;
  error_message?: string;
  visual_consistency?: { score?: number } | number;
  created_at?: string;
};

type PreviewMedia = {
  title: string;
  assetType: string;
  url: string;
  thumbnailUrl?: string;
  description?: string;
};

type AssetViewPreset = {
  entity_type: string;
  category: string;
  title: string;
  description?: string;
  views: {
    key: string;
    label: string;
    aspect_ratio?: string;
    prompt_hint?: string;
  }[];
  recommended_aspect_ratios?: string[];
  style_examples?: {
    style: string;
    label: string;
    aspect_ratio?: string;
    sample_url?: string;
    prompt?: string;
  }[];
};

const FALLBACK_CATEGORIES: AssetCategory[] = [
  { id: 'character', name: 'character', name_cn: '角色' },
  { id: 'scene', name: 'scene', name_cn: '场景' },
  { id: 'prop', name: 'prop', name_cn: '道具' },
  { id: 'costume', name: 'costume', name_cn: '服装' },
  { id: 'pose', name: 'pose', name_cn: '姿势' },
  { id: 'expression', name: 'expression', name_cn: '表情' },
  { id: 'style', name: 'style', name_cn: '风格' },
  { id: 'aspect_ratio', name: 'aspect_ratio', name_cn: '画面比例' },
  { id: 'effect', name: 'effect', name_cn: '特效' },
  { id: 'voice', name: 'voice', name_cn: '音色' },
  { id: 'music', name: 'music', name_cn: '音乐' },
  { id: 'sfx', name: 'sfx', name_cn: '音效' },
  { id: 'template', name: 'template', name_cn: '模板' },
  { id: 'prompt', name: 'prompt', name_cn: '提示词' },
];

const ASSET_TYPE_OPTIONS = [
  { value: 'image', label: '图片 / 参考图' },
  { value: 'video', label: '视频 / 关键帧' },
  { value: 'audio', label: '音频 / 配音素材' },
  { value: 'text', label: '文本 / 提示词' },
  { value: 'lora', label: '角色模型 / LoRA' },
  { value: 'ipadapter', label: '参考适配 / IP-Adapter' },
];

const ASSET_TYPE_LABELS = ASSET_TYPE_OPTIONS.reduce<Record<string, string>>((acc, option) => {
  acc[option.value] = option.label;
  return acc;
}, {});

const QUICK_PRESET_FILTERS = [
  { label: '角色三视图', category: 'character' },
  { label: '场景四视图', category: 'scene' },
  { label: '道具多视图', category: 'prop' },
  { label: '风格图', category: 'style' },
  { label: '画面比例', category: 'aspect_ratio' },
];

const ENTITY_TYPE_LABELS: Record<string, string> = {
  character: '角色',
  scene: '场景',
  prop: '道具',
  event: '事件',
  environment: '环境',
};

const FALLBACK_VIEW_PRESETS: AssetViewPreset[] = [
  {
    entity_type: 'character',
    category: 'character',
    title: '角色三视图',
    description: '锁定角色正面、侧面、背面外观，供后续镜头保持人物一致。',
    recommended_aspect_ratios: ['9:16', '3:4', '1:1'],
    style_examples: [
      {
        style: 'xianxia',
        label: '修仙仙侠',
        aspect_ratio: '9:16',
        sample_url: '/static/starter/character-xianxia.png',
        prompt: '少年剑修，黑衣银发带，古剑背负，东方修仙动漫风，三视图设定稿。',
      },
      {
        style: 'urban',
        label: '现代都市',
        aspect_ratio: '3:4',
        sample_url: '/static/starter/character-urban.png',
        prompt: '都市女主，干练外套，清晰五官与发型，现代动漫角色设定。',
      },
    ],
    views: [
      { key: 'front', label: '正面', aspect_ratio: '9:16', prompt_hint: '完整头身、发型、五官、服装和主要配饰清晰。' },
      { key: 'side', label: '侧面', aspect_ratio: '9:16', prompt_hint: '展示轮廓、发型、服装结构和配饰位置。' },
      { key: 'back', label: '背面', aspect_ratio: '9:16', prompt_hint: '展示背部服装、发型、武器或披风细节。' },
    ],
  },
  {
    entity_type: 'scene',
    category: 'scene',
    title: '场景四视图',
    description: '固定场景全景、空间布局、关键细节和光影氛围。',
    recommended_aspect_ratios: ['16:9', '21:9', '9:16'],
    style_examples: [
      {
        style: 'wuxia',
        label: '武侠江湖',
        aspect_ratio: '16:9',
        sample_url: '/static/starter/scene-wuxia.png',
        prompt: '山间客栈，青石路、竹林、薄雾，武侠动漫场景，全景定场。',
      },
      {
        style: 'fantasy',
        label: '东方玄幻',
        aspect_ratio: '21:9',
        sample_url: '/static/starter/scene-fantasy.png',
        prompt: '玄幻古城，悬浮灵石、宫阙与云海，宏大空间设定图。',
      },
    ],
    views: [
      { key: 'establishing', label: '全景定场', aspect_ratio: '16:9' },
      { key: 'layout', label: '空间布局', aspect_ratio: '16:9' },
      { key: 'detail', label: '关键细节', aspect_ratio: '16:9' },
      { key: 'lighting', label: '光影氛围', aspect_ratio: '16:9' },
    ],
  },
  {
    entity_type: 'prop',
    category: 'prop',
    title: '道具多视图',
    description: '固定道具主视图、细节、比例和使用状态。',
    recommended_aspect_ratios: ['1:1', '4:3', '16:9'],
    style_examples: [
      {
        style: 'xianxia',
        label: '修仙法器',
        aspect_ratio: '1:1',
        sample_url: '/static/starter/prop-xianxia.png',
        prompt: '古剑法器，青铜纹理、灵光符文，主视图与细节参考，动漫设定稿。',
      },
      {
        style: 'urban',
        label: '都市物件',
        aspect_ratio: '1:1',
        sample_url: '/static/starter/prop-urban.png',
        prompt: '关键手机道具，屏幕裂纹和挂饰清晰，现代动画道具设定。',
      },
    ],
    views: [
      { key: 'main', label: '主视图', aspect_ratio: '1:1' },
      { key: 'detail', label: '细节纹理', aspect_ratio: '1:1' },
      { key: 'scale', label: '比例参考', aspect_ratio: '1:1' },
      { key: 'in_use', label: '使用状态', aspect_ratio: '1:1' },
    ],
  },
];

const FALLBACK_STYLE_TEMPLATES: ImageStyleTemplate[] = DEFAULT_IMAGE_STYLE_TEMPLATES;

const typeIcon = (assetType?: string) => {
  if (assetType === 'video') return Video;
  if (assetType === 'audio') return Volume2;
  if (assetType === 'music') return Music;
  return ImageIcon;
};

const categoryIcon = (category?: string, assetType?: string) => {
  if (category === 'style') return Palette;
  if (category === 'aspect_ratio') return PanelsTopLeft;
  if (category === 'expression') return Smile;
  if (category === 'pose') return PersonStanding;
  if (category === 'effect') return Sparkles;
  return typeIcon(assetType);
};

const splitTags = (value: string) => value.split(/[，,]/).map((item) => item.trim()).filter(Boolean);

const isImageLikeUrl = (url?: string) => Boolean(url && /\.(png|jpe?g|webp|gif|svg)(\?.*)?$/i.test(url));

function AssetImagePreview({
  src,
  fallbackSrc,
  alt,
  className,
}: {
  src?: string;
  fallbackSrc?: string;
  alt: string;
  className?: string;
}) {
  const [useFallback, setUseFallback] = useState(false);
  const imageSrc = useFallback && fallbackSrc ? fallbackSrc : src;

  useEffect(() => {
    setUseFallback(false);
  }, [src, fallbackSrc]);

  if (!imageSrc) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-black/20 text-xs text-white/35">
        暂无预览图
      </div>
    );
  }

  return (
    <img
      src={imageSrc}
      alt={alt}
      loading="lazy"
      className={className}
      onError={() => {
        if (fallbackSrc && imageSrc !== fallbackSrc) {
          setUseFallback(true);
        }
      }}
    />
  );
}

function MediaPreviewDialog({
  media,
  onClose,
}: {
  media: PreviewMedia | null;
  onClose: () => void;
}) {
  if (!media) return null;
  const isImage = media.assetType === 'image' || isImageLikeUrl(media.url) || isImageLikeUrl(media.thumbnailUrl);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
      <div
        role="dialog"
        aria-label="资产预览"
        className="flex max-h-[88vh] w-full max-w-5xl flex-col overflow-hidden rounded-xl border border-white/15 bg-slate-950 shadow-2xl"
      >
        <div className="flex items-center justify-between gap-3 border-b border-white/10 px-4 py-3">
          <div className="min-w-0">
            <div className="text-sm text-white/45">资产预览</div>
            <div className="truncate text-base font-semibold text-white">{media.title}</div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {media.url && (
              <Button type="button" variant="outline" size="sm" className="border-white/20 text-white" onClick={() => window.open(media.url, '_blank')}>
                <ExternalLink className="mr-1 h-3.5 w-3.5" />
                新窗口打开
              </Button>
            )}
            <Button type="button" variant="outline" size="sm" className="border-white/20 text-white" onClick={onClose}>
              <X className="mr-1 h-3.5 w-3.5" />
              关闭
            </Button>
          </div>
        </div>
        <div className="min-h-0 overflow-auto bg-black/35 p-4">
          {isImage ? (
            <div className="flex min-h-[420px] items-center justify-center rounded-lg border border-white/10 bg-black/40">
              <AssetImagePreview
                src={media.thumbnailUrl || media.url}
                fallbackSrc={media.url}
                alt={media.title}
                className="max-h-[68vh] w-full object-contain"
              />
            </div>
          ) : media.assetType === 'video' ? (
            <video src={media.url} controls className="max-h-[68vh] w-full rounded-lg bg-black" />
          ) : media.assetType === 'audio' ? (
            <div className="rounded-lg border border-white/10 bg-black/35 p-4">
              <audio src={media.url} controls className="w-full" />
            </div>
          ) : (
            <div className="rounded-lg border border-white/10 bg-black/35 p-6 text-sm text-white/55">
              该资产类型暂不支持内嵌预览，可使用“新窗口打开”查看。
            </div>
          )}
          {media.description && (
            <div className="mt-3 rounded-lg border border-white/10 bg-white/[0.04] p-3 text-sm leading-6 text-white/60">
              {media.description}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const isCompositeCharacterName = (name?: string) => {
  const text = (name || '').trim();
  if (!text) return false;
  return /[、,，/／]|和|与|及|以及|们|众人|群|一行人|弟子们|外门弟子们/.test(text)
    || text.startsWith('某')
    || text.slice(0, 4).includes('某');
};

const stringifyJsonField = (value: any) => {
  if (value === undefined || value === null || value === '') return '';
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return '';
  }
};

const parseJsonField = (value: string, label: string) => {
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  try {
    return JSON.parse(trimmed);
  } catch {
    throw new Error(`${label} 必须是合法 JSON`);
  }
};

const compactText = (value?: string, max = 96) => {
  const text = (value || '').replace(/\s+/g, ' ').trim();
  return text.length > max ? `${text.slice(0, max)}...` : text;
};

const readViewItems = (shotTemplate: any) => {
  if (!shotTemplate) return [];
  if (Array.isArray(shotTemplate.views)) return shotTemplate.views;
  if (Array.isArray(shotTemplate.shots)) return shotTemplate.shots;
  return [];
};

const readAspectRatios = (shotTemplate: any) => {
  if (!shotTemplate) return [];
  if (Array.isArray(shotTemplate.aspect_ratios)) {
    return shotTemplate.aspect_ratios
      .map((item: any) => item?.ratio || item?.value || item)
      .filter(Boolean);
  }
  if (Array.isArray(shotTemplate.recommended_aspect_ratios)) {
    return shotTemplate.recommended_aspect_ratios.filter(Boolean);
  }
  return [];
};

const assetFailureInfo = (asset: Asset) => {
  const params = asset.generation_params || {};
  const status = asset.status || params.status;
  const failed = status === 'failed' || status === 'error';
  if (!failed) return null;
  return {
    error: asset.error_message || params.error_message || params.error_reason || '生成失败，暂无详细原因',
    retryable: params.retryable !== false,
    viewLabel: params.view_label || params.view_title || params.view_key,
  };
};

const visualConsistencyScore = (asset: Asset) => {
  const topLevel = typeof asset.visual_consistency === 'number'
    ? asset.visual_consistency
    : asset.visual_consistency?.score;
  const nested = asset.generation_params?.visual_consistency?.score;
  const score = topLevel ?? nested;
  return typeof score === 'number' && Number.isFinite(score) ? Math.round(score) : null;
};

const VIEW_KEY_LABELS: Record<string, string> = {
  front: '正面',
  side: '侧面',
  back: '背面',
  establishing: '全景定场',
  layout: '空间布局',
  detail: '关键细节',
  lighting: '光影氛围',
  main: '主视图',
  scale: '比例参考',
  in_use: '使用状态',
};

const visualLineageInfo = (asset: Asset) => {
  const params = asset.generation_params || {};
  const contract = params.visual_contract || {};
  const contractId = typeof contract.id === 'string' ? contract.id : '';
  const referenceKey = typeof params.reference_view_key === 'string' ? params.reference_view_key : '';
  if (!contractId && !referenceKey) return null;
  return {
    contractId,
    referenceLabel: referenceKey ? (VIEW_KEY_LABELS[referenceKey] || referenceKey) : '',
  };
};

const assetTypeLabel = (assetType?: string) => {
  if (!assetType) return '图片 / 参考图';
  return ASSET_TYPE_LABELS[assetType] || assetType;
};

const entityTypeLabel = (entityType?: string) => {
  if (!entityType) return '实体';
  return ENTITY_TYPE_LABELS[entityType] || entityType;
};

const emptyForm = {
  name: '',
  category: 'character',
  asset_type: 'image',
  project_id: '',
  novel_id: '',
  chapter_id: '',
  script_id: '',
  entity_id: '',
  url: '',
  thumbnail_url: '',
  tags: '',
  style_tags: '',
  description: '',
  prompt_template: '',
  variables: '',
  shot_template: '',
  source_prompt: '',
  generation_params: '',
  is_public: false,
};

type AssetMediaFieldProps = {
  label: string;
  field: 'url' | 'thumbnail_url';
  value: string;
  assetType: string;
  uploading: boolean;
  previewUrl: string;
  onValueChange: (value: string) => void;
  onUpload: (file: File | undefined) => void;
  onOpen: () => void;
};

function AssetMediaField({
  label,
  field,
  value,
  assetType,
  uploading,
  previewUrl,
  onValueChange,
  onUpload,
  onOpen,
}: AssetMediaFieldProps) {
  const inputId = `asset-${field}-upload`;
  const accepts = field === 'thumbnail_url'
    ? 'image/*'
    : assetType === 'video'
      ? 'video/*'
      : assetType === 'audio'
        ? 'audio/*'
        : assetType === 'text'
          ? '.txt,.json,.md,.srt,.vtt,text/*,application/json'
          : 'image/*,.safetensors,.ckpt,.pt,.bin,.json';

  return (
    <div className="space-y-2 rounded-lg border border-white/10 bg-black/20 p-3 md:col-span-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-sm font-medium text-white">{label}</div>
          <div className="text-xs text-white/45">可上传本地文件，也可粘贴公网 URL 或 /static 路径。</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <input
            id={inputId}
            type="file"
            accept={accepts}
            className="hidden"
            onChange={(event) => {
              onUpload(event.target.files?.[0]);
              event.target.value = '';
            }}
          />
          <Button asChild variant="outline" size="sm" className="border-white/20 text-white">
            <label htmlFor={inputId} className="cursor-pointer">
              {uploading ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <FileUp className="mr-1 h-3.5 w-3.5" />}
              选择上传
            </label>
          </Button>
          <Button type="button" variant="outline" size="sm" className="border-white/20 text-white" disabled={!value} onClick={onOpen}>
            <ExternalLink className="mr-1 h-3.5 w-3.5" />
            打开
          </Button>
        </div>
      </div>
      <Input
        value={value}
        onChange={(event) => onValueChange(event.target.value)}
        placeholder={field === 'url' ? '资源 URL 或 /static/... 路径' : '缩略图 URL，可选'}
        className="bg-white/5 border-white/10 text-white"
      />
      {previewUrl ? (
        <div className="overflow-hidden rounded-md border border-white/10 bg-black/30">
          {field === 'thumbnail_url' || assetType === 'image' || isImageLikeUrl(value) ? (
            <AssetImagePreview src={previewUrl} alt={label} className="h-40 w-full object-contain" />
          ) : assetType === 'video' ? (
            <video src={previewUrl} controls className="h-40 w-full bg-black" />
          ) : assetType === 'audio' ? (
            <div className="p-3">
              <audio src={previewUrl} controls className="w-full" />
            </div>
          ) : (
            <div className="flex h-24 items-center justify-center text-xs text-white/45">该类型不支持内嵌预览，可点击打开查看。</div>
          )}
        </div>
      ) : (
        <div className="rounded-md border border-dashed border-white/10 bg-white/[0.03] px-3 py-4 text-xs text-white/40">
          上传或填写路径后会在这里显示预览。
        </div>
      )}
    </div>
  );
}

export default function AssetsPage() {
  const formSectionRef = useRef<HTMLDivElement | null>(null);
  const nameInputRef = useRef<HTMLInputElement | null>(null);
  const lineageContextRef = useRef('');
  const [assets, setAssets] = useState<Asset[]>([]);
  const [categories, setCategories] = useState<AssetCategory[]>(FALLBACK_CATEGORIES);
  const [projects, setProjects] = useState<Project[]>([]);
  const [novels, setNovels] = useState<Novel[]>([]);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [scripts, setScripts] = useState<ScriptItem[]>([]);
  const [entities, setEntities] = useState<StoryEntity[]>([]);
  const [viewPresets, setViewPresets] = useState<AssetViewPreset[]>(FALLBACK_VIEW_PRESETS);
  const [styleTemplates, setStyleTemplates] = useState<ImageStyleTemplate[]>(FALLBACK_STYLE_TEMPLATES);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedProjectId, setSelectedProjectId] = useState('all');
  const [selectedNovelId, setSelectedNovelId] = useState('');
  const [selectedChapterId, setSelectedChapterId] = useState('');
  const [selectedScriptId, setSelectedScriptId] = useState('');
  const [selectedEntityId, setSelectedEntityId] = useState('');
  const [pendingEntityId, setPendingEntityId] = useState('');
  const [selectedScope, setSelectedScope] = useState('');
  const [selectedEntityType, setSelectedEntityType] = useState('character');
  const [selectedGenerationStyle, setSelectedGenerationStyle] = useState('anime');
  const [includePublic, setIncludePublic] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [generatingViews, setGeneratingViews] = useState(false);
  const [retryingAssetId, setRetryingAssetId] = useState<string | null>(null);
  const [regeneratingAssetId, setRegeneratingAssetId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [showAdvancedFields, setShowAdvancedFields] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [uploadingField, setUploadingField] = useState<'url' | 'thumbnail_url' | null>(null);
  const [selectedAssets, setSelectedAssets] = useState<Set<string>>(new Set());
  const [showVersionHistory, setShowVersionHistory] = useState(false);
  const [versionHistoryEntity, setVersionHistoryEntity] = useState<{id: string; type: string; name: string} | null>(null);
  const [versionHistory, setVersionHistory] = useState<Asset[]>([]);
  const [previewMedia, setPreviewMedia] = useState<PreviewMedia | null>(null);

  const categoryOptions = useMemo(() => [
    { value: 'all', label: '全部分类' },
    ...categories.map((category) => ({
      value: category.name,
      label: `${category.name_cn || category.name}${category.asset_count ? ` (${category.asset_count})` : ''}`,
    })),
  ], [categories]);

  const projectOptions = useMemo(() => [
    { value: 'all', label: '全部资产' },
    { value: 'global', label: '仅全局资产' },
    ...projects.map((project) => ({ value: project.id, label: project.name })),
  ], [projects]);

  const formProjectOptions = useMemo(() => [
    { value: '', label: '全局资产' },
    ...projects.map((project) => ({ value: project.id, label: project.name })),
  ], [projects]);

  const scopeOptions = [
    { value: '', label: '全部范围（含全局）' },
    { value: 'global', label: '仅全局' },
    { value: 'project', label: '仅项目' },
    { value: 'novel', label: '仅小说' },
    { value: 'chapter', label: '仅章节' },
    { value: 'script', label: '仅剧本' },
    { value: 'entity', label: '仅实体' },
  ];

  const visibleAssets = useMemo(() => {
    if (selectedProjectId !== 'global') return assets;
    return assets.filter((asset) => !asset.project_id && !asset.novel_id && !asset.chapter_id && !asset.script_id && !asset.entity_id);
  }, [assets, selectedProjectId]);

  const activePreset = useMemo(
    () => viewPresets.find((preset) => preset.entity_type === selectedEntityType) || FALLBACK_VIEW_PRESETS[0],
    [viewPresets, selectedEntityType]
  );

  const styleOptions = useMemo(
    () => (styleTemplates.length ? styleTemplates : FALLBACK_STYLE_TEMPLATES).map((template) => ({
      value: template.style,
      label: template.label,
    })),
    [styleTemplates]
  );

  const wizardEntities = useMemo(
    () => entities.filter((entity) => entity.entity_type === selectedEntityType),
    [entities, selectedEntityType]
  );

  const selectedWizardEntity = useMemo(
    () => entities.find((entity) => entity.id === selectedEntityId),
    [entities, selectedEntityId]
  );

  const selectedWizardEntityInvalid = selectedEntityType === 'character'
    && Boolean(selectedWizardEntity && isCompositeCharacterName(selectedWizardEntity.name));

  const disabledWizardEntityCount = useMemo(
    () => selectedEntityType === 'character'
      ? wizardEntities.filter((entity) => isCompositeCharacterName(entity.name)).length
      : 0,
    [selectedEntityType, wizardEntities]
  );

  const wizardEntityOptions = useMemo(
    () => wizardEntities.map((entity) => {
      const disabled = selectedEntityType === 'character' && isCompositeCharacterName(entity.name);
      return {
        value: entity.id,
        label: disabled ? `${entity.name}（群体/复合角色，请先拆分）` : entity.name,
        disabled,
      };
    }),
    [selectedEntityType, wizardEntities]
  );

  const selectedFormEntity = useMemo(
    () => entities.find((entity) => entity.id === form.entity_id),
    [entities, form.entity_id]
  );

  const editingAsset = useMemo(
    () => assets.find((asset) => asset.id === editingId) || null,
    [assets, editingId]
  );

  const viewAssetsByKey = useMemo(() => {
    const mapping: Record<string, Asset> = {};
    if (!selectedEntityId) return mapping;
    for (const asset of visibleAssets) {
      const viewKey = asset.generation_params?.view_key || asset.generation_params?.asset_subtype;
      if (asset.entity_id === selectedEntityId && viewKey && !mapping[viewKey]) {
        mapping[viewKey] = asset;
      }
    }
    return mapping;
  }, [visibleAssets, selectedEntityId]);

  const missingViewKeys = useMemo(
    () => activePreset.views.filter((view) => !viewAssetsByKey[view.key]?.url).map((view) => view.key),
    [activePreset, viewAssetsByKey]
  );

  const categoryLabel = (categoryName: string) => (
    categories.find((category) => category.name === categoryName)?.name_cn || categoryName
  );

  const projectLabel = (projectId?: string) => {
    if (!projectId) return '全局资产';
    return projects.find((project) => project.id === projectId)?.name || '项目资产';
  };

  const novelLabel = (novelId?: string) => {
    if (!novelId) return '';
    return novels.find((novel) => novel.id === novelId)?.title || `小说 ${novelId.slice(0, 8)}`;
  };

  const chapterLabel = (chapterId?: string) => {
    if (!chapterId) return '';
    const chapter = chapters.find((item) => item.id === chapterId);
    return chapter ? formatChapterLabel(chapter) : `章节 ${chapterId.slice(0, 8)}`;
  };

  const scriptLabel = (scriptId?: string) => {
    if (!scriptId) return '';
    return scripts.find((script) => script.id === scriptId)?.title || `剧本 ${scriptId.slice(0, 8)}`;
  };

  const entityLabel = (entityId?: string) => {
    if (!entityId) return '';
    const entity = entities.find((item) => item.id === entityId);
    return entity ? `${entity.name} · ${entityTypeLabel(entity.entity_type)}` : `实体 ${entityId.slice(0, 8)}`;
  };

  const scopeLabel = (asset: Asset) => {
    if (asset.entity_id) return '实体资产';
    if (asset.script_id) return '剧本资产';
    if (asset.chapter_id) return '章节资产';
    if (asset.novel_id) return '小说资产';
    if (asset.project_id) return '项目资产';
    return '全局资产';
  };

  const toMediaUrl = (url?: string) => {
    if (!url) return '';
    if (/^https?:\/\//.test(url)) return url;
    const base = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1').replace(/\/api\/v1$/, '');
    return `${base}${url.startsWith('/') ? url : `/${url}`}`;
  };

  const previewAssetMedia = (asset: Asset) => {
    const url = toMediaUrl(asset.url || asset.thumbnail_url);
    if (!url) {
      setMessage('该资产暂无可预览的资源地址');
      return;
    }
    setPreviewMedia({
      title: asset.name,
      assetType: asset.asset_type || 'image',
      url,
      thumbnailUrl: toMediaUrl(asset.thumbnail_url || asset.url),
      description: asset.description || compactText(asset.source_prompt, 180),
    });
  };

  const previewFormMedia = (title: string, assetType: string, url?: string, thumbnailUrl?: string, description?: string) => {
    const mediaUrl = toMediaUrl(url || thumbnailUrl);
    if (!mediaUrl) {
      setMessage('请先上传或填写资源地址');
      return;
    }
    setPreviewMedia({
      title,
      assetType: assetType || 'image',
      url: mediaUrl,
      thumbnailUrl: toMediaUrl(thumbnailUrl || url),
      description,
    });
  };

  const uploadAssetMedia = async (file: File | undefined, field: 'url' | 'thumbnail_url') => {
    if (!file) return;
    setUploadingField(field);
    setMessage(null);
    try {
      const result = await apiClient.uploadAssetFile(file, {
        asset_type: form.asset_type,
        kind: field === 'thumbnail_url' ? 'thumbnail' : 'resource',
      });
      setForm((current) => ({
        ...current,
        [field]: result.url,
        thumbnail_url: field === 'url' && current.asset_type === 'image' && !current.thumbnail_url ? result.url : current.thumbnail_url,
      }));
      setMessage('文件已上传并回填路径');
    } catch (err: any) {
      setMessage(err?.message || '文件上传失败');
    } finally {
      setUploadingField(null);
    }
  };

  const loadAssets = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const [categoryList, projectList, assetList] = await Promise.all([
        apiClient.getAssetCategories().catch(() => FALLBACK_CATEGORIES),
        apiClient.getProjects().catch(() => []),
        apiClient.getAssets({
          category: selectedCategory === 'all' ? undefined : selectedCategory,
          project_id: selectedProjectId === 'all' || selectedProjectId === 'global' ? undefined : selectedProjectId,
          novel_id: selectedNovelId || undefined,
          chapter_id: selectedChapterId || undefined,
          script_id: selectedScriptId || undefined,
          entity_id: selectedEntityId || undefined,
          scope: selectedScope || undefined,
          search: searchQuery.trim() || undefined,
          include_public: includePublic,
          limit: 200,
        }),
      ]);
      setCategories(categoryList?.length ? categoryList : FALLBACK_CATEGORIES);
      setProjects(projectList || []);
      setAssets(assetList || []);
    } catch (err: any) {
      setAssets([]);
      setMessage(err?.message || '资产加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAssets();
  }, [selectedCategory, selectedProjectId, selectedScope, selectedNovelId, selectedChapterId, selectedScriptId, selectedEntityId, includePublic]);

  useEffect(() => {
    const searchParams = new URLSearchParams(window.location.search);
    const novelId = searchParams.get('novel_id') || '';
    const entityType = searchParams.get('entity_type') || '';
    const entityId = searchParams.get('entity_id') || '';
    if (novelId) setSelectedNovelId(novelId);
    if (['character', 'scene', 'prop'].includes(entityType)) {
      setSelectedEntityType(entityType);
      setSelectedCategory(entityType);
    }
    if (entityId) setPendingEntityId(entityId);
  }, []);

  useEffect(() => {
    const loadNovels = async () => {
      try {
        const [data, presetData, styleData] = await Promise.all([
          apiClient.getNovels().catch(() => []),
          apiClient.getAssetViewPresets().catch(() => ({ presets: FALLBACK_VIEW_PRESETS })),
          apiClient.getAssetStyleTemplates().catch(() => ({ templates: FALLBACK_STYLE_TEMPLATES })),
        ]);
        setNovels(Array.isArray(data) ? data : []);
        const presets = Array.isArray(presetData?.presets) ? presetData.presets : FALLBACK_VIEW_PRESETS;
        setViewPresets(presets.length ? presets : FALLBACK_VIEW_PRESETS);
        const templates = Array.isArray(styleData?.templates) ? styleData.templates : FALLBACK_STYLE_TEMPLATES;
        setStyleTemplates(templates.length ? templates : FALLBACK_STYLE_TEMPLATES);
      } catch {
        setNovels([]);
        setViewPresets(FALLBACK_VIEW_PRESETS);
        setStyleTemplates(FALLBACK_STYLE_TEMPLATES);
      }
    };
    loadNovels();
  }, []);

  useEffect(() => {
    const loadLineageOptions = async () => {
      const formNovelId = formOpen && form.novel_id ? form.novel_id : '';
      const activeNovelId = selectedNovelId || formNovelId;
      if (!activeNovelId) {
        setChapters([]);
        setScripts([]);
        setEntities([]);
        return;
      }
      try {
        const [chapterList, scriptList, entityList] = await Promise.all([
          apiClient.getChapters(activeNovelId).catch(() => []),
          apiClient.getScripts({ novel_id: activeNovelId, page_size: 100 }).catch(() => []),
          apiClient.getStoryEntities({ novel_id: activeNovelId, limit: 200 }).catch(() => []),
        ]);
        setChapters(Array.isArray(chapterList) ? chapterList : []);
        setScripts(Array.isArray(scriptList) ? scriptList : []);
        const nextEntities = Array.isArray(entityList) ? entityList : [];
        setEntities(nextEntities);
        if (pendingEntityId && nextEntities.some((entity) => entity.id === pendingEntityId)) {
          setSelectedEntityId(pendingEntityId);
          setPendingEntityId('');
        }
      } catch {
        setChapters([]);
        setScripts([]);
        setEntities([]);
      }
    };
    const nextContextKey = `${selectedNovelId}|${formOpen && form.novel_id ? form.novel_id : ''}`;
    const contextChanged = lineageContextRef.current !== nextContextKey;
    lineageContextRef.current = nextContextKey;
    setSelectedChapterId('');
    setSelectedScriptId('');
    if (contextChanged && !pendingEntityId) {
      setSelectedEntityId('');
    }
    loadLineageOptions();
  }, [selectedNovelId, formOpen, form.novel_id, pendingEntityId]);

  const generateMissingViews = async () => {
    if (!selectedEntityId || !activePreset) {
      setMessage('请先选择小说和要制作的角色、场景或道具');
      return;
    }
    if (selectedWizardEntityInvalid) {
      setMessage('角色三视图只能用于单一角色；群体/复合角色请先在实体库拆分成具体角色。');
      return;
    }
    setGeneratingViews(true);
    setMessage('正在生成多视图参考图，请稍候...');
    try {
      const keys = missingViewKeys.length > 0 ? missingViewKeys : activePreset.views.map((view) => view.key);
      const result = await apiClient.generateEntityViewAssets({
        entity_id: selectedEntityId,
        view_keys: keys,
        style: selectedGenerationStyle,
      });
      const generatedCount = result?.total ?? keys.length;
      const failedCount = Array.isArray(result?.failures) ? result.failures.length : 0;
      setSelectedCategory(activePreset.category || selectedEntityType);
      setSelectedScope('');
      await loadAssets();
      if (failedCount > 0 && generatedCount > 0) {
        setMessage(`已生成 ${generatedCount} 张参考图，${failedCount} 个视图生成失败，已记录原因，可在资产列表中重试`);
      } else if (failedCount > 0) {
        setMessage(`${failedCount} 个视图生成失败，已记录原因，可在资产列表中重试`);
      } else {
        setMessage(`已生成 ${generatedCount} 张${activePreset.title}参考图，可在下方预览并锁定定稿`);
      }
    } catch (err: any) {
      setMessage(err?.message || '多视图资产生成失败，请检查图像模型配置');
    } finally {
      setGeneratingViews(false);
    }
  };

  const startCreate = () => {
    setEditingId(null);
    setShowAdvancedFields(false);
    setForm({
      ...emptyForm,
      category: selectedCategory === 'all' ? 'character' : selectedCategory,
      project_id: selectedProjectId === 'all' || selectedProjectId === 'global' ? '' : selectedProjectId,
      novel_id: selectedNovelId,
      chapter_id: selectedChapterId,
      script_id: selectedScriptId,
      entity_id: selectedEntityId,
    });
    setFormOpen(true);
    setMessage(null);
    requestAnimationFrame(() => {
      formSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      nameInputRef.current?.focus({ preventScroll: true });
    });
  };

  const startEdit = (asset: Asset) => {
    setEditingId(asset.id);
    setFormOpen(true);
    setShowAdvancedFields(Boolean(asset.variables || asset.shot_template || asset.source_prompt || asset.generation_params));
    setForm({
      name: asset.name || '',
      category: asset.category || 'character',
      asset_type: asset.asset_type || 'image',
      project_id: asset.project_id || '',
      novel_id: asset.novel_id || '',
      chapter_id: asset.chapter_id || '',
      script_id: asset.script_id || '',
      entity_id: asset.entity_id || '',
      url: asset.url || '',
      thumbnail_url: asset.thumbnail_url || '',
      tags: (asset.tags || []).join('，'),
      style_tags: (asset.style_tags || []).join('，'),
      description: asset.description || '',
      prompt_template: asset.prompt_template || '',
      variables: stringifyJsonField(asset.variables),
      shot_template: stringifyJsonField(asset.shot_template),
      source_prompt: asset.source_prompt || '',
      generation_params: stringifyJsonField(asset.generation_params),
      is_public: Boolean(asset.is_public),
    });
    setMessage(null);
    requestAnimationFrame(() => {
      formSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      nameInputRef.current?.focus({ preventScroll: true });
    });
  };

  const resetForm = () => {
    setEditingId(null);
    setFormOpen(false);
    setShowAdvancedFields(false);
    setForm(emptyForm);
  };

  const saveAsset = async () => {
    if (!form.name.trim()) {
      setMessage('请输入资产名称');
      return;
    }
    setSaving(true);
    setMessage(null);

    let variables: any[] | undefined;
    let shotTemplate: any | undefined;
    let generationParams: Record<string, any> | undefined;
    try {
      variables = parseJsonField(form.variables, '变量配置') as any[] | undefined;
      shotTemplate = parseJsonField(form.shot_template, '视图/比例配置');
      generationParams = parseJsonField(form.generation_params, '生成参数') as Record<string, any> | undefined;
    } catch (err: any) {
      setSaving(false);
      setMessage(err?.message || 'JSON 格式不正确');
      return;
    }

    const payload = {
      category: form.category,
      name: form.name.trim(),
      description: form.description.trim() || undefined,
      asset_type: form.asset_type,
      url: form.url.trim() || undefined,
      thumbnail_url: form.thumbnail_url.trim() || undefined,
      project_id: form.project_id || undefined,
      novel_id: form.novel_id || undefined,
      chapter_id: form.chapter_id || undefined,
      script_id: form.script_id || undefined,
      entity_id: form.entity_id || undefined,
      entity_type: selectedFormEntity?.entity_type || (form.entity_id ? selectedEntityType : undefined),
      tags: splitTags(form.tags),
      style_tags: splitTags(form.style_tags),
      prompt_template: form.prompt_template.trim() || undefined,
      variables,
      shot_template: shotTemplate,
      source_prompt: form.source_prompt.trim() || undefined,
      generation_params: generationParams,
      is_public: form.is_public,
    };
    try {
      const isEditing = Boolean(editingId);
      if (editingId) {
        const updated = await apiClient.updateAsset(editingId, payload);
        setAssets((prev) => prev.map((asset) => asset.id === editingId ? updated : asset));
      } else {
        const created = await apiClient.createAsset(payload);
        setAssets((prev) => [created, ...prev]);
      }
      resetForm();
      await loadAssets();
      setMessage(isEditing ? '资产已更新' : '资产已保存');
    } catch (err: any) {
      setMessage(err?.message || '资产保存失败');
    } finally {
      setSaving(false);
    }
  };

  const archiveAsset = async (assetId: string) => {
    setMessage(null);
    try {
      await apiClient.deleteAsset(assetId);
      setAssets((prev) => prev.filter((asset) => asset.id !== assetId));
      setMessage('资产已归档');
    } catch (err: any) {
      setMessage(err?.message || '资产归档失败');
    }
  };

  const lockAsset = async (assetId: string) => {
    setMessage(null);
    try {
      const updated = await apiClient.lockAsset(assetId);
      setAssets((prev) => prev.map((asset) => asset.id === assetId ? { ...asset, is_locked: true, is_final: true } : asset));
      setMessage('资产已锁定为定稿');
    } catch (err: any) {
      setMessage(err?.message || '资产锁定失败');
    }
  };

  const unlockAsset = async (assetId: string) => {
    setMessage(null);
    try {
      const updated = await apiClient.unlockAsset(assetId);
      setAssets((prev) => prev.map((asset) => asset.id === assetId ? { ...asset, is_locked: false, is_final: false } : asset));
      setMessage('资产已解锁');
    } catch (err: any) {
      setMessage(err?.message || '资产解锁失败');
    }
  };

  const retryAssetGeneration = async (asset: Asset) => {
    setRetryingAssetId(asset.id);
    setMessage(null);
    try {
      const result = await apiClient.retryAssetGeneration(asset.id);
      const generatedCount = result?.total ?? (Array.isArray(result?.assets) ? result.assets.length : 0);
      const failedCount = Array.isArray(result?.failures) ? result.failures.length : 0;
      await loadAssets();
      if (generatedCount > 0) {
        setMessage(`已重新生成 ${generatedCount} 张参考图`);
      } else if (failedCount > 0) {
        setMessage('重试仍未生成成功，失败原因已更新');
      } else {
        setMessage('已提交重试，请稍后刷新查看结果');
      }
    } catch (err: any) {
      setMessage(err?.message || '重试生成失败，请检查图像模型配置');
    } finally {
      setRetryingAssetId(null);
    }
  };

  const regenerateAsset = async (asset: Asset) => {
    setRegeneratingAssetId(asset.id);
    setMessage(null);
    try {
      const regenerated = await apiClient.regenerateAsset(asset.id, {
        style: selectedGenerationStyle,
      });
      setAssets((prev) => [regenerated, ...prev.filter((item) => item.id !== regenerated.id)]);
      setMessage(`已按「${styleOptions.find((item) => item.value === selectedGenerationStyle)?.label || selectedGenerationStyle}」重新生成 ${asset.name}`);
      if (editingId === asset.id) {
        startEdit(regenerated);
      }
      await loadAssets();
    } catch (err: any) {
      setMessage(err?.message || '重新生成失败，请检查图像模型配置和资产绑定关系');
    } finally {
      setRegeneratingAssetId(null);
    }
  };

  const batchLockAssets = async () => {
    if (selectedAssets.size === 0) {
      setMessage('请先选择要锁定的资产');
      return;
    }
    setMessage(null);
    try {
      const result = await apiClient.bulkActionAssets({
        asset_ids: Array.from(selectedAssets),
        action: 'lock',
      });
      setAssets((prev) => prev.map((asset) =>
        selectedAssets.has(asset.id) ? { ...asset, is_locked: true, is_final: true } : asset
      ));
      setSelectedAssets(new Set());
      setMessage(`已锁定 ${result.updated_count || 0} 个资产`);
    } catch (err: any) {
      setMessage(err?.message || '批量锁定失败');
    }
  };

  const batchUnlockAssets = async () => {
    if (selectedAssets.size === 0) {
      setMessage('请先选择要解锁的资产');
      return;
    }
    setMessage(null);
    try {
      const result = await apiClient.bulkActionAssets({
        asset_ids: Array.from(selectedAssets),
        action: 'unlock',
      });
      setAssets((prev) => prev.map((asset) =>
        selectedAssets.has(asset.id) ? { ...asset, is_locked: false, is_final: false } : asset
      ));
      setSelectedAssets(new Set());
      setMessage(`已解锁 ${result.updated_count || 0} 个资产`);
    } catch (err: any) {
      setMessage(err?.message || '批量解锁失败');
    }
  };

  const batchArchiveAssets = async () => {
    if (selectedAssets.size === 0) {
      setMessage('请先选择要归档的资产');
      return;
    }
    if (!confirm('批量归档会跳过锁定、定稿或已引用资产。确认继续？')) return;
    setMessage(null);
    try {
      const result = await apiClient.bulkActionAssets({
        asset_ids: Array.from(selectedAssets),
        action: 'archive',
      });
      const archivedIds = new Set((result.assets || []).map((asset: Asset) => asset.id));
      setAssets((prev) => prev.filter((asset) => !archivedIds.has(asset.id)));
      setSelectedAssets(new Set());
      const skipped = Array.isArray(result.skipped) && result.skipped.length
        ? `，跳过 ${result.skipped.length} 个：${result.skipped.slice(0, 2).map((item: any) => item.reason).join('；')}`
        : '';
      setMessage(`已归档 ${result.deleted_count || result.updated_count || 0} 个资产${skipped}`);
    } catch (err: any) {
      setMessage(err?.message || '批量归档失败');
    }
  };

  const parseTagsInput = (value: string) => value
    .split(/[，,]/)
    .map((item) => item.trim())
    .filter(Boolean);

  const currentAssetScopePayload = () => {
    if (selectedEntityId) {
      return {
        scope: 'entity' as const,
        novel_id: selectedNovelId || undefined,
        chapter_id: selectedChapterId || undefined,
        script_id: selectedScriptId || undefined,
        entity_id: selectedEntityId,
      };
    }
    if (selectedScriptId) {
      return {
        scope: 'script' as const,
        novel_id: selectedNovelId || undefined,
        chapter_id: selectedChapterId || undefined,
        script_id: selectedScriptId,
      };
    }
    if (selectedChapterId) {
      return {
        scope: 'chapter' as const,
        novel_id: selectedNovelId || undefined,
        chapter_id: selectedChapterId,
      };
    }
    if (selectedNovelId) {
      return {
        scope: 'novel' as const,
        novel_id: selectedNovelId,
      };
    }
    if (selectedProjectId && selectedProjectId !== 'all' && selectedProjectId !== 'global') {
      return {
        scope: 'project' as const,
        project_id: selectedProjectId,
      };
    }
    if (selectedProjectId === 'global') {
      return { scope: 'global' as const };
    }
    return null;
  };

  const batchSetAssetsToCurrentScope = async () => {
    if (selectedAssets.size === 0) {
      setMessage('请先选择要调整作用域的资产');
      return;
    }
    const scopePayload = currentAssetScopePayload();
    if (!scopePayload) {
      setMessage('请先选择项目、小说、章节、剧本、实体或全局筛选条件，再批量设置当前范围');
      return;
    }
    setMessage(null);
    try {
      const result = await apiClient.bulkActionAssets({
        asset_ids: Array.from(selectedAssets),
        action: 'set_scope',
        ...scopePayload,
      });
      setSelectedAssets(new Set());
      await loadAssets();
      setMessage(`已调整 ${result.updated_count || 0} 个资产到当前范围`);
    } catch (err: any) {
      setMessage(err?.message || '批量调整资产作用域失败');
    }
  };

  const batchSetAssetTags = async () => {
    if (selectedAssets.size === 0) {
      setMessage('请先选择要标记的资产');
      return;
    }
    const raw = window.prompt('输入资产标签，多个标签用逗号分隔');
    if (raw === null) return;
    const tags = parseTagsInput(raw);
    if (!tags.length) {
      setMessage('请至少输入一个标签');
      return;
    }
    setMessage(null);
    try {
      const result = await apiClient.bulkActionAssets({
        asset_ids: Array.from(selectedAssets),
        action: 'set_tags',
        tags,
      });
      setSelectedAssets(new Set());
      await loadAssets();
      setMessage(`已更新 ${result.updated_count || 0} 个资产标签`);
    } catch (err: any) {
      setMessage(err?.message || '批量更新资产标签失败');
    }
  };

  const loadVersionHistory = async (entityId: string, entityType: string) => {
    setMessage(null);
    try {
      const versions = await apiClient.getEntityAssetVersions(entityId, entityType);
      setVersionHistory(versions || []);
      setShowVersionHistory(true);
    } catch (err: any) {
      setMessage(err?.message || '版本历史加载失败');
    }
  };

  const toggleAssetSelection = (assetId: string) => {
    setSelectedAssets((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(assetId)) {
        newSet.delete(assetId);
      } else {
        newSet.add(assetId);
      }
      return newSet;
    });
  };

  const bindAssetScope = async (asset: Asset, scope: 'global' | 'novel' | 'chapter' | 'script' | 'entity') => {
    setMessage(null);
    if (scope === 'novel' && !(selectedNovelId || asset.novel_id)) {
      setMessage('请先选择小说，或选择已有小说资产');
      return;
    }
    if (scope === 'chapter' && !(selectedChapterId || asset.chapter_id)) {
      setMessage('请先选择章节，或选择已有章节资产');
      return;
    }
    if (scope === 'script' && !(selectedScriptId || asset.script_id)) {
      setMessage('请先选择剧本，或选择已有剧本资产');
      return;
    }
    if (scope === 'entity' && !(selectedEntityId || asset.entity_id)) {
      setMessage('请先选择实体，或选择已有实体资产');
      return;
    }
    try {
      const updated = await apiClient.updateAssetScope(asset.id, {
        scope,
        novel_id: selectedNovelId || asset.novel_id || undefined,
        chapter_id: selectedChapterId || asset.chapter_id || undefined,
        script_id: selectedScriptId || asset.script_id || undefined,
        entity_id: selectedEntityId || asset.entity_id || undefined,
      });
      setAssets((prev) => prev.map((item) => item.id === asset.id ? updated : item));
      setMessage(`已调整「${asset.name}」作用域`);
      await loadAssets();
    } catch (err: any) {
      setMessage(err?.message || '资产作用域调整失败');
    }
  };

  const stats = useMemo(() => ({
    total: visibleAssets.length,
    global: visibleAssets.filter((asset) => !asset.project_id && !asset.novel_id && !asset.chapter_id && !asset.script_id && !asset.entity_id).length,
    public: visibleAssets.filter((asset) => asset.is_public).length,
    referenced: visibleAssets.filter((asset) => (asset.usage_count || 0) > 0).length,
    locked: visibleAssets.filter((asset) => asset.is_locked).length,
    final: visibleAssets.filter((asset) => asset.is_final).length,
  }), [visibleAssets]);

  const completedViewCount = activePreset.views.filter((view) => Boolean(viewAssetsByKey[view.key]?.url)).length;
  const totalRequiredViewCount = activePreset.views.length;
  const wizardProgress = totalRequiredViewCount ? Math.round((completedViewCount / totalRequiredViewCount) * 100) : 0;
  const selectedStyleLabel = styleOptions.find((option) => option.value === selectedGenerationStyle)?.label || selectedGenerationStyle || '未选择';
  const selectedEntityTypeLabel = ENTITY_TYPE_LABELS[selectedEntityType] || selectedEntityType;

  const resourcePreviewUrl = toMediaUrl(form.url);
  const thumbnailPreviewUrl = toMediaUrl(form.thumbnail_url);

  return (
    <MainLayout>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-white">资产库</h1>
            <p className="mt-1 text-white/60">统一管理角色三视图、场景/道具多视图、风格图、画面比例、音效、关键帧和提示词资产</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" className="border-white/20 text-white" onClick={loadAssets} disabled={loading}>
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
              刷新
            </Button>
            <Button className="bg-violet-600 hover:bg-violet-700" onClick={startCreate}>
              <Plus className="mr-2 h-4 w-4" />
              新建资产
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 md:grid-cols-6">
          {[
            ['资产总数', stats.total],
            ['全局资产', stats.global],
            ['公开资产', stats.public],
            ['已被引用', stats.referenced],
            ['已锁定', stats.locked],
            ['定稿', stats.final],
          ].map(([label, value]) => (
            <Card key={label} className="border-white/10 bg-white/[0.04]">
              <CardContent className="flex items-center justify-between gap-2 px-3 py-2.5">
                <div className="text-xs text-white/45">{label}</div>
                <div className="text-lg font-semibold text-white">{value}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        <Card className="bg-white/5 border-white/10" data-testid="asset-wizard">
          <CardHeader className="pb-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle className="flex items-center gap-2 text-white">
                  <Sparkles className="h-5 w-5 text-violet-300" />
                  AI 资产制片向导
                </CardTitle>
                <p className="mt-1 text-sm text-white/55">
                  先选小说对象，再补齐必备视图；生成后的参考图会自动绑定对象，后续镜头和视频可直接复用。
                </p>
              </div>
              <div className="flex flex-wrap gap-2 text-xs">
                <Badge variant="outline" className="border-white/20 text-white/70">{selectedEntityTypeLabel}</Badge>
                <Badge variant="outline" className="border-violet-300/35 text-violet-100">{selectedStyleLabel}</Badge>
                <Badge variant="outline" className="border-emerald-300/35 text-emerald-100">
                  {completedViewCount}/{totalRequiredViewCount} 已完成
                </Badge>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-[360px_1fr]">
              <div className="space-y-3 rounded-lg border border-white/10 bg-black/20 p-4">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-lg font-semibold text-white">{activePreset.title}</h2>
                  <Badge variant="outline" className="border-white/20 text-white/65">
                    {activePreset.views.length} 个必备视图
                  </Badge>
                </div>
                <p className="text-sm leading-6 text-white/55">
                  {activePreset.description || '补齐视图后，可锁定为定稿参考，避免后续视频生成时人物、空间或道具随机变化。'}
                </p>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-1">
                  <label className="space-y-1 text-sm text-white/70" htmlFor="asset-wizard-novel">
                    <span>向导小说</span>
                    <Select
                      id="asset-wizard-novel"
                      value={selectedNovelId}
                      onChange={(event) => setSelectedNovelId(event.target.value)}
                      options={[{ value: '', label: '请选择小说' }, ...novels.map((novel) => ({ value: novel.id, label: novel.title }))]}
                    />
                  </label>
                  <label className="space-y-1 text-sm text-white/70" htmlFor="asset-wizard-entity-type">
                    <span>资产对象类型</span>
                    <Select
                      id="asset-wizard-entity-type"
                      value={selectedEntityType}
                      onChange={(event) => {
                        setSelectedEntityType(event.target.value);
                        setSelectedEntityId('');
                        setSelectedCategory(event.target.value);
                      }}
                      options={[
                        { value: 'character', label: '角色' },
                        { value: 'scene', label: '场景' },
                        { value: 'prop', label: '道具' },
                      ]}
                    />
                  </label>
                  <label className="space-y-1 text-sm text-white/70" htmlFor="asset-wizard-entity">
                    <span>小说对象</span>
                    <Select
                      id="asset-wizard-entity"
                      value={selectedEntityId}
                      disabled={!selectedNovelId || wizardEntities.length === 0}
                      onChange={(event) => {
                        setSelectedEntityId(event.target.value);
                        setSelectedScope('');
                      }}
                      options={[
                        {
                          value: '',
                          label: selectedNovelId
                            ? wizardEntities.length
                              ? `请选择${ENTITY_TYPE_LABELS[selectedEntityType]}`
                              : `暂无${ENTITY_TYPE_LABELS[selectedEntityType]}，请先在实体库提取或创建`
                            : '请先选择小说',
                        },
                        ...wizardEntityOptions,
                      ]}
                    />
                  </label>
                  <label className="space-y-1 text-sm text-white/70" htmlFor="asset-wizard-style">
                    <span>画面风格</span>
                    <Select
                      id="asset-wizard-style"
                      value={selectedGenerationStyle}
                      onChange={(event) => setSelectedGenerationStyle(event.target.value)}
                      options={styleOptions}
                    />
                  </label>
                </div>

                {(disabledWizardEntityCount > 0 || selectedWizardEntityInvalid) && (
                  <div className="rounded-md border border-amber-400/25 bg-amber-500/10 px-3 py-2 text-xs leading-5 text-amber-100">
                    角色三视图只能用于单一角色，群体/复合角色请先在实体库拆分；否则容易生成多人拼接图、性别错乱或前后视图不是同一人物。
                  </div>
                )}

                {selectedWizardEntity && (
                  <div className="rounded-md border border-emerald-400/20 bg-emerald-500/10 px-3 py-2 text-xs leading-5 text-emerald-50">
                    已绑定：{selectedWizardEntity.name}
                  </div>
                )}

                <div className="space-y-2 rounded-md border border-white/10 bg-white/[0.03] p-3">
                  <div className="flex items-center justify-between text-xs text-white/55">
                    <span>必备视图进度</span>
                    <span>{completedViewCount}/{totalRequiredViewCount}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-white/10">
                    <div className="h-full rounded-full bg-violet-400" style={{ width: `${wizardProgress}%` }} />
                  </div>
                </div>

                <Button
                  className="w-full bg-violet-600 hover:bg-violet-700"
                  disabled={!selectedEntityId || generatingViews || selectedWizardEntityInvalid}
                  onClick={generateMissingViews}
                >
                  {generatingViews ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                  生成缺失视图
                </Button>
              </div>

              <div className="space-y-3">
                <ImageStyleTemplatePicker
                  templates={styleTemplates}
                  value={selectedGenerationStyle}
                  onChange={setSelectedGenerationStyle}
                  toMediaUrl={toMediaUrl}
                  recommendedFor={selectedEntityType}
                  compact
                  layout="inline"
                />

                {(activePreset.recommended_aspect_ratios?.length || activePreset.style_examples?.length) && (
                  <div className="grid grid-cols-1 gap-3 lg:grid-cols-[220px_1fr]">
                    {activePreset.recommended_aspect_ratios?.length ? (
                      <div className="rounded-lg border border-cyan-300/20 bg-cyan-500/10 p-3">
                        <div className="text-xs text-cyan-100/70">推荐比例</div>
                        <div className="mt-1 text-sm font-medium text-cyan-50">
                          推荐比例：{activePreset.recommended_aspect_ratios.join('、')}
                        </div>
                      </div>
                    ) : null}
                    {activePreset.style_examples?.length ? (
                      <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                        <div className="mb-2 text-xs text-white/45">题材模板示例</div>
                        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                          {activePreset.style_examples.slice(0, 4).map((example) => {
                            const sampleUrl = toMediaUrl(example.sample_url);
                            return (
                              <div
                                key={`${example.style}-${example.label}`}
                                data-testid="asset-style-example"
                                className="flex gap-3 rounded-md border border-white/10 bg-white/[0.04] p-2"
                              >
                                {sampleUrl ? (
                                  <img src={sampleUrl} alt="" className="h-12 w-12 shrink-0 rounded object-cover" />
                                ) : (
                                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded bg-white/5">
                                    <Palette className="h-5 w-5 text-white/30" />
                                  </div>
                                )}
                                <div className="min-w-0">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className="text-sm font-medium text-white">{example.label}</span>
                                    {example.aspect_ratio && (
                                      <Badge variant="outline" className="border-cyan-300/30 text-cyan-100 text-[10px]">
                                        {example.aspect_ratio}
                                      </Badge>
                                    )}
                                  </div>
                                  {example.prompt && (
                                    <div className="mt-1 line-clamp-1 text-xs leading-5 text-white/45">{example.prompt}</div>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ) : null}
                  </div>
                )}

              </div>
            </div>

            <div className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="text-sm font-medium text-white">必备视图参考</div>
                  <div className="mt-1 text-xs text-white/45">优先锁定可复用的定稿图，后续镜头会继承这些视觉参考。</div>
                </div>
                <Badge variant="outline" className="border-white/20 text-white/65">
                  {completedViewCount}/{totalRequiredViewCount} 已完成
                </Badge>
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
                {activePreset.views.map((view) => {
                  const matchedAsset = viewAssetsByKey[view.key];
                  const previewUrl = toMediaUrl(matchedAsset?.thumbnail_url || matchedAsset?.url);
                  const failure = matchedAsset ? assetFailureInfo(matchedAsset) : null;
                  return (
                    <div
                      key={view.key}
                      data-testid={`asset-wizard-view-${view.key}`}
                      className="flex min-h-[340px] flex-col overflow-hidden rounded-lg border border-white/10 bg-black/20"
                    >
                      <div className="relative flex h-56 items-center justify-center bg-black/35">
                        {previewUrl ? (
                          <AssetImagePreview
                            src={previewUrl}
                            fallbackSrc={toMediaUrl(matchedAsset?.url)}
                            alt={matchedAsset?.name || view.label}
                            className="h-full w-full object-contain"
                          />
                        ) : (
                          <ImageIcon className="h-8 w-8 text-white/25" />
                        )}
                        {matchedAsset && (
                          <div className="absolute right-2 top-2 flex items-center gap-1 rounded-md border border-white/10 bg-slate-950/80 p-1 shadow-lg backdrop-blur">
                            {previewUrl && (
                              <Button
                                type="button"
                                variant="outline"
                                size="icon"
                                aria-label="预览"
                                title="预览"
                                className="h-8 w-8 rounded-md border-white/15 bg-white/5 p-0 text-white hover:bg-white/15"
                                onClick={() => previewAssetMedia(matchedAsset)}
                              >
                                <Eye className="h-3.5 w-3.5" />
                              </Button>
                            )}
                            <Button
                              type="button"
                              variant="outline"
                              size="icon"
                              aria-label="编辑"
                              title="编辑"
                              className="h-8 w-8 rounded-md border-white/15 bg-white/5 p-0 text-white hover:bg-white/15"
                              onClick={() => startEdit(matchedAsset)}
                            >
                              <Edit3 className="h-3.5 w-3.5" />
                            </Button>
                            {!matchedAsset.is_locked && (
                              <Button
                                type="button"
                                variant="outline"
                                size="icon"
                                aria-label="锁定"
                                title="锁定为定稿"
                                className="h-8 w-8 rounded-md border-emerald-500/40 bg-emerald-500/10 p-0 text-emerald-200 hover:bg-emerald-500/20"
                                onClick={() => lockAsset(matchedAsset.id)}
                              >
                                <Lock className="h-3.5 w-3.5" />
                              </Button>
                            )}
                            {failure?.retryable && (
                              <Button
                                type="button"
                                variant="outline"
                                size="icon"
                                aria-label="重试生成"
                                title="重试生成"
                                className="h-8 w-8 rounded-md border-red-300/40 bg-red-500/10 p-0 text-red-100 hover:bg-red-500/20"
                                disabled={retryingAssetId === matchedAsset.id}
                                onClick={() => retryAssetGeneration(matchedAsset)}
                              >
                                {retryingAssetId === matchedAsset.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                              </Button>
                            )}
                          </div>
                        )}
                      </div>
                      <div className="flex flex-1 flex-col gap-2.5 p-3">
                        <div className="flex items-center justify-between gap-2">
                          <div className="text-base font-semibold text-white">{view.label}</div>
                          {matchedAsset?.is_locked ? (
                            <Badge variant="outline" className="shrink-0 border-emerald-400/40 px-2 py-0.5 text-xs text-emerald-200">已定稿</Badge>
                          ) : failure ? (
                            <Badge variant="outline" className="shrink-0 border-red-400/40 px-2 py-0.5 text-xs text-red-200">生成失败</Badge>
                          ) : previewUrl ? (
                            <Badge variant="outline" className="shrink-0 border-cyan-400/40 px-2 py-0.5 text-xs text-cyan-100">已生成</Badge>
                          ) : (
                            <Badge variant="outline" className="shrink-0 border-amber-400/40 px-2 py-0.5 text-xs text-amber-100">待补齐</Badge>
                          )}
                        </div>
                        <div className="line-clamp-2 text-xs leading-5 text-white/45">
                          {view.aspect_ratio ? `推荐比例 ${view.aspect_ratio}。` : ''}
                          {view.prompt_hint || '用于保持后续镜头视觉一致。'}
                        </div>
                        {failure && (
                          <div className="rounded-md border border-red-400/20 bg-red-500/10 p-2 text-xs leading-5 text-red-100">
                            {failure.error}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white/5 border-white/10">
          <CardContent className="p-4 space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-[1fr_180px_180px_150px_auto_auto] gap-3">
              <div className="relative">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-white/40" />
                <Input
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') loadAssets();
                  }}
                  placeholder="搜索资产名称、描述、标签"
                  className="pl-9 bg-white/5 border-white/10 text-white"
                />
              </div>
              <Select value={selectedCategory} onChange={(event) => setSelectedCategory(event.target.value)} options={categoryOptions} />
              <Select value={selectedProjectId} onChange={(event) => setSelectedProjectId(event.target.value)} options={projectOptions} />
              <Select value={selectedScope} onChange={(event) => setSelectedScope(event.target.value)} options={scopeOptions} />
              <label className="flex items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-white/70">
                <input type="checkbox" checked={includePublic} onChange={(event) => setIncludePublic(event.target.checked)} />
                包含公开
              </label>
              <Button variant="outline" className="border-white/20 text-white" onClick={loadAssets}>
                搜索
              </Button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <Select
                value={selectedNovelId}
                onChange={(event) => setSelectedNovelId(event.target.value)}
                options={[{ value: '', label: '全部小说' }, ...novels.map((novel) => ({ value: novel.id, label: novel.title }))]}
              />
              <Select
                value={selectedChapterId}
                onChange={(event) => setSelectedChapterId(event.target.value)}
                options={[
                  { value: '', label: '全部章节' },
                  ...chapters.map((chapter) => ({
                    value: chapter.id,
                    label: formatChapterLabel(chapter),
                  })),
                ]}
              />
              <Select
                value={selectedScriptId}
                onChange={(event) => setSelectedScriptId(event.target.value)}
                options={[{ value: '', label: '全部剧本' }, ...scripts.map((script) => ({ value: script.id, label: script.title }))]}
              />
              <Select
                value={selectedEntityId}
                onChange={(event) => setSelectedEntityId(event.target.value)}
                options={[
                  { value: '', label: '全部实体' },
                  ...entities.map((entity) => ({ value: entity.id, label: `${entity.name} · ${entityTypeLabel(entity.entity_type)}` })),
                ]}
              />
            </div>
            <div className="text-xs text-white/45">
              选择小说、章节、剧本或实体时，会同时展示可复用的全局资产；需要只看绑定资产时，使用“仅小说/仅章节/仅剧本/仅实体”范围。
            </div>
            {selectedAssets.size > 0 && (
              <div className="flex flex-wrap items-center gap-2 rounded-md border border-violet-400/25 bg-violet-500/10 px-3 py-2">
                <span className="text-sm text-white/70">已选择 {selectedAssets.size} 个资产</span>
                <Button variant="outline" size="sm" className="border-emerald-400/40 text-emerald-200" onClick={batchLockAssets}>
                  <Lock className="mr-1 h-3 w-3" />
                  批量锁定
                </Button>
                <Button variant="outline" size="sm" className="border-amber-400/40 text-amber-200" onClick={batchUnlockAssets}>
                  <Unlock className="mr-1 h-3 w-3" />
                  批量解锁
                </Button>
                <Button variant="outline" size="sm" className="border-red-300/40 text-red-200" onClick={batchArchiveAssets}>
                  <Trash2 className="mr-1 h-3 w-3" />
                  批量归档
                </Button>
                <Button variant="outline" size="sm" className="border-cyan-300/40 text-cyan-100" onClick={batchSetAssetsToCurrentScope}>
                  批量设为当前范围
                </Button>
                <Button variant="outline" size="sm" className="border-white/20 text-white" onClick={batchSetAssetTags}>
                  批量标签
                </Button>
                <Button variant="outline" size="sm" className="border-white/20 text-white" onClick={() => setSelectedAssets(new Set())}>
                  取消选择
                </Button>
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              {QUICK_PRESET_FILTERS.map((preset) => (
                <Button
                  key={preset.label}
                  type="button"
                  size="sm"
                  variant={selectedCategory === preset.category ? 'default' : 'outline'}
                  className={selectedCategory === preset.category ? 'bg-violet-600 hover:bg-violet-700' : 'border-white/20 text-white'}
                  onClick={() => setSelectedCategory(preset.category)}
                >
                  {preset.label}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>

        {message && (
          <div className="rounded-md border border-white/10 bg-white/5 px-4 py-3 text-sm text-white/75">
            {message}
          </div>
        )}

        {formOpen && (
          <Card ref={formSectionRef} className="scroll-mt-6 bg-white/5 border-white/10">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-white">
                <Boxes className="h-5 w-5 text-violet-300" />
                {editingId ? '编辑资产' : '新建资产'}
              </CardTitle>
              <Button variant="ghost" size="sm" className="text-white/60" onClick={resetForm}>
                <X className="h-4 w-4" />
              </Button>
            </CardHeader>
            <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Input ref={nameInputRef} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="资产名称" className="bg-white/5 border-white/10 text-white" />
              <Select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} options={categories.map((category) => ({ value: category.name, label: category.name_cn || category.name }))} />
              <Select value={form.asset_type} onChange={(event) => setForm({ ...form, asset_type: event.target.value })} options={ASSET_TYPE_OPTIONS} />
              <Select value={form.project_id} onChange={(event) => setForm({ ...form, project_id: event.target.value })} options={formProjectOptions} />
              <Select value={form.novel_id} onChange={(event) => setForm({ ...form, novel_id: event.target.value, chapter_id: '', script_id: '', entity_id: '' })} options={[{ value: '', label: '不绑定小说' }, ...novels.map((novel) => ({ value: novel.id, label: novel.title }))]} />
              <Select value={form.chapter_id} onChange={(event) => setForm({ ...form, chapter_id: event.target.value })} options={[{ value: '', label: '不绑定章节' }, ...chapters.map((chapter) => ({ value: chapter.id, label: chapter.title }))]} />
              <Select value={form.script_id} onChange={(event) => setForm({ ...form, script_id: event.target.value })} options={[{ value: '', label: '不绑定剧本' }, ...scripts.map((script) => ({ value: script.id, label: script.title }))]} />
              <Select value={form.entity_id} onChange={(event) => setForm({ ...form, entity_id: event.target.value })} options={[{ value: '', label: '不绑定实体' }, ...entities.map((entity) => ({ value: entity.id, label: `${entity.name} · ${entityTypeLabel(entity.entity_type)}` }))]} />
              <AssetMediaField
                label="资源文件"
                field="url"
                value={form.url}
                assetType={form.asset_type}
                uploading={uploadingField === 'url'}
                previewUrl={resourcePreviewUrl}
                onValueChange={(value) => setForm({ ...form, url: value })}
                onUpload={(file) => uploadAssetMedia(file, 'url')}
                onOpen={() => previewFormMedia(form.name || '资产资源预览', form.asset_type, form.url, form.thumbnail_url, form.description)}
              />
              <AssetMediaField
                label="缩略图"
                field="thumbnail_url"
                value={form.thumbnail_url}
                assetType="image"
                uploading={uploadingField === 'thumbnail_url'}
                previewUrl={thumbnailPreviewUrl}
                onValueChange={(value) => setForm({ ...form, thumbnail_url: value })}
                onUpload={(file) => uploadAssetMedia(file, 'thumbnail_url')}
                onOpen={() => previewFormMedia(form.name || '资产缩略图预览', 'image', form.thumbnail_url, form.url, form.description)}
              />
              <Input value={form.tags} onChange={(event) => setForm({ ...form, tags: event.target.value })} placeholder="业务标签，例如：主角，夜景，法器" className="bg-white/5 border-white/10 text-white" />
              <Input value={form.style_tags} onChange={(event) => setForm({ ...form, style_tags: event.target.value })} placeholder="风格标签，例如：动漫，玄幻，冷色" className="bg-white/5 border-white/10 text-white" />
              <Textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="资产用途、视觉 DNA、适用镜头或一致性说明" className="md:col-span-2" />
              <Textarea
                value={form.prompt_template}
                onChange={(event) => setForm({ ...form, prompt_template: event.target.value })}
                placeholder="生成提示词，可使用 {{character}} / {{scene}} / {{prop}} / {{aspect_ratio}} 等变量"
                className="md:col-span-2"
              />
              <div className="md:col-span-2 rounded-lg border border-violet-300/15 bg-violet-500/10 p-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-white">AI 辅助说明</div>
                    <div className="mt-1 text-xs leading-5 text-white/50">
                      {selectedFormEntity
                        ? `当前资产会绑定到「${selectedFormEntity.name}」，后续可在上方制片向导补齐三视图/四视图/多视图。`
                        : '建议先绑定小说对象，再用上方制片向导生成参考图；这里可补充视觉 DNA、用途和提示词。'}
                    </div>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="border-white/20 text-white"
                    onClick={() => setShowAdvancedFields((value) => !value)}
                  >
                    {showAdvancedFields ? '收起高级设置' : '高级设置'}
                  </Button>
                </div>
              </div>
              {editingAsset && editingAsset.entity_id && (editingAsset.generation_params?.view_key || editingAsset.generation_params?.asset_subtype || editingAsset.generation_params?.view_angle) && (
                <div className="md:col-span-2 space-y-3 rounded-lg border border-pink-300/20 bg-pink-500/10 p-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium text-white">AI 重新生成当前视图</div>
                      <div className="mt-1 text-xs leading-5 text-white/50">
                        会沿用当前资产绑定的小说对象、视图方向、角色/场景/道具约束和参考血缘，生成一个新版本；旧版本仍保留在历史中。
                      </div>
                    </div>
                    <Button
                      type="button"
                      size="sm"
                      className="bg-pink-600 hover:bg-pink-700"
                      disabled={regeneratingAssetId === editingAsset.id}
                      onClick={() => regenerateAsset(editingAsset)}
                    >
                      {regeneratingAssetId === editingAsset.id ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <Sparkles className="mr-1 h-3.5 w-3.5" />}
                      AI重新生成
                    </Button>
                  </div>
                  <ImageStyleTemplatePicker
                    templates={styleTemplates}
                    value={selectedGenerationStyle}
                    onChange={setSelectedGenerationStyle}
                    toMediaUrl={toMediaUrl}
                    recommendedFor={editingAsset.entity_type || editingAsset.category}
                    title="重新生成风格"
                    compact
                    layout="inline"
                  />
                </div>
              )}
              {showAdvancedFields && (
                <div className="md:col-span-2 grid grid-cols-1 gap-3 rounded-lg border border-white/10 bg-black/20 p-3">
                  <div>
                    <div className="text-sm font-medium text-white">高级设置</div>
                    <div className="mt-1 text-xs text-white/45">
                      这些字段主要给需要接入自定义模板、批量生成或调试生成链路的人使用；普通创作不需要维护。
                    </div>
                  </div>
                  <Textarea
                    value={form.variables}
                    onChange={(event) => setForm({ ...form, variables: event.target.value })}
                    placeholder={'变量配置 JSON，例如：[{ "name": "front_view", "label": "正面视图" }]'}
                    className="min-h-24 font-mono text-xs"
                  />
                  <Textarea
                    value={form.shot_template}
                    onChange={(event) => setForm({ ...form, shot_template: event.target.value })}
                    placeholder={'视图/比例配置 JSON，例如：{ "views": [{ "label": "正面" }], "aspect_ratios": [{ "ratio": "9:16" }] }'}
                    className="min-h-28 font-mono text-xs"
                  />
                  <Textarea
                    value={form.source_prompt}
                    onChange={(event) => setForm({ ...form, source_prompt: event.target.value })}
                    placeholder="参考图或素材来源提示词，可选"
                  />
                  <Textarea
                    value={form.generation_params}
                    onChange={(event) => setForm({ ...form, generation_params: event.target.value })}
                    placeholder={'生成参数 JSON，可选，例如：{ "source": "starter", "editable": true }'}
                    className="min-h-20 font-mono text-xs"
                  />
                </div>
              )}
              <label className="flex items-center gap-2 text-sm text-white/70">
                <input type="checkbox" checked={form.is_public} onChange={(event) => setForm({ ...form, is_public: event.target.checked })} />
                允许公开复用
              </label>
              <div className="flex justify-end gap-2 md:col-span-2">
                <Button variant="outline" className="border-white/20 text-white" onClick={resetForm}>取消</Button>
                <Button className="bg-violet-600 hover:bg-violet-700" onClick={saveAsset} disabled={saving}>
                  {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                  保存资产
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {loading ? (
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-8 text-center text-white/60">
              <Loader2 className="mx-auto mb-3 h-6 w-6 animate-spin" />
              正在加载资产...
            </CardContent>
          </Card>
        ) : visibleAssets.length === 0 ? (
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-8 text-center">
              <Archive className="mx-auto mb-3 h-8 w-8 text-white/30" />
              <div className="text-white">暂无资产</div>
              <div className="mt-1 text-sm text-white/50">可先登记角色参考图、场景参考图、道具图或音效素材。</div>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {visibleAssets.map((asset) => {
              const Icon = categoryIcon(asset.category, asset.asset_type);
              const previewUrl = toMediaUrl(asset.thumbnail_url || asset.url);
              const promptSummary = compactText(asset.prompt_template || asset.source_prompt);
              const viewItems = readViewItems(asset.shot_template);
              const ratioItems = readAspectRatios(asset.shot_template);
              const isStarter = asset.source_url?.startsWith('starter:') || asset.generation_params?.source === 'starter';
              const failure = assetFailureInfo(asset);
              const consistencyScore = visualConsistencyScore(asset);
              const lineageInfo = visualLineageInfo(asset);
              return (
                <Card key={asset.id} data-testid="asset-card" className="overflow-hidden border-white/10 bg-white/5 md:grid md:grid-cols-[168px_1fr]">
                  <div className="h-36 bg-black/30 md:h-full md:min-h-44">
                    {previewUrl && ((asset.asset_type || 'image') === 'image' || isImageLikeUrl(asset.url) || isImageLikeUrl(asset.thumbnail_url)) ? (
                      <AssetImagePreview
                        src={previewUrl}
                        fallbackSrc={toMediaUrl(asset.url)}
                        alt={asset.name}
                        className="h-full w-full object-contain"
                      />
                    ) : (
                      <div className="flex h-full items-center justify-center">
                        <Icon className="h-10 w-10 text-white/30" />
                      </div>
                    )}
                  </div>
                  <CardContent className="space-y-3 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex min-w-0 flex-wrap items-center gap-2">
                          <div className="truncate font-medium text-white">{asset.name}</div>
                          {isStarter && (
                            <Badge variant="outline" className="border-violet-300/40 text-violet-100 text-[10px]">系统预置 · 可编辑</Badge>
                          )}
                          {failure && (
                            <Badge variant="outline" className="border-red-400/40 text-red-200 text-[10px]">生成失败</Badge>
                          )}
                        </div>
                        <div className="mt-1 text-xs text-white/45">{categoryLabel(asset.category)} · {projectLabel(asset.project_id)} · {scopeLabel(asset)}</div>
                        <div className="mt-1 text-[11px] text-white/30">
                          {[
                            novelLabel(asset.novel_id),
                            chapterLabel(asset.chapter_id),
                            scriptLabel(asset.script_id),
                            entityLabel(asset.entity_id),
                          ].filter(Boolean).join(' · ')}
                        </div>
                      </div>
                      <Badge variant="outline" className="text-white/70 border-white/30 shrink-0">
                        {assetTypeLabel(asset.asset_type)}
                      </Badge>
                    </div>
                    {asset.description && (
                      <p className="line-clamp-2 text-sm text-white/60">{asset.description}</p>
                    )}
                    {failure && (
                      <div className="rounded-md border border-red-400/20 bg-red-500/10 p-2 text-xs leading-5 text-red-100">
                        <div className="mb-1 flex flex-wrap items-center gap-2 text-[11px] text-red-100/80">
                          <span>生成失败</span>
                          {failure.viewLabel && (
                            <Badge variant="outline" className="border-red-300/30 text-red-100 text-[10px]">
                              {failure.viewLabel}
                            </Badge>
                          )}
                        </div>
                        {failure.error}
                      </div>
                    )}
                    {consistencyScore !== null && (
                      <div className="rounded-md border border-emerald-400/20 bg-emerald-500/10 px-2 py-1.5 text-xs text-emerald-50">
                        一致性 {consistencyScore}
                      </div>
                    )}
                    {lineageInfo && (
                      <div className="rounded-md border border-cyan-400/20 bg-cyan-500/10 px-2 py-1.5 text-xs leading-5 text-cyan-50">
                        {lineageInfo.contractId && <div>视觉契约 {lineageInfo.contractId}</div>}
                        {lineageInfo.referenceLabel && <div>继承{lineageInfo.referenceLabel}参考</div>}
                      </div>
                    )}
                    {promptSummary && (
                      <div className="rounded-md border border-violet-400/20 bg-violet-500/10 p-2 text-xs leading-5 text-violet-50">
                        <div className="mb-1 text-[11px] text-violet-200/80">提示词</div>
                        {promptSummary}
                      </div>
                    )}
                    {viewItems.length > 0 && (
                      <div className="space-y-1">
                        <div className="text-[11px] text-white/35">视图/镜头结构</div>
                        <div className="flex flex-wrap gap-1">
                          {viewItems.slice(0, 5).map((view: any, index: number) => (
                            <Badge key={`${asset.id}-view-${index}`} variant="outline" className="border-white/20 text-white/65">
                              {view?.label || view?.name || view?.camera_angle || `视图 ${index + 1}`}
                            </Badge>
                          ))}
                          {viewItems.length > 5 && (
                            <Badge variant="outline" className="border-white/20 text-white/45">+{viewItems.length - 5}</Badge>
                          )}
                        </div>
                      </div>
                    )}
                    {ratioItems.length > 0 && (
                      <div className="space-y-1">
                        <div className="text-[11px] text-white/35">推荐画面比例</div>
                        <div className="flex flex-wrap gap-1">
                          {ratioItems.slice(0, 6).map((ratio: any, index: number) => (
                            <Badge key={`${asset.id}-ratio-${index}`} variant="outline" className="border-cyan-300/40 text-cyan-100">
                              {String(ratio)}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                    <div className="flex flex-wrap gap-1">
                      {(asset.tags || []).slice(0, 4).map((tag) => (
                        <Badge key={tag} variant="outline" className="border-violet-300/40 text-violet-100">{tag}</Badge>
                      ))}
                      {(asset.style_tags || []).slice(0, 3).map((tag) => (
                        <Badge key={tag} variant="outline" className="border-cyan-300/40 text-cyan-100">{tag}</Badge>
                      ))}
                    </div>
                    <div className="flex items-center justify-between text-xs text-white/45">
                      <span>引用 {asset.usage_count || 0}</span>
                      <div className="flex items-center gap-2">
                        {(asset as Asset).is_locked && (
                          <span className="flex items-center gap-1 text-violet-400">
                            <Lock className="h-3 w-3" />
                            锁定
                          </span>
                        )}
                        {(asset as Asset).is_final && (
                          <Badge variant="outline" className="border-emerald-500/40 text-emerald-300 text-[10px]">定稿</Badge>
                        )}
                        <span>{(asset as Asset).is_public ? '公开' : '私有'}</span>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <div className="flex items-center gap-1">
                        <input
                          type="checkbox"
                          aria-label={`选择${asset.name}`}
                          checked={selectedAssets.has(asset.id)}
                          onChange={() => toggleAssetSelection(asset.id)}
                          className="rounded border-white/20"
                        />
                      </div>
                      {asset.url && (
                        <Button variant="outline" size="sm" className="border-white/20 text-white" onClick={() => previewAssetMedia(asset)}>
                          <ExternalLink className="mr-1 h-3 w-3" />
                          预览
                        </Button>
                      )}
                      {failure?.retryable && (
                        <Button
                          variant="outline"
                          size="sm"
                          title="重试生成"
                          className="border-red-300/40 text-red-100"
                          disabled={retryingAssetId === asset.id}
                          onClick={() => retryAssetGeneration(asset)}
                        >
                          {retryingAssetId === asset.id ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <RefreshCw className="mr-1 h-3 w-3" />}
                          重试生成
                        </Button>
                      )}
                      {asset.entity_id && (asset.generation_params?.view_key || asset.generation_params?.asset_subtype || asset.generation_params?.view_angle) && (
                        <Button
                          variant="outline"
                          size="sm"
                          title="按当前约束重新生成一个新版本"
                          className="border-pink-300/40 text-pink-100"
                          disabled={regeneratingAssetId === asset.id}
                          onClick={() => regenerateAsset(asset)}
                        >
                          {regeneratingAssetId === asset.id ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <Sparkles className="mr-1 h-3 w-3" />}
                          重生成
                        </Button>
                      )}
                      <Button variant="outline" size="sm" title="编辑资产" className="border-white/20 text-white" onClick={() => startEdit(asset)}>
                        <Edit3 className="mr-1 h-3 w-3" />
                        编辑
                      </Button>
                      {(asset as Asset).is_locked ? (
                        <Button variant="outline" size="sm" title="解锁资产" className="border-amber-500/50 text-amber-300" onClick={() => unlockAsset(asset.id)}>
                          <Unlock className="mr-1 h-3 w-3" />
                          解锁
                        </Button>
                      ) : (
                        <Button variant="outline" size="sm" title="锁定为定稿" className="border-emerald-500/50 text-emerald-300" onClick={() => lockAsset(asset.id)}>
                          <Lock className="mr-1 h-3 w-3" />
                          锁定
                        </Button>
                      )}
                      {asset.entity_id && (
                        <Button variant="outline" size="sm" title="版本历史" className="border-cyan-500/50 text-cyan-300" onClick={() => loadVersionHistory(asset.entity_id!, asset.category)}>
                          <History className="mr-1 h-3 w-3" />
                          历史
                        </Button>
                      )}
                      <Button variant="outline" size="sm" title="升为全局资产" className="border-white/20 text-white" onClick={() => bindAssetScope(asset, 'global')}>
                        全局
                      </Button>
                      <Button variant="outline" size="sm" title="归档资产" className="border-red-300/30 text-red-200" onClick={() => archiveAsset(asset.id)}>
                        <Trash2 className="mr-1 h-3 w-3" />
                        归档
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>
      <MediaPreviewDialog media={previewMedia} onClose={() => setPreviewMedia(null)} />
    </MainLayout>
  );
}

'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { MainLayout } from '@/components/layout/main-layout';
import { ModelCapabilitySelector } from '@/components/model-capability-selector';
import {
  DEFAULT_IMAGE_STYLE_TEMPLATES,
  ImageStyleTemplatePicker,
  type ImageStyleTemplate,
} from '@/components/media/image-style-template-picker';
import { ReferenceImagePreview } from '@/components/media/reference-image-preview';
import { fetchWithAuth } from '@/lib/fetch-with-auth';
import { apiClient } from '@/lib/api-client';
import { useToast } from '@/components/ui/toast';
import {
  getDefaultConfigForCapability,
  SavedModelConfig,
} from '@/lib/model-configs';
import {
  CAMERA_ANGLE_LABELS,
  CAMERA_ANGLE_OPTIONS,
  CAMERA_MOVEMENT_OPTIONS,
  COLOR_GRADING_OPTIONS,
  EMOTION_OPTIONS,
  LIGHTING_OPTIONS,
  STORYBOARD_STYLE_OPTIONS,
  getShotAttributeLabel,
} from '@/lib/shot-labels';
import {
  LayoutGrid,
  Plus,
  Edit2,
  Trash2,
  Search,
  Image as ImageIcon,
  Clock,
  ChevronLeft,
  ChevronRight,
  Copy,
  Download,
  Film,
  Move,
  Eye,
  Sparkles,
  Loader2,
  Save,
  RefreshCw,
  Video,
  X
} from 'lucide-react';

// 分镜数据类型 - 与后端 Shot 模型匹配
interface Shot {
  id: string;
  shot_number: number;
  duration: number;
  prompt: string;
  dialogue?: string;
  visual_description?: string;
  camera_angle?: string;
  video_url?: string;
  audio_url?: string;
  video_status: string;
  audio_status: string;
  image_url?: string;
  image_status?: string;
  image_asset_id?: string;
  // 精细化控制字段
  camera_movement?: string;
  movement_speed?: number;
  emotion?: string;
  emotion_intensity?: number;
  lighting?: string;
  color_grading?: string;
  music_cue?: string;
  sfx_cue?: string;
  keyframes?: any[];
  character_refs?: any[];
  extra_data?: any;
  version?: number;
  created_at: string;
  updated_at: string;
}

// 分镜卡数据类型 - 与后端 Storyboard 模型匹配
interface Storyboard {
  id: string;
  script_id: string;
  novel_id?: string;
  chapter_id?: string;
  title: string;
  description?: string;
  content?: any;
  shot_count: number;
  total_duration: number;
  status: string;
  script_title?: string;
  created_at: string;
  updated_at: string;
}

interface StoryboardMergeResult {
  job_id: string;
  storyboard_id?: string;
  output_url?: string;
  manifest_url?: string;
  srt_url?: string;
  segment_count?: number;
  duration_seconds?: number;
  segments?: any[];
  message?: string;
  selected_shot_ids?: string[];
  selected_shot_numbers?: number[];
  skipped_shot_numbers?: number[];
  version_number?: number;
  parent_job_id?: string;
  render_backend?: string;
  is_real_merged?: boolean;
  render_message?: string;
  created_at?: string;
}

// 剧本数据
interface Script {
  id: string;
  title: string;
  novel_id?: string;
  chapter_id?: string;
  novel_title?: string;
}

interface Novel {
  id: string;
  title: string;
  genre?: string;
}

interface Chapter {
  id: string;
  novel_id?: string;
  title: string;
  chapter_number: number;
}

interface StoryboardTemplateMatch {
  template: {
    id: string;
    name: string;
    description: string;
    shot_count: number;
  };
  score: number;
  reason: string;
}

interface Asset {
  id: string;
  name: string;
  url?: string;
  generation_params?: Record<string, any>;
  is_locked?: boolean;
}

interface EntityAssetsResponse {
  assets: Asset[];
  locked_assets: Asset[];
  total: number;
}

interface AssetViewPreset {
  entity_type: string;
  title: string;
  views: {
    key: string;
    label: string;
  }[];
}

interface ShotReferencedEntity {
  id: string;
  name: string;
  entity_type: 'character' | 'scene' | 'prop';
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const API_ORIGIN = API_BASE.replace(/\/api\/v1\/?$/, '');

const toMediaUrl = (url?: string | null) => {
  if (!url) return '';
  return url.startsWith('/') ? `${API_ORIGIN}${url}` : url;
};

const FALLBACK_VIEW_PRESETS: AssetViewPreset[] = [
  {
    entity_type: 'character',
    title: '角色三视图',
    views: [
      { key: 'front', label: '正面' },
      { key: 'side', label: '侧面' },
      { key: 'back', label: '背面' },
    ],
  },
  {
    entity_type: 'scene',
    title: '场景四视图',
    views: [
      { key: 'establishing', label: '全景定场' },
      { key: 'layout', label: '空间布局' },
      { key: 'detail', label: '关键细节' },
      { key: 'lighting', label: '光影氛围' },
    ],
  },
  {
    entity_type: 'prop',
    title: '道具多视图',
    views: [
      { key: 'main', label: '主视图' },
      { key: 'detail', label: '细节纹理' },
      { key: 'scale', label: '比例参考' },
      { key: 'in_use', label: '使用状态' },
    ],
  },
];

export default function StoryboardsPage() {
  const { toast } = useToast();
  const [storyboards, setStoryboards] = useState<Storyboard[]>([]);
  const [selectedStoryboard, setSelectedStoryboard] = useState<Storyboard | null>(null);
  const [selectedShot, setSelectedShot] = useState<Shot | null>(null);
  const [shots, setShots] = useState<Shot[]>([]);
  const [scripts, setScripts] = useState<Script[]>([]);
  const [novels, setNovels] = useState<Novel[]>([]);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingShots, setLoadingShots] = useState(false);
  const [showNewModal, setShowNewModal] = useState(false);
  const [newStoryboardTitle, setNewStoryboardTitle] = useState('');
  const [newStoryboardScriptId, setNewStoryboardScriptId] = useState('');
  const [smartNovelId, setSmartNovelId] = useState('');
  const [smartChapterId, setSmartChapterId] = useState('');
  const [smartShotCount, setSmartShotCount] = useState(5);
  const [matchedTemplate, setMatchedTemplate] = useState<StoryboardTemplateMatch | null>(null);
  const [newStoryboardStyle, setNewStoryboardStyle] = useState('anime');
  const [generatingStoryboard, setGeneratingStoryboard] = useState(false);
  const [generatingSmartStoryboard, setGeneratingSmartStoryboard] = useState(false);
  const [generatingImage, setGeneratingImage] = useState(false);
  const [lineageNovelId, setLineageNovelId] = useState('');
  const [lineageChapterId, setLineageChapterId] = useState('');
  const [modelConfigs, setModelConfigs] = useState<SavedModelConfig[]>([]);
  const [textModelConfigId, setTextModelConfigId] = useState('');
  const [deleteShotTarget, setDeleteShotTarget] = useState<Shot | null>(null);
  const [deletingShot, setDeletingShot] = useState(false);
  const [deleteStoryboardTarget, setDeleteStoryboardTarget] = useState<Storyboard | null>(null);
  const [deletingStoryboard, setDeletingStoryboard] = useState(false);
  const [confirmGenerateFromScript, setConfirmGenerateFromScript] = useState(false);
  const [pendingGenerateScriptId, setPendingGenerateScriptId] = useState('');
  const [mergingVideos, setMergingVideos] = useState(false);
  const [mergeResult, setMergeResult] = useState<StoryboardMergeResult | null>(null);
  const [selectedMergeShotIds, setSelectedMergeShotIds] = useState<string[]>([]);
  const [mergeVersions, setMergeVersions] = useState<StoryboardMergeResult[]>([]);
  const [loadingMergeVersions, setLoadingMergeVersions] = useState(false);
  const [viewPresets, setViewPresets] = useState<AssetViewPreset[]>(FALLBACK_VIEW_PRESETS);
  const [shotEntityAssetPacks, setShotEntityAssetPacks] = useState<Record<string, EntityAssetsResponse>>({});
  const [imageStyleTemplates, setImageStyleTemplates] = useState<ImageStyleTemplate[]>(DEFAULT_IMAGE_STYLE_TEMPLATES);
  const [shotImageStyle, setShotImageStyle] = useState('anime');

  const getScriptForStoryboard = (storyboard?: Storyboard | null) =>
    storyboard ? scripts.find((script) => script.id === storyboard.script_id) : undefined;

  const getStoryboardChapterId = (storyboard?: Storyboard | null) =>
    storyboard?.chapter_id || storyboard?.content?.chapter_id || getScriptForStoryboard(storyboard)?.chapter_id || '';

  const getStoryboardNovelId = (storyboard?: Storyboard | null) =>
    storyboard?.novel_id || storyboard?.content?.novel_id || getScriptForStoryboard(storyboard)?.novel_id || '';

  const getNovelLabel = (novelId?: string) =>
    novels.find((novel) => novel.id === novelId)?.title || (novelId ? `小说 ${novelId.slice(0, 8)}...` : '未绑定小说');

  const getChapterLabel = (chapterId?: string) => {
    const chapter = chapters.find((item) => item.id === chapterId);
    return chapter ? formatChapterLabel(chapter) : chapterId ? `章节 ${chapterId.slice(0, 8)}...` : '未绑定章节';
  };

  const formatChapterLabel = (chapter: Chapter) => {
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
    return `第${chapter.chapter_number || 1}章${title ? ` ${title}` : ''}`;
  };

  const getScriptChapterId = (script?: Script | null) => script?.chapter_id || '';
  const getScriptNovelId = (script?: Script | null) => script?.novel_id || '';

  const filteredSmartScripts = scripts.filter((script) => {
    const scriptNovelId = getScriptNovelId(script);
    const scriptChapterId = getScriptChapterId(script);
    if (smartNovelId && scriptNovelId && scriptNovelId !== smartNovelId) return false;
    if (smartChapterId) return !scriptChapterId || scriptChapterId === smartChapterId;
    if (smartNovelId) return !scriptNovelId || scriptNovelId === smartNovelId;
    return true;
  });

  const refNames = (refs?: any[]) =>
    (refs || [])
      .map((ref) => ref?.name || ref?.character_name || ref?.title)
      .filter(Boolean)
      .join('、');

  const getShotEntityRefs = (shot?: Shot | null) => {
    const extra = shot?.extra_data || {};
    const entityRefs = extra.entity_refs || {};
    return {
      characters: shot?.character_refs?.length ? shot.character_refs : (entityRefs.characters || []),
      scenes: extra.scene_refs || entityRefs.scenes || [],
      props: extra.prop_refs || entityRefs.props || [],
      events: extra.event_refs || entityRefs.events || [],
      subtitle: extra.subtitle_text || shot?.dialogue,
    };
  };

  const getRefId = (ref: any) => ref?.entity_id || ref?.story_entity_id || (ref?.entity_type ? ref?.id : '');

  const getRefName = (ref: any) => ref?.name || ref?.entity_name || ref?.character_name || ref?.title || '';

  const getShotReferencedEntities = (shot?: Shot | null): ShotReferencedEntity[] => {
    const refs = getShotEntityRefs(shot);
    const seen = new Set<string>();
    const result: ShotReferencedEntity[] = [];
    const append = (items: any[], entityType: ShotReferencedEntity['entity_type']) => {
      for (const item of items || []) {
        const id = getRefId(item);
        if (!id || seen.has(id)) continue;
        seen.add(id);
        result.push({
          id,
          name: getRefName(item) || `${entityType} ${id.slice(0, 8)}`,
          entity_type: entityType,
        });
      }
    };
    append(refs.characters || [], 'character');
    append(refs.scenes || [], 'scene');
    append(refs.props || [], 'prop');
    return result;
  };

  const assetViewKey = (asset?: Asset) => (
    asset?.generation_params?.view_key || asset?.generation_params?.asset_subtype || ''
  );

  const assetWizardHref = (entity: ShotReferencedEntity) => {
    const params = new URLSearchParams();
    const novelId = getStoryboardNovelId(selectedStoryboard);
    if (novelId) params.set('novel_id', novelId);
    params.set('entity_type', entity.entity_type);
    params.set('entity_id', entity.id);
    return `/assets?${params.toString()}`;
  };

  const renderShotMultiviewStatus = (shot?: Shot | null) => {
    const entities = getShotReferencedEntities(shot);
    if (!entities.length) return null;

    return (
      <div data-testid="shot-multiview-status" className="mb-4 rounded-lg border border-cyan-400/20 bg-cyan-500/10 p-3">
        <div className="mb-2 flex items-center gap-2 text-sm font-medium text-white">
          <ImageIcon className="h-4 w-4 text-cyan-100" />
          参考资产完整度
        </div>
        <div className="space-y-2">
          {entities.map((entity) => {
            const preset = viewPresets.find((item) => item.entity_type === entity.entity_type)
              || FALLBACK_VIEW_PRESETS.find((item) => item.entity_type === entity.entity_type);
            if (!preset) return null;
            const pack = shotEntityAssetPacks[entity.id] || { assets: [], locked_assets: [], total: 0 };
            const lockedKeys = new Set((pack.locked_assets || []).map(assetViewKey).filter(Boolean));
            const generatedKeys = new Set((pack.assets || []).map(assetViewKey).filter(Boolean));
            const lockedCount = preset.views.filter((view) => lockedKeys.has(view.key)).length;
            const missingLabels = preset.views
              .filter((view) => !lockedKeys.has(view.key) && !generatedKeys.has(view.key))
              .map((view) => view.label);
            return (
              <div key={entity.id} className="rounded-md border border-white/10 bg-black/20 px-3 py-2 text-xs">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-white/80">
                    {entity.name} · {preset.title} · {lockedCount}/{preset.views.length} 已定稿
                  </div>
                  <Link className="text-cyan-100 hover:text-white" href={assetWizardHref(entity)}>
                    补齐参考图
                  </Link>
                </div>
                {missingLabels.length > 0 ? (
                  <div className="mt-1 text-amber-100">待补齐：{missingLabels.join('、')}</div>
                ) : (
                  <div className="mt-1 text-emerald-200">必备视图已补齐，可用于后续视频一致性生成。</div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const videoGenerationHref = (shot?: Shot) => {
    if (!selectedStoryboard) return '/video-generation';
    const params = new URLSearchParams();
    const novelId = getStoryboardNovelId(selectedStoryboard);
    const chapterId = getStoryboardChapterId(selectedStoryboard);
    if (novelId) params.set('novel_id', novelId);
    if (chapterId) params.set('chapter_id', chapterId);
    if (selectedStoryboard.script_id) params.set('script_id', selectedStoryboard.script_id);
    params.set('storyboard_id', selectedStoryboard.id);
    if (shot?.id) params.set('shot_id', shot.id);
    return `/video-generation?${params.toString()}`;
  };

  const getReferenceImageStatusText = (shot?: Shot | null) => {
    if (!shot) return '';
    const errorMessage = shot.extra_data?.image_generation_error;
    if (shot.image_status === 'succeeded' && shot.image_url) {
      return '参考图已生成，可用于保持后续图生视频画面一致。';
    }
    if (shot.image_status === 'failed') {
      return errorMessage || '参考图生成失败，请检查图像模型配置、提示词或重新生成。';
    }
    if (shot.image_status === 'generating') {
      return generatingImage
        ? '正在等待图像模型返回图片，请稍候。'
        : '上一次任务已提交但尚未返回图片；如果长时间无结果，可以重新生成。';
    }
    if (shot.image_status === 'pending') {
      return '尚未生成参考图。';
    }
    return '';
  };

  const handleGenerateShotImage = async (shotId: string) => {
    setGeneratingImage(true);
    try {
      const response = await fetchWithAuth(`${API_BASE}/shots/${shotId}/generate-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ style: shotImageStyle }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || data.message || '参考图生成失败，请检查图像模型配置。');
      }

      if (data.status === 'succeeded' && data.image_url) {
        setShots(prev => prev.map(shot => (
          shot.id === shotId
            ? { ...shot, image_url: data.image_url, image_status: 'succeeded', image_asset_id: data.image_asset_id }
            : shot
        )));
        setSelectedShot(prev => prev && prev.id === shotId
          ? { ...prev, image_url: data.image_url, image_status: 'succeeded', image_asset_id: data.image_asset_id }
          : prev
        );
        toast({
          title: '参考图已生成',
          description: data.model ? `已使用图像模型 ${data.model}` : undefined,
          type: 'success',
        });
        setGeneratingImage(false);
        return;
      }

      setSelectedShot(prev => prev && prev.id === shotId ? { ...prev, image_status: data.status || 'generating' } : prev);
      toast({
        title: '参考图任务已提交',
        description: data.message || '正在等待图像模型返回结果。',
        type: 'info',
      });
      pollShotImage(shotId);
    } catch (err: any) {
      console.error("Image generation failed:", err);
      const message = err?.message || '请检查图像模型配置和后端服务日志。';
      setShots(prev => prev.map(shot => (
        shot.id === shotId
          ? { ...shot, image_status: 'failed', extra_data: { ...(shot.extra_data || {}), image_generation_error: message } }
          : shot
      )));
      setSelectedShot(prev => prev && prev.id === shotId
        ? { ...prev, image_status: 'failed', extra_data: { ...(prev.extra_data || {}), image_generation_error: message } }
        : prev
      );
      toast({
        title: '生成参考图失败',
        description: message,
        type: 'error',
      });
      setGeneratingImage(false);
    }
  };

  const pollShotImage = async (shotId: string) => {
    for (let i = 0; i < 60; i++) {
      await new Promise(r => setTimeout(r, 2000));
      try {
        const res = await fetchWithAuth(`${API_BASE}/shots/${shotId}`);
        if (!res.ok) continue;
        const shot = await res.json();
        if (shot.image_status === "succeeded") {
          const shotsRes = await fetchWithAuth(`${API_BASE}/shots/storyboard/${selectedStoryboard?.id}`);
          if (shotsRes.ok) {
            const updated = await shotsRes.json();
            setShots(updated);
          }
          setSelectedShot(shot);
          toast({ title: '参考图已生成', type: 'success' });
          setGeneratingImage(false);
          return;
        }
        if (shot.image_status === "failed") {
          setSelectedShot(shot);
          toast({
            title: '参考图生成失败',
            description: shot.extra_data?.image_generation_error || '图像模型任务失败，请调整提示词或检查模型配置后重试。',
            type: 'error',
          });
          setGeneratingImage(false);
          return;
        }
      } catch {
        // continue polling
      }
    }
    toast({
      title: '参考图仍在生成',
      description: '暂未拿到图片结果，请稍后刷新镜头或检查图像生成历史。',
      type: 'info',
    });
    setSelectedShot(prev => prev && prev.id === shotId ? { ...prev, image_status: 'generating' } : prev);
    setGeneratingImage(false);
  };

  // 加载剧本列表
  const loadScripts = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/scripts`);
      if (res.ok) {
        const data = await res.json();
        const scriptsList = Array.isArray(data) ? data : [];
        setScripts(scriptsList);
        return scriptsList;
      }
      setScripts([]);
      return [];
    } catch (error) {
      console.error('加载剧本失败:', error);
      setScripts([]);
      return [];
    }
  };

  const loadNovels = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/novels`);
      if (!res.ok) {
        setNovels([]);
        return [];
      }
      const data = await res.json();
      const list = Array.isArray(data) ? data : [];
      setNovels(list);
      return list;
    } catch (error) {
      console.error('加载小说失败:', error);
      setNovels([]);
      return [];
    }
  };

  const loadChapters = async (novelId: string) => {
    if (!novelId) {
      setChapters([]);
      return [];
    }
    try {
      const res = await fetchWithAuth(`${API_BASE}/chapters/novel/${novelId}`);
      if (!res.ok) {
        setChapters([]);
        return [];
      }
      const data = await res.json();
      const list = Array.isArray(data) ? data : [];
      setChapters(list);
      return list;
    } catch (error) {
      console.error('加载章节失败:', error);
      setChapters([]);
      return [];
    }
  };

  const matchSmartTemplate = async (novelId: string, chapterId?: string) => {
    if (!novelId) {
      setMatchedTemplate(null);
      return;
    }
    try {
      const res = await fetchWithAuth(`${API_BASE}/storyboards/templates/match`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          novel_id: novelId,
          chapter_id: chapterId || undefined,
          shot_count: smartShotCount,
          style: newStoryboardStyle || 'anime',
          use_ai_refine: false,
        }),
      });
      if (res.ok) {
        setMatchedTemplate(await res.json());
      } else {
        setMatchedTemplate(null);
      }
    } catch (error) {
      console.error('匹配模板失败:', error);
      setMatchedTemplate(null);
    }
  };

  // 加载分镜列表
  const loadStoryboards = async () => {
    setLoading(true);
    try {
      // 先获取所有剧本
      const scriptsList = await loadScripts();
      const novelList = await loadNovels();

      // 再获取每个剧本的分镜
      const allStoryboards: Storyboard[] = [];
      for (const script of scriptsList) {
        const sbRes = await fetchWithAuth(`${API_BASE}/storyboards/script/${script.id}`);
        if (sbRes.ok) {
          const sbs = await sbRes.json();
          const sbsWithScript = (Array.isArray(sbs) ? sbs : []).map((sb: any) => ({
            ...sb,
            script_title: script.title,
            novel_id: sb.novel_id || script.novel_id,
            chapter_id: sb.chapter_id || sb.content?.chapter_id || script.chapter_id,
            novel_title: script.novel_title,
          }));
          allStoryboards.push(...sbsWithScript);
        }
      }
      setStoryboards(allStoryboards);
      const urlParams = new URLSearchParams(window.location.search);
      const targetNovelId = urlParams.get('novel_id') || '';
      const targetChapterId = urlParams.get('chapter_id') || '';
      const targetStoryboardId = urlParams.get('storyboard_id') || urlParams.get('sb');
      const target = allStoryboards.find((storyboard) => storyboard.id === targetStoryboardId);
      if (target) {
        setSelectedStoryboard(target);
        const novelId = target.novel_id || target.content?.novel_id || scriptsList.find((script) => script.id === target.script_id)?.novel_id || '';
        if (novelId) {
          setLineageNovelId(novelId);
          await loadChapters(novelId);
        }
        setLineageChapterId(target.chapter_id || target.content?.chapter_id || scriptsList.find((script) => script.id === target.script_id)?.chapter_id || '');
      } else if (targetNovelId) {
        setLineageNovelId(targetNovelId);
        await loadChapters(targetNovelId);
        setLineageChapterId(targetChapterId);
      } else if (!lineageNovelId && novelList.length > 0) {
        // Keep list unfiltered by default.
      }
    } catch (error) {
      console.error('加载分镜失败:', error);
      setStoryboards([]);
    } finally {
      setLoading(false);
    }
  };

  // 加载指定分镜的镜头
  const loadShots = async (storyboardId: string) => {
    setLoadingShots(true);
    try {
      const res = await fetchWithAuth(`${API_BASE}/shots/storyboard/${storyboardId}`);
      if (res.ok) {
        const data = await res.json();
        const shotList = Array.isArray(data) ? data : [];
        setShots(shotList);
        setSelectedMergeShotIds(shotList.filter((shot: Shot) => shot.video_url).map((shot: Shot) => shot.id));
      } else {
        setShots([]);
        setSelectedMergeShotIds([]);
      }
    } catch (error) {
      console.error('加载镜头失败:', error);
      setShots([]);
      setSelectedMergeShotIds([]);
    } finally {
      setLoadingShots(false);
    }
  };

  const loadMergeVersions = async (storyboardId: string) => {
    setLoadingMergeVersions(true);
    try {
      const res = await fetchWithAuth(`${API_BASE}/storyboards/${storyboardId}/merge-videos`);
      if (!res.ok) {
        setMergeVersions([]);
        return;
      }
      const data = await res.json();
      setMergeVersions(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('加载合并版本失败:', error);
      setMergeVersions([]);
    } finally {
      setLoadingMergeVersions(false);
    }
  };

  useEffect(() => {
    loadStoryboards();
    loadModelConfigs();
  }, []);

  useEffect(() => {
    const loadViewPresets = async () => {
      try {
        const data = await apiClient.getAssetViewPresets();
        const presets = Array.isArray(data?.presets) ? data.presets : FALLBACK_VIEW_PRESETS;
        setViewPresets(presets.length ? presets : FALLBACK_VIEW_PRESETS);
      } catch (error) {
        console.error('加载多视图预设失败:', error);
        setViewPresets(FALLBACK_VIEW_PRESETS);
      }
    };
    loadViewPresets();
  }, []);

  useEffect(() => {
    const loadImageStyleTemplates = async () => {
      try {
        const data = await apiClient.getAssetStyleTemplates();
        const templates = Array.isArray(data?.templates) ? data.templates : DEFAULT_IMAGE_STYLE_TEMPLATES;
        setImageStyleTemplates(templates.length ? templates : DEFAULT_IMAGE_STYLE_TEMPLATES);
      } catch (error) {
        console.error('加载画面风格模板失败:', error);
        setImageStyleTemplates(DEFAULT_IMAGE_STYLE_TEMPLATES);
      }
    };
    loadImageStyleTemplates();
  }, []);

  useEffect(() => {
    const storyboardStyle = selectedStoryboard?.content?.style;
    if (storyboardStyle) {
      setShotImageStyle(storyboardStyle);
    }
  }, [selectedStoryboard?.id]);

  useEffect(() => {
    const loadShotEntityAssets = async () => {
      const entities = getShotReferencedEntities(selectedShot);
      if (!entities.length) {
        setShotEntityAssetPacks({});
        return;
      }
      const entries = await Promise.all(
        entities.map(async (entity) => {
          try {
            const data = await apiClient.getEntityAssets(entity.id);
            return [entity.id, data as EntityAssetsResponse] as const;
          } catch (error) {
            console.error(`加载镜头实体资产失败: ${entity.name}`, error);
            return [entity.id, { assets: [], locked_assets: [], total: 0 }] as const;
          }
        })
      );
      setShotEntityAssetPacks(Object.fromEntries(entries));
    };
    loadShotEntityAssets();
  }, [selectedShot?.id]);

  const loadModelConfigs = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/llm/configs`);
      if (!res.ok) return;
      const configs = await res.json();
      const list = Array.isArray(configs) ? configs : [];
      setModelConfigs(list);
      const textDefault = getDefaultConfigForCapability(list, 'text');
      if (textDefault) setTextModelConfigId(textDefault.id);
    } catch (error) {
      console.error('加载模型配置失败:', error);
    }
  };

  useEffect(() => {
    if (smartNovelId) {
      loadChapters(smartNovelId);
    } else {
      setChapters([]);
    }
  }, [smartNovelId]);

  useEffect(() => {
    if (!newStoryboardScriptId) return;
    const selectedScript = scripts.find((script) => script.id === newStoryboardScriptId);
    if (!selectedScript) return;
    const scriptNovelId = getScriptNovelId(selectedScript);
    const scriptChapterId = getScriptChapterId(selectedScript);
    if ((smartNovelId && scriptNovelId && scriptNovelId !== smartNovelId) || (smartChapterId && scriptChapterId && scriptChapterId !== smartChapterId)) {
      setNewStoryboardScriptId('');
    }
  }, [smartNovelId, smartChapterId, newStoryboardScriptId, scripts]);

  useEffect(() => {
    if (lineageNovelId) {
      loadChapters(lineageNovelId);
    } else {
      setLineageChapterId('');
    }
  }, [lineageNovelId]);

  useEffect(() => {
    if (smartNovelId) {
      matchSmartTemplate(smartNovelId, smartChapterId);
    }
  }, [smartNovelId, smartChapterId, newStoryboardStyle, smartShotCount]);

  // 选中分镜时加载镜头
  useEffect(() => {
    if (selectedStoryboard) {
      loadShots(selectedStoryboard.id);
      loadMergeVersions(selectedStoryboard.id);
      setSelectedShot(null);
      const latestFinalVideo = selectedStoryboard.content?.latest_final_video;
      setMergeResult(latestFinalVideo?.synthesis_job_id ? {
        job_id: latestFinalVideo.synthesis_job_id,
        storyboard_id: selectedStoryboard.id,
        output_url: latestFinalVideo.output_url,
        manifest_url: latestFinalVideo.manifest_url,
        srt_url: latestFinalVideo.srt_url,
        segment_count: latestFinalVideo.segment_count,
        duration_seconds: latestFinalVideo.duration_seconds,
        version_number: latestFinalVideo.version_number,
        render_backend: latestFinalVideo.render_backend,
        is_real_merged: latestFinalVideo.is_real_merged,
        render_message: latestFinalVideo.render_message,
      } : null);
    } else {
      setShots([]);
      setMergeResult(null);
      setSelectedMergeShotIds([]);
      setMergeVersions([]);
    }
  }, [selectedStoryboard?.id]);

  // 筛选分镜
  const filteredStoryboards = storyboards.filter((sb) => {
    const novelId = getStoryboardNovelId(sb);
    const chapterId = getStoryboardChapterId(sb);
    if (lineageNovelId && novelId !== lineageNovelId) return false;
    if (lineageChapterId && chapterId !== lineageChapterId) return false;
    return (
      sb.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      sb.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      sb.script_title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      getNovelLabel(novelId).toLowerCase().includes(searchQuery.toLowerCase()) ||
      getChapterLabel(chapterId).toLowerCase().includes(searchQuery.toLowerCase())
    );
  });

  // 创建分镜
  const handleCreateStoryboard = async () => {
    if (!newStoryboardTitle.trim()) {
      toast({ title: '请输入分镜标题', description: '标题是创建分镜的必填项。', type: 'error' });
      return;
    }
    if (!newStoryboardScriptId) {
      toast({ title: '请选择关联剧本', description: '需要先选择一个剧本。', type: 'error' });
      return;
    }

    try {
      const response = await fetchWithAuth(`${API_BASE}/storyboards`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script_id: newStoryboardScriptId,
          title: newStoryboardTitle,
          description: '',
        })
      });

      if (response.ok) {
        await loadStoryboards();
        setShowNewModal(false);
        setNewStoryboardTitle('');
        setNewStoryboardScriptId('');
        toast({ title: '分镜已创建', description: newStoryboardTitle, type: 'success' });
      } else {
        const err = await response.json();
        toast({ title: '创建失败', description: err.detail || '请重试。', type: 'error' });
      }
    } catch (error) {
      console.error('创建分镜失败:', error);
      toast({ title: '创建失败', description: '请重试。', type: 'error' });
    }
  };

  // AI 生成故事板（从剧本生成）
  const handleAIGenerateStoryboard = async (scriptIdOverride?: string) => {
    const effectiveScriptId = scriptIdOverride || pendingGenerateScriptId || newStoryboardScriptId;
    if (!effectiveScriptId) {
      toast({ title: '请选择剧本', description: '需要先选择一个剧本。', type: 'error' });
      return;
    }
    setGeneratingStoryboard(true);
    try {
      const useSmartContext = Boolean(smartNovelId);
      const response = await fetchWithAuth(`${API_BASE}/storyboards/${useSmartContext ? 'generate-smart' : 'generate'}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(useSmartContext ? {
          novel_id: smartNovelId,
          chapter_id: smartChapterId || undefined,
          script_id: effectiveScriptId,
          shot_count: smartShotCount || 5,
          style: newStoryboardStyle || 'anime',
          title: newStoryboardTitle.trim() || undefined,
          template_id: matchedTemplate?.template.id,
          use_ai_refine: true,
          model_config_id: textModelConfigId || undefined,
        } : {
          script_id: effectiveScriptId,
          shot_count: 5,
          style: newStoryboardStyle || 'anime',
          model_config_id: textModelConfigId || undefined,
        }),
      });
      if (response.ok) {
        const data = await response.json();
        await loadStoryboards();
        // 选中新创建的分镜
        const newSb = storyboards.find(sb => sb.id === data.id) || data;
        setSelectedStoryboard(newSb);
        toast({ title: '分镜生成成功', description: `已生成 ${data.shot_count} 个镜头。`, type: 'success' });
      } else {
        const errData = await response.json();
        throw new Error(errData.detail || '生成失败');
      }
    } catch (err: any) {
      console.error('生成故事板失败:', err);
      toast({ title: '生成失败', description: err.message || '请重试。', type: 'error' });
    } finally {
      setGeneratingStoryboard(false);
    }
  };

  const handleSmartGenerateStoryboard = async () => {
    if (!smartNovelId) {
      toast({ title: '请选择小说', description: '需要先选择用于生成分镜的小说。', type: 'error' });
      return;
    }
    const selectedScript = scripts.find((script) => script.id === newStoryboardScriptId);
    if (newStoryboardScriptId && !selectedScript) {
      toast({ title: '剧本不存在', description: '请重新选择当前小说章节下的剧本。', type: 'error' });
      return;
    }
    if (selectedScript) {
      const scriptNovelId = getScriptNovelId(selectedScript);
      const scriptChapterId = getScriptChapterId(selectedScript);
      if (scriptNovelId && scriptNovelId !== smartNovelId) {
        toast({ title: '剧本与小说不匹配', description: '请只选择当前小说下的剧本，或不选剧本让系统自动创建。', type: 'error' });
        return;
      }
      if (smartChapterId && scriptChapterId && scriptChapterId !== smartChapterId) {
        toast({ title: '剧本与章节不匹配', description: '请只选择当前章节下的剧本，或不选剧本让系统自动创建。', type: 'error' });
        return;
      }
    }
    setGeneratingSmartStoryboard(true);
    try {
      const response = await fetchWithAuth(`${API_BASE}/storyboards/generate-smart`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          novel_id: smartNovelId,
          chapter_id: smartChapterId || undefined,
          script_id: newStoryboardScriptId || undefined,
          shot_count: smartShotCount,
          style: newStoryboardStyle || 'anime',
          title: newStoryboardTitle.trim() || undefined,
          template_id: matchedTemplate?.template.id,
          use_ai_refine: true,
          model_config_id: textModelConfigId || undefined,
        }),
      });
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || '智能生成失败');
      }
      const data = await response.json();
      const selectedNovelForResult = smartNovelId;
      const selectedChapterForResult = smartChapterId || data.chapter_id || '';
      await loadStoryboards();
      setSelectedStoryboard(data);
      if (selectedNovelForResult) {
        setLineageNovelId(selectedNovelForResult);
        await loadChapters(selectedNovelForResult);
      }
      setLineageChapterId(selectedChapterForResult);
      setShowNewModal(false);
      setNewStoryboardTitle('');
      setNewStoryboardScriptId('');
      setSmartNovelId('');
      setSmartChapterId('');
      setChapters([]);
      setMatchedTemplate(null);
      toast({ title: '智能分镜已生成', description: `${data.shot_count} 个镜头已生成，可在右侧审核微调。`, type: 'success' });
    } catch (err: any) {
      console.error('智能生成分镜失败:', err);
      toast({ title: '智能生成失败', description: err.message || '请重试。', type: 'error' });
    } finally {
      setGeneratingSmartStoryboard(false);
    }
  };

  const prepareGenerateFromScript = (storyboard?: Storyboard | null) => {
    const target = storyboard || selectedStoryboard;
    const scriptId = target?.script_id || newStoryboardScriptId;
    if (!scriptId) {
      toast({ title: '请选择剧本', description: '需要先选择一个剧本。', type: 'error' });
      return;
    }
    if (target?.script_id) {
      setNewStoryboardScriptId(target.script_id);
      setNewStoryboardTitle(`${target.title || '分镜'} AI 重生成`);
      setNewStoryboardStyle((target.content?.style || newStoryboardStyle || 'anime'));
    }
    setPendingGenerateScriptId(scriptId);
    setConfirmGenerateFromScript(true);
  };

  // 创建镜头
  const handleAddShot = async () => {
    if (!selectedStoryboard) return;

    try {
      const newShotData = {
        storyboard_id: selectedStoryboard.id,
        shot_number: shots.length + 1,
        duration: 4,
        prompt: `镜头 ${shots.length + 1} 描述`,
        dialogue: '',
        visual_description: '',
        camera_angle: 'medium',
      };

      const response = await fetchWithAuth(`${API_BASE}/shots`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newShotData)
      });

      if (response.ok) {
        const createdShot = await response.json();
        setShots([...shots, createdShot]);
        setSelectedShot(createdShot);
        toast({ title: '镜头已创建', description: `镜头 ${createdShot.shot_number || shots.length + 1}`, type: 'success' });
      }
    } catch (error) {
      console.error('创建镜头失败:', error);
      toast({ title: '创建镜头失败', description: '请重试。', type: 'error' });
    }
  };

  // 更新镜头
  const handleUpdateShot = async (updated: Shot) => {
    try {
      const response = await fetchWithAuth(`${API_BASE}/shots/${updated.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated)
      });

      if (response.ok) {
        const updatedData = await response.json();
        const newShots = shots.map(s =>
          s.id === updated.id ? { ...updated, ...updatedData } : s
        );
        setShots(newShots);
        setSelectedShot(null);
        toast({ title: '镜头已保存', description: `镜头 ${updatedData.shot_number || updated.shot_number}`, type: 'success' });
      } else {
        toast({ title: '更新失败', description: '请重试。', type: 'error' });
      }
    } catch (error) {
      console.error('更新镜头失败:', error);
      toast({ title: '更新失败', description: '请重试。', type: 'error' });
    }
  };

  // 删除镜头
  const handleDeleteShot = async (shotId: string) => {
    if (!selectedStoryboard) return;

    try {
      const response = await fetchWithAuth(`${API_BASE}/shots/${shotId}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        const newShots = shots.filter(s => s.id !== shotId);
        setShots(newShots);
        if (selectedShot?.id === shotId) {
          setSelectedShot(null);
        }
        toast({ title: '镜头已删除', description: '镜头列表已更新。', type: 'success' });
      }
    } catch (error) {
      console.error('删除镜头失败:', error);
      toast({ title: '删除失败', description: '请重试。', type: 'error' });
    }
  };

  const handleDeleteStoryboard = async (storyboard: Storyboard) => {
    setDeletingStoryboard(true);
    try {
      const response = await fetchWithAuth(`${API_BASE}/storyboards/${storyboard.id}`, {
        method: 'DELETE',
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || data.message || '删除失败');
      }
      setStoryboards(prev => prev.filter(item => item.id !== storyboard.id));
      if (selectedStoryboard?.id === storyboard.id) {
        setSelectedStoryboard(null);
        setSelectedShot(null);
        setShots([]);
      }
      toast({
        title: '分镜已删除',
        description: data.deleted_shot_count ? `已同步删除 ${data.deleted_shot_count} 个镜头。` : '列表已更新。',
        type: 'success',
      });
    } catch (err: any) {
      console.error('删除分镜失败:', err);
      toast({ title: '删除分镜失败', description: err?.message || '请稍后重试。', type: 'error' });
    } finally {
      setDeletingStoryboard(false);
    }
  };

  const toggleMergeShot = (shot: Shot, checked: boolean) => {
    if (!shot.video_url) return;
    setSelectedMergeShotIds(prev => {
      if (checked) {
        return prev.includes(shot.id) ? prev : [...prev, shot.id];
      }
      return prev.filter(id => id !== shot.id);
    });
  };

  const handleMergeStoryboardVideos = async (parentJobId?: string) => {
    if (!selectedStoryboard) return;
    if (shots.length === 0) {
      toast({ title: '没有可合并的镜头', description: '请先创建镜头并生成视频。', type: 'error' });
      return;
    }
    const selectedShots = shots.filter((shot) => selectedMergeShotIds.includes(shot.id));
    if (selectedShots.length === 0) {
      toast({ title: '请选择要合并的镜头', description: '可以只勾选其中几个已有视频的镜头。', type: 'error' });
      return;
    }
    const missing = selectedShots.filter((shot) => !shot.video_url);
    if (missing.length > 0) {
      toast({
        title: '已选镜头还有视频缺失',
        description: `缺少：${missing.map((shot) => `镜头 ${shot.shot_number}`).join('、')}`,
        type: 'error',
      });
      return;
    }

    setMergingVideos(true);
    try {
      const response = await fetchWithAuth(`${API_BASE}/storyboards/${selectedStoryboard.id}/merge-videos`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: `${selectedStoryboard.title} - 分镜成片 V${(mergeVersions[0]?.version_number || 0) + 1}`,
          shot_ids: selectedShots.map((shot) => shot.id),
          include_subtitles: true,
          subtitle_mode: 'soft',
          transition_style: 'cut',
          audio_mix_strategy: 'shot_audio_first',
          quality_profile: 'review',
          render_strategy: 'auto',
          parent_job_id: parentJobId,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || data.message || '合并失败');
      }

      setMergeResult(data);
      const latestFinalVideo = {
        synthesis_job_id: data.job_id,
        output_url: data.output_url,
        manifest_url: data.manifest_url,
        srt_url: data.srt_url,
        segment_count: data.segment_count,
        duration_seconds: data.duration_seconds,
        version_number: data.version_number,
        render_backend: data.render_backend,
        is_real_merged: data.is_real_merged,
        render_message: data.render_message,
      };
      setStoryboards(prev => prev.map(item => (
        item.id === selectedStoryboard.id
          ? { ...item, content: { ...(item.content || {}), latest_final_video: latestFinalVideo } }
          : item
      )));
      setSelectedStoryboard(prev => prev ? {
        ...prev,
        content: { ...(prev.content || {}), latest_final_video: latestFinalVideo },
      } : prev);
      await loadMergeVersions(selectedStoryboard.id);
      toast({
        title: data.is_real_merged ? '分镜成片已真实合并' : '分镜成片清单已生成',
        description: `已合并 ${data.segment_count || selectedShots.length} 个镜头，版本 V${data.version_number || 1}。`,
        type: 'success',
      });
    } catch (err: any) {
      console.error('合并分镜视频失败:', err);
      toast({ title: '合并失败', description: err?.message || '请重试。', type: 'error' });
    } finally {
      setMergingVideos(false);
    }
  };

  // 移动镜头顺序
  const moveShot = async (index: number, direction: 'up' | 'down') => {
    const newIndex = direction === 'up' ? index - 1 : index + 1;
    if (newIndex < 0 || newIndex >= shots.length) return;

    const newShots = [...shots];
    [newShots[index], newShots[newIndex]] = [newShots[newIndex], newShots[index]];

    // 更新shot_number
    newShots.forEach((shot, i) => {
      shot.shot_number = i + 1;
    });

    setShots(newShots);

    // 同步到后端
    try {
      await fetchWithAuth(`${API_BASE}/shots/reorder?storyboard_id=${selectedStoryboard?.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ shot_ids: newShots.map(s => s.id) })
      });
    } catch (error) {
      console.error('更新顺序失败:', error);
    }
  };

  // 总时长
  const totalDuration = shots.reduce((sum, s) => sum + (s.duration || 0), 0);
  const videoReadyCount = shots.filter(s => s.video_url).length;
  const missingVideoShots = shots.filter(s => !s.video_url);
  const selectedMergeShots = shots.filter(s => selectedMergeShotIds.includes(s.id));
  const selectedMissingVideoShots = selectedMergeShots.filter(s => !s.video_url);
  const mergeDisabledReason = !shots.length
    ? '当前分镜还没有镜头'
    : selectedMergeShots.length === 0
      ? '请选择要合并的镜头'
      : selectedMissingVideoShots.length > 0
        ? `已选镜头中还有 ${selectedMissingVideoShots.length} 个未生成视频`
      : '';
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">分镜设计</h1>
            <p className="text-white/60 mt-1">设计视频分镜和镜头序列</p>
          </div>
          <div className="flex gap-3">
            <Button
              variant="outline"
              className="border-violet-500/40 text-violet-300 hover:bg-violet-600/20"
              onClick={() => {
                setSmartNovelId(lineageNovelId);
                if (lineageNovelId) {
                  loadChapters(lineageNovelId).then(() => {
                    if (lineageChapterId) setSmartChapterId(lineageChapterId);
                  });
                }
                setShowNewModal(true);
              }}
            >
              <Sparkles className="w-4 h-4 mr-2" />
              智能生成分镜
            </Button>
            <Button
              variant="outline"
              className="border-white/20 text-white"
              onClick={() => setShowNewModal(true)}
            >
              <Plus className="w-4 h-4 mr-2" />
              新建分镜
            </Button>
          </div>
        </div>

        {/* 统计信息 */}
        <div className="grid grid-cols-4 gap-4">
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-white">{storyboards.length}</div>
              <div className="text-sm text-white/60">分镜数量</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-purple-400">{formatTime(totalDuration)}</div>
              <div className="text-sm text-white/60">当前总时长</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-blue-400">{videoReadyCount}</div>
              <div className="text-sm text-white/60">已生成视频</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-green-400">{shots.length}</div>
              <div className="text-sm text-white/60">当前镜头数</div>
            </CardContent>
          </Card>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
            <span className="ml-3 text-white/60">加载中…</span>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* 分镜列表 */}
            <div className="lg:col-span-1 space-y-4">
              {/* 搜索 */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                <Input
                  placeholder="搜索分镜…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 bg-white/5 border-white/10 text-white placeholder:text-white/40"
                />
              </div>

              <Card className="bg-white/5 border-white/10">
                <CardContent className="p-3 space-y-3">
                  <div>
                    <label className="text-xs text-white/50 mb-1 block">按小说筛选</label>
                    <select
                      value={lineageNovelId}
                      onChange={(event) => {
                        setLineageNovelId(event.target.value);
                        setLineageChapterId('');
                        setSelectedStoryboard(null);
                      }}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                    >
                      <option value="">全部小说</option>
                      {novels.map((novel) => (
                        <option key={novel.id} value={novel.id}>{novel.title}</option>
                      ))}
                    </select>
                  </div>
                  {lineageNovelId && (
                    <div>
                      <label className="text-xs text-white/50 mb-1 block">按章节筛选</label>
                      <select
                        value={lineageChapterId}
                        onChange={(event) => {
                          setLineageChapterId(event.target.value);
                          setSelectedStoryboard(null);
                        }}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                      >
                        <option value="">全部章节</option>
                        {chapters.map((chapter) => (
                          <option key={chapter.id} value={chapter.id}>
                            {formatChapterLabel(chapter)}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* 分镜列表 */}
              <div className="space-y-2 max-h-[600px] overflow-y-auto">
                {filteredStoryboards.map((sb) => (
                  <div
                    key={sb.id}
                    onClick={() => setSelectedStoryboard(sb)}
                    className={`p-3 rounded-lg cursor-pointer transition-all ${
                      selectedStoryboard?.id === sb.id
                        ? 'bg-purple-600/20 border-purple-500'
                        : 'bg-white/5 border-white/10 hover:border-white/30'
                    } border`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="min-w-0 pr-2">
                        <div className="text-white font-medium">{sb.title}</div>
                        <div className="text-xs text-white/40">
                          {sb.shot_count || 0} 个镜头 · {sb.script_title || sb.script_id}
                        </div>
                        <div className="text-xs text-white/35 mt-1">
                          {getNovelLabel(getStoryboardNovelId(sb))} · {getChapterLabel(getStoryboardChapterId(sb))}
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-1">
                        <span className={`text-xs px-2 py-0.5 rounded ${
                          sb.status === 'approved' ? 'bg-green-600/30 text-green-400' :
                          sb.status === 'rejected' ? 'bg-red-600/30 text-red-400' :
                          'bg-white/10 text-white/60'
                        }`}>
                          {sb.status || 'draft'}
                        </span>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`删除分镜 ${sb.title}`}
                          title="删除分镜"
                          className="h-7 w-7 text-white/40 hover:text-red-400"
                          onClick={(event) => {
                            event.stopPropagation();
                            setDeleteStoryboardTarget(sb);
                          }}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}

                {filteredStoryboards.length === 0 && (
                  <div className="text-center py-8">
                    <LayoutGrid className="w-12 h-12 mx-auto text-white/20" />
                    <p className="text-white/40 mt-2">暂无分镜</p>
                    <div className="mt-3 flex justify-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        className="border-violet-500/40 text-violet-300"
                        onClick={() => setShowNewModal(true)}
                      >
                        <Sparkles className="w-4 h-4 mr-1" />
                        AI 生成
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="border-white/20 text-white/60"
                        onClick={() => setShowNewModal(true)}
                      >
                        手动创建
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* 分镜详情 */}
            <div className="lg:col-span-2">
              {selectedStoryboard ? (
                <Card className="bg-white/5 border-white/10">
                  <CardHeader>
                    <CardTitle className="text-white flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                      <div className="flex min-w-0 items-center gap-2">
                        <LayoutGrid className="w-5 h-5 text-purple-400" />
                        <span className="truncate text-lg">{selectedStoryboard.title}</span>
                        <span className="text-sm text-white/50">· {shots.length} 个镜头</span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => prepareGenerateFromScript(selectedStoryboard)}
                          disabled={generatingStoryboard}
                          className="border-violet-500/50 text-violet-300 hover:bg-violet-600/20"
                        >
                          {generatingStoryboard ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Sparkles className="w-4 h-4 mr-1" />}
                          从剧本生成
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleMergeStoryboardVideos()}
                          disabled={mergingVideos || Boolean(mergeDisabledReason)}
                          title={mergeDisabledReason || '按镜头顺序合并已勾选的视频'}
                          className="border-emerald-500/50 text-emerald-300 hover:bg-emerald-600/20"
                        >
                          {mergingVideos ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Film className="w-4 h-4 mr-1" />}
                          合并所选
                        </Button>
                        <Button
                          asChild
                          variant="outline"
                          size="sm"
                          className="border-violet-500/50 text-violet-300 hover:bg-violet-600/20"
                        >
                          <Link href={videoGenerationHref()}>
                            <Video className="w-4 h-4 mr-1" />
                            生成视频
                          </Link>
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setDeleteStoryboardTarget(selectedStoryboard)}
                          className="border-red-500/40 text-red-300 hover:bg-red-600/20"
                        >
                          <Trash2 className="w-4 h-4 mr-1" />
                          删除
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => loadShots(selectedStoryboard.id)}
                          className="border-purple-500/50 text-purple-400 hover:bg-purple-600/20"
                        >
                          <RefreshCw className="w-4 h-4 mr-1" />
                          刷新
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleAddShot}
                          className="border-purple-500/50 text-purple-400 hover:bg-purple-600/20"
                        >
                          <Plus className="w-4 h-4 mr-1" />
                          添加镜头
                        </Button>
                      </div>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div data-testid="storyboard-lineage" className="mb-4 rounded-lg border border-white/10 bg-white/5 p-3 text-sm">
                      <div className="text-white/70">上游链路</div>
                      <div className="mt-1 text-white/50">
                        {getNovelLabel(getStoryboardNovelId(selectedStoryboard))} / {getChapterLabel(getStoryboardChapterId(selectedStoryboard))} / {selectedStoryboard.script_title || selectedStoryboard.script_id}
                      </div>
                      <div className="mt-2 text-xs text-white/40">
                        视频合并准备：已选 {selectedMergeShots.length} 个，{videoReadyCount}/{shots.length} 个镜头已有视频
                        {missingVideoShots.length > 0 && `，缺少 ${missingVideoShots.map((shot) => `镜头 ${shot.shot_number}`).join('、')}`}
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 border-white/20 text-xs text-white/70"
                          onClick={() => setSelectedMergeShotIds(shots.filter((shot) => shot.video_url).map((shot) => shot.id))}
                        >
                          选择全部已有视频
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 border-white/20 text-xs text-white/70"
                          onClick={() => setSelectedMergeShotIds([])}
                        >
                          清空选择
                        </Button>
                      </div>
                    </div>

                    {mergeResult && (
                      <div className="mb-4 rounded-lg border border-emerald-500/25 bg-emerald-500/10 p-4">
                        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 text-sm font-medium text-emerald-200">
                              <Film className="h-4 w-4 shrink-0" />
                              <span>当前分镜成片</span>
                              <span className={`rounded px-2 py-0.5 text-xs ${
                                mergeResult.is_real_merged
                                  ? 'bg-emerald-500/20 text-emerald-200'
                                  : 'bg-yellow-500/20 text-yellow-200'
                              }`}>
                                {mergeResult.is_real_merged ? 'FFmpeg 真拼接' : '清单/占位'}
                              </span>
                            </div>
                            <div className="mt-1 text-xs text-white/50">
                              V{mergeResult.version_number || 1} · {mergeResult.segment_count || shots.length} 个镜头 · {formatTime(Math.round(mergeResult.duration_seconds || totalDuration))}
                              {mergeResult.render_message && ` · ${mergeResult.render_message}`}
                            </div>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              className="border-emerald-500/40 text-emerald-200"
                              onClick={() => handleMergeStoryboardVideos(mergeResult.job_id)}
                              disabled={mergingVideos || Boolean(mergeDisabledReason)}
                            >
                              {mergingVideos ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-1" />}
                              重新合成
                            </Button>
                            {mergeResult.output_url && (
                              <>
                                <Button asChild size="sm" variant="outline" className="border-emerald-500/40 text-emerald-200">
                                  <a href={toMediaUrl(mergeResult.output_url)} target="_blank" rel="noreferrer">
                                    <Eye className="w-4 h-4 mr-1" />
                                    播放
                                  </a>
                                </Button>
                                <Button asChild size="sm" variant="outline" className="border-white/20 text-white/70">
                                  <a href={toMediaUrl(mergeResult.output_url)} download>
                                    <Download className="w-4 h-4 mr-1" />
                                    下载视频
                                  </a>
                                </Button>
                              </>
                            )}
                            {mergeResult.manifest_url && (
                              <Button asChild size="sm" variant="outline" className="border-white/20 text-white/70">
                                <a href={toMediaUrl(mergeResult.manifest_url)} target="_blank" rel="noreferrer">
                                  <Download className="w-4 h-4 mr-1" />
                                  Manifest
                                </a>
                              </Button>
                            )}
                            {mergeResult.srt_url && (
                              <Button asChild size="sm" variant="outline" className="border-white/20 text-white/70">
                                <a href={toMediaUrl(mergeResult.srt_url)} download>
                                  <Download className="w-4 h-4 mr-1" />
                                  字幕 SRT
                                </a>
                              </Button>
                            )}
                          </div>
                        </div>
                        {mergeResult.output_url ? (
                          <video
                            controls
                            className="mt-3 aspect-video w-full rounded-lg border border-white/10 bg-black"
                            src={toMediaUrl(mergeResult.output_url)}
                          />
                        ) : (
                          <div className="mt-3 rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-white/50">
                            已生成成片清单，等待生产渲染器输出最终视频。
                          </div>
                        )}
                      </div>
                    )}

                    {mergeVersions.length > 0 && (
                      <div className="mb-4 rounded-lg border border-white/10 bg-white/5 p-3">
                        <div className="mb-2 flex items-center justify-between">
                          <div className="text-sm text-white/70">合并版本</div>
                          {loadingMergeVersions && <Loader2 className="h-4 w-4 animate-spin text-white/40" />}
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {mergeVersions.map((version) => (
                            <button
                              key={version.job_id}
                              type="button"
                              onClick={() => setMergeResult(version)}
                              className={`rounded border px-3 py-2 text-left text-xs transition ${
                                mergeResult?.job_id === version.job_id
                                  ? 'border-emerald-400 bg-emerald-500/15 text-emerald-100'
                                  : 'border-white/10 bg-black/10 text-white/60 hover:border-white/30'
                              }`}
                            >
                              <div>V{version.version_number || 1} · {version.segment_count || 0} 镜头</div>
                              <div className="mt-1 text-white/40">
                                {version.is_real_merged ? '真拼接' : '清单/占位'}
                                {version.selected_shot_numbers?.length ? ` · 镜头 ${version.selected_shot_numbers.join('、')}` : ''}
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className={selectedShot ? 'grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,0.92fr)_minmax(380px,1.08fr)]' : 'space-y-3'}>
                    {/* 镜头列表 */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="text-sm font-medium text-white">镜头列表</div>
                          <div className="text-xs text-white/40">点击镜头后在右侧工作台编辑，勾选已有视频的镜头可合并成片。</div>
                        </div>
                        <div className="text-xs text-white/40">{shots.length} 个镜头</div>
                      </div>
                      {loadingShots ? (
                        <div className="flex items-center justify-center py-8">
                          <Loader2 className="w-6 h-6 animate-spin text-purple-400" />
                          <span className="ml-2 text-white/60">加载镜头...</span>
                        </div>
                      ) : shots.length > 0 ? (
                        shots.map((shot, index) => (
                        <div
                          key={shot.id}
                          onClick={() => setSelectedShot(shot)}
                          className={`p-3 rounded-lg cursor-pointer transition-all ${
                            selectedShot?.id === shot.id
                              ? 'bg-purple-600/20 border-purple-500'
                              : 'bg-white/5 border-white/10 hover:border-white/30'
                          } border`}
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2">
                              <input
                                type="checkbox"
                                aria-label={`选择镜头 ${shot.shot_number} 用于合并`}
                                title={shot.video_url ? '选择用于合并成片' : '该镜头还没有视频，暂不能合并'}
                                checked={selectedMergeShotIds.includes(shot.id)}
                                disabled={!shot.video_url}
                                onClick={(event) => event.stopPropagation()}
                                onChange={(event) => toggleMergeShot(shot, event.target.checked)}
                                className="h-4 w-4 rounded border-white/20 bg-white/10 accent-emerald-500 disabled:cursor-not-allowed disabled:opacity-30"
                              />
                              <span className="w-6 h-6 rounded bg-purple-600/30 text-purple-300 text-xs flex items-center justify-center">
                                {shot.shot_number}
                              </span>
                              <div>
                                <div className="text-white font-medium line-clamp-1">{shot.prompt || '未设置描述'}</div>
                                <div className="text-xs text-white/40">
                                  {shot.duration}秒 · {getShotAttributeLabel(CAMERA_ANGLE_LABELS, shot.camera_angle, '中景')}
                                  {shot.video_status !== 'pending' && (
                                    <span className={`ml-2 ${
                                      shot.video_status === 'completed' ? 'text-green-400' :
                                      shot.video_status === 'failed' ? 'text-red-400' :
                                      'text-yellow-400'
                                    }`}>
                                      视频: {shot.video_status}
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                            <div className="flex gap-1">
                              <Button
                                asChild
                                variant="ghost"
                                size="icon"
                                aria-label={`生成镜头 ${shot.shot_number} 视频`}
                                title={`生成镜头${shot.shot_number}视频`}
                                className="w-6 h-6 text-violet-300"
                                onClick={(e) => e.stopPropagation()}
                              >
                                <Link href={videoGenerationHref(shot)}>
                                  <Video className="w-3 h-3" />
                                </Link>
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                aria-label={`镜头 ${shot.shot_number} 上移`}
                                title="上移"
                                className="w-6 h-6 text-white/40"
                                onClick={(e) => { e.stopPropagation(); moveShot(index, 'up'); }}
                                disabled={index === 0}
                              >
                                <ChevronLeft className="w-3 h-3" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                aria-label={`镜头 ${shot.shot_number} 下移`}
                                title="下移"
                                className="w-6 h-6 text-white/40"
                                onClick={(e) => { e.stopPropagation(); moveShot(index, 'down'); }}
                                disabled={index === shots.length - 1}
                              >
                                <ChevronRight className="w-3 h-3" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                aria-label={`删除镜头 ${shot.shot_number}`}
                                title="删除镜头"
                                className="w-6 h-6 text-white/40 hover:text-red-400"
                                onClick={(e) => { e.stopPropagation(); setDeleteShotTarget(shot); }}
                              >
                                <Trash2 className="w-3 h-3" />
                              </Button>
                            </div>
                          </div>
                        </div>
                      ))) : (
                        <div className="text-center py-8">
                          <Film className="w-12 h-12 mx-auto text-white/20" />
                          <p className="text-white/40 mt-2">暂无镜头，点击上方添加或使用AI生成</p>
                        </div>
                      )}
                    </div>

                    {/* 镜头详情编辑 */}
                    {selectedShot && (
                      <div className="rounded-xl border border-purple-500/20 bg-purple-500/[0.06] p-4 xl:sticky xl:top-4 xl:max-h-[calc(100vh-150px)] xl:overflow-y-auto">
                        <div className="mb-4 flex items-start justify-between gap-3">
                          <div>
                            <h4 className="text-white font-medium">镜头工作台</h4>
                            <p className="mt-1 text-xs text-white/45">正在编辑镜头 {selectedShot.shot_number}，修改后点击保存镜头写入数据库。</p>
                          </div>
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label="关闭镜头工作台"
                            title="关闭"
                            className="h-8 w-8 text-white/45 hover:text-white"
                            onClick={() => setSelectedShot(null)}
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </div>
                        {(() => {
                          const refs = getShotEntityRefs(selectedShot);
                          return (refNames(refs.characters) || refNames(refs.scenes) || refNames(refs.props) || refNames(refs.events) || refs.subtitle) ? (
                            <div className="mb-4 rounded-lg border border-violet-500/20 bg-violet-500/10 p-3 text-xs space-y-1">
                              {refNames(refs.characters) && <div className="text-white/70">人物：{refNames(refs.characters)}</div>}
                              {refNames(refs.scenes) && <div className="text-white/70">场景：{refNames(refs.scenes)}</div>}
                              {refNames(refs.props) && <div className="text-white/70">道具：{refNames(refs.props)}</div>}
                              {refNames(refs.events) && <div className="text-white/70">事件：{refNames(refs.events)}</div>}
                              {refs.subtitle && <div className="text-green-200">字幕：{refs.subtitle}</div>}
                            </div>
                          ) : null;
                        })()}

                        {renderShotMultiviewStatus(selectedShot)}

                        {/* 快速操作按钮 */}
                        <div className="flex gap-2 mb-4">
                          <Button asChild variant="outline" className="border-violet-500/50 text-violet-300">
                            <Link href={videoGenerationHref(selectedShot)}>
                              <Video className="w-4 h-4 mr-2" />
                              生成此镜头视频
                            </Link>
                          </Button>
                          <Button
                            onClick={() => handleUpdateShot(selectedShot)}
                            className="bg-purple-600 hover:bg-purple-700"
                          >
                            <Save className="w-4 h-4 mr-2" />
                            保存镜头
                          </Button>
                          <Button
                            variant="outline"
                            onClick={() => setSelectedShot(null)}
                            className="border-white/20 text-white"
                          >
                            取消
                          </Button>
                        </div>

                        <section className="space-y-4 rounded-lg border border-white/10 bg-black/15 p-3">
                        <div>
                          <h5 className="text-sm font-semibold text-white">基础镜头</h5>
                          <p className="mt-1 text-xs text-white/45">确认时长、景别和视频生成 Prompt。</p>
                        </div>
                        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                          <div>
                            <label className="text-sm text-white/60 mb-2 block">镜头时长（秒）</label>
                            <Input
                              type="number"
                              value={selectedShot.duration}
                              onChange={(e) => setSelectedShot({ ...selectedShot, duration: parseInt(e.target.value) || 4 })}
                              className="bg-white/5 border-white/10 text-white"
                            />
                          </div>
                          <div>
                            <label className="text-sm text-white/60 mb-2 block">镜头角度</label>
                            <select
                              value={selectedShot.camera_angle || 'medium'}
                              onChange={(e) => setSelectedShot({ ...selectedShot, camera_angle: e.target.value })}
                              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                            >
                              {CAMERA_ANGLE_OPTIONS.map(angle => (
                                <option key={angle.value} value={angle.value}>{angle.label}</option>
                              ))}
                            </select>
                          </div>
                        </div>

                        <div className="mt-4">
                          <label className="text-sm text-white/60 mb-2 block">
                            视频生成 Prompt <span className="text-red-400">*</span>
                          </label>
                          <Input
                            value={selectedShot.prompt || ''}
                            onChange={(e) => setSelectedShot({ ...selectedShot, prompt: e.target.value })}
                            placeholder="用于AI视频生成的关键描述词，简洁有力"
                            className="bg-white/5 border-white/10 text-white"
                          />
                        </div>
                        </section>

                        <section className="mt-4 space-y-4 rounded-lg border border-white/10 bg-black/15 p-3">
                        <div>
                          <h5 className="text-sm font-semibold text-white">画面与运镜</h5>
                          <p className="mt-1 text-xs text-white/45">维护画面细节、参考图、运镜、情绪、光线和调色。</p>
                        </div>

                        <div>
                          <label className="text-sm text-white/60 mb-2 block">视觉描述</label>
                          <textarea
                            value={selectedShot.visual_description || ''}
                            onChange={(e) => setSelectedShot({ ...selectedShot, visual_description: e.target.value })}
                            placeholder="人物动作、环境、表情等细节描述"
                            rows={3}
                            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white resize-none"
                          />
                        </div>

                        {/* 参考图 */}
                        <div>
                          <div className="mb-3">
                            <ImageStyleTemplatePicker
                              templates={imageStyleTemplates}
                              value={shotImageStyle}
                              onChange={setShotImageStyle}
                              toMediaUrl={toMediaUrl}
                              recommendedFor="shot"
                              title="镜头参考图风格"
                              compact
                              layout="inline"
                            />
                          </div>
                          <div className="flex items-center justify-between mb-2">
                            <label className="text-sm font-medium text-white/60">参考图</label>
                            <button
                              type="button"
                              onClick={() => handleGenerateShotImage(selectedShot.id)}
                              disabled={generatingImage || !selectedShot.visual_description}
                              className="px-3 py-1 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              {generatingImage
                                ? "生成中…"
                                : selectedShot.image_status === 'generating' || selectedShot.image_status === 'failed'
                                  ? "重新生成参考图"
                                  : "生成参考图"}
                            </button>
                          </div>
                          {getReferenceImageStatusText(selectedShot) && (
                            <div className={`text-sm ${
                              selectedShot.image_status === 'failed'
                                ? 'text-red-300'
                                : selectedShot.image_status === 'succeeded'
                                  ? 'text-emerald-300'
                                  : 'text-yellow-300'
                            }`}>
                              {getReferenceImageStatusText(selectedShot)}
                            </div>
                          )}
                          <ReferenceImagePreview
                            src={toMediaUrl(selectedShot.image_url)}
                            title={`镜头 ${selectedShot.shot_number} 参考图`}
                            alt={`镜头 ${selectedShot.shot_number} 参考图`}
                            caption={selectedShot.visual_description || selectedShot.prompt}
                            className="mt-2 h-48 w-full"
                            thumbnailClassName="p-1"
                          />
                        </div>

                        <div>
                          <label className="text-sm text-white/60 mb-2 block">台词/配音</label>
                          <Input
                            value={selectedShot.dialogue || ''}
                            onChange={(e) => setSelectedShot({ ...selectedShot, dialogue: e.target.value })}
                            placeholder="输入镜头台词或配音内容"
                            className="bg-white/5 border-white/10 text-white"
                          />
                        </div>

                        {/* 精细化控制 */}
                        <div className="pt-2">
                          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                            <div>
                              <label className="text-sm text-white/60 mb-2 block">运镜方式</label>
                              <select
                                value={selectedShot.camera_movement || 'static'}
                                onChange={(e) => setSelectedShot({ ...selectedShot, camera_movement: e.target.value })}
                                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                              >
                                {CAMERA_MOVEMENT_OPTIONS.map(m => (
                                  <option key={m.value} value={m.value}>{m.label}</option>
                                ))}
                              </select>
                            </div>
                            <div>
                              <label className="text-sm text-white/60 mb-2 block">情绪</label>
                              <select
                                value={selectedShot.emotion || 'neutral'}
                                onChange={(e) => setSelectedShot({ ...selectedShot, emotion: e.target.value })}
                                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                              >
                                {EMOTION_OPTIONS.map(e => (
                                  <option key={e.value} value={e.value}>{e.label}</option>
                                ))}
                              </select>
                            </div>
                            <div>
                              <label className="text-sm text-white/60 mb-2 block">光线</label>
                              <select
                                value={selectedShot.lighting || 'natural'}
                                onChange={(e) => setSelectedShot({ ...selectedShot, lighting: e.target.value })}
                                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                              >
                                {LIGHTING_OPTIONS.map(l => (
                                  <option key={l.value} value={l.value}>{l.label}</option>
                                ))}
                              </select>
                            </div>
                            <div>
                              <label className="text-sm text-white/60 mb-2 block">调色</label>
                              <select
                                value={selectedShot.color_grading || 'cinematic'}
                                onChange={(e) => setSelectedShot({ ...selectedShot, color_grading: e.target.value })}
                                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                              >
                                {COLOR_GRADING_OPTIONS.map(c => (
                                  <option key={c.value} value={c.value}>{c.label}</option>
                                ))}
                              </select>
                            </div>
                          </div>

                          <div className="grid grid-cols-1 gap-4 mt-4 md:grid-cols-2">
                            <div>
                              <label className="text-sm text-white/60 mb-2 block">配乐提示</label>
                              <Input
                                value={selectedShot.music_cue || ''}
                                onChange={(e) => setSelectedShot({ ...selectedShot, music_cue: e.target.value })}
                                placeholder="背景音乐风格"
                                className="bg-white/5 border-white/10 text-white"
                              />
                            </div>
                            <div>
                              <label className="text-sm text-white/60 mb-2 block">音效提示</label>
                              <Input
                                value={selectedShot.sfx_cue || ''}
                                onChange={(e) => setSelectedShot({ ...selectedShot, sfx_cue: e.target.value })}
                                placeholder="环境音效"
                                className="bg-white/5 border-white/10 text-white"
                              />
                            </div>
                          </div>
                        </div>
                        </section>

                        {/* 视频/音频URL */}
                        <div className="mt-6 pt-4 border-t border-white/10">
                          <h5 className="text-white font-medium mb-3">生成结果</h5>
                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <label className="text-sm text-white/60 mb-2 block">视频 URL</label>
                              <Input
                                value={selectedShot.video_url || ''}
                                onChange={(e) => setSelectedShot({ ...selectedShot, video_url: e.target.value })}
                                placeholder="生成后的视频链接"
                                className="bg-white/5 border-white/10 text-white"
                              />
                            </div>
                            <div>
                              <label className="text-sm text-white/60 mb-2 block">音频 URL</label>
                              <Input
                                value={selectedShot.audio_url || ''}
                                onChange={(e) => setSelectedShot({ ...selectedShot, audio_url: e.target.value })}
                                placeholder="配音音频链接"
                                className="bg-white/5 border-white/10 text-white"
                              />
                            </div>
                          </div>
                          <div className="grid grid-cols-2 gap-4 mt-4">
                            <div>
                              <label className="text-sm text-white/60 mb-2 block">视频状态</label>
                              <span className={`px-2 py-1 rounded text-xs ${
                                selectedShot.video_status === 'completed' ? 'bg-green-600/30 text-green-400' :
                                selectedShot.video_status === 'failed' ? 'bg-red-600/30 text-red-400' :
                                selectedShot.video_status === 'processing' ? 'bg-yellow-600/30 text-yellow-400' :
                                'bg-white/10 text-white/60'
                              }`}>
                                {selectedShot.video_status}
                              </span>
                            </div>
                            <div>
                              <label className="text-sm text-white/60 mb-2 block">音频状态</label>
                              <span className={`px-2 py-1 rounded text-xs ${
                                selectedShot.audio_status === 'completed' ? 'bg-green-600/30 text-green-400' :
                                selectedShot.audio_status === 'failed' ? 'bg-red-600/30 text-red-400' :
                                selectedShot.audio_status === 'processing' ? 'bg-yellow-600/30 text-yellow-400' :
                                'bg-white/10 text-white/60'
                              }`}>
                                {selectedShot.audio_status}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                    </div>
                  </CardContent>
                </Card>
              ) : (
                <div className="h-full flex items-center justify-center">
                  <div className="text-center">
                    <LayoutGrid className="w-16 h-16 mx-auto text-white/20" />
                    <p className="text-white/40 mt-4">从左侧选择或创建分镜</p>
                    <div className="mt-4 flex justify-center gap-2">
                      <Button
                        variant="outline"
                        className="border-violet-500/40 text-violet-300"
                        onClick={() => setShowNewModal(true)}
                      >
                        <Sparkles className="w-4 h-4 mr-2" />
                        AI 智能生成
                      </Button>
                      <Button
                        variant="outline"
                        className="border-white/20 text-white"
                        onClick={() => setShowNewModal(true)}
                      >
                        <Plus className="w-4 h-4 mr-2" />
                        新建分镜
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={confirmGenerateFromScript}
        title="AI 从剧本生成分镜"
        description="将从所选剧本内容自动生成分镜镜头，生成完成后会在当前页面展示。"
        confirmText="开始生成"
        loading={generatingStoryboard}
        onOpenChange={(open) => {
          setConfirmGenerateFromScript(open);
          if (!open) setPendingGenerateScriptId('');
        }}
        onConfirm={async () => {
          await handleAIGenerateStoryboard(pendingGenerateScriptId);
          setConfirmGenerateFromScript(false);
          setPendingGenerateScriptId('');
        }}
      />

      <ConfirmDialog
        open={Boolean(deleteStoryboardTarget)}
        title="删除分镜"
        description={`确定要删除${deleteStoryboardTarget ? `「${deleteStoryboardTarget.title}」` : '这个分镜'}吗？删除后会同步清理该分镜下的镜头。`}
        confirmText="删除分镜"
        destructive
        loading={deletingStoryboard}
        onOpenChange={(open) => {
          if (!open) setDeleteStoryboardTarget(null);
        }}
        onConfirm={async () => {
          if (!deleteStoryboardTarget) return;
          await handleDeleteStoryboard(deleteStoryboardTarget);
          setDeleteStoryboardTarget(null);
        }}
      />

      <ConfirmDialog
        open={Boolean(deleteShotTarget)}
        title="删除镜头"
        description={`确定要删除镜头 ${deleteShotTarget?.shot_number || ''} 吗？此操作无法撤销。`}
        confirmText="删除"
        destructive
        loading={deletingShot}
        onOpenChange={(open) => {
          if (!open) setDeleteShotTarget(null);
        }}
        onConfirm={async () => {
          if (!deleteShotTarget) return;
          setDeletingShot(true);
          try {
            await handleDeleteShot(deleteShotTarget.id);
            setDeleteShotTarget(null);
          } finally {
            setDeletingShot(false);
          }
        }}
      />

      {/* 新建分镜弹窗 */}
      <Dialog open={showNewModal} onOpenChange={setShowNewModal}>
        <DialogContent className="max-w-2xl border-white/20 bg-slate-950/95">
            <DialogHeader className="pr-10">
              <DialogTitle>新建分镜</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="rounded-lg border border-purple-500/30 bg-purple-500/10 p-3 space-y-3">
                <div>
                  <div className="text-sm font-medium text-purple-200">智能生成</div>
                  <div className="text-xs text-white/50 mt-1">从小说或章节自动匹配模板，生成可审核的分镜与镜头细节</div>
                </div>

                <div>
                  <label className="text-sm text-white/60 mb-2 block">选择小说</label>
                  <select
                    value={smartNovelId}
                    onChange={(e) => {
                      setSmartNovelId(e.target.value);
                      setSmartChapterId('');
                      setNewStoryboardScriptId('');
                      setMatchedTemplate(null);
                    }}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                  >
                    <option value="">请选择小说…</option>
                    {novels.map(novel => (
                      <option key={novel.id} value={novel.id}>{novel.title}</option>
                    ))}
                  </select>
                </div>

                {smartNovelId && (
                  <div>
                    <label className="text-sm text-white/60 mb-2 block">选择章节</label>
                    <select
                      value={smartChapterId}
                      onChange={(e) => {
                        setSmartChapterId(e.target.value);
                        setNewStoryboardScriptId('');
                      }}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                    >
                      <option value="">整部小说/简介</option>
                      {chapters.map(chapter => (
                        <option key={chapter.id} value={chapter.id}>
                          {formatChapterLabel(chapter)}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-sm text-white/60 mb-2 block">镜头数</label>
                    <Input
                      type="number"
                      min={1}
                      max={50}
                      value={smartShotCount}
                      onChange={(e) => setSmartShotCount(Math.max(1, Math.min(50, parseInt(e.target.value) || 5)))}
                      className="bg-white/5 border-white/10 text-white"
                    />
                  </div>
                  <div>
                    <label className="text-sm text-white/60 mb-2 block">分镜风格</label>
                    <select
                      value={newStoryboardStyle}
                      onChange={(e) => setNewStoryboardStyle(e.target.value)}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                    >
                      {STORYBOARD_STYLE_OPTIONS.map(style => (
                        <option key={style.value} value={style.value}>{style.label}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {matchedTemplate && (
                  <div className="rounded-md bg-white/5 border border-white/10 p-3">
                    <div className="text-sm text-white">匹配模板：{matchedTemplate.template.name}</div>
                    <div className="text-xs text-white/50 mt-1">{matchedTemplate.reason}</div>
                  </div>
                )}

                <ModelCapabilitySelector
                  capability="text"
                  configs={modelConfigs}
                  value={textModelConfigId}
                  onChange={setTextModelConfigId}
                  disabled={generatingSmartStoryboard}
                  title="智能分镜文本模型"
                  description="模型会根据小说、章节、模板、角色、场景、事件和对白上下文细化分镜镜头。"
                  compact
                />

                <Button
                  onClick={handleSmartGenerateStoryboard}
                  disabled={!smartNovelId || generatingSmartStoryboard}
                  className="w-full bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700"
                >
                  {generatingSmartStoryboard ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      智能生成中…
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4 mr-2" />
                      智能生成分镜与镜头
                    </>
                  )}
                </Button>
              </div>

              <div>
                <label className="text-sm text-white/60 mb-2 block">分镜标题 *</label>
                <Input
                  placeholder="例如：第一章 分镜A"
                  value={newStoryboardTitle}
                  onChange={(e) => setNewStoryboardTitle(e.target.value)}
                  className="bg-white/5 border-white/10 text-white placeholder:text-white/40"
                />
              </div>

              <div>
                <label className="text-sm text-white/60 mb-2 block">关联剧本 *</label>
                <select
                  value={newStoryboardScriptId}
                  onChange={(e) => setNewStoryboardScriptId(e.target.value)}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                >
                  <option value="">请选择剧本…</option>
                  {filteredSmartScripts.map(script => (
                    <option key={script.id} value={script.id}>{script.title}</option>
                  ))}
                </select>
                {smartNovelId && filteredSmartScripts.length === 0 && (
                  <p className="mt-2 text-xs text-white/45">
                    当前{smartChapterId ? '章节' : '小说'}还没有可用剧本；智能生成可不选择剧本，系统会基于所选章节自动创建。
                  </p>
                )}
              </div>

              <div>
                <label className="text-sm text-white/60 mb-2 block">分镜风格</label>
                <select
                  value={newStoryboardStyle}
                  onChange={(e) => setNewStoryboardStyle(e.target.value)}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                >
                  {STORYBOARD_STYLE_OPTIONS.map(style => (
                    <option key={style.value} value={style.value}>{style.label}</option>
                  ))}
                </select>
              </div>

              <div className="flex gap-3 pt-4">
                <Button
                  variant="outline"
                  onClick={() => setShowNewModal(false)}
                  className="flex-1 border-white/20 text-white"
                >
                  取消
                </Button>
                <Button
                  onClick={handleCreateStoryboard}
                  disabled={!newStoryboardTitle.trim() || !newStoryboardScriptId}
                  className="flex-1 bg-purple-600 hover:bg-purple-700"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  创建空分镜
                </Button>
              </div>

              <div className="pt-2 border-t border-white/10">
                <p className="text-xs text-white/40">
                  手动创建适合空分镜搭建；智能生成会自动创建脚本、分镜和镜头，生成后在详情区审核修改。
                </p>
              </div>

              {newStoryboardScriptId && (
                <div className="pt-4 border-t border-white/10">
                  <Button
                    onClick={() => prepareGenerateFromScript(null)}
                    disabled={!newStoryboardScriptId || generatingStoryboard}
                    className="w-full bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700"
                  >
                    {generatingStoryboard ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        AI 生成分镜中…
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-4 h-4 mr-2" />
                        AI 从剧本生成
                      </>
                    )}
                  </Button>
                  <ModelCapabilitySelector
                    capability="text"
                    configs={modelConfigs}
                    value={textModelConfigId}
                    onChange={setTextModelConfigId}
                    disabled={generatingStoryboard}
                    title="剧本转分镜文本模型"
                    description="从剧本生成分镜时使用该文本模型配置。"
                    className="mt-3"
                    compact
                  />
                  <p className="text-xs text-white/40 mt-2 text-center">
                    将从所选剧本内容自动生成 {newStoryboardStyle} 风格的分镜镜头
                  </p>
                </div>
              )}
            </div>
        </DialogContent>
      </Dialog>
    </MainLayout>
  );
}

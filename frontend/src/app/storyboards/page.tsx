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
import { fetchWithAuth } from '@/lib/fetch-with-auth';
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
  Video
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

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const API_ORIGIN = API_BASE.replace(/\/api\/v1\/?$/, '');

const toMediaUrl = (url?: string | null) => {
  if (!url) return '';
  return url.startsWith('/') ? `${API_ORIGIN}${url}` : url;
};

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
    return chapter ? `第${chapter.chapter_number}章 ${chapter.title}` : chapterId ? `章节 ${chapterId.slice(0, 8)}...` : '未绑定章节';
  };

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

  const handleGenerateShotImage = async (shotId: string) => {
    setGeneratingImage(true);
    try {
      await fetchWithAuth(`${API_BASE}/shots/${shotId}/generate-image`, { method: 'POST' });
      pollShotImage(shotId);
    } catch (err) {
      console.error("Image generation failed:", err);
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
          setGeneratingImage(false);
          return;
        }
        if (shot.image_status === "failed") {
          setGeneratingImage(false);
          return;
        }
      } catch {
        // continue polling
      }
    }
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
      setSmartChapterId('');
      setMatchedTemplate(null);
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
      setSmartChapterId(list[0]?.id || '');
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
      const targetStoryboardId = urlParams.get('storyboard_id');
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
        setShots(Array.isArray(data) ? data : []);
      } else {
        setShots([]);
      }
    } catch (error) {
      console.error('加载镜头失败:', error);
      setShots([]);
    } finally {
      setLoadingShots(false);
    }
  };

  useEffect(() => {
    loadStoryboards();
    loadModelConfigs();
  }, []);

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
    }
  }, [smartNovelId]);

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
      setSelectedShot(null);
    } else {
      setShots([]);
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
  const handleAIGenerateStoryboard = async () => {
    if (!newStoryboardScriptId) {
      toast({ title: '请选择剧本', description: '需要先选择一个剧本。', type: 'error' });
      return;
    }
    setGeneratingStoryboard(true);
    try {
      const response = await fetchWithAuth(`${API_BASE}/storyboards/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script_id: newStoryboardScriptId,
          shot_count: 5,
          style: newStoryboardStyle || 'anime',
          model_config_id: textModelConfigId || undefined,
        })
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
    setGeneratingSmartStoryboard(true);
    try {
      const response = await fetchWithAuth(`${API_BASE}/storyboards/generate-smart`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          novel_id: smartNovelId,
          chapter_id: smartChapterId || undefined,
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
    if (target?.script_id) {
      setNewStoryboardScriptId(target.script_id);
      setNewStoryboardTitle(`${target.title || '分镜'} AI 重生成`);
      setNewStoryboardStyle((target.content?.style || newStoryboardStyle || 'anime'));
    }
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
              <div className="text-2xl font-bold text-blue-400">{shots.filter(s => s.video_url).length}</div>
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
                            第{chapter.chapter_number}章 {chapter.title}
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
                    <CardTitle className="text-white flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <LayoutGrid className="w-5 h-5 text-purple-400" />
                        <span className="text-lg">{selectedStoryboard.title}</span>
                        <span className="text-sm text-white/50">· {shots.length} 个镜头</span>
                      </div>
                      <div className="flex gap-2">
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
                    </div>
                    {/* 镜头列表 */}
                    <div className="space-y-3">
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
                      <div className="mt-6 pt-6 border-t border-white/10">
                        <h4 className="text-white font-medium mb-4">镜头 {selectedShot.shot_number} 详情</h4>
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

                        <div className="grid grid-cols-2 gap-4">
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

                        <div className="mt-4">
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
                        <div className="mt-4">
                          <div className="flex items-center justify-between mb-2">
                            <label className="text-sm font-medium text-white/60">参考图</label>
                            <button
                              type="button"
                              onClick={() => handleGenerateShotImage(selectedShot.id)}
                              disabled={generatingImage || !selectedShot.visual_description}
                              className="px-3 py-1 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              {generatingImage ? "生成中…" : "生成参考图"}
                            </button>
                          </div>
                          {(selectedShot.image_status === "generating" || selectedShot.image_status === "pending") && (
                            <div className="text-sm text-yellow-400">生成中…</div>
                          )}
                          {selectedShot.image_url && (
                            <img
                              src={toMediaUrl(selectedShot.image_url)}
                              alt="Shot reference"
                              width={640}
                              height={192}
                              loading="lazy"
                              className="w-full max-h-48 object-cover rounded-lg border border-white/10"
                            />
                          )}
                        </div>

                        <div className="mt-4">
                          <label className="text-sm text-white/60 mb-2 block">台词/配音</label>
                          <Input
                            value={selectedShot.dialogue || ''}
                            onChange={(e) => setSelectedShot({ ...selectedShot, dialogue: e.target.value })}
                            placeholder="输入镜头台词或配音内容"
                            className="bg-white/5 border-white/10 text-white"
                          />
                        </div>

                        {/* 精细化控制 */}
                        <div className="mt-6 pt-4 border-t border-white/10">
                          <h5 className="text-white font-medium mb-3">精细化控制</h5>
                          <div className="grid grid-cols-2 gap-4">
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

                          <div className="grid grid-cols-2 gap-4 mt-4">
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
        onOpenChange={setConfirmGenerateFromScript}
        onConfirm={async () => {
          await handleAIGenerateStoryboard();
          setConfirmGenerateFromScript(false);
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
                    onChange={(e) => setSmartNovelId(e.target.value)}
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
                      onChange={(e) => setSmartChapterId(e.target.value)}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                    >
                      <option value="">整部小说/简介</option>
                      {chapters.map(chapter => (
                        <option key={chapter.id} value={chapter.id}>
                          第{chapter.chapter_number}章 {chapter.title}
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
                  {scripts.map(script => (
                    <option key={script.id} value={script.id}>{script.title}</option>
                  ))}
                </select>
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

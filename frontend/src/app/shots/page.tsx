'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { MainLayout } from '@/components/layout/main-layout';
import { useToast } from '@/components/ui/toast';
import { fetchWithAuth } from '@/lib/fetch-with-auth';
import apiClient from '@/lib/api-client';
import {
  CAMERA_ANGLE_LABELS,
  CAMERA_ANGLE_OPTIONS,
  CAMERA_MOVEMENT_LABELS,
  CAMERA_MOVEMENT_OPTIONS,
  COLOR_GRADING_LABELS,
  COLOR_GRADING_OPTIONS,
  EMOTION_LABELS,
  EMOTION_OPTIONS,
  LIGHTING_LABELS,
  LIGHTING_OPTIONS,
  getShotAttributeLabel,
} from '@/lib/shot-labels';
import {
  Film,
  Loader2,
  AlertCircle,
  Search,
  Clock,
  Video,
  Mic,
  Camera,
  Play,
  CheckSquare,
  Square,
  Sparkles,
  Edit2,
  Trash2,
  ChevronDown,
  X,
  ImageIcon,
  ShieldCheck
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const API_ORIGIN = API_BASE.replace(/\/api\/v1\/?$/, '');

const toMediaUrl = (url?: string | null) => {
  if (!url) return '';
  return url.startsWith('/') ? `${API_ORIGIN}${url}` : url;
};

interface Shot {
  id: string;
  storyboard_id: string;
  storyboard_title?: string;
  script_id?: string;
  script_title?: string;
  novel_id?: string;
  novel_title?: string;
  chapter_id?: string;
  chapter_title?: string;
  shot_number: number;
  duration: number;
  prompt?: string;
  dialogue?: string;
  visual_description?: string;
  camera_angle?: string;
  video_url?: string;
  audio_url?: string;
  video_status: string;
  audio_status: string;
  camera_movement?: string;
  emotion?: string;
  lighting?: string;
  color_grading?: string;
  image_url?: string;
  image_status?: string;
  keyframes?: any[];
  character_refs?: any[];
  extra_data?: any;
  created_at: string;
  updated_at: string;
}

interface Storyboard {
  id: string;
  script_id?: string;
  novel_id?: string;
  chapter_id?: string;
  title: string;
  script_title?: string;
  shot_count: number;
  total_duration: number;
  content?: any;
}

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
}

interface Chapter {
  id: string;
  novel_id?: string;
  title: string;
  chapter_number?: number;
}

const VIDEO_STATUS_LABELS: Record<string, string> = {
  pending: '等待',
  running: '生成中',
  succeeded: '已完成',
  failed: '失败'
};

const QUALITY_STATUS_LABELS: Record<string, string> = {
  ready: '可生成',
  warning: '需注意',
  blocked: '阻断',
  unchecked: '未检查',
};

const QUALITY_STATUS_CLASSES: Record<string, string> = {
  ready: 'bg-green-500/20 text-green-300',
  warning: 'bg-yellow-500/20 text-yellow-200',
  blocked: 'bg-red-500/20 text-red-300',
  unchecked: 'bg-white/10 text-white/45',
};

const REVIEW_STATE_LABELS: Record<string, string> = {
  pending_review: '待审核',
  changes_requested: '需修改',
  approved: '已通过',
  locked: '已锁定',
};

const getShotQualityStatus = (shot: Shot) => shot.extra_data?.quality_report?.status || 'unchecked';
const getShotQualityScore = (shot: Shot) => shot.extra_data?.quality_report?.score;
const getShotReviewState = (shot: Shot) =>
  shot.extra_data?.production_context?.review_state || shot.extra_data?.review_state || 'pending_review';

export default function ShotsPage() {
  const { toast } = useToast();
  const router = useRouter();
  const [shots, setShots] = useState<Shot[]>([]);
  const [storyboards, setStoryboards] = useState<Storyboard[]>([]);
  const [scripts, setScripts] = useState<Script[]>([]);
  const [novels, setNovels] = useState<Novel[]>([]);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedNovel, setSelectedNovel] = useState<string>('all');
  const [selectedChapter, setSelectedChapter] = useState<string>('all');
  const [selectedScript, setSelectedScript] = useState<string>('all');
  const [selectedStoryboard, setSelectedStoryboard] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [selectedQuality, setSelectedQuality] = useState<string>('all');
  const [selectedReviewState, setSelectedReviewState] = useState<string>('all');
  const [selectedShot, setSelectedShot] = useState<Shot | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Shot | null>(null);
  const [deletingShotId, setDeletingShotId] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState<Partial<Shot>>({});
  const [saving, setSaving] = useState(false);
  const [selectedShots, setSelectedShots] = useState<Set<string>>(new Set());
  const [showFilters, setShowFilters] = useState(false);
  const [batchGenerating, setBatchGenerating] = useState(false);
  const [batchProgress, setBatchProgress] = useState<Record<string, string>>({});
  const [productionContext, setProductionContext] = useState<any>({});
  const [qualityReport, setQualityReport] = useState<any>({});
  const [budgetEstimate, setBudgetEstimate] = useState<any>({});
  const [qualityLoading, setQualityLoading] = useState(false);
  const [qualityBatchLoading, setQualityBatchLoading] = useState(false);
  const [reviewBatchLoading, setReviewBatchLoading] = useState(false);
  const [productionSaving, setProductionSaving] = useState(false);
  const [productionForm, setProductionForm] = useState({
    assetLocksJson: '[]',
    keyframesJson: '[]',
    multiviewJson: '[]',
    entityBindingsJson: '[]',
    lipSyncJson: '{}',
    reviewState: 'pending_review',
    reviewNotes: '',
    reviewAssignees: '',
  });

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

  const getChapterLabel = (chapterId?: string) => {
    const chapter = chapters.find((item) => item.id === chapterId);
    if (!chapter) return chapterId ? `章节 ${chapterId.slice(0, 8)}...` : '未绑定章节';
    return chapter.chapter_number ? `第${chapter.chapter_number}章 ${chapter.title}` : chapter.title;
  };

  const loadChaptersForNovel = async (novelId: string) => {
    if (!novelId || novelId === 'all') {
      setChapters([]);
      return [];
    }
    try {
      const response = await fetchWithAuth(`${API_BASE}/chapters/novel/${novelId}`);
      if (!response.ok) {
        setChapters([]);
        return [];
      }
      const data = await response.json();
      const list = Array.isArray(data) ? data : [];
      setChapters(list);
      return list;
    } catch (err) {
      console.error('加载章节失败:', err);
      setChapters([]);
      return [];
    }
  };

  // 加载所有镜头和上游链路
  const loadShots = async () => {
    setLoading(true);
    setError(null);
    try {
      const novelsRes = await fetchWithAuth(`${API_BASE}/novels`);
      if (novelsRes.ok) {
        const novelData = await novelsRes.json();
        setNovels(Array.isArray(novelData) ? novelData : []);
      }

      const urlParams = new URLSearchParams(window.location.search);
      const urlNovelId = urlParams.get('novel_id') || '';
      const urlChapterId = urlParams.get('chapter_id') || '';
      const urlScriptId = urlParams.get('script_id') || '';
      const urlStoryboardId = urlParams.get('storyboard_id') || '';
      if (urlNovelId) {
        setSelectedNovel(urlNovelId);
        await loadChaptersForNovel(urlNovelId);
      }
      if (urlChapterId) setSelectedChapter(urlChapterId);
      if (urlScriptId) setSelectedScript(urlScriptId);
      if (urlStoryboardId) setSelectedStoryboard(urlStoryboardId);

      const scriptsRes = await fetchWithAuth(`${API_BASE}/scripts`);
      if (!scriptsRes.ok) throw new Error('加载剧本失败');
      const scriptsData = await scriptsRes.json();
      const scriptsList: Script[] = Array.isArray(scriptsData) ? scriptsData : [];
      setScripts(scriptsList);

      // 再获取每个剧本的分镜和镜头
      const allShots: Shot[] = [];
      const allStoryboards: Storyboard[] = [];
      for (const script of scriptsList) {
        const sbRes = await fetchWithAuth(`${API_BASE}/storyboards/script/${script.id}`);
        if (sbRes.ok) {
          const sbs = await sbRes.json();
          for (const sb of Array.isArray(sbs) ? sbs : []) {
            const sbNovelId = sb.novel_id || sb.content?.novel_id || script.novel_id;
            const sbChapterId = sb.chapter_id || sb.content?.chapter_id || script.chapter_id;
            const sbWithLineage: Storyboard = {
              id: sb.id,
              script_id: script.id,
              novel_id: sbNovelId,
              chapter_id: sbChapterId,
              title: sb.title,
              script_title: script.title,
              shot_count: sb.shot_count,
              total_duration: sb.total_duration,
              content: sb.content,
            };
            allStoryboards.push(sbWithLineage);
            const shotsRes = await fetchWithAuth(`${API_BASE}/shots/storyboard/${sb.id}`);
            if (shotsRes.ok) {
              const shotsData = await shotsRes.json();
              const shotsWithTitle = (Array.isArray(shotsData) ? shotsData : []).map((shot: any) => ({
                ...shot,
                storyboard_title: sb.title,
                script_id: script.id,
                script_title: script.title,
                novel_id: sbNovelId,
                novel_title: script.novel_title,
                chapter_id: sbChapterId,
                chapter_title: getChapterLabel(sbChapterId),
              }));
              allShots.push(...shotsWithTitle);
            }
          }
        }
      }
      setStoryboards(allStoryboards);
      setShots(allShots);
    } catch (err: any) {
      console.error('加载镜头失败:', err);
      setError(err.message || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadShots();
  }, []);

  useEffect(() => {
    if (selectedNovel !== 'all') {
      loadChaptersForNovel(selectedNovel);
    } else {
      setChapters([]);
      setSelectedChapter('all');
    }
  }, [selectedNovel]);

  // 筛选镜头
  const filteredShots = shots.filter(shot => {
    const matchesSearch = !searchQuery ||
      shot.prompt?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      shot.dialogue?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      shot.visual_description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      shot.storyboard_title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      shot.script_title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      shot.novel_title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      shot.chapter_title?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesNovel = selectedNovel === 'all' || shot.novel_id === selectedNovel;
    const matchesChapter = selectedChapter === 'all' || shot.chapter_id === selectedChapter;
    const matchesScript = selectedScript === 'all' || shot.script_id === selectedScript;
    const matchesStoryboard = selectedStoryboard === 'all' || shot.storyboard_id === selectedStoryboard;
    const matchesStatus = selectedStatus === 'all' || shot.video_status === selectedStatus;
    const matchesQuality = selectedQuality === 'all' || getShotQualityStatus(shot) === selectedQuality;
    const matchesReview = selectedReviewState === 'all' || getShotReviewState(shot) === selectedReviewState;
    return matchesSearch && matchesNovel && matchesChapter && matchesScript && matchesStoryboard && matchesStatus && matchesQuality && matchesReview;
  });

  const filteredScriptsForSelect = scripts.filter(script => {
    if (selectedNovel !== 'all' && script.novel_id !== selectedNovel) return false;
    if (selectedChapter !== 'all' && script.chapter_id !== selectedChapter) return false;
    return true;
  });

  const filteredStoryboardsForSelect = storyboards.filter(storyboard => {
    if (selectedNovel !== 'all' && storyboard.novel_id !== selectedNovel) return false;
    if (selectedChapter !== 'all' && storyboard.chapter_id !== selectedChapter) return false;
    if (selectedScript !== 'all' && storyboard.script_id !== selectedScript) return false;
    return true;
  });

  // 选择/取消选择镜头
  const toggleShotSelection = (shotId: string) => {
    const newSelected = new Set(selectedShots);
    if (newSelected.has(shotId)) {
      newSelected.delete(shotId);
    } else {
      newSelected.add(shotId);
    }
    setSelectedShots(newSelected);
  };

  // 全选/取消全选
  const toggleSelectAll = () => {
    if (selectedShots.size === filteredShots.length) {
      setSelectedShots(new Set());
    } else {
      setSelectedShots(new Set(filteredShots.map(s => s.id)));
    }
  };

  // 生成视频（单个）
  const handleGenerateVideo = (shot: Shot) => {
    const params = new URLSearchParams();
    if (shot.novel_id) params.set('novel_id', shot.novel_id);
    if (shot.chapter_id) params.set('chapter_id', shot.chapter_id);
    if (shot.script_id) params.set('script_id', shot.script_id);
    if (shot.storyboard_id) params.set('storyboard_id', shot.storyboard_id);
    params.set('shot_id', shot.id);
    params.set('prompt', shot.prompt || shot.visual_description || '');
    router.push(`/video-generation?${params.toString()}`);
  };

  // 生成语音（单个）
  const handleGenerateTTS = async (shot: Shot) => {
    if (!shot.dialogue) {
      toast({ title: '无法生成语音', description: '该镜头没有对话文本。', type: 'info' });
      return;
    }
    try {
      const res = await fetchWithAuth(`${API_BASE}/tts/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text_content: shot.dialogue,
          title: `镜头${shot.shot_number}语音`,
          shot_id: shot.id,
          storyboard_id: shot.storyboard_id,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        toast({ title: '语音生成任务已创建', description: `当前状态：${data.status || '已提交'}`, type: 'success' });
      } else {
        const err = await res.json();
        toast({ title: '生成失败', description: err.detail || err.message || '未知错误', type: 'error' });
      }
    } catch (err: any) {
      toast({ title: '生成失败', description: err.message || '请稍后重试。', type: 'error' });
    }
  };

  // 批量生成视频
  const handleBatchGenerate = () => {
    const ids = Array.from(selectedShots).join(',');
    router.push(`/video-generation?shot_ids=${ids}`);
  };

  // 批量生成参考图
  const handleBatchGenerateImages = async () => {
    if (selectedShots.size === 0) return;
    // Find a common storyboard for the selected shots
    const shotArray = shots.filter(s => selectedShots.has(s.id));
    const storyboardIds = Array.from(new Set(shotArray.map(s => s.storyboard_id)));
    if (storyboardIds.length === 0) return;

    setBatchGenerating(true);
    const progress: Record<string, string> = {};
    shotArray.forEach(shot => { progress[shot.id] = "pending"; });
    setBatchProgress(progress);

    try {
      // Process each storyboard's shots
      for (const sbId of storyboardIds) {
        const sbShotIds = shotArray.filter(s => s.storyboard_id === sbId).map(s => s.id);
        try {
          const results = await fetchWithAuth(`${API_BASE}/storyboards/${sbId}/shots/generate-images`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(sbShotIds)
          });
          const data = await results.json();
          for (const r of data.results || []) {
            if (r.status === "generating") {
              setBatchProgress(prev => ({ ...prev, [r.shot_id]: "generating" }));
              pollBatchShotImage(r.shot_id, sbId);
            } else if (r.status === "skipped" || r.status === "error") {
              setBatchProgress(prev => ({ ...prev, [r.shot_id]: r.status }));
            }
          }
        } catch (err) {
          console.error(`Batch generation failed for storyboard ${sbId}:`, err);
        }
      }
      setBatchGenerating(false);
    } catch (err) {
      console.error("Batch generation failed:", err);
      setBatchGenerating(false);
    }
  };

  const pollBatchShotImage = async (shotId: string, storyboardId: string) => {
    for (let i = 0; i < 60; i++) {
      await new Promise(r => setTimeout(r, 3000));
      try {
        const response = await fetchWithAuth(`${API_BASE}/shots/${shotId}`);
        if (!response.ok) continue;
        const shot: Shot = await response.json();
        if (shot.image_status === "succeeded") {
          setBatchProgress(prev => ({ ...prev, [shotId]: "succeeded" }));
          // Refresh shots list for this storyboard
          const updated = await fetchWithAuth(`${API_BASE}/shots/storyboard/${storyboardId}`);
          if (updated.ok) {
            const updatedShots: Shot[] = await updated.json();
            setShots(prev => prev.map(s => {
              const updated = updatedShots.find(u => u.id === s.id);
              return updated ? { ...s, ...updated } : s;
            }));
          }
          setBatchProgress(prev => {
            const nextProgress = { ...prev, [shotId]: "succeeded" };
            const vals = Object.values(nextProgress);
            if (!vals.includes("generating") && !vals.includes("pending")) {
              setBatchGenerating(false);
            }
            return nextProgress;
          });
          return;
        }
        if (shot.image_status === "failed") {
          setBatchProgress(prev => ({ ...prev, [shotId]: "failed" }));
          setBatchGenerating(false);
          return;
        }
      } catch (err) {
        console.error(`Poll failed for shot ${shotId}:`, err);
      }
    }
    setBatchProgress(prev => ({ ...prev, [shotId]: "timeout" }));
    setBatchGenerating(false);
  };

  // 编辑镜头
  const handleEdit = (shot: Shot) => {
    setSelectedShot(shot);
    setEditData({ ...shot });
    setIsEditing(true);
    loadProductionContext(shot);
    loadShotQuality(shot);
  };

  const loadProductionContext = async (shot: Shot) => {
    const fallback = shot.extra_data?.production_context || {};
    try {
      const response = await apiClient.getShotProductionContext(shot.id);
      const context = response.production_context || fallback;
      setProductionContext(context);
      setProductionForm({
        assetLocksJson: JSON.stringify(context.asset_version_locks || [], null, 2),
        keyframesJson: JSON.stringify(context.keyframes || shot.keyframes || [], null, 2),
        multiviewJson: JSON.stringify(context.character_multiview_refs || [], null, 2),
        entityBindingsJson: JSON.stringify(context.entity_reference_bindings || [], null, 2),
        lipSyncJson: JSON.stringify(context.lip_sync || {}, null, 2),
        reviewState: context.review_state || 'pending_review',
        reviewNotes: context.review_notes || '',
        reviewAssignees: (context.review_assignees || []).join(', '),
      });
    } catch (err) {
      setProductionContext(fallback);
      setProductionForm({
        assetLocksJson: JSON.stringify(fallback.asset_version_locks || [], null, 2),
        keyframesJson: JSON.stringify(fallback.keyframes || shot.keyframes || [], null, 2),
        multiviewJson: JSON.stringify(fallback.character_multiview_refs || [], null, 2),
        entityBindingsJson: JSON.stringify(fallback.entity_reference_bindings || [], null, 2),
        lipSyncJson: JSON.stringify(fallback.lip_sync || {}, null, 2),
        reviewState: fallback.review_state || 'pending_review',
        reviewNotes: fallback.review_notes || '',
        reviewAssignees: (fallback.review_assignees || []).join(', '),
      });
    }
  };

  const loadShotQuality = async (shot: Shot) => {
    setQualityLoading(true);
    try {
      const response = await apiClient.getShotQuality(shot.id);
      setQualityReport(response.quality_report || {});
      setBudgetEstimate(response.budget_estimate || {});
    } catch (err) {
      setQualityReport(shot.extra_data?.quality_report || {});
      setBudgetEstimate(shot.extra_data?.budget_estimate || {});
    } finally {
      setQualityLoading(false);
    }
  };

  const refreshShotQuality = async () => {
    if (!selectedShot) return;
    setQualityLoading(true);
    try {
      const response = await apiClient.refreshShotQuality(selectedShot.id);
      setQualityReport(response.quality_report || {});
      setBudgetEstimate(response.budget_estimate || {});
      setShots(prev => prev.map(s => s.id === selectedShot.id ? {
        ...s,
        extra_data: {
          ...(s.extra_data || {}),
          quality_report: response.quality_report,
          budget_estimate: response.budget_estimate,
        },
      } : s));
    } catch (err: any) {
      toast({ title: '质量检查失败', description: err.message || '请稍后重试。', type: 'error' });
    } finally {
      setQualityLoading(false);
    }
  };

  const applyQualityItemsToShots = (items: any[]) => {
    setShots(prev => prev.map(shot => {
      const item = items.find((entry: any) => entry.shot_id === shot.id);
      if (!item) return shot;
      return {
        ...shot,
        extra_data: {
          ...(shot.extra_data || {}),
          quality_report: item.quality_report,
          budget_estimate: item.budget_estimate,
        },
      };
    }));
  };

  const handleBatchRefreshQuality = async () => {
    const shotIds = Array.from(selectedShots);
    if (shotIds.length === 0) return;
    setQualityBatchLoading(true);
    try {
      const response = await apiClient.refreshShotsQuality(shotIds);
      applyQualityItemsToShots(response.items || []);
      toast({ title: '批量质量检查完成', description: `已重检 ${response.refreshed || 0} 个镜头。`, type: 'success' });
    } catch (err: any) {
      toast({ title: '批量质量检查失败', description: err.message || '请稍后重试。', type: 'error' });
    } finally {
      setQualityBatchLoading(false);
    }
  };

  // 保存镜头
  const handleSave = async () => {
    if (!selectedShot) return;
    setSaving(true);
    try {
      const response = await fetchWithAuth(`${API_BASE}/shots/${selectedShot.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editData)
      });
      if (response.ok) {
        const updated: Shot = await response.json();
        const updatedWithLineage = { ...selectedShot, ...updated };
        setShots(shots.map(s => s.id === updated.id ? updatedWithLineage : s));
        setSelectedShot(updatedWithLineage);
        setIsEditing(false);
        toast({ title: '镜头已保存', type: 'success' });
      } else {
        throw new Error('保存失败');
      }
    } catch (err: any) {
      toast({ title: '保存失败', description: err.message || '请稍后重试。', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const parseJsonField = (value: string, fallback: any) => {
    const trimmed = value.trim();
    if (!trimmed) return fallback;
    return JSON.parse(trimmed);
  };

  const handleSaveProductionContext = async () => {
    if (!selectedShot) return;
    setProductionSaving(true);
    try {
      const payload = {
        asset_version_locks: parseJsonField(productionForm.assetLocksJson, []),
        keyframes: parseJsonField(productionForm.keyframesJson, []),
        character_multiview_refs: parseJsonField(productionForm.multiviewJson, []),
        entity_reference_bindings: parseJsonField(productionForm.entityBindingsJson, []),
        lip_sync: parseJsonField(productionForm.lipSyncJson, {}),
        review_state: productionForm.reviewState,
        review_notes: productionForm.reviewNotes,
        review_assignees: productionForm.reviewAssignees
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
      };
      const response = await apiClient.updateShotProductionContext(selectedShot.id, payload);
      setProductionContext(response.production_context || {});
      setShots(prev => prev.map(s => s.id === selectedShot.id ? {
        ...s,
        keyframes: payload.keyframes,
        extra_data: {
          ...(s.extra_data || {}),
          production_context: response.production_context,
        },
      } : s));
      await refreshShotQuality();
      toast({ title: '生产上下文已保存', type: 'success' });
    } catch (err: any) {
      toast({ title: '生产上下文保存失败', description: err.message || '请检查 JSON 格式。', type: 'error' });
    } finally {
      setProductionSaving(false);
    }
  };

  const handleBatchReviewState = async (reviewState: string) => {
    const shotIds = Array.from(selectedShots);
    if (shotIds.length === 0) return;
    setReviewBatchLoading(true);
    try {
      const updatedContexts: Record<string, any> = {};
      for (const shotId of shotIds) {
        const response = await apiClient.updateShotProductionContext(shotId, {
          review_state: reviewState,
          review_notes: reviewState === 'approved' ? '批量审核通过' : '批量标记需修改',
        });
        updatedContexts[shotId] = response.production_context || {};
      }
      setShots(prev => prev.map(shot => updatedContexts[shot.id] ? {
        ...shot,
        extra_data: {
          ...(shot.extra_data || {}),
          production_context: updatedContexts[shot.id],
        },
      } : shot));
      const qualityResponse = await apiClient.refreshShotsQuality(shotIds);
      applyQualityItemsToShots(qualityResponse.items || []);
      toast({ title: '批量审核已更新', description: `已更新 ${shotIds.length} 个镜头审核状态。`, type: 'success' });
    } catch (err: any) {
      toast({ title: '批量审核失败', description: err.message || '请稍后重试。', type: 'error' });
    } finally {
      setReviewBatchLoading(false);
    }
  };

  // 删除镜头
  const handleDelete = async (shotId: string) => {
    setDeletingShotId(shotId);
    try {
      const response = await fetchWithAuth(`${API_BASE}/shots/${shotId}`, {
        method: 'DELETE'
      });
      if (response.ok) {
        setShots(shots.filter(s => s.id !== shotId));
        if (selectedShot?.id === shotId) {
          setSelectedShot(null);
          setIsEditing(false);
        }
        toast({ title: '镜头已删除', type: 'success' });
      }
    } catch (err: any) {
      console.error('删除镜头失败:', err);
      toast({ title: '删除失败', description: err?.message || '请稍后重试。', type: 'error' });
    } finally {
      setDeletingShotId(null);
    }
  };

  const totalDuration = filteredShots.reduce((sum, s) => sum + (s.duration || 0), 0);
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
            <h1 className="text-3xl font-bold text-white flex items-center gap-2">
              <Film className="w-7 h-7" />
              镜头管理
            </h1>
            <p className="text-white/60 mt-1">管理镜头、资产版本锁、关键帧、多视图参考、口型和审核状态</p>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            {selectedShots.size > 0 && (
              <Button
                onClick={handleBatchGenerateImages}
                disabled={batchGenerating}
                className="bg-purple-600 hover:bg-purple-700"
              >
                {batchGenerating ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <ImageIcon className="w-4 h-4 mr-1" />}
                批量生成参考图 ({selectedShots.size})
              </Button>
            )}
            {selectedShots.size > 0 && (
              <Button
                onClick={handleBatchRefreshQuality}
                disabled={qualityBatchLoading}
                className="bg-cyan-600 hover:bg-cyan-700"
              >
                {qualityBatchLoading ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <ShieldCheck className="w-4 h-4 mr-1" />}
                批量重检 ({selectedShots.size})
              </Button>
            )}
            {selectedShots.size > 0 && (
              <Button
                onClick={() => handleBatchReviewState('approved')}
                disabled={reviewBatchLoading}
                className="bg-emerald-600 hover:bg-emerald-700"
              >
                {reviewBatchLoading ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <CheckSquare className="w-4 h-4 mr-1" />}
                批量通过
              </Button>
            )}
            {selectedShots.size > 0 && (
              <Button
                onClick={() => handleBatchReviewState('changes_requested')}
                disabled={reviewBatchLoading}
                variant="outline"
                className="border-yellow-500/50 text-yellow-200 hover:bg-yellow-500/10"
              >
                退回修改
              </Button>
            )}
            {selectedShots.size > 0 && (
              <Button
                onClick={handleBatchGenerate}
                className="bg-violet-600 hover:bg-violet-700"
              >
                <Video className="w-4 h-4 mr-1" />
                批量生成 ({selectedShots.size})
              </Button>
            )}
            <Button
              variant="outline"
              onClick={() => setShowFilters(!showFilters)}
              className="border-white/20 text-white"
            >
              <Camera className="w-4 h-4 mr-1" />
              筛选
              <ChevronDown className={`w-4 h-4 ml-1 transition-transform ${showFilters ? 'rotate-180' : ''}`} />
            </Button>
          </div>
        </div>

        <Card className="bg-cyan-500/10 border-cyan-500/20">
          <CardContent className="p-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="text-white font-medium flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-cyan-300" />
                镜头生产上下文已接入
              </div>
              <div className="text-white/55 text-sm mt-1">
                打开任意镜头的编辑面板，可维护资产锁、关键帧、多视图角色参考、口型配置和多人审核状态。
              </div>
            </div>
            <Button asChild variant="outline" className="border-cyan-500/40 text-cyan-100 hover:bg-cyan-500/10">
              <Link href="/production-adapters">
                生产适配配置
              </Link>
            </Button>
          </CardContent>
        </Card>

        {/* 统计信息 */}
        <div className="grid grid-cols-4 gap-4">
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-white">{shots.length}</div>
              <div className="text-sm text-white/60">总镜头数</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-green-400">
                {shots.filter(s => s.video_status === 'succeeded').length}
              </div>
              <div className="text-sm text-white/60">已生成</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-blue-400">
                {shots.filter(s => s.video_status === 'running' || s.video_status === 'pending').length}
              </div>
              <div className="text-sm text-white/60">生成中/等待</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-violet-400">{formatTime(totalDuration)}</div>
              <div className="text-sm text-white/60">总时长</div>
            </CardContent>
          </Card>
        </div>

        {/* 搜索和筛选 */}
        {showFilters && (
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4">
              <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-8 gap-4">
                <div>
                  <label className="text-sm text-white/60 mb-1 block">搜索</label>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                    <Input
                      placeholder="搜索镜头内容…"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pl-10 bg-white/5 border-white/10 text-white placeholder:text-white/40"
                    />
                  </div>
                </div>
                <div>
                  <label className="text-sm text-white/60 mb-1 block">小说</label>
                  <select
                    value={selectedNovel}
                    onChange={(e) => {
                      setSelectedNovel(e.target.value);
                      setSelectedChapter('all');
                      setSelectedScript('all');
                      setSelectedStoryboard('all');
                    }}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                  >
                    <option value="all">全部小说</option>
                    {novels.map(novel => (
                      <option key={novel.id} value={novel.id}>{novel.title}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-sm text-white/60 mb-1 block">章节</label>
                  <select
                    value={selectedChapter}
                    onChange={(e) => {
                      setSelectedChapter(e.target.value);
                      setSelectedScript('all');
                      setSelectedStoryboard('all');
                    }}
                    disabled={selectedNovel === 'all'}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white disabled:opacity-50"
                  >
                    <option value="all">全部章节</option>
                    {chapters.map(chapter => (
                      <option key={chapter.id} value={chapter.id}>
                        {chapter.chapter_number ? `第${chapter.chapter_number}章 ` : ''}{chapter.title}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-sm text-white/60 mb-1 block">剧本</label>
                  <select
                    value={selectedScript}
                    onChange={(e) => {
                      setSelectedScript(e.target.value);
                      setSelectedStoryboard('all');
                    }}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                  >
                    <option value="all">全部剧本</option>
                    {filteredScriptsForSelect.map(script => (
                      <option key={script.id} value={script.id}>{script.title}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-sm text-white/60 mb-1 block">分镜</label>
                  <select
                    value={selectedStoryboard}
                    onChange={(e) => setSelectedStoryboard(e.target.value)}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                  >
                    <option value="all">全部</option>
                    {filteredStoryboardsForSelect.map(sb => (
                      <option key={sb.id} value={sb.id}>{sb.title}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-sm text-white/60 mb-1 block">视频状态</label>
                  <select
                    value={selectedStatus}
                    onChange={(e) => setSelectedStatus(e.target.value)}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                  >
                    <option value="all">全部</option>
                    <option value="pending">等待</option>
                    <option value="running">生成中</option>
                    <option value="succeeded">已完成</option>
                    <option value="failed">失败</option>
                  </select>
                </div>
                <div>
                  <label className="text-sm text-white/60 mb-1 block">质量状态</label>
                  <select
                    value={selectedQuality}
                    onChange={(e) => setSelectedQuality(e.target.value)}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                  >
                    <option value="all">全部</option>
                    <option value="ready">可生成</option>
                    <option value="warning">需注意</option>
                    <option value="blocked">阻断</option>
                    <option value="unchecked">未检查</option>
                  </select>
                </div>
                <div>
                  <label className="text-sm text-white/60 mb-1 block">审核状态</label>
                  <select
                    value={selectedReviewState}
                    onChange={(e) => setSelectedReviewState(e.target.value)}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                  >
                    <option value="all">全部</option>
                    <option value="pending_review">待审核</option>
                    <option value="changes_requested">需修改</option>
                    <option value="approved">已通过</option>
                    <option value="locked">已锁定</option>
                  </select>
                </div>
              </div>
              {(searchQuery || selectedNovel !== 'all' || selectedChapter !== 'all' || selectedScript !== 'all' || selectedStoryboard !== 'all' || selectedStatus !== 'all' || selectedQuality !== 'all' || selectedReviewState !== 'all') && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setSearchQuery('');
                    setSelectedNovel('all');
                    setSelectedChapter('all');
                    setSelectedScript('all');
                    setSelectedStoryboard('all');
                    setSelectedStatus('all');
                    setSelectedQuality('all');
                    setSelectedReviewState('all');
                  }}
                  className="mt-2 text-white/60 hover:text-white"
                >
                  <X className="w-4 h-4 mr-1" />
                  清除筛选
                </Button>
              )}
            </CardContent>
          </Card>
        )}

        {/* 加载状态 */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-violet-400" />
            <span className="ml-3 text-white/60">加载中…</span>
          </div>
        )}

        {/* 错误提示 */}
        {error && (
          <Card className="bg-red-500/10 border-red-500/30">
            <CardContent className="p-4 flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-red-400" />
              <span className="text-red-300">{error}</span>
              <Button variant="outline" size="sm" onClick={loadShots} className="ml-auto border-red-500/50 text-red-400">
                重试
              </Button>
            </CardContent>
          </Card>
        )}

        {/* 镜头列表 */}
        {!loading && !error && (
          <div className="space-y-4">
            {/* 全选栏 */}
            {filteredShots.length > 0 && (
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={toggleSelectAll}
                  className="text-white/60 hover:text-white"
                >
                  {selectedShots.size === filteredShots.length ? (
                    <CheckSquare className="w-4 h-4 mr-1" />
                  ) : (
                    <Square className="w-4 h-4 mr-1" />
                  )}
                  {selectedShots.size === filteredShots.length ? '取消全选' : '全选'}
                </Button>
                <span className="text-white/40 text-sm">
                  已选择 {selectedShots.size} / {filteredShots.length} 个镜头
                </span>
              </div>
            )}

            {/* 网格布局 */}
            {filteredShots.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {filteredShots.map((shot) => (
                  <Card
                    key={shot.id}
                    className={`bg-white/5 border-white/10 hover:border-violet-500/30 transition-colors cursor-pointer ${
                      selectedShots.has(shot.id) ? 'ring-2 ring-violet-500' : ''
                    }`}
                    onClick={() => !isEditing && setSelectedShot(shot)}
                  >
                    <CardContent className="p-4 relative">
                      {(() => {
                        const qualityStatus = getShotQualityStatus(shot);
                        const qualityScore = getShotQualityScore(shot);
                        const reviewState = getShotReviewState(shot);
                        return (
                          <div className="absolute top-2 right-2 z-10 flex flex-col items-end gap-1">
                            <span className={`px-2 py-0.5 rounded text-xs ${QUALITY_STATUS_CLASSES[qualityStatus] || QUALITY_STATUS_CLASSES.unchecked}`}>
                              {QUALITY_STATUS_LABELS[qualityStatus] || qualityStatus}
                              {qualityScore !== undefined ? ` ${qualityScore}` : ''}
                            </span>
                            <span className="px-2 py-0.5 rounded bg-white/10 text-white/55 text-xs">
                              {REVIEW_STATE_LABELS[reviewState] || reviewState}
                            </span>
                          </div>
                        );
                      })()}
                      {/* Image status overlay */}
                      {batchProgress[shot.id] === "generating" && (
                        <span className="absolute top-2 left-2 z-20 px-2 py-1 bg-yellow-500 text-white text-xs rounded flex items-center gap-1">
                          <Loader2 className="w-3 h-3 animate-spin" />
                          生成中…
                        </span>
                      )}
                      {batchProgress[shot.id] === "succeeded" && (
                        <span className="absolute top-2 left-2 z-20 px-2 py-1 bg-green-500 text-white text-xs rounded">
                          图片已生成
                        </span>
                      )}
                      {batchProgress[shot.id] === "failed" && (
                        <span className="absolute top-2 left-2 z-20 px-2 py-1 bg-red-500 text-white text-xs rounded">
                          生成失败
                        </span>
                      )}
                      {shot.image_status === "succeeded" && shot.image_url && (
                        <img
                          src={toMediaUrl(shot.image_url)}
                          className="absolute inset-0 w-full h-full object-cover opacity-20 rounded-lg"
                          alt=""
                          width={480}
                          height={270}
                          loading="lazy"
                        />
                      )}
                      <div className="flex items-start justify-between mb-3 pr-24">
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            aria-label={`${selectedShots.has(shot.id) ? '取消选择' : '选择'}镜头 ${shot.shot_number}`}
                            title={selectedShots.has(shot.id) ? '取消选择' : '选择镜头'}
                            onClick={(e) => { e.stopPropagation(); toggleShotSelection(shot.id); }}
                            className="rounded text-white/40 transition-colors hover:text-violet-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
                          >
                            {selectedShots.has(shot.id) ? (
                              <CheckSquare className="w-4 h-4" />
                            ) : (
                              <Square className="w-4 h-4" />
                            )}
                          </button>
                          <span className="w-7 h-7 rounded bg-violet-500/20 text-violet-300 text-xs flex items-center justify-center">
                            {shot.shot_number}
                          </span>
                          <div>
                            <span className="text-white/40 text-xs">{shot.storyboard_title}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-1">
                          {shot.video_status === 'succeeded' && shot.video_url && (
                            <Button
                              variant="ghost"
                              size="icon"
                              aria-label={`播放镜头 ${shot.shot_number} 视频`}
                              title="播放视频"
                              className="w-6 h-6 text-green-400"
                              onClick={(e) => { e.stopPropagation(); window.open(shot.video_url, '_blank'); }}
                            >
                              <Play className="w-3 h-3" />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label={`编辑镜头 ${shot.shot_number}`}
                            title="编辑镜头"
                            className="w-6 h-6 text-white/40 hover:text-white"
                            onClick={(e) => { e.stopPropagation(); handleEdit(shot); }}
                          >
                            <Edit2 className="w-3 h-3" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label={`删除镜头 ${shot.shot_number}`}
                            title="删除镜头"
                            className="w-6 h-6 text-red-400/60 hover:text-red-400"
                            onClick={(e) => { e.stopPropagation(); setDeleteTarget(shot); }}
                            disabled={deletingShotId === shot.id}
                          >
                            <Trash2 className="w-3 h-3" />
                          </Button>
                        </div>
                      </div>

                      {/* 镜头信息 */}
                      <div className="space-y-2">
                        {shot.prompt && (
                          <p className="text-white text-sm line-clamp-2">{shot.prompt}</p>
                        )}
                        {shot.visual_description && (
                          <p className="text-white/60 text-xs line-clamp-2">{shot.visual_description}</p>
                        )}

                        {(shot.novel_title || shot.chapter_title || shot.script_title) && (
                          <div className="rounded border border-white/10 bg-white/5 px-2 py-1 text-xs text-white/45 line-clamp-2">
                            {[shot.novel_title, shot.chapter_title, shot.script_title].filter(Boolean).join(' / ')}
                          </div>
                        )}

                        {/* 元数据 */}
                        <div className="flex flex-wrap gap-2 text-xs text-white/40">
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {shot.duration}s
                          </span>
                          {shot.camera_angle && (
                            <span className="flex items-center gap-1">
                              <Camera className="w-3 h-3" />
                              {getShotAttributeLabel(CAMERA_ANGLE_LABELS, shot.camera_angle)}
                            </span>
                          )}
                          {shot.camera_movement && (
                            <span className="px-1.5 py-0.5 rounded bg-white/10">
                              {getShotAttributeLabel(CAMERA_MOVEMENT_LABELS, shot.camera_movement)}
                            </span>
                          )}
                          {shot.emotion && (
                            <span className="px-1.5 py-0.5 rounded bg-white/10">
                              {getShotAttributeLabel(EMOTION_LABELS, shot.emotion)}
                            </span>
                          )}
                          {shot.lighting && (
                            <span className="px-1.5 py-0.5 rounded bg-white/10">
                              {getShotAttributeLabel(LIGHTING_LABELS, shot.lighting)}
                            </span>
                          )}
                          {shot.color_grading && (
                            <span className="px-1.5 py-0.5 rounded bg-white/10">
                              {getShotAttributeLabel(COLOR_GRADING_LABELS, shot.color_grading)}
                            </span>
                          )}
                        </div>

                        {(shot.extra_data?.quality_report?.warnings?.length || shot.extra_data?.quality_report?.blockers?.length) && (
                          <div className="rounded border border-white/10 bg-black/20 px-2 py-1 text-xs text-white/50">
                            {shot.extra_data?.quality_report?.blockers?.length ? (
                              <span className="text-red-300">阻断 {shot.extra_data.quality_report.blockers.length}</span>
                            ) : (
                              <span className="text-yellow-200">风险 {shot.extra_data.quality_report.warnings.length}</span>
                            )}
                            {shot.extra_data?.budget_estimate?.estimated_total_tokens && (
                              <span className="ml-2">预算 {shot.extra_data.budget_estimate.estimated_total_tokens} tokens</span>
                            )}
                          </div>
                        )}

                        {/* 台词 */}
                        {shot.dialogue && (
                          <div className="flex items-start gap-1 mt-1">
                            <Mic className="w-3 h-3 text-blue-400 mt-0.5 flex-shrink-0" />
                            <p className="text-blue-300/80 text-xs italic line-clamp-2">"{shot.dialogue}"</p>
                          </div>
                        )}

                        {/* 状态 */}
                        <div className="flex items-center justify-between mt-2 pt-2 border-t border-white/5">
                          <span className={`px-2 py-0.5 rounded text-xs ${
                            shot.video_status === 'succeeded' ? 'bg-green-500/20 text-green-400' :
                            shot.video_status === 'failed' ? 'bg-red-500/20 text-red-400' :
                            shot.video_status === 'running' ? 'bg-blue-500/20 text-blue-400' :
                            'bg-yellow-500/20 text-yellow-400'
                          }`}>
                            {VIDEO_STATUS_LABELS[shot.video_status] || shot.video_status}
                          </span>
                          {shot.video_status === 'pending' && (
                            <>
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-6 text-xs border-violet-500/50 text-violet-400 hover:bg-violet-500/10"
                              onClick={(e) => { e.stopPropagation(); handleGenerateVideo(shot); }}
                            >
                              <Sparkles className="w-3 h-3 mr-1" />
                              视频
                            </Button>
                            {shot.dialogue && (
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-6 text-xs border-blue-500/50 text-blue-400 hover:bg-blue-500/10 ml-1"
                                onClick={(e) => { e.stopPropagation(); handleGenerateTTS(shot); }}
                              >
                                <Mic className="w-3 h-3 mr-1" />
                                语音
                              </Button>
                            )}
                            </>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <Card className="bg-white/5 border-white/10">
                <CardContent className="p-12 text-center">
                  <Film className="w-12 h-12 mx-auto text-white/20" />
                  <p className="text-white/40 mt-4">
                    {searchQuery || selectedStoryboard !== 'all' || selectedStatus !== 'all'
                      ? '没有找到匹配的镜头'
                      : '暂无镜头'}
                  </p>
                  <p className="text-white/40 text-sm mt-1">
                    {searchQuery || selectedStoryboard !== 'all' || selectedStatus !== 'all'
                      ? '尝试调整筛选条件'
                      : '在分镜管理中创建镜头'}
                  </p>
                  <Button asChild className="mt-4 bg-violet-600 hover:bg-violet-700">
                    <Link href="/storyboards">
                      前往分镜管理
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {/* 镜头编辑弹窗 */}
        <Dialog open={isEditing && Boolean(selectedShot)} onOpenChange={(open) => setIsEditing(open)}>
          {selectedShot && (
            <DialogContent className="max-w-2xl gap-6 bg-[#1a1a2e] p-6">
              <DialogHeader className="pr-10">
                <DialogTitle className="flex items-center gap-2">
                  <Edit2 className="w-5 h-5" />
                  编辑镜头 {selectedShot.shot_number}
                </DialogTitle>
              </DialogHeader>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm text-white/60 mb-1 block">镜头序号</label>
                      <Input
                        type="number"
                        value={editData.shot_number}
                        onChange={(e) => setEditData({ ...editData, shot_number: parseInt(e.target.value) })}
                        className="bg-white/5 border-white/10 text-white"
                      />
                    </div>
                    <div>
                      <label className="text-sm text-white/60 mb-1 block">时长（秒）</label>
                      <Input
                        type="number"
                        value={editData.duration}
                        onChange={(e) => setEditData({ ...editData, duration: parseInt(e.target.value) })}
                        className="bg-white/5 border-white/10 text-white"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="text-sm text-white/60 mb-1 block">视频描述（Prompt）</label>
                    <textarea
                      value={editData.prompt || ''}
                      onChange={(e) => setEditData({ ...editData, prompt: e.target.value })}
                      rows={3}
                      className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-white/40 resize-none"
                      placeholder="描述镜头画面…"
                    />
                  </div>

                  <div>
                    <label className="text-sm text-white/60 mb-1 block">视觉描述</label>
                    <textarea
                      value={editData.visual_description || ''}
                      onChange={(e) => setEditData({ ...editData, visual_description: e.target.value })}
                      rows={2}
                      className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-white/40 resize-none"
                      placeholder="视觉细节描述…"
                    />
                  </div>

                  <div>
                    <label className="text-sm text-white/60 mb-1 block">台词/配音</label>
                    <Input
                      value={editData.dialogue || ''}
                      onChange={(e) => setEditData({ ...editData, dialogue: e.target.value })}
                      placeholder="输入台词…"
                      className="bg-white/5 border-white/10 text-white"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm text-white/60 mb-1 block">镜头角度</label>
                      <select
                        value={editData.camera_angle || ''}
                        onChange={(e) => setEditData({ ...editData, camera_angle: e.target.value })}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                      >
                        <option value="">选择角度</option>
                        {CAMERA_ANGLE_OPTIONS.map(a => <option key={a.value} value={a.value}>{a.label}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="text-sm text-white/60 mb-1 block">运镜方式</label>
                      <select
                        value={editData.camera_movement || ''}
                        onChange={(e) => setEditData({ ...editData, camera_movement: e.target.value })}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                      >
                        <option value="">选择运镜</option>
                        {CAMERA_MOVEMENT_OPTIONS.map(option => (
                          <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm text-white/60 mb-1 block">情绪</label>
                      <select
                        value={editData.emotion || ''}
                        onChange={(e) => setEditData({ ...editData, emotion: e.target.value })}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                      >
                        <option value="">选择情绪</option>
                        {EMOTION_OPTIONS.map(option => (
                          <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="text-sm text-white/60 mb-1 block">光线</label>
                      <select
                        value={editData.lighting || ''}
                        onChange={(e) => setEditData({ ...editData, lighting: e.target.value })}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                      >
                        <option value="">选择光线</option>
                        {LIGHTING_OPTIONS.map(option => (
                          <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="text-sm text-white/60 mb-1 block">调色</label>
                    <select
                      value={editData.color_grading || ''}
                      onChange={(e) => setEditData({ ...editData, color_grading: e.target.value })}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                    >
                      <option value="">选择调色</option>
                      {COLOR_GRADING_OPTIONS.map(option => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                  </div>

                  <div className="rounded-lg border border-cyan-500/20 bg-cyan-500/5 p-4 space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-white font-medium flex items-center gap-2">
                          <ShieldCheck className="w-4 h-4 text-cyan-300" />
                          生产上下文
                        </div>
                        <div className="text-xs text-white/50 mt-1">
                          资产版本锁、关键帧、多视图角色参考、实体引用、口型和审核状态会随媒体任务提交给生产适配器。
                        </div>
                      </div>
                      {productionContext.updated_at && (
                        <div className="text-xs text-white/40">已更新</div>
                      )}
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div className="rounded border border-white/10 bg-black/20 p-3">
                        <div className="flex items-center justify-between gap-2">
                          <div className="text-sm font-medium text-white">质量检查</div>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={refreshShotQuality}
                            disabled={qualityLoading}
                            className="h-7 border-cyan-500/30 text-cyan-100 hover:bg-cyan-500/10"
                          >
                            {qualityLoading ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <ShieldCheck className="w-3 h-3 mr-1" />}
                            重新检查
                          </Button>
                        </div>
                        <div className="mt-2 text-xs text-white/55">
                          状态：{qualityReport.status || 'unknown'}，评分：{qualityReport.score ?? '-'}
                        </div>
                        {Array.isArray(qualityReport.blockers) && qualityReport.blockers.length > 0 && (
                          <div className="mt-2 text-xs text-red-300 space-y-1">
                            {qualityReport.blockers.map((item: string, index: number) => (
                              <div key={index}>• {item}</div>
                            ))}
                          </div>
                        )}
                        {Array.isArray(qualityReport.warnings) && qualityReport.warnings.length > 0 && (
                          <div className="mt-2 text-xs text-yellow-200 space-y-1">
                            {qualityReport.warnings.map((item: string, index: number) => (
                              <div key={index}>• {item}</div>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="rounded border border-white/10 bg-black/20 p-3">
                        <div className="text-sm font-medium text-white">预算提示</div>
                        <div className="mt-2 text-xs text-white/55 space-y-1">
                          <div>预估时长：{budgetEstimate.estimated_duration_seconds ?? selectedShot.duration ?? 4}s</div>
                          <div>提示词 token：{budgetEstimate.estimated_prompt_tokens ?? '-'}</div>
                          <div>字幕 token：{budgetEstimate.estimated_subtitle_tokens ?? '-'}</div>
                          <div>合计 token：{budgetEstimate.estimated_total_tokens ?? '-'}</div>
                          {budgetEstimate.estimated_video_task?.default_model_id && (
                            <div>视频默认模型：{budgetEstimate.estimated_video_task.default_model_id}</div>
                          )}
                          {budgetEstimate.estimated_direct_av_task?.default_model_id && (
                            <div>直生音视频默认模型：{budgetEstimate.estimated_direct_av_task.default_model_id}</div>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div>
                        <label className="text-sm text-white/60 mb-1 block">资产版本锁 JSON</label>
                        <textarea
                          rows={5}
                          value={productionForm.assetLocksJson}
                          onChange={(e) => setProductionForm({ ...productionForm, assetLocksJson: e.target.value })}
                          className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs font-mono resize-none"
                          placeholder='[{"asset_id":"...","role":"character_front","version":1}]'
                        />
                      </div>
                      <div>
                        <label className="text-sm text-white/60 mb-1 block">关键帧 JSON</label>
                        <textarea
                          rows={5}
                          value={productionForm.keyframesJson}
                          onChange={(e) => setProductionForm({ ...productionForm, keyframesJson: e.target.value })}
                          className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs font-mono resize-none"
                          placeholder='[{"time":0,"role":"start"},{"time":4,"role":"end"}]'
                        />
                      </div>
                      <div>
                        <label className="text-sm text-white/60 mb-1 block">多视图角色参考 JSON</label>
                        <textarea
                          rows={5}
                          value={productionForm.multiviewJson}
                          onChange={(e) => setProductionForm({ ...productionForm, multiviewJson: e.target.value })}
                          className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs font-mono resize-none"
                          placeholder='[{"character":"主角","front":"...","side":"..."}]'
                        />
                      </div>
                      <div>
                        <label className="text-sm text-white/60 mb-1 block">实体参考绑定 JSON</label>
                        <textarea
                          rows={5}
                          value={productionForm.entityBindingsJson}
                          onChange={(e) => setProductionForm({ ...productionForm, entityBindingsJson: e.target.value })}
                          className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs font-mono resize-none"
                          placeholder='[{"entity_id":"...","role":"character_primary","usage":"character_reference"}]'
                        />
                      </div>
                      <div>
                        <label className="text-sm text-white/60 mb-1 block">口型/唇形 JSON</label>
                        <textarea
                          rows={5}
                          value={productionForm.lipSyncJson}
                          onChange={(e) => setProductionForm({ ...productionForm, lipSyncJson: e.target.value })}
                          className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs font-mono resize-none"
                          placeholder='{"mode":"provider","language":"zh-CN"}'
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      <div>
                        <label className="text-sm text-white/60 mb-1 block">审核状态</label>
                        <select
                          value={productionForm.reviewState}
                          onChange={(e) => setProductionForm({ ...productionForm, reviewState: e.target.value })}
                          className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                        >
                          <option value="pending_review">待审核</option>
                          <option value="changes_requested">需修改</option>
                          <option value="approved">已通过</option>
                          <option value="locked">已锁定</option>
                        </select>
                      </div>
                      <div>
                        <label className="text-sm text-white/60 mb-1 block">审核人</label>
                        <Input
                          value={productionForm.reviewAssignees}
                          onChange={(e) => setProductionForm({ ...productionForm, reviewAssignees: e.target.value })}
                          placeholder="director, animator"
                          className="bg-white/5 border-white/10 text-white"
                        />
                      </div>
                      <div>
                        <label className="text-sm text-white/60 mb-1 block">审核备注</label>
                        <Input
                          value={productionForm.reviewNotes}
                          onChange={(e) => setProductionForm({ ...productionForm, reviewNotes: e.target.value })}
                          placeholder="需要保持服装和道具一致"
                          className="bg-white/5 border-white/10 text-white"
                        />
                      </div>
                    </div>

                    <Button
                      variant="outline"
                      onClick={handleSaveProductionContext}
                      disabled={productionSaving}
                      className="border-cyan-500/40 text-cyan-100 hover:bg-cyan-500/10"
                    >
                      {productionSaving ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <ShieldCheck className="w-4 h-4 mr-1" />}
                      保存生产上下文
                    </Button>
                  </div>

                  <div className="flex gap-3 pt-4">
                    <Button
                      variant="outline"
                      onClick={() => setIsEditing(false)}
                      className="flex-1 border-white/20 text-white"
                    >
                      取消
                    </Button>
                    <Button
                      onClick={handleSave}
                      disabled={saving}
                      className="flex-1 bg-violet-600 hover:bg-violet-700"
                    >
                      {saving ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Edit2 className="w-4 h-4 mr-1" />}
                      保存
                    </Button>
                  </div>
                </div>
            </DialogContent>
          )}
        </Dialog>
      </div>
      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="删除镜头"
        description={`确定要删除镜头 ${deleteTarget?.shot_number ?? ''}？删除后该镜头会从当前分镜列表移除。`}
        confirmText="删除镜头"
        destructive
        loading={Boolean(deleteTarget && deletingShotId === deleteTarget.id)}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        onConfirm={async () => {
          if (!deleteTarget) return;
          await handleDelete(deleteTarget.id);
          setDeleteTarget(null);
        }}
      />
    </MainLayout>
  );
}

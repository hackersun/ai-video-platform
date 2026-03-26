'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { MainLayout } from '@/components/layout/main-layout';
import { fetchWithAuth } from '@/lib/fetch-with-auth';
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
  ImageIcon
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

interface Shot {
  id: string;
  storyboard_id: string;
  storyboard_title?: string;
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
  created_at: string;
  updated_at: string;
}

interface Storyboard {
  id: string;
  title: string;
  shot_count: number;
  total_duration: number;
}

const VIDEO_STATUS_LABELS: Record<string, string> = {
  pending: '等待',
  running: '生成中',
  succeeded: '已完成',
  failed: '失败'
};

const CAMERA_ANGLES = ['全景', '远景', '中景', '近景', '特写', '跟拍', '摇镜头', '推镜头', '俯拍', '仰拍'];
const EMOTIONS = ['neutral', 'happy', 'sad', 'angry', 'surprised', 'tense', 'relaxed', 'excited'];

const EMOTION_LABELS: Record<string, string> = {
  neutral: '平静',
  happy: '开心',
  sad: '悲伤',
  angry: '愤怒',
  surprised: '惊讶',
  tense: '紧张',
  relaxed: '放松',
  excited: '兴奋'
};

const CAMERA_MOVEMENT_LABELS: Record<string, string> = {
  static: '固定',
  pan_left: '左摇',
  pan_right: '右摇',
  tilt_up: '上摇',
  tilt_down: '下摇',
  zoom_in: '推进',
  zoom_out: '拉远',
  dolly: '移动',
  crane: '升降',
  handheld: '手持'
};

const LIGHTING_LABELS: Record<string, string> = {
  natural: '自然光',
  dramatic: '戏剧光',
  soft: '柔光',
  rim: '轮廓光',
  back: '逆光',
  neon: '霓虹',
  moonlight: '月光',
  golden_hour: '黄金时段'
};

export default function ShotsPage() {
  const router = useRouter();
  const [shots, setShots] = useState<Shot[]>([]);
  const [storyboards, setStoryboards] = useState<Storyboard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedStoryboard, setSelectedStoryboard] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [selectedShot, setSelectedShot] = useState<Shot | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState<Partial<Shot>>({});
  const [saving, setSaving] = useState(false);
  const [selectedShots, setSelectedShots] = useState<Set<string>>(new Set());
  const [showFilters, setShowFilters] = useState(false);
  const [batchGenerating, setBatchGenerating] = useState(false);
  const [batchProgress, setBatchProgress] = useState<Record<string, string>>({});

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

  // 加载分镜列表
  const loadStoryboards = async () => {
    try {
      const response = await fetchWithAuth(`${API_BASE}/scripts`);
      if (response.ok) {
        const data = await response.json();
        // Also try to get storyboards
        if (data[0]?.id) {
          const sbResponse = await fetchWithAuth(`${API_BASE}/storyboards/script/${data[0].id}`);
          if (sbResponse.ok) {
            const sbData = await sbResponse.json();
            setStoryboards(Array.isArray(sbData) ? sbData.map((s: any) => ({
              id: s.id,
              title: s.title,
              shot_count: s.shot_count,
              total_duration: s.total_duration
            })) : []);
          }
        }
      }
    } catch (err) {
      console.error('加载分镜失败:', err);
    }
  };

  // 加载所有镜头
  const loadShots = async () => {
    setLoading(true);
    setError(null);
    try {
      // 先获取所有剧本
      const scriptsRes = await fetchWithAuth(`${API_BASE}/scripts`);
      if (!scriptsRes.ok) throw new Error('加载剧本失败');
      const scripts = await scriptsRes.json();

      // 再获取每个剧本的分镜和镜头
      const allShots: Shot[] = [];
      for (const script of scripts) {
        const sbRes = await fetchWithAuth(`${API_BASE}/storyboards/script/${script.id}`);
        if (sbRes.ok) {
          const sbs = await sbRes.json();
          for (const sb of Array.isArray(sbs) ? sbs : []) {
            const shotsRes = await fetchWithAuth(`${API_BASE}/shots/storyboard/${sb.id}`);
            if (shotsRes.ok) {
              const shotsData = await shotsRes.json();
              const shotsWithTitle = (Array.isArray(shotsData) ? shotsData : []).map((shot: any) => ({
                ...shot,
                storyboard_title: sb.title
              }));
              allShots.push(...shotsWithTitle);
            }
          }
        }
      }
      setShots(allShots);
    } catch (err: any) {
      console.error('加载镜头失败:', err);
      setError(err.message || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStoryboards();
    loadShots();
  }, []);

  // 筛选镜头
  const filteredShots = shots.filter(shot => {
    const matchesSearch = !searchQuery ||
      shot.prompt?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      shot.dialogue?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      shot.visual_description?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStoryboard = selectedStoryboard === 'all' || shot.storyboard_id === selectedStoryboard;
    const matchesStatus = selectedStatus === 'all' || shot.video_status === selectedStatus;
    return matchesSearch && matchesStoryboard && matchesStatus;
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
    router.push(`/video-generation?shot_id=${shot.id}&prompt=${encodeURIComponent(shot.prompt || shot.visual_description || '')}`);
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
    const storyboardIds = [...new Set(shotArray.map(s => s.storyboard_id))];
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
          const nextProgress = { ...batchProgress, [shotId]: "succeeded" };
          const vals = Object.values(nextProgress);
          if (!vals.includes("generating") && !vals.includes("pending")) {
            setBatchGenerating(false);
          }
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
        setShots(shots.map(s => s.id === updated.id ? { ...updated, storyboard_title: selectedShot.storyboard_title } : s));
        setSelectedShot(updated);
        setIsEditing(false);
      } else {
        throw new Error('保存失败');
      }
    } catch (err: any) {
      alert(err.message || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  // 删除镜头
  const handleDelete = async (shotId: string) => {
    if (!confirm('确定要删除这个镜头吗？')) return;
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
      }
    } catch (err) {
      console.error('删除镜头失败:', err);
      alert('删除失败');
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
            <p className="text-white/60 mt-1">管理所有分镜中的镜头</p>
          </div>
          <div className="flex gap-2">
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
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="text-sm text-white/60 mb-1 block">搜索</label>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                    <Input
                      placeholder="搜索镜头内容..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pl-10 bg-white/5 border-white/10 text-white placeholder:text-white/40"
                    />
                  </div>
                </div>
                <div>
                  <label className="text-sm text-white/60 mb-1 block">分镜</label>
                  <select
                    value={selectedStoryboard}
                    onChange={(e) => setSelectedStoryboard(e.target.value)}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                  >
                    <option value="all">全部</option>
                    {storyboards.map(sb => (
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
              </div>
              {(searchQuery || selectedStoryboard !== 'all' || selectedStatus !== 'all') && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => { setSearchQuery(''); setSelectedStoryboard('all'); setSelectedStatus('all'); }}
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
            <span className="ml-3 text-white/60">加载中...</span>
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
                    className={`bg-white/5 border-white/10 hover:border-violet-500/30 transition-all cursor-pointer ${
                      selectedShots.has(shot.id) ? 'ring-2 ring-violet-500' : ''
                    }`}
                    onClick={() => !isEditing && setSelectedShot(shot)}
                  >
                    <CardContent className="p-4 relative">
                      {/* Image status overlay */}
                      {batchProgress[shot.id] === "generating" && (
                        <span className="absolute top-2 left-2 z-10 px-2 py-1 bg-yellow-500 text-white text-xs rounded flex items-center gap-1">
                          <Loader2 className="w-3 h-3 animate-spin" />
                          生成中...
                        </span>
                      )}
                      {batchProgress[shot.id] === "succeeded" && (
                        <span className="absolute top-2 left-2 z-10 px-2 py-1 bg-green-500 text-white text-xs rounded">
                          图片已生成
                        </span>
                      )}
                      {batchProgress[shot.id] === "failed" && (
                        <span className="absolute top-2 left-2 z-10 px-2 py-1 bg-red-500 text-white text-xs rounded">
                          生成失败
                        </span>
                      )}
                      {shot.image_status === "succeeded" && shot.image_url && (
                        <img
                          src={shot.image_url}
                          className="absolute inset-0 w-full h-full object-cover opacity-20 rounded-lg"
                          alt=""
                        />
                      )}
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={(e) => { e.stopPropagation(); toggleShotSelection(shot.id); }}
                            className="text-white/40 hover:text-violet-400"
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
                              className="w-6 h-6 text-green-400"
                              onClick={(e) => { e.stopPropagation(); window.open(shot.video_url, '_blank'); }}
                            >
                              <Play className="w-3 h-3" />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            className="w-6 h-6 text-white/40 hover:text-white"
                            onClick={(e) => { e.stopPropagation(); handleEdit(shot); }}
                          >
                            <Edit2 className="w-3 h-3" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="w-6 h-6 text-red-400/60 hover:text-red-400"
                            onClick={(e) => { e.stopPropagation(); handleDelete(shot.id); }}
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

                        {/* 元数据 */}
                        <div className="flex flex-wrap gap-2 text-xs text-white/40">
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {shot.duration}s
                          </span>
                          {shot.camera_angle && (
                            <span className="flex items-center gap-1">
                              <Camera className="w-3 h-3" />
                              {shot.camera_angle}
                            </span>
                          )}
                          {shot.camera_movement && (
                            <span className="px-1.5 py-0.5 rounded bg-white/10">
                              {CAMERA_MOVEMENT_LABELS[shot.camera_movement] || shot.camera_movement}
                            </span>
                          )}
                          {shot.emotion && (
                            <span className="px-1.5 py-0.5 rounded bg-white/10">
                              {EMOTION_LABELS[shot.emotion] || shot.emotion}
                            </span>
                          )}
                        </div>

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
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-6 text-xs border-violet-500/50 text-violet-400 hover:bg-violet-500/10"
                              onClick={(e) => { e.stopPropagation(); handleGenerateVideo(shot); }}
                            >
                              <Sparkles className="w-3 h-3 mr-1" />
                              生成
                            </Button>
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
                  <Link href="/storyboards">
                    <Button className="mt-4 bg-violet-600 hover:bg-violet-700">
                      前往分镜管理
                    </Button>
                  </Link>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {/* 镜头编辑弹窗 */}
        {isEditing && selectedShot && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={() => setIsEditing(false)}>
            <div className="bg-[#1a1a2e] border border-white/10 rounded-xl w-full max-w-2xl max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
              <div className="p-6">
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-xl font-bold text-white flex items-center gap-2">
                    <Edit2 className="w-5 h-5" />
                    编辑镜头 {selectedShot.shot_number}
                  </h2>
                  <Button variant="ghost" size="icon" onClick={() => setIsEditing(false)} className="text-white/60 hover:text-white">
                    <X className="w-5 h-5" />
                  </Button>
                </div>

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
                      placeholder="描述镜头画面..."
                    />
                  </div>

                  <div>
                    <label className="text-sm text-white/60 mb-1 block">视觉描述</label>
                    <textarea
                      value={editData.visual_description || ''}
                      onChange={(e) => setEditData({ ...editData, visual_description: e.target.value })}
                      rows={2}
                      className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-white/40 resize-none"
                      placeholder="视觉细节描述..."
                    />
                  </div>

                  <div>
                    <label className="text-sm text-white/60 mb-1 block">台词/配音</label>
                    <Input
                      value={editData.dialogue || ''}
                      onChange={(e) => setEditData({ ...editData, dialogue: e.target.value })}
                      placeholder="输入台词..."
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
                        {CAMERA_ANGLES.map(a => <option key={a} value={a}>{a}</option>)}
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
                        {Object.entries(CAMERA_MOVEMENT_LABELS).map(([k, v]) => (
                          <option key={k} value={k}>{v}</option>
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
                        {Object.entries(EMOTION_LABELS).map(([k, v]) => (
                          <option key={k} value={k}>{v}</option>
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
                        {Object.entries(LIGHTING_LABELS).map(([k, v]) => (
                          <option key={k} value={k}>{v}</option>
                        ))}
                      </select>
                    </div>
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
              </div>
            </div>
          </div>
        )}
      </div>
    </MainLayout>
  );
}

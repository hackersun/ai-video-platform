'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { MainLayout } from '@/components/layout/main-layout';
import { fetchWithAuth } from '@/lib/fetch-with-auth';
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
  X,
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
  version?: number;
  created_at: string;
  updated_at: string;
}

// 分镜卡数据类型 - 与后端 Storyboard 模型匹配
interface Storyboard {
  id: string;
  script_id: string;
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
}

// 分镜生成请求
interface GenerateRequest {
  script_id: string;
  shot_count?: number;
  style?: string;
}

const CAMERA_ANGLES = ['wide', 'medium', 'close-up', 'extreme-close-up', 'over-shoulder', 'dutch', 'two-shot', 'pov', 'birds-eye', 'worms-eye'];
const CAMERA_MOVEMENTS = ['static', 'pan_left', 'pan_right', 'tilt_up', 'tilt_down', 'zoom_in', 'zoom_out', 'dolly', 'crane', 'handheld'];
const EMOTIONS = ['happy', 'sad', 'angry', 'surprised', 'neutral', 'tense', 'relaxed', 'excited'];
const LIGHTING_OPTIONS = ['natural', 'dramatic', 'soft', 'rim', 'back', 'neon', 'moonlight', 'golden_hour'];
const COLOR_GRADING_OPTIONS = ['warm', 'cool', 'desaturated', 'vibrant', 'vintage', 'cinematic', 'noir'];
const STORYBOARD_STYLES = ['anime', 'realistic', 'cartoon', 'noir', 'fantasy', 'sci-fi'];
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export default function StoryboardsPage() {
  const [storyboards, setStoryboards] = useState<Storyboard[]>([]);
  const [selectedStoryboard, setSelectedStoryboard] = useState<Storyboard | null>(null);
  const [selectedShot, setSelectedShot] = useState<Shot | null>(null);
  const [shots, setShots] = useState<Shot[]>([]);
  const [scripts, setScripts] = useState<Script[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingShots, setLoadingShots] = useState(false);
  const [showNewModal, setShowNewModal] = useState(false);
  const [newStoryboardTitle, setNewStoryboardTitle] = useState('');
  const [newStoryboardScriptId, setNewStoryboardScriptId] = useState('');
  const [newStoryboardStyle, setNewStoryboardStyle] = useState('anime');
  const [generatingStoryboard, setGeneratingStoryboard] = useState(false);
  const [generatingImage, setGeneratingImage] = useState(false);

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
        setScripts(Array.isArray(data) ? data : []);
      }
    } catch (error) {
      console.error('加载剧本失败:', error);
      setScripts([]);
    }
  };

  // 加载分镜列表
  const loadStoryboards = async () => {
    setLoading(true);
    try {
      // 先获取所有剧本
      await loadScripts();

      // 再获取每个剧本的分镜
      const allStoryboards: Storyboard[] = [];
      for (const script of scripts) {
        const sbRes = await fetchWithAuth(`${API_BASE}/storyboards/script/${script.id}`);
        if (sbRes.ok) {
          const sbs = await sbRes.json();
          const sbsWithScript = (Array.isArray(sbs) ? sbs : []).map((sb: any) => ({
            ...sb,
            script_title: script.title,
          }));
          allStoryboards.push(...sbsWithScript);
        }
      }
      setStoryboards(allStoryboards);
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
  }, []);

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
  const filteredStoryboards = storyboards.filter(sb =>
    sb.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    sb.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    sb.script_title?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // 创建分镜
  const handleCreateStoryboard = async () => {
    if (!newStoryboardTitle.trim()) {
      alert('请输入分镜标题');
      return;
    }
    if (!newStoryboardScriptId) {
      alert('请选择关联的剧本');
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
      } else {
        const err = await response.json();
        alert(err.detail || '创建失败');
      }
    } catch (error) {
      console.error('创建分镜失败:', error);
      alert('创建失败');
    }
  };

  // AI 生成故事板（从剧本生成）
  const handleAIGenerateStoryboard = async () => {
    if (!newStoryboardScriptId) {
      alert('请先选择一个剧本');
      return;
    }
    if (!confirm('确定要使用AI自动生成分镜吗？这将从剧本内容生成镜头。')) return;
    setGeneratingStoryboard(true);
    try {
      const response = await fetchWithAuth(`${API_BASE}/storyboards/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script_id: newStoryboardScriptId,
          shot_count: 5,
          style: newStoryboardStyle || 'anime'
        })
      });
      if (response.ok) {
        const data = await response.json();
        await loadStoryboards();
        // 选中新创建的分镜
        const newSb = storyboards.find(sb => sb.id === data.id) || data;
        setSelectedStoryboard(newSb);
        alert(`分镜生成成功！共 ${data.shot_count} 个镜头。`);
      } else {
        const errData = await response.json();
        throw new Error(errData.detail || '生成失败');
      }
    } catch (err: any) {
      console.error('生成故事板失败:', err);
      alert(err.message || '生成失败');
    } finally {
      setGeneratingStoryboard(false);
    }
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
      }
    } catch (error) {
      console.error('创建镜头失败:', error);
      alert('创建镜头失败');
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
      } else {
        alert('更新失败');
      }
    } catch (error) {
      console.error('更新镜头失败:', error);
      alert('更新失败');
    }
  };

  // 删除镜头
  const handleDeleteShot = async (shotId: string) => {
    if (!selectedStoryboard) return;
    if (!confirm('确定要删除这个镜头吗？')) return;

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
      }
    } catch (error) {
      console.error('删除镜头失败:', error);
      alert('删除失败');
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
        body: JSON.stringify({
          shot_ids: newShots.map(s => s.id)
        })
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
            <span className="ml-3 text-white/60">加载中...</span>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* 分镜列表 */}
            <div className="lg:col-span-1 space-y-4">
              {/* 搜索 */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                <Input
                  placeholder="搜索分镜..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 bg-white/5 border-white/10 text-white placeholder:text-white/40"
                />
              </div>

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
                      <div>
                        <div className="text-white font-medium">{sb.title}</div>
                        <div className="text-xs text-white/40">
                          {sb.shot_count || 0} 个镜头 · {sb.script_title || sb.script_id}
                        </div>
                      </div>
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        sb.status === 'approved' ? 'bg-green-600/30 text-green-400' :
                        sb.status === 'rejected' ? 'bg-red-600/30 text-red-400' :
                        'bg-white/10 text-white/60'
                      }`}>
                        {sb.status || 'draft'}
                      </span>
                    </div>
                  </div>
                ))}

                {filteredStoryboards.length === 0 && (
                  <div className="text-center py-8">
                    <LayoutGrid className="w-12 h-12 mx-auto text-white/20" />
                    <p className="text-white/40 mt-2">暂无分镜</p>
                    <Button 
                      variant="outline" 
                      size="sm"
                      className="mt-2 border-white/20 text-white/60"
                      onClick={() => setShowNewModal(true)}
                    >
                      创建第一个分镜
                    </Button>
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
                                  {shot.duration}秒 · {shot.camera_angle || 'medium'}
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
                                variant="ghost"
                                size="icon"
                                className="w-6 h-6 text-white/40"
                                onClick={(e) => { e.stopPropagation(); moveShot(index, 'up'); }}
                                disabled={index === 0}
                              >
                                <ChevronLeft className="w-3 h-3" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="w-6 h-6 text-white/40"
                                onClick={(e) => { e.stopPropagation(); moveShot(index, 'down'); }}
                                disabled={index === shots.length - 1}
                              >
                                <ChevronRight className="w-3 h-3" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="w-6 h-6 text-white/40 hover:text-red-400"
                                onClick={(e) => { e.stopPropagation(); handleDeleteShot(shot.id); }}
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

                        {/* 快速操作按钮 */}
                        <div className="flex gap-2 mb-4">
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
                              {CAMERA_ANGLES.map(angle => (
                                <option key={angle} value={angle}>{angle}</option>
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
                              onClick={() => handleGenerateShotImage(selectedShot.id)}
                              disabled={generatingImage || !selectedShot.visual_description}
                              className="px-3 py-1 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              {generatingImage ? "生成中..." : "生成参考图"}
                            </button>
                          </div>
                          {(selectedShot.image_status === "generating" || selectedShot.image_status === "pending") && (
                            <div className="text-sm text-yellow-400">生成中...</div>
                          )}
                          {selectedShot.image_url && (
                            <img
                              src={selectedShot.image_url}
                              alt="Shot reference"
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
                                {CAMERA_MOVEMENTS.map(m => (
                                  <option key={m} value={m}>{m}</option>
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
                                {EMOTIONS.map(e => (
                                  <option key={e} value={e}>{e}</option>
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
                                  <option key={l} value={l}>{l}</option>
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
                                  <option key={c} value={c}>{c}</option>
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
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* 新建分镜弹窗 */}
      {showNewModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="bg-white/10 backdrop-blur-lg border-white/20 w-full max-w-md">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-white">新建分镜</CardTitle>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowNewModal(false)}
                className="text-white/60 hover:text-white"
              >
                <X className="w-5 h-5" />
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
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
                  <option value="">请选择剧本...</option>
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
                  {STORYBOARD_STYLES.map(style => (
                    <option key={style} value={style}>{style}</option>
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
                  className="flex-1 bg-purple-600 hover:bg-purple-700"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  创建
                </Button>
              </div>

              {newStoryboardScriptId && (
                <div className="pt-4 border-t border-white/10">
                  <Button
                    onClick={handleAIGenerateStoryboard}
                    disabled={generatingStoryboard}
                    className="w-full bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700"
                  >
                    {generatingStoryboard ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        AI 生成分镜中...
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-4 h-4 mr-2" />
                        AI 从剧本生成
                      </>
                    )}
                  </Button>
                  <p className="text-xs text-white/40 mt-2 text-center">
                    将从所选剧本内容自动生成 {newStoryboardStyle} 风格的分镜镜头
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </MainLayout>
  );
}

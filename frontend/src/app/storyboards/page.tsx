'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { MainLayout } from '@/components/layout/main-layout';
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
  Save
} from 'lucide-react';

// 分镜数据类型
interface Shot {
  id: string;
  shot_number: number;
  title: string;
  description: string;
  duration: number;
  image_url?: string;
  dialogue?: string;
  camera_type: string;
  effect?: string;
  created_at: string;
  updated_at: string;
}

// 分镜卡数据类型
interface Storyboard {
  id: string;
  title: string;
  description?: string;
  script_id: string;
  status: 'draft' | 'approved' | 'rejected';
  shots: Shot[];
  created_at: string;
  updated_at: string;
}

const CAMERA_TYPES = ['全景', '远景', '中景', '近景', '特写', '跟拍', '摇镜头', '推镜头'];
const EFFECTS = ['无', '光晕', '暗光', '虚化', '旋转', '闪烁', '渐变', '粒子'];
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function StoryboardsPage() {
  const [storyboards, setStoryboards] = useState<Storyboard[]>([]);
  const [selectedStoryboard, setSelectedStoryboard] = useState<Storyboard | null>(null);
  const [selectedShot, setSelectedShot] = useState<Shot | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [showNewModal, setShowNewModal] = useState(false);
  const [newStoryboardTitle, setNewStoryboardTitle] = useState('');
  const [newStoryboardScriptId, setNewStoryboardScriptId] = useState('');
  
  // 加载分镜数据
  const loadStoryboards = async () => {
    setLoading(true);
    try {
      // 由于分镜是挂在script下的，我们从API获取
      // 这里简化处理，实际应该先获取所有storyboard列表
      const response = await fetch(`${API_BASE}/api/v1/storyboards/script/mock`);
      const data = await response.json();
      setStoryboards(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('加载分镜失败:', error);
      setStoryboards([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStoryboards();
  }, []);

  // 筛选分镜
  const filteredStoryboards = storyboards.filter(sb => 
    sb.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    sb.description?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // 创建分镜
  const handleCreateStoryboard = async () => {
    if (!newStoryboardTitle.trim()) {
      alert('请输入分镜标题');
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/api/v1/storyboards`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: newStoryboardTitle,
          description: '',
          script_id: newStoryboardScriptId || 'default'
        })
      });

      if (response.ok) {
        const newSb = await response.json();
        setStoryboards([newSb, ...storyboards]);
        setShowNewModal(false);
        setNewStoryboardTitle('');
        setSelectedStoryboard(newSb);
      }
    } catch (error) {
      console.error('创建分镜失败:', error);
      alert('创建失败');
    }
  };

  // 创建镜头
  const handleAddShot = async () => {
    if (!selectedStoryboard) return;

    try {
      const newShot = {
        shot_number: selectedStoryboard.shots?.length + 1 || 1,
        title: `镜头 ${(selectedStoryboard.shots?.length || 0) + 1}`,
        description: '新镜头描述',
        duration: 5,
        camera_type: '中景',
        effect: '无'
      };

      const response = await fetch(`${API_BASE}/api/v1/shots`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...newShot,
          storyboard_id: selectedStoryboard.id
        })
      });

      if (response.ok) {
        const createdShot = await response.json();
        const updatedStoryboard = {
          ...selectedStoryboard,
          shots: [...(selectedStoryboard.shots || []), createdShot]
        };
        setSelectedStoryboard(updatedStoryboard);
        setStoryboards(storyboards.map(sb => 
          sb.id === updatedStoryboard.id ? updatedStoryboard : sb
        ));
      }
    } catch (error) {
      console.error('创建镜头失败:', error);
    }
  };

  // 更新镜头
  const handleUpdateShot = async (updated: Shot) => {
    if (!selectedStoryboard) return;

    try {
      const response = await fetch(`${API_BASE}/api/v1/shots/${updated.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated)
      });

      if (response.ok) {
        const newShots = selectedStoryboard.shots.map(s => 
          s.id === updated.id ? updated : s
        );
        const updatedStoryboard = { ...selectedStoryboard, shots: newShots };
        setSelectedStoryboard(updatedStoryboard);
        setStoryboards(storyboards.map(sb => 
          sb.id === updatedStoryboard.id ? updatedStoryboard : sb
        ));
      }
    } catch (error) {
      console.error('更新镜头失败:', error);
    }
  };

  // 删除镜头
  const handleDeleteShot = async (shotId: string) => {
    if (!selectedStoryboard) return;
    if (!confirm('确定要删除这个镜头吗？')) return;

    try {
      const response = await fetch(`${API_BASE}/api/v1/shots/${shotId}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        const newShots = selectedStoryboard.shots.filter(s => s.id !== shotId);
        const updatedStoryboard = { ...selectedStoryboard, shots: newShots };
        setSelectedStoryboard(updatedStoryboard);
        setStoryboards(storyboards.map(sb => 
          sb.id === updatedStoryboard.id ? updatedStoryboard : sb
        ));
        if (selectedShot?.id === shotId) {
          setSelectedShot(null);
        }
      }
    } catch (error) {
      console.error('删除镜头失败:', error);
    }
  };

  // 移动镜头顺序
  const moveShot = async (index: number, direction: 'up' | 'down') => {
    if (!selectedStoryboard || !selectedStoryboard.shots) return;
    
    const newIndex = direction === 'up' ? index - 1 : index + 1;
    if (newIndex < 0 || newIndex >= selectedStoryboard.shots.length) return;

    const newShots = [...selectedStoryboard.shots];
    [newShots[index], newShots[newIndex]] = [newShots[newIndex], newShots[index]];
    
    // 更新shot_number
    newShots.forEach((shot, i) => {
      shot.shot_number = i + 1;
    });

    const updatedStoryboard = { ...selectedStoryboard, shots: newShots };
    setSelectedStoryboard(updatedStoryboard);
    setStoryboards(storyboards.map(sb => 
      sb.id === updatedStoryboard.id ? updatedStoryboard : sb
    ));

    // 同步到后端
    try {
      await fetch(`${API_BASE}/api/v1/shots/reorder`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          storyboard_id: selectedStoryboard.id,
          shot_ids: newShots.map(s => s.id)
        })
      });
    } catch (error) {
      console.error('更新顺序失败:', error);
    }
  };

  // 总时长
  const totalDuration = selectedStoryboard?.shots?.reduce((sum, s) => sum + (s.duration || 0), 0) || 0;
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
            <Button className="bg-purple-600 hover:bg-purple-700">
              <Sparkles className="w-4 h-4 mr-2" />
              AI 生成
            </Button>
          </div>
        </div>

        {/* 统计信息 */}
        <div className="grid grid-cols-3 gap-4">
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
              <div className="text-2xl font-bold text-blue-400">
                {selectedStoryboard?.shots?.filter(s => s.image_url).length || 0}
              </div>
              <div className="text-sm text-white/60">已配图</div>
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
                    onClick={() => { setSelectedStoryboard(sb); setSelectedShot(null); }}
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
                          {sb.shots?.length || 0} 个镜头 · {sb.status}
                        </div>
                      </div>
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
                        {selectedStoryboard.title}
                      </div>
                      <div className="flex gap-2">
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
                      {selectedStoryboard.shots?.map((shot, index) => (
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
                                <div className="text-white font-medium">{shot.title}</div>
                                <div className="text-xs text-white/40">
                                  {shot.duration}秒 · {shot.camera_type}
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
                                disabled={index === (selectedStoryboard.shots?.length || 0) - 1}
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
                      ))}

                      {(!selectedStoryboard.shots || selectedStoryboard.shots.length === 0) && (
                        <div className="text-center py-8">
                          <Film className="w-12 h-12 mx-auto text-white/20" />
                          <p className="text-white/40 mt-2">暂无镜头，点击上方添加</p>
                        </div>
                      )}
                    </div>

                    {/* 镜头详情编辑 */}
                    {selectedShot && (
                      <div className="mt-6 pt-6 border-t border-white/10">
                        <h4 className="text-white font-medium mb-4">镜头 {selectedShot.shot_number} 详情</h4>
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <label className="text-sm text-white/60 mb-2 block">镜头标题</label>
                            <Input
                              value={selectedShot.title}
                              onChange={(e) => setSelectedShot({ ...selectedShot, title: e.target.value })}
                              className="bg-white/5 border-white/10 text-white"
                            />
                          </div>
                          <div>
                            <label className="text-sm text-white/60 mb-2 block">时长（秒）</label>
                            <Input
                              type="number"
                              value={selectedShot.duration}
                              onChange={(e) => setSelectedShot({ ...selectedShot, duration: parseInt(e.target.value) || 0 })}
                              className="bg-white/5 border-white/10 text-white"
                            />
                          </div>
                        </div>

                        <div className="mt-4">
                          <label className="text-sm text-white/60 mb-2 block">镜头描述</label>
                          <Input
                            value={selectedShot.description}
                            onChange={(e) => setSelectedShot({ ...selectedShot, description: e.target.value })}
                            className="bg-white/5 border-white/10 text-white"
                          />
                        </div>

                        <div className="grid grid-cols-2 gap-4 mt-4">
                          <div>
                            <label className="text-sm text-white/60 mb-2 block">镜头类型</label>
                            <select
                              value={selectedShot.camera_type}
                              onChange={(e) => setSelectedShot({ ...selectedShot, camera_type: e.target.value })}
                              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                            >
                              {CAMERA_TYPES.map(type => (
                                <option key={type} value={type}>{type}</option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label className="text-sm text-white/60 mb-2 block">特效</label>
                            <select
                              value={selectedShot.effect || '无'}
                              onChange={(e) => setSelectedShot({ ...selectedShot, effect: e.target.value })}
                              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                            >
                              {EFFECTS.map(effect => (
                                <option key={effect} value={effect}>{effect}</option>
                              ))}
                            </select>
                          </div>
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

                        <div className="mt-4">
                          <label className="text-sm text-white/60 mb-2 block">图片URL</label>
                          <Input
                            value={selectedShot.image_url || ''}
                            onChange={(e) => setSelectedShot({ ...selectedShot, image_url: e.target.value })}
                            placeholder="输入分镜图片URL"
                            className="bg-white/5 border-white/10 text-white"
                          />
                        </div>

                        <div className="flex gap-2 mt-4">
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
                <label className="text-sm text-white/60 mb-2 block">关联剧本ID</label>
                <Input
                  placeholder="留空为默认剧本"
                  value={newStoryboardScriptId}
                  onChange={(e) => setNewStoryboardScriptId(e.target.value)}
                  className="bg-white/5 border-white/10 text-white placeholder:text-white/40"
                />
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
            </CardContent>
          </Card>
        </div>
      )}
    </MainLayout>
  );
}

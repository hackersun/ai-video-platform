'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { 
  ChevronLeft, 
  Plus,
  Play,
  Image as ImageIcon,
  Film,
  Volume2,
  MoreVertical,
  GripVertical,
  Trash2,
  Edit3,
  Sparkles,
  Loader2,
  ChevronDown,
  ChevronRight,
  Save
} from 'lucide-react';
import { scriptApi } from '@/lib/api';

interface Scene {
  id: string;
  scene_number: number;
  title: string;
  description: string;
  location: string;
  time_of_day: string;
  characters: string[];
  dialogue: any;
  action_description: string;
  camera_direction: string;
}

interface Script {
  id: string;
  title: string;
  content: any;
  status: string;
  ai_generated: boolean;
}

export default function ScriptEditorPage() {
  const router = useRouter();
  const params = useParams();
  const scriptId = params.id as string;
  
  const [script, setScript] = useState<Script | null>(null);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedScene, setSelectedScene] = useState<Scene | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  useEffect(() => {
    if (scriptId) {
      loadData();
    }
  }, [scriptId]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [scriptRes, scenesRes] = await Promise.all([
        scriptApi.get(scriptId),
        scriptApi.getScenes(scriptId)
      ]);
      
      setScript(scriptRes.data);
      setScenes(scenesRes.data.items || []);
      
      if (scenesRes.data.items?.length > 0) {
        setSelectedScene(scenesRes.data.items[0]);
      }
    } catch (error) {
      console.error('加载数据失败', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddScene = async () => {
    const newSceneNumber = scenes.length + 1;
    try {
      const response = await scriptApi.createScene(scriptId, {
        scene_number: newSceneNumber,
        title: `场景 ${newSceneNumber}`,
        description: '',
        location: '',
        time_of_day: '白天',
        characters: [],
        dialogue: {},
        action_description: '',
        camera_direction: ''
      });
      
      setScenes([...scenes, response.data]);
      setSelectedScene(response.data);
    } catch (error) {
      console.error('创建场景失败', error);
      alert('创建场景失败');
    }
  };

  const handleDeleteScene = async (sceneId: string) => {
    if (!confirm('确定要删除这个场景吗？')) return;
    
    try {
      await scriptApi.deleteScene(scriptId, sceneId);
      const updatedScenes = scenes.filter(s => s.id !== sceneId);
      setScenes(updatedScenes);
      
      if (selectedScene?.id === sceneId) {
        setSelectedScene(updatedScenes[0] || null);
      }
    } catch (error) {
      console.error('删除场景失败', error);
      alert('删除失败');
    }
  };

  const handleGenerateVideo = async (sceneId: string) => {
    setIsGenerating(true);
    try {
      // TODO: 调用视频生成API
      await new Promise(resolve => setTimeout(resolve, 2000));
      alert('视频生成任务已提交');
    } catch (error) {
      console.error('生成失败', error);
      alert('生成失败');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleUpdateScene = async (sceneId: string, updates: Partial<Scene>) => {
    try {
      const response = await scriptApi.updateScene(scriptId, sceneId, updates);
      setScenes(scenes.map(s => s.id === sceneId ? response.data : s));
      if (selectedScene?.id === sceneId) {
        setSelectedScene(response.data);
      }
    } catch (error) {
      console.error('更新失败', error);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-violet-500 animate-spin" />
      </div>
    );
  }

  if (!script) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="text-center">
          <p className="text-white/60">剧本不存在</p>
          <Link href="/scripts" className="text-violet-400 hover:underline mt-2">
            返回剧本列表
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900">
      {/* 顶部导航 */}
      <header className="glass sticky top-0 z-50 border-b border-white/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <Link href="/scripts" className="p-2 rounded-lg hover:bg-white/5 transition-colors">
                <ChevronLeft className="w-5 h-5 text-white/60" />
              </Link>
              <h1 className="text-xl font-bold text-white">{script.title}</h1>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleAddScene()}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-colors"
              >
                <Plus className="w-4 h-4" />
                添加场景
              </button>
              <button
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-green-600 text-white hover:bg-green-700 transition-colors"
              >
                <Play className="w-4 h-4" />
                预览
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* 主内容 */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 左侧：场景列表 */}
          <div className="lg:col-span-1">
            <div className="glass rounded-2xl p-4">
              <h2 className="text-lg font-semibold text-white mb-4">场景列表</h2>
              
              <div className="space-y-2 max-h-[calc(100vh-280px)] overflow-y-auto">
                {scenes.map((scene, index) => (
                  <div
                    key={scene.id}
                    onClick={() => setSelectedScene(scene)}
                    className={`p-3 rounded-xl cursor-pointer transition-all ${
                      selectedScene?.id === scene.id
                        ? 'bg-violet-600/20 border border-violet-500/50'
                        : 'bg-white/5 border border-white/10 hover:border-white/20'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-violet-600/20 flex items-center justify-center text-violet-400 text-sm font-medium">
                        {scene.scene_number}
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="text-white font-medium text-sm truncate">
                          {scene.title || `场景 ${scene.scene_number}`}
                        </h3>
                        <p className="text-white/40 text-xs truncate">
                          {scene.location || '未设置地点'}
                        </p>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteScene(scene.id);
                        }}
                        className="p-1 rounded hover:bg-red-500/20 text-white/40 hover:text-red-400 transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
                
                {scenes.length === 0 && (
                  <div className="text-center py-8">
                    <p className="text-white/40 mb-4">还没有场景</p>
                    <button
                      onClick={handleAddScene}
                      className="flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-colors mx-auto"
                    >
                      <Plus className="w-4 h-4" />
                      添加场景
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* 右侧：场景编辑器 */}
          <div className="lg:col-span-2">
            {selectedScene ? (
              <div className="glass rounded-2xl p-6">
                {/* 场景标题 */}
                <div className="mb-6">
                  <input
                    type="text"
                    value={selectedScene.title}
                    onChange={(e) => handleUpdateScene(selectedScene.id, { title: e.target.value })}
                    className="w-full text-2xl font-bold text-white bg-transparent border-none focus:outline-none focus:ring-0 placeholder-white/40"
                    placeholder="场景标题"
                  />
                </div>

                {/* 场景信息 */}
                <div className="grid grid-cols-2 gap-4 mb-6">
                  <div>
                    <label className="block text-sm text-white/60 mb-2">地点</label>
                    <input
                      type="text"
                      value={selectedScene.location}
                      onChange={(e) => handleUpdateScene(selectedScene.id, { location: e.target.value })}
                      className="w-full px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-violet-500"
                      placeholder="例如：客厅"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-white/60 mb-2">时间</label>
                    <select
                      value={selectedScene.time_of_day}
                      onChange={(e) => handleUpdateScene(selectedScene.id, { time_of_day: e.target.value })}
                      className="w-full px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                    >
                      <option value="白天">白天</option>
                      <option value="夜晚">夜晚</option>
                      <option value="清晨">清晨</option>
                      <option value="黄昏">黄昏</option>
                    </select>
                  </div>
                </div>

                {/* 场景描述 */}
                <div className="mb-6">
                  <label className="block text-sm text-white/60 mb-2">场景描述</label>
                  <textarea
                    value={selectedScene.description}
                    onChange={(e) => handleUpdateScene(selectedScene.id, { description: e.target.value })}
                    className="w-full px-4 py-3 rounded-lg bg-white/5 border border-white/10 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-violet-500 resize-none"
                    rows={3}
                    placeholder="描述这个场景..."
                  />
                </div>

                {/* 动作描述 */}
                <div className="mb-6">
                  <label className="block text-sm text-white/60 mb-2">动作描述</label>
                  <textarea
                    value={selectedScene.action_description}
                    onChange={(e) => handleUpdateScene(selectedScene.id, { action_description: e.target.value })}
                    className="w-full px-4 py-3 rounded-lg bg-white/5 border border-white/10 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-violet-500 resize-none"
                    rows={3}
                    placeholder="角色的动作..."
                  />
                </div>

                {/* 镜头指示 */}
                <div className="mb-6">
                  <label className="block text-sm text-white/60 mb-2">镜头指示</label>
                  <input
                    type="text"
                    value={selectedScene.camera_direction}
                    onChange={(e) => handleUpdateScene(selectedScene.id, { camera_direction: e.target.value })}
                    className="w-full px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-violet-500"
                    placeholder="例如：特写、全景..."
                  />
                </div>

                {/* AI生成区域 */}
                <div className="border-t border-white/10 pt-6">
                  <h3 className="text-lg font-semibold text-white mb-4">AI生成</h3>
                  
                  <div className="grid grid-cols-3 gap-4">
                    <button
                      onClick={() => handleGenerateVideo(selectedScene.id)}
                      disabled={isGenerating}
                      className="flex flex-col items-center gap-2 p-4 rounded-xl bg-white/5 border border-white/10 hover:border-violet-500/50 transition-all disabled:opacity-50"
                    >
                      <Film className="w-8 h-8 text-violet-400" />
                      <span className="text-white text-sm">生成视频</span>
                    </button>
                    
                    <button className="flex flex-col items-center gap-2 p-4 rounded-xl bg-white/5 border border-white/10 hover:border-violet-500/50 transition-all">
                      <ImageIcon className="w-8 h-8 text-cyan-400" />
                      <span className="text-white text-sm">生成图片</span>
                    </button>
                    
                    <button className="flex flex-col items-center gap-2 p-4 rounded-xl bg-white/5 border border-white/10 hover:border-violet-500/50 transition-all">
                      <Volume2 className="w-8 h-8 text-pink-400" />
                      <span className="text-white text-sm">生成配音</span>
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="glass rounded-2xl p-12 text-center">
                <Film className="w-16 h-16 text-white/20 mx-auto mb-4" />
                <p className="text-white/40 mb-4">选择一个场景开始编辑</p>
                <button
                  onClick={handleAddScene}
                  className="flex items-center gap-2 px-6 py-3 rounded-xl bg-violet-600 text-white hover:bg-violet-700 transition-colors mx-auto"
                >
                  <Plus className="w-5 h-5" />
                  添加第一个场景
                </button>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { 
  ChevronLeft, 
  Play,
  Loader2
} from 'lucide-react';
import { scriptApi } from '@/lib/api';
import { SortableSceneList } from '@/components/script-editor/SortableSceneList';
import { SceneEditor } from '@/components/script-editor/SceneEditor';
import { Timeline } from '@/components/script-editor/Timeline';
import { Character } from '@/components/script-editor/SceneCard';

interface Scene {
  id: string;
  scene_number: number;
  title: string;
  description: string;
  location: string;
  time_of_day: string;
  characters: string[];
  dialogue: Record<string, unknown>;
  action_description: string;
  camera_direction: string;
  duration?: number;
  preview_image?: string;
}

interface Script {
  id: string;
  title: string;
  content: Record<string, unknown> | null;
  status: string;
  ai_generated: boolean;
}

export default function ScriptEditorPage() {
  const params = useParams();
  const scriptId = params.id as string;
  
  const [script, setScript] = useState<Script | null>(null);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedScene, setSelectedScene] = useState<Scene | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  useEffect(() => {
    if (scriptId) {
      loadData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scriptId]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [scriptRes, scenesRes] = await Promise.all([
        scriptApi.getById(scriptId),
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
      const response = await scriptApi.generateSceneVideo(sceneId, {
        style: 'animation',
        duration: 10
      });
      alert(`视频生成任务已提交: ${response.data.task_id}`);
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

  const handleReorderScenes = (newScenes: Scene[]) => {
    setScenes(newScenes);
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
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-green-600 text-white hover:bg-green-700 transition-colors"
              >
                <Play className="w-4 h-4" />
                预览
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1">
            <div className="glass rounded-2xl p-4 h-[calc(100vh-280px)]">
              <SortableSceneList
                scenes={scenes}
                characters={characters}
                selectedSceneId={selectedScene?.id}
                onSceneSelect={setSelectedScene}
                onSceneDelete={handleDeleteScene}
                onSceneReorder={handleReorderScenes}
                onAddScene={handleAddScene}
              />
            </div>
          </div>

          <div className="lg:col-span-2">
            {selectedScene ? (
              <div className="glass rounded-2xl p-6 max-h-[calc(100vh-280px)] overflow-y-auto">
                <SceneEditor
                  scene={selectedScene}
                  characters={characters}
                  isGenerating={isGenerating}
                  onUpdate={(updates) => handleUpdateScene(selectedScene.id, updates)}
                  onGenerateVideo={() => handleGenerateVideo(selectedScene.id)}
                  onGenerateImage={() => {}}
                  onGenerateAudio={() => {}}
                />
              </div>
            ) : (
              <div className="glass rounded-2xl p-12 text-center">
                <p className="text-white/40 mb-4">选择一个场景开始编辑</p>
                <button
                  onClick={handleAddScene}
                  className="flex items-center gap-2 px-6 py-3 rounded-xl bg-violet-600 text-white hover:bg-violet-700 transition-colors mx-auto"
                >
                  添加第一个场景
                </button>
              </div>
            )}
          </div>
        </div>

        <Timeline
          scenes={scenes}
          selectedSceneId={selectedScene?.id}
          onSceneSelect={setSelectedScene}
        />
      </main>
    </div>
  );
}
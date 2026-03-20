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
  Sparkles
} from 'lucide-react';

// 分镜数据类型
interface Scene {
  id: string;
  number: number;
  title: string;
  description: string;
  duration: number;
  image?: string;
  dialogue?: string;
  camera: string;
  effect?: string;
}

// 模拟分镜数据
const MOCK_SCENES: Scene[] = [
  {
    id: '1',
    number: 1,
    title: '开场',
    description: '主人公出现在山谷中，阳光照射',
    duration: 5,
    image: '',
    dialogue: '（旁白）这是一个关于成长的故事',
    camera: '全景',
    effect: '光晕'
  },
  {
    id: '2',
    number: 2,
    title: '下山',
    description: '主人公沿着山路往下走',
    duration: 8,
    image: '',
    dialogue: '我必须离开这里',
    camera: '跟拍',
    effect: '无'
  },
  {
    id: '3',
    number: 3,
    title: '村庄',
    description: '来到一个安静的村庄',
    duration: 10,
    image: '',
    dialogue: '',
    camera: '摇镜头',
    effect: '虚化'
  },
  {
    id: '4',
    number: 4,
    title: '相遇',
    description: '遇到神秘人物',
    duration: 12,
    image: '',
    dialogue: '你是什么人？',
    camera: '特写',
    effect: '暗光'
  }
];

const CAMERA_TYPES = ['全景', '远景', '中景', '近景', '特写', '跟拍', '摇镜头', '推镜头'];
const EFFECTS = ['无', '光晕', '暗光', '虚化', '旋转', '闪烁', '渐变', '粒子'];

// 从 localStorage 加载数据
const loadScenes = (): Scene[] => {
  if (typeof window === 'undefined') return MOCK_SCENES;
  const saved = localStorage.getItem('video-storyboards');
  if (saved) {
    return JSON.parse(saved);
  }
  return MOCK_SCENES;
};

// 保存到 localStorage
const saveScenes = (scenes: Scene[]) => {
  if (typeof window === 'undefined') return;
  localStorage.setItem('video-storyboards', JSON.stringify(scenes));
};

export default function StoryboardsPage() {
  const [scenes, setScenes] = useState<Scene[]>(MOCK_SCENES);
  const [selectedScene, setSelectedScene] = useState<Scene | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [isEditing, setIsEditing] = useState(false);

  // 初始化加载数据
  useEffect(() => {
    const loaded = loadScenes();
    setScenes(loaded);
  }, []);

  // 数据变化时保存
  useEffect(() => {
    saveScenes(scenes);
  }, [scenes]);

  // 筛选分镜
  const filteredScenes = scenes.filter(scene => 
    scene.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    scene.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // 添加分镜
  const handleAddScene = () => {
    const newScene: Scene = {
      id: Date.now().toString(),
      number: scenes.length + 1,
      title: `场景 ${scenes.length + 1}`,
      description: '新建场景',
      duration: 5,
      camera: '中景',
      effect: '无'
    };
    setScenes([...scenes, newScene]);
    setSelectedScene(newScene);
    setIsEditing(true);
  };

  // 更新分镜
  const handleUpdateScene = (updated: Scene) => {
    setScenes(scenes.map(s => s.id === updated.id ? updated : s));
    setSelectedScene(updated);
  };

  // 删除分镜
  const handleDeleteScene = (id: string) => {
    if (confirm('确定要删除这个分镜吗？')) {
      setScenes(scenes.filter(s => s.id !== id));
      if (selectedScene?.id === id) {
        setSelectedScene(null);
      }
    }
  };

  // 移动分镜
  const moveScene = (index: number, direction: 'up' | 'down') => {
    const newScenes = [...scenes];
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= newScenes.length) return;
    
    [newScenes[index], newScenes[targetIndex]] = [newScenes[targetIndex], newScenes[index]];
    newScenes.forEach((s, i) => s.number = i + 1);
    setScenes(newScenes);
  };

  // 总时长
  const totalDuration = scenes.reduce((sum, s) => sum + s.duration, 0);
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
            <Button variant="outline" className="border-white/20 text-white">
              <Download className="w-4 h-4 mr-2" />
              导出
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
              <div className="text-2xl font-bold text-white">{scenes.length}</div>
              <div className="text-sm text-white/60">分镜数量</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-purple-400">{formatTime(totalDuration)}</div>
              <div className="text-sm text-white/60">总时长</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-blue-400">{scenes.filter(s => s.image).length}</div>
              <div className="text-sm text-white/60">已配图</div>
            </CardContent>
          </Card>
        </div>

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
              {filteredScenes.map((scene, index) => (
                <div
                  key={scene.id}
                  onClick={() => setSelectedScene(scene)}
                  className={`p-3 rounded-lg cursor-pointer transition-all ${
                    selectedScene?.id === scene.id
                      ? 'bg-purple-600/20 border-purple-500'
                      : 'bg-white/5 border-white/10 hover:border-white/30'
                  } border`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-6 h-6 rounded bg-purple-600/30 text-purple-300 text-xs flex items-center justify-center">
                        {scene.number}
                      </span>
                      <div>
                        <div className="text-white font-medium">{scene.title}</div>
                        <div className="text-xs text-white/40">{scene.duration}秒 · {scene.camera}</div>
                      </div>
                    </div>
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="w-6 h-6 text-white/40"
                        onClick={(e) => { e.stopPropagation(); moveScene(index, 'up'); }}
                        disabled={index === 0}
                      >
                        <ChevronLeft className="w-3 h-3" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="w-6 h-6 text-white/40"
                        onClick={(e) => { e.stopPropagation(); moveScene(index, 'down'); }}
                        disabled={index === scenes.length - 1}
                      >
                        <ChevronRight className="w-3 h-3" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}

              {/* 添加按钮 */}
              <Button
                onClick={handleAddScene}
                variant="outline"
                className="w-full border-dashed border-white/20 text-white/60 hover:text-white hover:border-white/40"
              >
                <Plus className="w-4 h-4 mr-2" />
                添加分镜
              </Button>
            </div>
          </div>

          {/* 分镜详情 */}
          <div className="lg:col-span-2">
            {selectedScene ? (
              <Card className="bg-white/5 border-white/10">
                <CardHeader>
                  <CardTitle className="text-white flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <LayoutGrid className="w-5 h-5 text-purple-400" />
                      场景 {selectedScene.number}: {selectedScene.title}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-white/60 hover:text-white"
                        onClick={() => setIsEditing(!isEditing)}
                      >
                        <Edit2 className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-white/60 hover:text-red-400"
                        onClick={() => handleDeleteScene(selectedScene.id)}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* 预览图 */}
                  <div className="aspect-video rounded-lg bg-black/50 border border-white/10 flex items-center justify-center">
                    {selectedScene.image ? (
                      <img src={selectedScene.image} alt={selectedScene.title} className="w-full h-full object-cover rounded-lg" />
                    ) : (
                      <div className="text-center">
                        <ImageIcon className="w-12 h-12 mx-auto text-white/20" />
                        <p className="text-white/40 mt-2">点击上传分镜图片</p>
                      </div>
                    )}
                  </div>

                  {/* 基本信息 */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm text-white/60 mb-2 block">场景标题</label>
                      <Input
                        value={selectedScene.title}
                        onChange={(e) => handleUpdateScene({ ...selectedScene, title: e.target.value })}
                        disabled={!isEditing}
                        className="bg-white/5 border-white/10 text-white"
                      />
                    </div>
                    <div>
                      <label className="text-sm text-white/60 mb-2 block">时长（秒）</label>
                      <Input
                        type="number"
                        value={selectedScene.duration}
                        onChange={(e) => handleUpdateScene({ ...selectedScene, duration: parseInt(e.target.value) || 0 })}
                        disabled={!isEditing}
                        className="bg-white/5 border-white/10 text-white"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="text-sm text-white/60 mb-2 block">场景描述</label>
                    <Input
                      value={selectedScene.description}
                      onChange={(e) => handleUpdateScene({ ...selectedScene, description: e.target.value })}
                      disabled={!isEditing}
                      className="bg-white/5 border-white/10 text-white"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm text-white/60 mb-2 block">镜头类型</label>
                      <select
                        value={selectedScene.camera}
                        onChange={(e) => handleUpdateScene({ ...selectedScene, camera: e.target.value })}
                        disabled={!isEditing}
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
                        value={selectedScene.effect || '无'}
                        onChange={(e) => handleUpdateScene({ ...selectedScene, effect: e.target.value })}
                        disabled={!isEditing}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                      >
                        {EFFECTS.map(effect => (
                          <option key={effect} value={effect}>{effect}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="text-sm text-white/60 mb-2 block">台词/配音</label>
                    <Input
                      value={selectedScene.dialogue || ''}
                      onChange={(e) => handleUpdateScene({ ...selectedScene, dialogue: e.target.value })}
                      disabled={!isEditing}
                      placeholder="输入场景台词或配音内容"
                      className="bg-white/5 border-white/10 text-white"
                    />
                  </div>
                </CardContent>
              </Card>
            ) : (
              <div className="h-full flex items-center justify-center">
                <div className="text-center">
                  <LayoutGrid className="w-16 h-16 mx-auto text-white/20" />
                  <p className="text-white/40 mt-4">从左侧选择或添加分镜</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </MainLayout>
  );
}
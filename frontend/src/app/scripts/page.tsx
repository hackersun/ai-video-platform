"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "@/components/ui/toaster";
import { scriptApi, videoApi } from "@/lib/api";
import { 
  Plus, 
  Search, 
  MoreVertical, 
  Edit, 
  Trash2, 
  Film,
  ChevronLeft,
  Clock,
  CheckCircle,
  AlertCircle,
  Sparkles,
  Play,
  Users,
  MessageSquare,
  GripVertical,
  Loader2
} from "lucide-react";
import { cn } from "@/lib/utils";

const statusConfig = {
  completed: { label: "已完成", color: "text-green-400", bg: "bg-green-500/10", icon: CheckCircle },
  writing: { label: "写作中", color: "text-blue-400", bg: "bg-blue-500/10", icon: Clock },
  planning: { label: "规划中", color: "text-yellow-400", bg: "bg-yellow-500/10", icon: AlertCircle },
  draft: { label: "草稿", color: "text-gray-400", bg: "bg-gray-500/10", icon: Clock },
  generating: { label: "生成中", color: "text-purple-400", bg: "bg-purple-500/10", icon: Clock },
  published: { label: "已发布", color: "text-green-400", bg: "bg-green-500/10", icon: CheckCircle },
};

export default function ScriptsPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditor, setShowEditor] = useState(false);
  const [selectedScript, setSelectedScript] = useState<Script | null>(null);
  const [scripts, setScripts] = useState<Script[]>([]);
  const [loading, setLoading] = useState(true);
  const [generatingVideo, setGeneratingVideo] = useState<string | null>(null);

  interface Script {
    id: string;
    title: string;
    novel: string;
    description: string;
    status: string;
    scenes: number;
    characters: number;
    updatedAt: string;
  }

  useEffect(() => {
    loadScripts();
  }, []);

  const loadScripts = async () => {
    try {
      setLoading(true);
      const response = await scriptApi.getList();
      const items = response.data?.items || [];
      setScripts(items.map((s: any) => ({
        id: s.id,
        title: s.title,
        novel: s.novel_id || "未关联小说",
        description: s.content?.substring(0, 50) || "无描述",
        status: s.status || "draft",
        scenes: s.scenes?.length || 0,
        characters: 0,
        updatedAt: s.created_at || s.updated_at || new Date().toISOString()
      })));
    } catch (error: any) {
      console.error('Failed to load scripts:', error);
      if (error.response?.status === 401 || error.response?.status === 403) {
        toast({
          title: "请先登录",
          description: "登录后可查看剧本",
          variant: "error",
        });
      }
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateVideo = async (script: Script) => {
    try {
      setGeneratingVideo(script.id);
      
      // Create video for this script
      const createResponse = await videoApi.create({
        title: `${script.title} - 视频`,
        script_id: script.id,
        settings: {}
      });
      
      const videoId = createResponse.data.id;
      
      await videoApi.generate(videoId);
      
      toast({
        title: "生成已开始",
        description: "视频正在生成中，请稍候...",
        variant: "success",
      });
      
      router.push("/videos");
    } catch (error) {
      console.error('Failed to generate video:', error);
      toast({
        title: "生成失败",
        description: "无法生成视频",
        variant: "error",
      });
    } finally {
      setGeneratingVideo(null);
    }
  };

  const filteredScripts = scripts.filter(
    (script) =>
      script.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      script.novel.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleEditScript = (script: typeof scripts[0]) => {
    setSelectedScript(script);
    setShowEditor(true);
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f]">
      {/* Header */}
      <header className="h-16 border-b border-white/10 flex items-center px-8">
        <button 
          onClick={() => router.push("/dashboard")}
          className="flex items-center gap-2 text-white/60 hover:text-white transition-colors"
        >
          <ChevronLeft className="w-5 h-5" />
          返回
        </button>
        <h1 className="text-xl font-semibold ml-4">剧本编辑</h1>
      </header>

      {/* Content */}
      <div className="p-8">
        {/* Toolbar */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
              <Input
                placeholder="搜索剧本..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-64 pl-10"
              />
            </div>
          </div>
          <div className="flex gap-3">
            <Button variant="secondary">
              <Sparkles className="w-4 h-4 mr-2" />
              AI生成剧本
            </Button>
            <Button onClick={() => setShowCreateModal(true)}>
              <Plus className="w-4 h-4 mr-2" />
              新建剧本
            </Button>
          </div>
        </div>

        {/* Scripts Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredScripts.map((script) => {
            const status = statusConfig[script.status as keyof typeof statusConfig] || statusConfig.draft;
            return (
              <Card 
                key={script.id} 
                className="group hover:border-violet-500/30 transition-all"
              >
                <CardContent className="p-6">
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <h3 className="font-semibold text-lg">{script.title}</h3>
                      <p className="text-sm text-white/40">{script.novel}</p>
                    </div>
                    <div 
                      className={cn(
                        "flex items-center gap-1 px-2 py-1 rounded-full text-xs",
                        status.bg,
                        status.color
                      )}
                    >
                      <status.icon className="w-3 h-3" />
                      {status.label}
                    </div>
                  </div>
                  
                  <p className="text-sm text-white/60 mb-4">
                    {script.description}
                  </p>
                  
                  <div className="flex items-center gap-4 text-sm text-white/40 mb-4">
                    <span className="flex items-center gap-1">
                      <Film className="w-4 h-4" />
                      {script.scenes} 场景
                    </span>
                    <span className="flex items-center gap-1">
                      <Users className="w-4 h-4" />
                      {script.characters} 角色
                    </span>
                  </div>

                  <div className="flex gap-2">
                    <Button 
                      variant="outline" 
                      size="sm" 
                      className="flex-1"
                      onClick={() => handleEditScript(script)}
                    >
                      <Edit className="w-4 h-4 mr-1" />
                      编辑
                    </Button>
                    <Button 
                      variant="secondary" 
                      size="sm" 
                      className="flex-1"
                      onClick={() => handleGenerateVideo(script)}
                      disabled={generatingVideo === script.id}
                    >
                      {generatingVideo === script.id ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                          生成中
                        </>
                      ) : (
                        <>
                          <Play className="w-4 h-4 mr-1" />
                          生成视频
                        </>
                      )}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Empty state */}
        {filteredScripts.length === 0 && (
          <div className="text-center py-20">
            <Film className="w-16 h-16 text-white/20 mx-auto mb-4" />
            <p className="text-white/60">暂无剧本</p>
            <Button variant="outline" className="mt-4" onClick={() => setShowCreateModal(true)}>
              创建第一个剧本
            </Button>
          </div>
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle>新建剧本</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Input label="标题" placeholder="输入剧本标题" />
              <div>
                <label className="block text-sm font-medium text-white/80 mb-1.5">
                  关联小说
                </label>
                <select className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white">
                  <option>星际穿越</option>
                  <option>未来世界</option>
                  <option>魔法学院</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-white/80 mb-1.5">
                  简介
                </label>
                <textarea
                  className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-white/40 focus:outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 min-h-[100px]"
                  placeholder="输入剧本简介"
                />
              </div>
              <div className="flex gap-3 pt-4">
                <Button 
                  variant="outline" 
                  className="flex-1"
                  onClick={() => setShowCreateModal(false)}
                >
                  取消
                </Button>
                <Button className="flex-1" onClick={() => {
                  setShowCreateModal(false);
                  toast({
                    title: "创建成功",
                    description: "剧本已创建",
                    variant: "success",
                  });
                }}>
                  创建
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Script Editor Modal */}
      {showEditor && selectedScript && (
        <ScriptEditor 
          script={selectedScript} 
          onClose={() => setShowEditor(false)} 
        />
      )}
    </div>
  );
}

// Script Editor Component
function ScriptEditor({ script, onClose }: { script: typeof scripts[0]; onClose: () => void }) {
  const [scenes, setScenes] = useState([
    { id: 1, title: "场景1：神秘信号", content: "主角在实验室接收到来自外太空的神秘信号...", characters: ["主角", "助手"] },
    { id: 2, title: "场景2：解密", content: "团队开始分析信号内容，发现其中包含坐标信息...", characters: ["主角", "科学家"] },
    { id: 3, title: "场景3：决定", content: "经过讨论，决定派遣探测器前往信号来源地...", characters: ["主角", "指挥官"] },
  ]);
  const [activeScene, setActiveScene] = useState(1);

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex">
      {/* Sidebar - Scene List */}
      <div className="w-80 bg-[#0d0d12] border-r border-white/10 flex flex-col">
        <div className="p-4 border-b border-white/10 flex items-center justify-between">
          <h2 className="font-semibold">{script.title}</h2>
          <button onClick={onClose} className="text-white/40 hover:text-white">
            ✕
          </button>
        </div>
        
        <div className="flex-1 overflow-auto p-4">
          <div className="space-y-2">
            {scenes.map((scene, index) => (
              <div
                key={scene.id}
                onClick={() => setActiveScene(scene.id)}
                className={cn(
                  "p-3 rounded-lg cursor-pointer transition-all",
                  activeScene === scene.id 
                    ? "bg-violet-500/20 border border-violet-500/30" 
                    : "bg-white/5 hover:bg-white/10"
                )}
              >
                <div className="flex items-center gap-2">
                  <GripVertical className="w-4 h-4 text-white/20" />
                  <span className="text-xs text-white/40">场景 {index + 1}</span>
                </div>
                <p className="font-medium mt-1">{scene.title}</p>
                <p className="text-xs text-white/40 mt-1 line-clamp-2">{scene.content}</p>
              </div>
            ))}
          </div>
          
          <Button 
            variant="outline" 
            className="w-full mt-4"
            onClick={() => {
              const newId = scenes.length + 1;
              setScenes([...scenes, { 
                id: newId, 
                title: `场景${newId}`, 
                content: "", 
                characters: [] 
              }]);
              setActiveScene(newId);
            }}
          >
            <Plus className="w-4 h-4 mr-2" />
            添加场景
          </Button>
        </div>
      </div>

      {/* Main Editor */}
      <div className="flex-1 flex flex-col bg-[#0a0a0f]">
        <div className="h-14 border-b border-white/10 flex items-center justify-between px-6">
          <div className="flex items-center gap-4">
            <span className="text-white/40">编辑中</span>
            <span className="text-sm text-white/60">自动保存</span>
          </div>
          <div className="flex gap-3">
            <Button variant="outline" size="sm">
              <Sparkles className="w-4 h-4 mr-2" />
              AI续写
            </Button>
            <Button size="sm">
              <CheckCircle className="w-4 h-4 mr-2" />
              保存
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-auto p-8">
          {scenes.map((scene) => (
            scene.id === activeScene && (
              <div key={scene.id} className="max-w-3xl mx-auto space-y-6">
                <Input 
                  label="场景标题" 
                  defaultValue={scene.title}
                  className="text-xl font-semibold"
                />
                
                <div>
                  <label className="block text-sm font-medium text-white/80 mb-1.5">
                    场景描述
                  </label>
                  <textarea
                    defaultValue={scene.content}
                    className="w-full px-4 py-3 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-white/40 focus:outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 min-h-[200px] resize-y"
                    placeholder="描述场景内容..."
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-white/80 mb-1.5">
                    出场角色
                  </label>
                  <div className="flex gap-2">
                    {scene.characters.map((char, i) => (
                      <span 
                        key={i}
                        className="px-3 py-1 rounded-full bg-violet-500/20 text-violet-300 text-sm"
                      >
                        {char}
                      </span>
                    ))}
                    <button className="px-3 py-1 rounded-full border border-white/20 text-white/60 text-sm hover:bg-white/5">
                      + 添加
                    </button>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-white/80 mb-1.5">
                    对话
                  </label>
                  <div className="space-y-3">
                    <div className="flex gap-3">
                      <select className="w-32 px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm">
                        <option>主角</option>
                        <option>助手</option>
                      </select>
                      <input 
                        type="text" 
                        placeholder="输入对话内容..."
                        className="flex-1 px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-white"
                      />
                    </div>
                    <Button variant="outline" size="sm">
                      <MessageSquare className="w-4 h-4 mr-2" />
                      添加对话
                    </Button>
                  </div>
                </div>
              </div>
            )
          ))}
        </div>
      </div>
    </div>
  );
}

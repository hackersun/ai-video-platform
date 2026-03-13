"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "@/components/ui/toaster";
import { videoApi, scriptApi } from "@/lib/api";
import { 
  Plus, 
  Search, 
  Play, 
  Pause,
  Download, 
  Film,
  ChevronLeft,
  Clock,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  Settings,
  Video,
  Trash2,
  Share2,
  Eye,
  Loader2
} from "lucide-react";
import { cn } from "@/lib/utils";

const statusConfig = {
  completed: { 
    label: "已完成", 
    color: "text-green-400", 
    bg: "bg-green-500/10", 
    icon: CheckCircle,
    message: "视频生成完成"
  },
  generating: { 
    label: "生成中", 
    color: "text-blue-400", 
    bg: "bg-blue-500/10", 
    icon: RefreshCw,
    message: "正在生成视频..."
  },
  pending: { 
    label: "排队中", 
    color: "text-yellow-400", 
    bg: "bg-yellow-500/10", 
    icon: Clock,
    message: "等待生成..."
  },
  failed: { 
    label: "失败", 
    color: "text-red-400", 
    bg: "bg-red-500/10", 
    icon: AlertCircle,
    message: "生成失败，请重试"
  },
};

const resolutions = ["720p", "1080p", "4K"];
const videoStyles = ["写实", "动漫", "油画"];

interface Video {
  id: string;
  title: string;
  script_id?: string;
  status: string;
  video_url?: string;
  settings?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

interface Script {
  id: string;
  title: string;
}

export default function VideosPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showPlayer, setShowPlayer] = useState(false);
  const [selectedVideo, setSelectedVideo] = useState<Video | null>(null);
  const [videos, setVideos] = useState<Video[]>([]);
  const [scripts, setScripts] = useState<Script[]>([]);
  const [loading, setLoading] = useState(true);
  const [generatingVideos, setGeneratingVideos] = useState<string[]>([]);
  
  // Create modal state
  const [selectedScriptId, setSelectedScriptId] = useState("");
  const [videoTitle, setVideoTitle] = useState("");
  const [selectedResolution, setSelectedResolution] = useState("1080p");
  const [selectedStyle, setSelectedStyle] = useState("写实");
  const [creatingVideo, setCreatingVideo] = useState(false);

  // Load videos from API
  const loadVideos = async () => {
    try {
      setLoading(true);
      const response = await videoApi.getList();
      setVideos(response.data?.items || []);
    } catch (error) {
      console.error('Failed to load videos:', error);
    } finally {
      setLoading(false);
    }
  };

  // Load scripts for create modal
  const loadScripts = async () => {
    try {
      const response = await scriptApi.getList();
      const items = response.data?.items || [];
      setScripts(items.map((s: any) => ({
        id: s.id,
        title: s.title
      })));
    } catch (error) {
      console.error('Failed to load scripts:', error);
    }
  };

  useEffect(() => {
    loadVideos();
  }, []);

  useEffect(() => {
    if (showCreateModal) {
      loadScripts();
    }
  }, [showCreateModal]);

  // Poll for generating video status
  useEffect(() => {
    if (generatingVideos.length === 0) return;
    
    const interval = setInterval(async () => {
      for (const videoId of generatingVideos) {
        try {
          const response = await videoApi.getStatus(videoId);
          const status = response.data?.status;
          
          if (status === "completed" || status === "failed") {
            setGeneratingVideos(prev => prev.filter(id => id !== videoId));
            loadVideos();
            
            if (status === "completed") {
              toast({
                title: "视频生成完成",
                description: "视频已生成完毕",
                variant: "success",
              });
            }
          }
        } catch (error) {
          console.error('Failed to check video status:', error);
        }
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [generatingVideos]);

  const filteredVideos = videos.filter(
    (video) =>
      video.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handlePlayVideo = (video: Video) => {
    if (video.status === "completed" && video.video_url) {
      setSelectedVideo(video);
      setShowPlayer(true);
    }
  };

  const handleDownload = (video: Video) => {
    if (video.video_url) {
      window.open(video.video_url, '_blank');
    }
  };

  const handleRetry = async (video: Video) => {
    try {
      setGeneratingVideos(prev => [...prev, video.id]);
      await videoApi.generate(video.id);
      toast({
        title: "已重新开始生成",
        description: "视频正在重新生成",
        variant: "info",
      });
    } catch (error) {
      console.error('Failed to retry video:', error);
      toast({
        title: "重试失败",
        description: "无法重新生成视频",
        variant: "error",
      });
    }
  };

  const handleCreateVideo = async () => {
    if (!selectedScriptId) {
      toast({
        title: "请选择剧本",
        description: "需要选择一个剧本才能生成视频",
        variant: "error",
      });
      return;
    }

    try {
      setCreatingVideo(true);
      
      // Find selected script
      const selectedScript = scripts.find(s => s.id === selectedScriptId);
      const title = videoTitle || `${selectedScript?.title || '视频'} - 视频`;
      
      // Create video
      const createResponse = await videoApi.create({
        title,
        script_id: selectedScriptId,
        settings: {
          resolution: selectedResolution,
          style: selectedStyle
        }
      });
      
      const videoId = createResponse.data.id;
      
      // Start generation
      await videoApi.generate(videoId);
      
      setGeneratingVideos(prev => [...prev, videoId]);
      setShowCreateModal(false);
      
      // Reset form
      setSelectedScriptId("");
      setVideoTitle("");
      setSelectedResolution("1080p");
      setSelectedStyle("写实");
      
      toast({
        title: "已加入队列",
        description: "视频生成任务已创建",
        variant: "success",
      });
      
      // Reload videos
      loadVideos();
    } catch (error: any) {
      console.error('Failed to create video:', error);
      toast({
        title: "创建失败",
        description: error.response?.data?.detail || "无法创建视频",
        variant: "error",
      });
    } finally {
      setCreatingVideo(false);
    }
  };

  const handleDeleteVideo = async (videoId: string) => {
    try {
      await videoApi.delete(videoId);
      toast({
        title: "删除成功",
        variant: "success",
      });
      loadVideos();
    } catch (error) {
      console.error('Failed to delete video:', error);
      toast({
        title: "删除失败",
        variant: "error",
      });
    }
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
        <h1 className="text-xl font-semibold ml-4">视频生成</h1>
      </header>

      {/* Content */}
      <div className="p-8">
        {/* Toolbar */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
              <Input
                placeholder="搜索视频..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-64 pl-10"
              />
            </div>
          </div>
          <Button onClick={() => setShowCreateModal(true)}>
            <Plus className="w-4 h-4 mr-2" />
            新建视频
          </Button>
        </div>

        {loading ? (
          <div className="text-center py-20">
            <Loader2 className="w-8 h-8 text-violet-400 animate-spin mx-auto" />
            <p className="text-white/60 mt-4">加载中...</p>
          </div>
        ) : (
          <>
            {/* Videos Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredVideos.map((video) => {
                const status = statusConfig[video.status as keyof typeof statusConfig] || statusConfig.pending;
                const isGenerating = generatingVideos.includes(video.id);
                
                return (
                  <Card 
                    key={video.id} 
                    className="group hover:border-violet-500/30 transition-all overflow-hidden"
                  >
                    {/* Thumbnail */}
                    <div className="aspect-video bg-gradient-to-br from-violet-500/10 to-purple-600/10 flex items-center justify-center relative">
                      {video.status === "completed" ? (
                        <>
                          <Video className="w-16 h-16 text-white/20" />
                          <button 
                            onClick={() => handlePlayVideo(video)}
                            className="absolute inset-0 flex items-center justify-center bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            <div className="w-16 h-16 rounded-full bg-white/20 flex items-center justify-center">
                              <Play className="w-8 h-8 text-white" />
                            </div>
                          </button>
                        </>
                      ) : isGenerating || video.status === "generating" ? (
                        <div className="text-center">
                          <RefreshCw className="w-12 h-12 text-blue-400 animate-spin mx-auto mb-2" />
                          <p className="text-sm text-white/60">生成中...</p>
                        </div>
                      ) : video.status === "pending" ? (
                        <div className="text-center">
                          <Clock className="w-12 h-12 text-yellow-400 mx-auto mb-2" />
                          <p className="text-sm text-white/60">排队中</p>
                        </div>
                      ) : (
                        <div className="text-center">
                          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-2" />
                          <p className="text-sm text-white/60">生成失败</p>
                        </div>
                      )}

                      {/* Status badge */}
                      <div 
                        className={cn(
                          "absolute top-3 right-3 flex items-center gap-1 px-2 py-1 rounded-full text-xs",
                          status.bg,
                          status.color
                        )}
                      >
                        <status.icon className={cn("w-3 h-3", isGenerating && "animate-spin")} />
                        {status.label}
                      </div>
                    </div>
                    
                    {/* Info */}
                    <CardContent className="p-4">
                      <h3 className="font-semibold mb-1">{video.title}</h3>
                      <p className="text-sm text-white/40 mb-3">
                        {video.settings?.resolution && `分辨率: ${video.settings.resolution} | `}
                        {video.settings?.style && `风格: ${video.settings.style}`}
                      </p>

                      {/* Actions */}
                      <div className="flex gap-2">
                        {video.status === "completed" && (
                          <>
                            <Button 
                              variant="outline" 
                              size="sm" 
                              className="flex-1"
                              onClick={() => handlePlayVideo(video)}
                            >
                              <Eye className="w-4 h-4 mr-1" />
                              预览
                            </Button>
                            <Button 
                              variant="secondary" 
                              size="sm" 
                              className="flex-1"
                              onClick={() => handleDownload(video)}
                            >
                              <Download className="w-4 h-4 mr-1" />
                              下载
                            </Button>
                          </>
                        )}
                        {(video.status === "failed" || video.status === "pending") && (
                          <Button 
                            variant="secondary" 
                            size="sm" 
                            className="flex-1"
                            onClick={() => handleRetry(video)}
                          >
                            <RefreshCw className="w-4 h-4 mr-1" />
                            重试
                          </Button>
                        )}
                        <Button 
                          variant="ghost" 
                          size="sm"
                          className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                          onClick={() => handleDeleteVideo(video.id)}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>

            {/* Empty state */}
            {filteredVideos.length === 0 && (
              <div className="text-center py-20">
                <Film className="w-16 h-16 text-white/20 mx-auto mb-4" />
                <p className="text-white/60">暂无视频</p>
                <Button variant="outline" className="mt-4" onClick={() => setShowCreateModal(true)}>
                  生成第一个视频
                </Button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <Card className="w-full max-w-lg">
            <CardHeader>
              <CardTitle>新建视频</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-white/80 mb-1.5">
                  选择剧本
                </label>
                <select 
                  className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white"
                  value={selectedScriptId}
                  onChange={(e) => setSelectedScriptId(e.target.value)}
                >
                  <option value="">请选择剧本</option>
                  {scripts.map((script) => (
                    <option key={script.id} value={script.id}>
                      {script.title}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-white/80 mb-1.5">
                  视频标题
                </label>
                <Input 
                  placeholder="输入视频标题（留空则使用剧本标题）" 
                  value={videoTitle}
                  onChange={(e) => setVideoTitle(e.target.value)}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-white/80 mb-1.5">
                  分辨率
                </label>
                <div className="grid grid-cols-3 gap-3">
                  {resolutions.map((res) => (
                    <button
                      key={res}
                      type="button"
                      onClick={() => setSelectedResolution(res)}
                      className={cn(
                        "px-4 py-2 rounded-lg border text-sm transition-all",
                        selectedResolution === res
                          ? "border-violet-500 bg-violet-500/20 text-violet-300"
                          : "border-white/10 bg-white/5 text-white/60 hover:bg-white/10"
                      )}
                    >
                      {res}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-white/80 mb-1.5">
                  视频风格
                </label>
                <div className="grid grid-cols-3 gap-3">
                  {videoStyles.map((style) => (
                    <button
                      key={style}
                      type="button"
                      onClick={() => setSelectedStyle(style)}
                      className={cn(
                        "px-4 py-2 rounded-lg border text-sm transition-all",
                        selectedStyle === style
                          ? "border-violet-500 bg-violet-500/20 text-violet-300"
                          : "border-white/10 bg-white/5 text-white/60 hover:bg-white/10"
                      )}
                    >
                      {style}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex gap-3 pt-4">
                <Button 
                  variant="outline" 
                  className="flex-1"
                  onClick={() => setShowCreateModal(false)}
                >
                  取消
                </Button>
                <Button 
                  className="flex-1"
                  onClick={handleCreateVideo}
                  disabled={creatingVideo || !selectedScriptId}
                >
                  {creatingVideo ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      创建中...
                    </>
                  ) : (
                    <>
                      <Film className="w-4 h-4 mr-2" />
                      开始生成
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Video Player Modal */}
      {showPlayer && selectedVideo && (
        <div className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center">
          <div className="w-full max-w-5xl mx-4">
            {/* Player */}
            <div className="aspect-video bg-black rounded-lg overflow-hidden relative">
              <div className="absolute inset-0 flex items-center justify-center">
                {selectedVideo.video_url ? (
                  <video 
                    src={selectedVideo.video_url} 
                    controls 
                    className="w-full h-full"
                  />
                ) : (
                  <>
                    <Video className="w-24 h-24 text-white/20" />
                    <p className="absolute text-white/40 mt-32">视频播放器</p>
                  </>
                )}
              </div>
            </div>

            {/* Info */}
            <div className="mt-4 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-lg">{selectedVideo.title}</h3>
              </div>
              <div className="flex gap-3">
                <Button variant="secondary" size="sm">
                  <Download className="w-4 h-4 mr-2" />
                  下载
                </Button>
                <button 
                  onClick={() => setShowPlayer(false)}
                  className="text-white/60 hover:text-white"
                >
                  ✕
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

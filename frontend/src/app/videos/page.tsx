"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "@/components/ui/toaster";
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
  Eye
} from "lucide-react";
import { cn } from "@/lib/utils";

// Mock data
const videos = [
  {
    id: 1,
    title: "星际穿越 - 第一幕",
    script: "星际穿越 - 第一幕",
    status: "completed",
    progress: 100,
    duration: "2:34",
    resolution: "1080p",
    createdAt: "2024-03-10",
    thumbnail: null,
  },
  {
    id: 2,
    title: "未来世界 - 序章",
    script: "未来世界 - 序章",
    status: "generating",
    progress: 65,
    duration: null,
    resolution: "1080p",
    createdAt: "2024-03-12",
    thumbnail: null,
  },
  {
    id: 3,
    title: "魔法学院 - 入学测试",
    script: "魔法学院 - 入学测试",
    status: "queued",
    progress: 0,
    duration: null,
    resolution: "1080p",
    createdAt: "2024-03-12",
    thumbnail: null,
  },
  {
    id: 4,
    title: "星际穿越 - 第二幕",
    script: "星际穿越 - 第二幕",
    status: "failed",
    progress: 30,
    duration: null,
    resolution: "1080p",
    createdAt: "2024-03-08",
    thumbnail: null,
  },
];

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
  queued: { 
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

export default function VideosPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showPlayer, setShowPlayer] = useState(false);
  const [selectedVideo, setSelectedVideo] = useState<typeof videos[0] | null>(null);
  const [generatingVideos, setGeneratingVideos] = useState<number[]>([]);

  // Simulate progress for generating videos
  useEffect(() => {
    const interval = setInterval(() => {
      setGeneratingVideos(prev => {
        return prev.map(id => {
          const video = videos.find(v => v.id === id);
          if (video && video.status === "generating") {
            // In real app, this would be updated from API
          }
          return id;
        });
      });
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  const filteredVideos = videos.filter(
    (video) =>
      video.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      video.script.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handlePlayVideo = (video: typeof videos[0]) => {
    if (video.status === "completed") {
      setSelectedVideo(video);
      setShowPlayer(true);
    }
  };

  const handleDownload = (video: typeof videos[0]) => {
    toast({
      title: "开始下载",
      description: `${video.title} 正在下载`,
      variant: "info",
    });
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

        {/* Videos Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredVideos.map((video) => {
            const status = statusConfig[video.status as keyof typeof statusConfig];
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
                  ) : video.status === "generating" ? (
                    <div className="text-center">
                      <RefreshCw className="w-12 h-12 text-blue-400 animate-spin mx-auto mb-2" />
                      <p className="text-sm text-white/60">{video.progress}%</p>
                    </div>
                  ) : video.status === "queued" ? (
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
                    <status.icon className={cn("w-3 h-3", video.status === "generating" && "animate-spin")} />
                    {status.label}
                  </div>
                </div>
                
                {/* Info */}
                <CardContent className="p-4">
                  <h3 className="font-semibold mb-1">{video.title}</h3>
                  <p className="text-sm text-white/40 mb-3">{video.script}</p>
                  
                  {video.status === "completed" && (
                    <div className="flex items-center gap-4 text-sm text-white/40 mb-3">
                      <span>{video.duration}</span>
                      <span>{video.resolution}</span>
                    </div>
                  )}

                  {video.status === "generating" && (
                    <div className="mb-3">
                      <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-blue-500 rounded-full transition-all"
                          style={{ width: `${video.progress}%` }}
                        />
                      </div>
                      <p className="text-xs text-white/40 mt-1">{status.message}</p>
                    </div>
                  )}

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
                    {video.status === "failed" && (
                      <Button 
                        variant="secondary" 
                        size="sm" 
                        className="flex-1"
                      >
                        <RefreshCw className="w-4 h-4 mr-1" />
                        重试
                      </Button>
                    )}
                    <Button 
                      variant="ghost" 
                      size="sm"
                      className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
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
                <select className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white">
                  <option>星际穿越 - 第一幕</option>
                  <option>未来世界 - 序章</option>
                  <option>魔法学院 - 入学测试</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-white/80 mb-1.5">
                  视频标题
                </label>
                <Input placeholder="输入视频标题" defaultValue="星际穿越 - 第一幕" />
              </div>

              <div>
                <label className="block text-sm font-medium text-white/80 mb-1.5">
                  分辨率
                </label>
                <div className="grid grid-cols-3 gap-3">
                  {["720p", "1080p", "4K"].map((res) => (
                    <button
                      key={res}
                      className={cn(
                        "px-4 py-2 rounded-lg border text-sm transition-all",
                        res === "1080p"
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
                  {["写实", "动漫", "油画"].map((style) => (
                    <button
                      key={style}
                      className={cn(
                        "px-4 py-2 rounded-lg border text-sm transition-all",
                        style === "写实"
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
                  onClick={() => {
                    setShowCreateModal(false);
                    toast({
                      title: "已加入队列",
                      description: "视频生成任务已创建",
                      variant: "success",
                    });
                  }}
                >
                  <Film className="w-4 h-4 mr-2" />
                  开始生成
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
                <Video className="w-24 h-24 text-white/20" />
                <p className="absolute text-white/40 mt-32">视频播放器</p>
              </div>
              
              {/* Controls */}
              <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/80 to-transparent">
                <div className="flex items-center gap-4">
                  <button className="text-white hover:text-violet-400">
                    <Pause className="w-6 h-6" />
                  </button>
                  <div className="flex-1 h-1 bg-white/20 rounded-full">
                    <div className="w-1/3 h-full bg-violet-500 rounded-full" />
                  </div>
                  <span className="text-sm text-white/60">1:23 / {selectedVideo.duration}</span>
                </div>
              </div>
            </div>

            {/* Info */}
            <div className="mt-4 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-lg">{selectedVideo.title}</h3>
                <p className="text-sm text-white/40">{selectedVideo.script}</p>
              </div>
              <div className="flex gap-3">
                <Button variant="outline" size="sm">
                  <Share2 className="w-4 h-4 mr-2" />
                  分享
                </Button>
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

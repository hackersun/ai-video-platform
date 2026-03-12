"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "@/components/ui/toaster";
import { 
  Plus, 
  Search, 
  MoreVertical, 
  Edit, 
  Trash2, 
  FileText,
  ChevronLeft,
  Clock,
  CheckCircle,
  AlertCircle,
  Loader2
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDate } from "@/lib/utils";
import { useNovels, useCreateNovel, useDeleteNovel, Novel } from "@/hooks/use-novels";
import { useRequireAuth } from "@/hooks/use-auth";

const statusConfig = {
  completed: { label: "已完成", color: "text-green-400", bg: "bg-green-500/10", icon: CheckCircle },
  writing: { label: "写作中", color: "text-blue-400", bg: "bg-blue-500/10", icon: Clock },
  planning: { label: "规划中", color: "text-yellow-400", bg: "bg-yellow-500/10", icon: AlertCircle },
};

export default function NovelsPage() {
  const router = useRouter();
  const { shouldRedirect } = useRequireAuth();
  const [searchQuery, setSearchQuery] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newNovel, setNewNovel] = useState({ title: "", author: "", description: "" });

  // API Hooks
  const { data: novels, isLoading, error } = useNovels();
  const createNovel = useCreateNovel();
  const deleteNovel = useDeleteNovel();

  // 如果需要登录，重定向
  if (shouldRedirect) {
    router.push("/login");
    return null;
  }

  const filteredNovels = novels?.filter(
    (novel: Novel) =>
      novel.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      novel.author.toLowerCase().includes(searchQuery.toLowerCase())
  ) || [];

  const handleCreateNovel = async () => {
    try {
      await createNovel.mutateAsync(newNovel);
      setShowCreateModal(false);
      setNewNovel({ title: "", author: "", description: "" });
      toast({
        title: "创建成功",
        description: "小说已创建",
        variant: "success",
      });
    } catch (error: any) {
      toast({
        title: "创建失败",
        description: error.message || "请稍后重试",
        variant: "error",
      });
    }
  };

  const handleDeleteNovel = async (id: string) => {
    try {
      await deleteNovel.mutateAsync(id);
      toast({
        title: "删除成功",
        description: "小说已删除",
        variant: "success",
      });
    } catch (error: any) {
      toast({
        title: "删除失败",
        description: error.message || "请稍后重试",
        variant: "error",
      });
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-violet-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 mb-4">加载失败</p>
          <Button onClick={() => window.location.reload()}>重试</Button>
        </div>
      </div>
    );
  }

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
        <h1 className="text-xl font-semibold ml-4">小说管理</h1>
      </header>

      {/* Content */}
      <div className="p-8">
        {/* Toolbar */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
              <Input
                placeholder="搜索小说..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-64 pl-10"
              />
            </div>
          </div>
          <Button onClick={() => setShowCreateModal(true)}>
            <Plus className="w-4 h-4 mr-2" />
            新建小说
          </Button>
        </div>

        {/* Novels Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredNovels.map((novel: Novel) => {
            const status = statusConfig[novel.status as keyof typeof statusConfig];
            return (
              <Card 
                key={novel.id} 
                className="group hover:border-violet-500/30 transition-all cursor-pointer"
                onClick={() => router.push(`/novels/${novel.id}`)}
              >
                <CardContent className="p-0">
                  {/* Cover */}
                  <div className="aspect-[3/2] bg-gradient-to-br from-violet-500/20 to-purple-600/20 flex items-center justify-center">
                    <FileText className="w-16 h-16 text-white/20" />
                  </div>
                  
                  {/* Info */}
                  <div className="p-6">
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="font-semibold text-lg">{novel.title}</h3>
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
                    
                    <p className="text-sm text-white/60 mb-4 line-clamp-2">
                      {novel.description}
                    </p>
                    
                    <div className="flex items-center gap-4 text-sm text-white/40">
                      <span>{novel.chapters} 章节</span>
                      <span>{novel.characters} 角色</span>
                      <span>{formatDate(novel.updated_at)}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Empty state */}
        {filteredNovels.length === 0 && (
          <div className="text-center py-20">
            <FileText className="w-16 h-16 text-white/20 mx-auto mb-4" />
            <p className="text-white/60">暂无小说</p>
            <Button variant="outline" className="mt-4" onClick={() => setShowCreateModal(true)}>
              创建第一本小说
            </Button>
          </div>
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle>新建小说</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Input
                label="标题"
                placeholder="输入小说标题"
                value={newNovel.title}
                onChange={(e) => setNewNovel({ ...newNovel, title: e.target.value })}
              />
              <Input
                label="作者"
                placeholder="输入作者名称"
                value={newNovel.author}
                onChange={(e) => setNewNovel({ ...newNovel, author: e.target.value })}
              />
              <div>
                <label className="block text-sm font-medium text-white/80 mb-1.5">
                  简介
                </label>
                <textarea
                  className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-white/40 focus:outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 min-h-[100px]"
                  placeholder="输入小说简介"
                  value={newNovel.description}
                  onChange={(e) => setNewNovel({ ...newNovel, description: e.target.value })}
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
                <Button 
                  className="flex-1" 
                  onClick={handleCreateNovel}
                  isLoading={createNovel.isPending}
                >
                  创建
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

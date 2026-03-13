"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "@/components/ui/toaster";
import { novelApi, scriptApi } from "@/lib/api";
import { 
  Plus, 
  Search, 
  ChevronLeft,
  Sparkles,
  Loader2,
  FileText,
  BookOpen,
  Wand2
} from "lucide-react";
import { cn } from "@/lib/utils";

interface Novel {
  id: string;
  title: string;
  description?: string;
  status: string;
  chapters_count?: number;
  created_at: string;
}

export default function AIGeneratePage() {
  const router = useRouter();
  const [novels, setNovels] = useState<Novel[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedNovel, setSelectedNovel] = useState<Novel | null>(null);
  const [generating, setGenerating] = useState(false);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [generatedScript, setGeneratedScript] = useState<any>(null);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    loadNovels();
  }, []);

  const loadNovels = async () => {
    try {
      setLoading(true);
      const response = await novelApi.getList();
      setNovels(response.data?.items || []);
    } catch (error) {
      console.error('Failed to load novels:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateScript = async () => {
    if (!selectedNovel) {
      toast({
        title: "请选择小说",
        description: "请先选择要生成剧本的小说",
        variant: "error",
      });
      return;
    }

    try {
      setGenerating(true);
      setGenerationProgress(0);

      const progressInterval = setInterval(() => {
        setGenerationProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return prev;
          }
          return prev + 10;
        });
      }, 500);

      const response = await scriptApi.create({
        title: `${selectedNovel.title} - 剧本`,
        novel_id: selectedNovel.id,
        content: {}
      });

      clearInterval(progressInterval);
      setGenerationProgress(100);

      setGeneratedScript(response.data);
      
      toast({
        title: "生成成功",
        description: "剧本已成功生成",
        variant: "success",
      });
    } catch (error) {
      console.error('Failed to generate script:', error);
      toast({
        title: "生成失败",
        description: "无法生成剧本",
        variant: "error",
      });
    } finally {
      setGenerating(false);
    }
  };

  const filteredNovels = novels.filter(novel =>
    novel.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

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
        <h1 className="text-xl font-semibold ml-4">AI智能创作</h1>
      </header>

      <div className="p-8">
        <div className="max-w-4xl mx-auto">
          {/* Intro Card */}
          <Card className="mb-8">
            <CardContent className="p-6">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
                  <Wand2 className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold mb-2">AI剧本生成</h2>
                  <p className="text-white/60 text-sm">
                    选择一本小说，AI将自动分析小说内容并生成可用于视频拍摄的剧本。
                    生成的剧本包含场景描述、角色对话、动作指导等信息。
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {generatedScript ? (
            /* Generated Result */
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-green-400" />
                  生成完成
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="p-4 rounded-lg bg-green-500/10 border border-green-500/20">
                  <p className="text-green-400 font-medium">剧本已创建成功</p>
                  <p className="text-white/60 text-sm mt-1">{generatedScript.title}</p>
                </div>
                <div className="flex gap-3">
                  <Button onClick={() => router.push(`/scripts/${generatedScript.id}`)}>
                    <FileText className="w-4 h-4 mr-2" />
                    查看剧本
                  </Button>
                  <Button variant="outline" onClick={() => {
                    setGeneratedScript(null);
                    setSelectedNovel(null);
                    setGenerationProgress(0);
                  }}>
                    继续创作
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : (
            <>
              {/* Novel Selection */}
              <div className="mb-6">
                <h3 className="text-lg font-medium mb-4">选择小说</h3>
                <div className="relative mb-4">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                  <Input
                    placeholder="搜索小说..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-10"
                  />
                </div>

                {loading ? (
                  <div className="text-center py-12">
                    <Loader2 className="w-8 h-8 text-violet-400 animate-spin mx-auto" />
                    <p className="text-white/60 mt-4">加载中...</p>
                  </div>
                ) : filteredNovels.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {filteredNovels.map((novel) => (
                      <div
                        key={novel.id}
                        onClick={() => setSelectedNovel(novel)}
                        className={cn(
                          "p-4 rounded-xl border cursor-pointer transition-all",
                          selectedNovel?.id === novel.id
                            ? "border-violet-500 bg-violet-500/10"
                            : "border-white/10 bg-white/5 hover:border-white/20"
                        )}
                      >
                        <div className="flex items-start gap-3">
                          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-violet-500/20 to-purple-600/20 flex items-center justify-center">
                            <BookOpen className="w-5 h-5 text-violet-400" />
                          </div>
                          <div className="flex-1">
                            <h4 className="font-medium">{novel.title}</h4>
                            <p className="text-sm text-white/40 line-clamp-1">
                              {novel.description || "暂无描述"}
                            </p>
                            <p className="text-xs text-white/30 mt-1">
                              {novel.chapters_count || 0} 章 · {novel.status === 'published' ? '已发布' : '草稿'}
                            </p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12 text-white/40">
                    <BookOpen className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p>暂无小说</p>
                    <Button 
                      variant="outline" 
                      className="mt-4"
                      onClick={() => router.push("/novels/new")}
                    >
                      <Plus className="w-4 h-4 mr-2" />
                      创建小说
                    </Button>
                  </div>
                )}
              </div>

              {/* Generate Button */}
              <div className="flex justify-center">
                <Button 
                  size="lg"
                  onClick={handleGenerateScript}
                  disabled={!selectedNovel || generating}
                  className="min-w-[200px]"
                >
                  {generating ? (
                    <>
                      <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                      生成中... {generationProgress}%
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-5 h-5 mr-2" />
                      开始AI生成
                    </>
                  )}
                </Button>
              </div>

              {generating && (
                <div className="mt-6">
                  <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-gradient-to-r from-violet-500 to-purple-500 rounded-full transition-all"
                      style={{ width: `${generationProgress}%` }}
                    />
                  </div>
                  <p className="text-center text-sm text-white/40 mt-2">
                    {generationProgress < 30 && "分析小说内容中..."}
                    {generationProgress >= 30 && generationProgress < 60 && "生成场景中..."}
                    {generationProgress >= 60 && generationProgress < 90 && "完善角色对话中..."}
                    {generationProgress >= 90 && "生成剧本中..."}
                  </p>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

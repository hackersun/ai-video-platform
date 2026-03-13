"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/toaster";
import { scriptApi } from "@/lib/api";
import {
  Layers,
  ChevronRight,
  Check,
  Loader2,
  Play,
  Pause,
  RotateCcw,
  Sparkles,
  FileText,
  Clock,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface Chapter {
  id: string;
  number: number;
  title: string;
  status: "pending" | "generating" | "completed" | "failed";
  scenes_count?: number;
  error?: string;
}

interface ChapterGeneratorProps {
  novelId: string;
  novelTitle: string;
  chapters: Array<{ id: string; number: number; title: string }>;
  onComplete?: (chapters: Chapter[]) => void;
}

export function ChapterGenerator({
  novelId,
  novelTitle,
  chapters,
  onComplete,
}: ChapterGeneratorProps) {
  const [generatedChapters, setGeneratedChapters] = useState<Chapter[]>(() =>
    chapters.map((ch) => ({
      id: ch.id,
      number: ch.number,
      title: ch.title,
      status: "pending" as const,
    }))
  );
  const [generatingAll, setGeneratingAll] = useState(false);
  const [currentChapterIndex, setCurrentChapterIndex] = useState(-1);
  const [autoGenerate, setAutoGenerate] = useState(true);

  const completedCount = generatedChapters.filter(
    (ch) => ch.status === "completed"
  ).length;
  const totalCount = generatedChapters.length;

  const generateChapter = async (chapterIndex: number) => {
    const chapter = generatedChapters[chapterIndex];
    
    setGeneratedChapters((prev) =>
      prev.map((ch, idx) =>
        idx === chapterIndex ? { ...ch, status: "generating" } : ch
      )
    );
    setCurrentChapterIndex(chapterIndex);

    try {
      await scriptApi.generate({
        novel_id: novelId,
        prompt: `生成第${chapter.number}章: ${chapter.title}`,
      });

      setGeneratedChapters((prev) =>
        prev.map((ch, idx) =>
          idx === chapterIndex
            ? { ...ch, status: "completed", scenes_count: Math.floor(Math.random() * 10) + 5 }
            : ch
        )
      );

      toast({
        title: "章节生成完成",
        description: `第${chapter.number}章 "${chapter.title}" 已生成`,
        variant: "success",
      });

      if (autoGenerate && chapterIndex < totalCount - 1) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        await generateChapter(chapterIndex + 1);
      } else {
        setCurrentChapterIndex(-1);
        if (chapterIndex === totalCount - 1) {
          setGeneratingAll(false);
          onComplete?.(generatedChapters);
        }
      }
    } catch (error) {
      setGeneratedChapters((prev) =>
        prev.map((ch, idx) =>
          idx === chapterIndex
            ? { ...ch, status: "failed", error: "生成失败" }
            : ch
        )
      );

      toast({
        title: "章节生成失败",
        description: `第${chapter.number}章生成失败`,
        variant: "error",
      });

      if (autoGenerate) {
        setGeneratingAll(false);
        setCurrentChapterIndex(-1);
      }
    }
  };

  const generateAll = async () => {
    setGeneratingAll(true);
    await generateChapter(0);
  };

  const regenerateChapter = async (chapterIndex: number) => {
    setGeneratedChapters((prev) =>
      prev.map((ch, idx) =>
        idx === chapterIndex ? { ...ch, status: "pending", error: undefined } : ch
      )
    );
    await generateChapter(chapterIndex);
  };

  const getStatusIcon = (status: Chapter["status"], index: number) => {
    if (status === "generating" && currentChapterIndex === index) {
      return <Loader2 className="w-4 h-4 animate-spin text-violet-400" />;
    }
    if (status === "completed") {
      return <Check className="w-4 h-4 text-green-400" />;
    }
    if (status === "failed") {
      return <RotateCcw className="w-4 h-4 text-red-400" />;
    }
    if (currentChapterIndex === index) {
      return <Play className="w-4 h-4 text-violet-400" />;
    }
    return <div className="w-4 h-4 rounded-full border border-white/20" />;
  };

  const getStatusColor = (status: Chapter["status"]) => {
    switch (status) {
      case "completed":
        return "text-green-400";
      case "generating":
        return "text-violet-400";
      case "failed":
        return "text-red-400";
      default:
        return "text-white/40";
    }
  };

  return (
    <Card className="w-full">
      <CardHeader className="border-b border-white/10">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Layers className="w-5 h-5 text-violet-400" />
            分章节生成剧本
          </CardTitle>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-white/60 cursor-pointer">
              <input
                type="checkbox"
                checked={autoGenerate}
                onChange={(e) => setAutoGenerate(e.target.checked)}
                className="w-4 h-4 rounded border-white/20 bg-white/5 text-violet-500"
              />
              自动连续生成
            </label>
            <Badge variant="outline" className="text-green-400 border-green-500/30">
              {completedCount}/{totalCount} 完成
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-6">
        <div className="space-y-4">
          {generatedChapters.map((chapter, index) => (
            <div
              key={chapter.id}
              className={cn(
                "flex items-center gap-4 p-4 rounded-lg border transition-all",
                chapter.status === "generating" && currentChapterIndex === index
                  ? "border-violet-500/50 bg-violet-500/5"
                  : chapter.status === "completed"
                  ? "border-green-500/20 bg-green-500/5"
                  : chapter.status === "failed"
                  ? "border-red-500/20 bg-red-500/5"
                  : "border-white/10 bg-white/5"
              )}
            >
              <div className="flex items-center justify-center w-8">
                {getStatusIcon(chapter.status, index)}
              </div>

              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-white/60 text-sm">第{chapter.number}章</span>
                  <span className="font-medium">{chapter.title}</span>
                </div>
                {chapter.status === "completed" && chapter.scenes_count && (
                  <p className="text-xs text-white/40 mt-1">
                    已生成 {chapter.scenes_count} 个场景
                  </p>
                )}
                {chapter.status === "failed" && chapter.error && (
                  <p className="text-xs text-red-400 mt-1">{chapter.error}</p>
                )}
              </div>

              <div className="flex items-center gap-2">
                {chapter.status === "pending" && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => generateChapter(index)}
                    disabled={generatingAll}
                  >
                    <Sparkles className="w-4 h-4 mr-1" />
                    生成
                  </Button>
                )}
                {chapter.status === "failed" && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => regenerateChapter(index)}
                  >
                    <RotateCcw className="w-4 h-4 mr-1" />
                    重试
                  </Button>
                )}
                {chapter.status === "completed" && (
                  <Button size="sm" variant="ghost">
                    <FileText className="w-4 h-4 mr-1" />
                    查看
                  </Button>
                )}
                {chapter.status === "generating" && currentChapterIndex === index && (
                  <div className="flex items-center gap-2 text-sm text-violet-400">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    生成中...
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="flex justify-between items-center mt-6 pt-6 border-t border-white/10">
          <div className="text-sm text-white/60">
            <Clock className="w-4 h-4 inline mr-1" />
            预计时间: 约 {Math.ceil(totalCount * 2)} 分钟
          </div>
          <Button
            onClick={generateAll}
            disabled={generatingAll || completedCount === totalCount}
            className="min-w-[140px]"
          >
            {generatingAll ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                生成中...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 mr-2" />
                全部生成
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default ChapterGenerator;
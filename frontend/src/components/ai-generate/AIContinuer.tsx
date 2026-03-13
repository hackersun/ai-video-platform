"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/toaster";
import {
  Wand2,
  Sparkles,
  Loader2,
  Send,
  Zap,
  MessageSquare,
  ArrowRight,
  BookOpen,
  RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface Scene {
  id: string;
  title: string;
  content: string;
  scene_number: number;
}

interface AIContinuerProps {
  scriptId: string;
  scenes: Scene[];
  onContinue: (prompt: string, context: string) => Promise<string>;
  onInsert?: (content: string, afterSceneId: string) => void;
}

const CONTINUE_TEMPLATES = [
  {
    id: "extend",
    label: "扩展剧情",
    icon: ArrowRight,
    description: "在现有情节基础上扩展更多内容",
    prompt: "请根据当前剧情继续发展，添加更多细节和情节",
  },
  {
    id: "dialogue",
    label: "添加对话",
    icon: MessageSquare,
    description: "为当前场景添加角色对话",
    prompt: "请为当前场景添加角色之间的对话",
  },
  {
    id: "action",
    label: "添加动作",
    icon: Zap,
    description: "添加动作描写和场景转换",
    prompt: "请添加动作描写和场景转换描述",
  },
  {
    id: "ending",
    label: "完善结局",
    icon: BookOpen,
    description: "为当前章节添加结尾",
    prompt: "请为当前内容添加一个合适的结尾",
  },
];

export function AIContinuer({
  scriptId,
  scenes,
  onContinue,
  onInsert,
}: AIContinuerProps) {
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(
    scenes.length > 0 ? scenes[scenes.length - 1].id : null
  );
  const [customPrompt, setCustomPrompt] = useState("");
  const [continuing, setContinuing] = useState(false);
  const [generatedContent, setGeneratedContent] = useState<string>("");
  const [continuationHistory, setContinuationHistory] = useState<
    Array<{ prompt: string; content: string; timestamp: Date }>
  >([]);

  const selectedScene = scenes.find((s) => s.id === selectedSceneId);

  const handleQuickContinue = async (templateId: string) => {
    const template = CONTINUE_TEMPLATES.find((t) => t.id === templateId);
    if (!template || !selectedScene) return;

    await generateContent(template.prompt);
  };

  const handleCustomContinue = async () => {
    if (!customPrompt.trim() || !selectedScene) return;
    await generateContent(customPrompt);
  };

  const generateContent = async (prompt: string) => {
    if (!selectedScene) {
      toast({
        title: "请先选择场景",
        description: "请选择一个场景作为续写的上下文",
        variant: "error",
      });
      return;
    }

    setContinuing(true);
    setGeneratedContent("");

    try {
      const context = `当前场景: ${selectedScene.title}\n\n${selectedScene.content}`;
      const result = await onContinue(prompt, context);
      setGeneratedContent(result);
      setContinuationHistory((prev) => [
        ...prev,
        { prompt, content: result, timestamp: new Date() },
      ]);
      toast({
        title: "续写完成",
        description: "AI已生成续写内容",
        variant: "success",
      });
    } catch (error) {
      toast({
        title: "续写失败",
        description: "无法生成续写内容，请重试",
        variant: "error",
      });
    } finally {
      setContinuing(false);
    }
  };

  const handleInsertContent = () => {
    if (generatedContent && selectedSceneId && onInsert) {
      onInsert(generatedContent, selectedSceneId);
      setGeneratedContent("");
      toast({
        title: "已插入内容",
        description: "续写内容已添加到剧本中",
        variant: "success",
      });
    }
  };

  return (
    <Card className="w-full">
      <CardHeader className="border-b border-white/10">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Wand2 className="w-5 h-5 text-violet-400" />
          AI续写
        </CardTitle>
      </CardHeader>
      <CardContent className="p-6">
        <div className="grid grid-cols-3 gap-6">
          <div className="col-span-2 space-y-4">
            <div className="space-y-2">
              <label className="text-sm text-white/60">选择续写上下文场景</label>
              <div className="flex flex-wrap gap-2">
                {scenes.map((scene) => (
                  <button
                    key={scene.id}
                    onClick={() => setSelectedSceneId(scene.id)}
                    className={cn(
                      "px-3 py-2 rounded-lg border text-sm transition-all",
                      selectedSceneId === scene.id
                        ? "border-violet-500 bg-violet-500/10 text-violet-400"
                        : "border-white/10 hover:border-white/20"
                    )}
                  >
                    场景{scene.scene_number}: {scene.title}
                  </button>
                ))}
              </div>
            </div>

            {selectedScene && (
              <div className="p-4 rounded-lg bg-white/5 border border-white/10">
                <h4 className="font-medium mb-2">{selectedScene.title}</h4>
                <p className="text-sm text-white/60 line-clamp-4">
                  {selectedScene.content}
                </p>
              </div>
            )}

            <div className="space-y-3 pt-4">
              <label className="text-sm text-white/60">快速续写模板</label>
              <div className="grid grid-cols-2 gap-3">
                {CONTINUE_TEMPLATES.map((template) => (
                  <button
                    key={template.id}
                    onClick={() => handleQuickContinue(template.id)}
                    disabled={continuing || !selectedScene}
                    className="p-4 rounded-lg border border-white/10 hover:border-violet-500/50 hover:bg-violet-500/5 transition-all text-left disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <template.icon className="w-4 h-4 text-violet-400" />
                      <span className="font-medium">{template.label}</span>
                    </div>
                    <p className="text-xs text-white/40">{template.description}</p>
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2 pt-4">
              <label className="text-sm text-white/60">自定义提示词</label>
              <div className="flex gap-2">
                <Textarea
                  placeholder="描述您希望AI如何续写..."
                  value={customPrompt}
                  onChange={(e) => setCustomPrompt(e.target.value)}
                  className="flex-1 h-20 resize-none"
                  disabled={continuing}
                />
                <Button
                  onClick={handleCustomContinue}
                  disabled={continuing || !customPrompt.trim() || !selectedScene}
                  className="shrink-0"
                >
                  {continuing ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Send className="w-4 h-4" />
                  )}
                </Button>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="font-medium">生成结果</h4>
              {continuationHistory.length > 0 && (
                <Badge variant="outline" className="text-xs">
                  {continuationHistory.length} 条记录
                </Badge>
              )}
            </div>

            {continuing && (
              <div className="flex items-center gap-2 p-4 rounded-lg bg-violet-500/10 border border-violet-500/20">
                <Loader2 className="w-5 h-5 text-violet-400 animate-spin" />
                <span className="text-violet-400">AI正在续写中...</span>
              </div>
            )}

            {generatedContent && !continuing && (
              <div className="space-y-3">
                <div className="p-4 rounded-lg bg-white/5 border border-white/10">
                  <pre className="text-sm text-white/80 whitespace-pre-wrap font-sans">
                    {generatedContent}
                  </pre>
                </div>
                <div className="flex gap-2">
                  <Button
                    className="flex-1"
                    onClick={() => generateContent(customPrompt || "继续")}
                    disabled={continuing}
                  >
                    <RefreshCw className="w-4 h-4 mr-2" />
                    重新生成
                  </Button>
                  <Button
                    variant="outline"
                    className="flex-1"
                    onClick={handleInsertContent}
                    disabled={!onInsert}
                  >
                    <Sparkles className="w-4 h-4 mr-2" />
                    插入剧本
                  </Button>
                </div>
              </div>
            )}

            {!generatedContent && !continuing && (
              <div className="text-center py-12 text-white/40">
                <Sparkles className="w-8 h-8 mx-auto mb-3 opacity-50" />
                <p className="text-sm">选择场景并输入提示词开始续写</p>
              </div>
            )}

            {continuationHistory.length > 0 && (
              <div className="space-y-2 pt-4 border-t border-white/10">
                <h5 className="text-xs text-white/40 uppercase tracking-wider">
                  续写历史
                </h5>
                <div className="max-h-40 overflow-y-auto space-y-2">
                  {continuationHistory
                    .slice()
                    .reverse()
                    .map((item, index) => (
                      <button
                        key={index}
                        onClick={() => setGeneratedContent(item.content)}
                        className="w-full p-2 rounded-lg border border-white/10 hover:border-white/20 text-left transition-colors"
                      >
                        <p className="text-xs text-white/60 truncate">
                          {item.prompt}
                        </p>
                        <p className="text-xs text-white/40 mt-1">
                          {item.timestamp.toLocaleTimeString()}
                        </p>
                      </button>
                    ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default AIContinuer;
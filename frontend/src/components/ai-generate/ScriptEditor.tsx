"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/toaster";
import { scriptApi } from "@/lib/api";
import {
  Edit3,
  Save,
  RefreshCw,
  Sparkles,
  Undo,
  Redo,
  Eye,
  EyeOff,
  Copy,
  Check,
  Search,
  AlignLeft,
  MessageSquare,
  Film,
  Camera,
  Clock,
  User,
  X,
  Plus,
  GripVertical,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface Scene {
  id: string;
  title: string;
  content: string;
  scene_number: number;
  description?: string;
  location?: string;
  time_of_day?: string;
  characters?: string[];
  dialogue?: Record<string, string>;
  action_description?: string;
  camera_direction?: string;
}

interface ScriptEditorProps {
  scriptId: string;
  initialScenes: Scene[];
  onSave?: (scenes: Scene[]) => void;
  onAutoSave?: (scenes: Scene[]) => void;
}

const SCENE_TEMPLATES = {
  standard: {
    label: "标准格式",
    content: `【场景标题】

【内/外景】地点-时间

[画面描述]
[动作描述]
[对白]
`,
  },
  detailed: {
    label: "详细格式",
    content: `【场景标题】

【内/外景】地点-时间

【画面描述】
[详细描述场景画面]

【角色】
[登场角色]

【动作】
[角色的动作和行为]

【对话】
角色A: "对话内容"
角色B: "对话内容"

【摄像机】
[摄像机角度和运动建议]
`,
  },
  simple: {
    label: "简洁格式",
    content: `场景标题
地点，时间
对话内容
`,
  },
};

export function ScriptEditor({
  scriptId,
  initialScenes,
  onSave,
  onAutoSave,
}: ScriptEditorProps) {
  const [scenes, setScenes] = useState<Scene[]>(initialScenes);
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(
    initialScenes.length > 0 ? initialScenes[0].id : null
  );
  const [editedContent, setEditedContent] = useState<Record<string, string>>({});
  const [showPreview, setShowPreview] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    description: true,
    dialogue: true,
    camera: true,
  });

  const selectedScene = scenes.find((s) => s.id === selectedSceneId);

  useEffect(() => {
    const initialContent: Record<string, string> = {};
    initialScenes.forEach((scene) => {
      initialContent[scene.id] = scene.content;
    });
    setEditedContent(initialContent);
  }, [initialScenes]);

  useEffect(() => {
    if (!hasChanges) return;

    const timer = setTimeout(() => {
      const currentContent = editedContent[selectedSceneId || ""];
      if (currentContent !== undefined) {
        onAutoSave?.(scenes);
      }
    }, 2000);

    return () => clearTimeout(timer);
  }, [editedContent, hasChanges, scenes, selectedSceneId, onAutoSave]);

  const handleContentChange = (sceneId: string, content: string) => {
    setEditedContent((prev) => ({ ...prev, [sceneId]: content }));
    setHasChanges(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const updatedScenes = scenes.map((scene) => ({
        ...scene,
        content: editedContent[scene.id] || scene.content,
      }));

      for (const scene of updatedScenes) {
        await scriptApi.updateScene(scriptId, scene.id, {
          content: scene.content,
        });
      }

      setScenes(updatedScenes);
      setHasChanges(false);
      onSave?.(updatedScenes);

      toast({
        title: "保存成功",
        description: "剧本内容已保存",
        variant: "success",
      });
    } catch (error) {
      toast({
        title: "保存失败",
        description: "无法保存剧本内容",
        variant: "error",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleRevert = (sceneId: string) => {
    const originalScene = initialScenes.find((s) => s.id === sceneId);
    if (originalScene) {
      setEditedContent((prev) => ({
        ...prev,
        [sceneId]: originalScene.content,
      }));
    }
  };

  const handleCopy = async (content: string, id: string) => {
    await navigator.clipboard.writeText(content);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const addNewScene = () => {
    const newSceneNumber = scenes.length + 1;
    const newScene: Scene = {
      id: `new-${Date.now()}`,
      title: `新场景 ${newSceneNumber}`,
      content: SCENE_TEMPLATES.standard.content,
      scene_number: newSceneNumber,
    };
    setScenes([...scenes, newScene]);
    setEditedContent((prev) => ({ ...prev, [newScene.id]: newScene.content }));
    setSelectedSceneId(newScene.id);
  };

  const deleteScene = async (sceneId: string) => {
    try {
      await scriptApi.deleteScene(scriptId, sceneId);
      setScenes(scenes.filter((s) => s.id !== sceneId));
      setEditedContent((prev) => {
        const newContent = { ...prev };
        delete newContent[sceneId];
        return newContent;
      });
      if (selectedSceneId === sceneId) {
        setSelectedSceneId(scenes[0]?.id || null);
      }
    } catch (error) {
      toast({
        title: "删除失败",
        description: "无法删除场景",
        variant: "error",
      });
    }
  };

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const applyTemplate = (template: keyof typeof SCENE_TEMPLATES) => {
    if (selectedSceneId) {
      handleContentChange(
        selectedSceneId,
        SCENE_TEMPLATES[template].content
      );
    }
  };

  return (
    <Card className="w-full">
      <CardHeader className="border-b border-white/10">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Edit3 className="w-5 h-5 text-green-400" />
            剧本编辑器
          </CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className={hasChanges ? "text-yellow-400" : "text-green-400"}>
              {hasChanges ? "未保存" : "已保存"}
            </Badge>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setShowPreview(!showPreview)}
            >
              {showPreview ? (
                <>
                  <EyeOff className="w-4 h-4 mr-1" />
                  隐藏预览
                </>
              ) : (
                <>
                  <Eye className="w-4 h-4 mr-1" />
                  显示预览
                </>
              )}
            </Button>
            <Button
              size="sm"
              onClick={handleSave}
              disabled={saving || !hasChanges}
            >
              {saving ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4 mr-1" />
              )}
              保存
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div className="flex h-[600px]">
          <div className="w-64 border-r border-white/10 bg-white/5 overflow-y-auto">
            <div className="p-4 border-b border-white/10">
              <div className="flex items-center justify-between mb-3">
                <h4 className="font-medium text-sm">场景列表</h4>
                <Button size="sm" variant="ghost" onClick={addNewScene}>
                  <Plus className="w-4 h-4" />
                </Button>
              </div>
              <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-white/40" />
                <input
                  placeholder="搜索场景..."
                  className="w-full pl-9 pr-3 py-2 rounded-lg border border-white/10 bg-white/5 text-sm focus:outline-none focus:border-violet-500"
                />
              </div>
            </div>
            <div className="p-2">
              {scenes.map((scene) => (
                <button
                  key={scene.id}
                  onClick={() => setSelectedSceneId(scene.id)}
                  className={cn(
                    "w-full p-3 rounded-lg text-left transition-all mb-1",
                    selectedSceneId === scene.id
                      ? "bg-violet-500/10 border border-violet-500/50"
                      : "hover:bg-white/5 border border-transparent"
                  )}
                >
                  <div className="flex items-center gap-2">
                    <GripVertical className="w-4 h-4 text-white/20" />
                    <span className="text-sm font-medium">
                      {scene.scene_number}. {scene.title}
                    </span>
                  </div>
                  {scene.location && (
                    <p className="text-xs text-white/40 mt-1 ml-6">
                      {scene.location}
                    </p>
                  )}
                </button>
              ))}
            </div>
          </div>

          <div className="flex-1 flex flex-col overflow-hidden">
            {selectedScene && (
              <>
                <div className="p-4 border-b border-white/10 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <h3 className="font-medium">{selectedScene.title}</h3>
                    <Badge variant="outline" className="text-xs">
                      场景 {selectedScene.scene_number}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleRevert(selectedScene.id)}
                      disabled={!hasChanges}
                    >
                      <Undo className="w-4 h-4 mr-1" />
                      撤销
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() =>
                        handleCopy(
                          editedContent[selectedScene.id] || selectedScene.content,
                          selectedScene.id
                        )
                      }
                    >
                      {copiedId === selectedScene.id ? (
                        <Check className="w-4 h-4" />
                      ) : (
                        <Copy className="w-4 h-4" />
                      )}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-red-400 hover:text-red-300"
                      onClick={() => deleteScene(selectedScene.id)}
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  </div>
                </div>

                <div className="flex items-center gap-2 px-4 py-2 border-b border-white/10 bg-white/5">
                  <span className="text-xs text-white/60">应用模板:</span>
                  {Object.entries(SCENE_TEMPLATES).map(([key, template]) => (
                    <button
                      key={key}
                      onClick={() => applyTemplate(key as keyof typeof SCENE_TEMPLATES)}
                      className="px-2 py-1 text-xs rounded border border-white/10 hover:border-white/30 transition-colors"
                    >
                      {template.label}
                    </button>
                  ))}
                </div>

                <div className="flex-1 flex overflow-hidden">
                  <div className="flex-1 p-4 overflow-y-auto">
                    <Textarea
                      value={editedContent[selectedScene.id] || ""}
                      onChange={(e) =>
                        handleContentChange(selectedScene.id, e.target.value)
                      }
                      className="w-full h-full min-h-[400px] font-mono text-sm resize-none bg-transparent border-0 focus:ring-0"
                      placeholder="输入剧本内容..."
                    />
                  </div>

                  {showPreview && (
                    <div className="w-96 border-l border-white/10 bg-white/[0.02] overflow-y-auto p-4">
                      <h4 className="font-medium mb-4 flex items-center gap-2">
                        <Eye className="w-4 h-4" />
                        预览
                      </h4>

                      <div className="space-y-4">
                        <div className="space-y-2">
                          <button
                            onClick={() => toggleSection("description")}
                            className="flex items-center gap-2 text-sm text-white/60 hover:text-white"
                          >
                            {expandedSections.description ? (
                              <ChevronDown className="w-4 h-4" />
                            ) : (
                              <ChevronRight className="w-4 h-4" />
                            )}
                            <AlignLeft className="w-4 h-4" />
                            场景信息
                          </button>
                          {expandedSections.description && (
                            <div className="pl-6 space-y-2 text-sm">
                              <div>
                                <span className="text-white/40">位置:</span>
                                <input
                                  value={selectedScene.location || ""}
                                  onChange={() => {}}
                                  className="ml-2 bg-transparent border-b border-white/10 focus:border-violet-500 outline-none"
                                  placeholder="未设置"
                                />
                              </div>
                              <div>
                                <span className="text-white/40">时间:</span>
                                <input
                                  value={selectedScene.time_of_day || ""}
                                  onChange={() => {}}
                                  className="ml-2 bg-transparent border-b border-white/10 focus:border-violet-500 outline-none"
                                  placeholder="未设置"
                                />
                              </div>
                              <div>
                                <span className="text-white/40">描述:</span>
                                <p className="text-white/80 mt-1">
                                  {selectedScene.description || "暂无描述"}
                                </p>
                              </div>
                            </div>
                          )}
                        </div>

                        <div className="space-y-2">
                          <button
                            onClick={() => toggleSection("dialogue")}
                            className="flex items-center gap-2 text-sm text-white/60 hover:text-white"
                          >
                            {expandedSections.dialogue ? (
                              <ChevronDown className="w-4 h-4" />
                            ) : (
                              <ChevronRight className="w-4 h-4" />
                            )}
                            <MessageSquare className="w-4 h-4" />
                            对话
                          </button>
                          {expandedSections.dialogue && (
                            <div className="pl-6 space-y-2 text-sm">
                              {selectedScene.characters?.length ? (
                                selectedScene.characters.map((char) => (
                                  <div key={char} className="flex items-center gap-2">
                                    <User className="w-3 h-3 text-white/40" />
                                    <span>{char}</span>
                                  </div>
                                ))
                              ) : (
                                <p className="text-white/40">暂无角色</p>
                              )}
                            </div>
                          )}
                        </div>

                        <div className="space-y-2">
                          <button
                            onClick={() => toggleSection("camera")}
                            className="flex items-center gap-2 text-sm text-white/60 hover:text-white"
                          >
                            {expandedSections.camera ? (
                              <ChevronDown className="w-4 h-4" />
                            ) : (
                              <ChevronRight className="w-4 h-4" />
                            )}
                            <Camera className="w-4 h-4" />
                            摄像机
                          </button>
                          {expandedSections.camera && (
                            <div className="pl-6 text-sm">
                              <p className="text-white/80">
                                {selectedScene.camera_direction || "未设置摄像机方向"}
                              </p>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default ScriptEditor;
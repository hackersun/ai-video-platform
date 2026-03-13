"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Wand2,
  Sparkles,
  Film,
  Clock,
  Layers,
  Zap,
  Settings2,
  ChevronDown,
  Check,
} from "lucide-react";
import { cn } from "@/lib/utils";

export interface GenerateConfig {
  // 风格设置
  style: "realistic" | "anime" | "cinematic" | "documentary" | "fantasy";
  tone: "serious" | "humorous" | "romantic" | "thriller" | "action";
  
  // 节奏设置
  pacing: "fast" | "medium" | "slow";
  intensity: number; // 1-10
  
  // 场景设置
  sceneCount: number;
  scenesPerChapter: number;
  
  // 输出设置
  language: "zh-CN" | "en-US" | "ja-JP";
  format: "standard" | "detailed" | "simple";
  
  // 高级选项
  includeCameraAngles: boolean;
  includeActionDescription: boolean;
  includeDialogue: boolean;
  customPrompt?: string;
}

interface GenerateConfigPanelProps {
  onGenerate: (config: GenerateConfig) => void;
  loading?: boolean;
  disabled?: boolean;
}

const STYLE_OPTIONS = [
  { value: "realistic", label: "写实", icon: Film },
  { value: "anime", label: "动漫", icon: Sparkles },
  { value: "cinematic", label: "电影感", icon: Film },
  { value: "documentary", label: "纪录片", icon: Film },
  { value: "fantasy", label: "奇幻", icon: Sparkles },
];

const TONE_OPTIONS = [
  { value: "serious", label: "严肃" },
  { value: "humorous", label: "幽默" },
  { value: "romantic", label: "浪漫" },
  { value: "thriller", label: "惊悚" },
  { value: "action", label: "动作" },
];

const PACING_OPTIONS = [
  { value: "fast", label: "快节奏", description: "紧张刺激，场景快速切换" },
  { value: "medium", label: "中节奏", description: "平衡叙事，张弛有度" },
  { value: "slow", label: "慢节奏", description: "细腻描写，注重氛围" },
];

const LANGUAGE_OPTIONS = [
  { value: "zh-CN", label: "简体中文" },
  { value: "en-US", label: "English" },
  { value: "ja-JP", label: "日本語" },
];

const FORMAT_OPTIONS = [
  { value: "standard", label: "标准格式", description: "包含场景、对白、动作描述" },
  { value: "detailed", label: "详细格式", description: "包含摄像机角度、灯光、特效说明" },
  { value: "simple", label: "简洁格式", description: "仅包含场景和主要对话" },
];

export function GenerateConfigPanel({
  onGenerate,
  loading = false,
  disabled = false,
}: GenerateConfigPanelProps) {
  const [expandedSection, setExpandedSection] = useState<string>("style");
  
  const [config, setConfig] = useState<GenerateConfig>({
    style: "cinematic",
    tone: "serious",
    pacing: "medium",
    intensity: 5,
    sceneCount: 10,
    scenesPerChapter: 3,
    language: "zh-CN",
    format: "standard",
    includeCameraAngles: true,
    includeActionDescription: true,
    includeDialogue: true,
  });

  const updateConfig = <K extends keyof GenerateConfig>(
    key: K,
    value: GenerateConfig[K]
  ) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = () => {
    onGenerate(config);
  };

  return (
    <Card className="w-full">
      <CardHeader className="border-b border-white/10">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Settings2 className="w-5 h-5 text-violet-400" />
          生成参数配置
        </CardTitle>
      </CardHeader>
      <CardContent className="p-6 space-y-6">
        {/* 风格设置 */}
        <section className="space-y-4">
          <button
            onClick={() => setExpandedSection(expandedSection === "style" ? "" : "style")}
            className="flex items-center justify-between w-full text-left"
          >
            <h3 className="font-medium flex items-center gap-2">
              <Wand2 className="w-4 h-4 text-violet-400" />
              风格设置
            </h3>
            <span className="text-white/40 text-sm">
              {expandedSection === "style" ? "收起" : "展开"}
            </span>
          </button>
          
          {expandedSection === "style" && (
            <div className="grid grid-cols-2 gap-4 pt-2">
              <div className="space-y-2">
                <label className="text-sm text-white/60">视觉风格</label>
                <div className="grid grid-cols-3 gap-2">
                  {STYLE_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      onClick={() => updateConfig("style", option.value as GenerateConfig["style"])}
                      className={cn(
                        "p-3 rounded-lg border transition-all flex flex-col items-center gap-1",
                        config.style === option.value
                          ? "border-violet-500 bg-violet-500/10 text-violet-400"
                          : "border-white/10 hover:border-white/20"
                      )}
                    >
                      <option.icon className="w-5 h-5" />
                      <span className="text-xs">{option.label}</span>
                    </button>
                  ))}
                </div>
              </div>
              
              <div className="space-y-2">
                <label className="text-sm text-white/60">叙事风格</label>
                <div className="grid grid-cols-3 gap-2">
                  {TONE_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      onClick={() => updateConfig("tone", option.value as GenerateConfig["tone"])}
                      className={cn(
                        "p-3 rounded-lg border transition-all",
                        config.tone === option.value
                          ? "border-violet-500 bg-violet-500/10 text-violet-400"
                          : "border-white/10 hover:border-white/20"
                      )}
                    >
                      <span className="text-xs">{option.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </section>

        {/* 节奏设置 */}
        <section className="space-y-4">
          <button
            onClick={() => setExpandedSection(expandedSection === "pacing" ? "" : "pacing")}
            className="flex items-center justify-between w-full text-left"
          >
            <h3 className="font-medium flex items-center gap-2">
              <Clock className="w-4 h-4 text-blue-400" />
              节奏设置
            </h3>
            <span className="text-white/40 text-sm">
              {expandedSection === "pacing" ? "收起" : "展开"}
            </span>
          </button>
          
          {expandedSection === "pacing" && (
            <div className="grid grid-cols-3 gap-4 pt-2">
              {PACING_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  onClick={() => updateConfig("pacing", option.value as GenerateConfig["pacing"])}
                  className={cn(
                    "p-4 rounded-lg border transition-all text-left",
                    config.pacing === option.value
                      ? "border-blue-500 bg-blue-500/10"
                      : "border-white/10 hover:border-white/20"
                  )}
                >
                  <p className={cn(
                    "font-medium",
                    config.pacing === option.value ? "text-blue-400" : ""
                  )}>
                    {option.label}
                  </p>
                  <p className="text-xs text-white/40 mt-1">{option.description}</p>
                </button>
              ))}
            </div>
          )}
          
          {expandedSection === "pacing" && (
            <div className="pt-4 space-y-3">
              <div className="flex justify-between">
                <label className="text-sm text-white/60">激烈程度</label>
                <span className="text-sm text-violet-400">{config.intensity}/10</span>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-xs text-white/40">平和</span>
                <input
                  type="range"
                  min="1"
                  max="10"
                  value={config.intensity}
                  onChange={(e) => updateConfig("intensity", parseInt(e.target.value))}
                  className="flex-1 h-2 bg-white/10 rounded-full appearance-none cursor-pointer
                    [&::-webkit-slider-thumb]:appearance-none
                    [&::-webkit-slider-thumb]:w-4
                    [&::-webkit-slider-thumb]:h-4
                    [&::-webkit-slider-thumb]:rounded-full
                    [&::-webkit-slider-thumb]:bg-violet-500
                    [&::-webkit-slider-thumb]:cursor-pointer"
                />
                <span className="text-xs text-white/40">激烈</span>
              </div>
            </div>
          )}
        </section>

        {/* 场景设置 */}
        <section className="space-y-4">
          <button
            onClick={() => setExpandedSection(expandedSection === "scenes" ? "" : "scenes")}
            className="flex items-center justify-between w-full text-left"
          >
            <h3 className="font-medium flex items-center gap-2">
              <Layers className="w-4 h-4 text-green-400" />
              场景设置
            </h3>
            <span className="text-white/40 text-sm">
              {expandedSection === "scenes" ? "收起" : "展开"}
            </span>
          </button>
          
          {expandedSection === "scenes" && (
            <div className="grid grid-cols-2 gap-6 pt-2">
              <div className="space-y-3">
                <div className="flex justify-between">
                  <label className="text-sm text-white/60">总场景数</label>
                  <span className="text-sm text-green-400">{config.sceneCount} 个</span>
                </div>
                <input
                  type="range"
                  min="3"
                  max="50"
                  value={config.sceneCount}
                  onChange={(e) => updateConfig("sceneCount", parseInt(e.target.value))}
                  className="w-full h-2 bg-white/10 rounded-full appearance-none cursor-pointer
                    [&::-webkit-slider-thumb]:appearance-none
                    [&::-webkit-slider-thumb]:w-4
                    [&::-webkit-slider-thumb]:h-4
                    [&::-webkit-slider-thumb]:rounded-full
                    [&::-webkit-slider-thumb]:bg-green-500
                    [&::-webkit-slider-thumb]:cursor-pointer"
                />
              </div>
              
              <div className="space-y-3">
                <div className="flex justify-between">
                  <label className="text-sm text-white/60">每章节场景数</label>
                  <span className="text-sm text-green-400">{config.scenesPerChapter} 个</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="10"
                  value={config.scenesPerChapter}
                  onChange={(e) => updateConfig("scenesPerChapter", parseInt(e.target.value))}
                  className="w-full h-2 bg-white/10 rounded-full appearance-none cursor-pointer
                    [&::-webkit-slider-thumb]:appearance-none
                    [&::-webkit-slider-thumb]:w-4
                    [&::-webkit-slider-thumb]:h-4
                    [&::-webkit-slider-thumb]:rounded-full
                    [&::-webkit-slider-thumb]:bg-green-500
                    [&::-webkit-slider-thumb]:cursor-pointer"
                />
              </div>
            </div>
          )}
        </section>

        {/* 输出设置 */}
        <section className="space-y-4">
          <button
            onClick={() => setExpandedSection(expandedSection === "output" ? "" : "output")}
            className="flex items-center justify-between w-full text-left"
          >
            <h3 className="font-medium flex items-center gap-2">
              <Zap className="w-4 h-4 text-yellow-400" />
              输出设置
            </h3>
            <span className="text-white/40 text-sm">
              {expandedSection === "output" ? "收起" : "展开"}
            </span>
          </button>
          
          {expandedSection === "output" && (
            <div className="space-y-4 pt-2">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm text-white/60">语言</label>
                  <select
                    value={config.language}
                    onChange={(e) => updateConfig("language", e.target.value as GenerateConfig["language"])}
                    className="flex h-10 w-full items-center justify-between rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-white/40 focus:outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {LANGUAGE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
                
                <div className="space-y-2">
                  <label className="text-sm text-white/60">输出格式</label>
                  <select
                    value={config.format}
                    onChange={(e) => updateConfig("format", e.target.value as GenerateConfig["format"])}
                    className="flex h-10 w-full items-center justify-between rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-white/40 focus:outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {FORMAT_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* 高级选项 */}
        <section className="space-y-4">
          <button
            onClick={() => setExpandedSection(expandedSection === "advanced" ? "" : "advanced")}
            className="flex items-center justify-between w-full text-left"
          >
            <h3 className="font-medium flex items-center gap-2">
              <Settings2 className="w-4 h-4 text-orange-400" />
              高级选项
            </h3>
            <span className="text-white/40 text-sm">
              {expandedSection === "advanced" ? "收起" : "展开"}
            </span>
          </button>
          
          {expandedSection === "advanced" && (
            <div className="space-y-4 pt-2">
              <div className="space-y-3">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={config.includeCameraAngles}
                    onChange={(e) => updateConfig("includeCameraAngles", e.target.checked)}
                    className="w-4 h-4 rounded border-white/20 bg-white/5 text-violet-500 focus:ring-violet-500"
                  />
                  <span className="text-sm">包含摄像机角度说明</span>
                </label>
                
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={config.includeActionDescription}
                    onChange={(e) => updateConfig("includeActionDescription", e.target.checked)}
                    className="w-4 h-4 rounded border-white/20 bg-white/5 text-violet-500 focus:ring-violet-500"
                  />
                  <span className="text-sm">包含动作描述</span>
                </label>
                
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={config.includeDialogue}
                    onChange={(e) => updateConfig("includeDialogue", e.target.checked)}
                    className="w-4 h-4 rounded border-white/20 bg-white/5 text-violet-500 focus:ring-violet-500"
                  />
                  <span className="text-sm">包含对话内容</span>
                </label>
              </div>
              
              <div className="space-y-2 pt-2">
                <label className="text-sm text-white/60">自定义提示词（可选）</label>
                <Textarea
                  placeholder="添加额外的提示词来引导AI生成更符合您需求的内容..."
                  value={config.customPrompt || ""}
                  onChange={(e) => updateConfig("customPrompt", e.target.value)}
                  className="h-20 resize-none"
                />
              </div>
            </div>
          )}
        </section>

        {/* 提交按钮 */}
        <div className="pt-4 border-t border-white/10">
          <Button
            onClick={handleSubmit}
            disabled={disabled || loading}
            className="w-full"
            size="lg"
          >
            {loading ? (
              <>
                <Sparkles className="w-5 h-5 mr-2 animate-pulse" />
                生成中...
              </>
            ) : (
              <>
                <Wand2 className="w-5 h-5 mr-2" />
                开始AI生成
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default GenerateConfigPanel;
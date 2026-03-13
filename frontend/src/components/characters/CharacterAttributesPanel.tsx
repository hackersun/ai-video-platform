"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "@/components/ui/toaster";
import { cn } from "@/lib/utils";
import {
  User,
  Smile,
  Volume2,
  BookOpen,
  Heart,
  Save,
  Loader2,
  Sparkles,
  Palette,
  Clock,
  Star
} from "lucide-react";

export interface CharacterAttributes {
  // 基本信息
  name: string;
  age?: number;
  gender?: string;
  role?: string; // 主角/配角/反派/客串
  
  // 外貌
  appearance?: string;
  height?: string;
  build?: string; // 体型
  hair?: string;
  eyes?: string;
  distinguishing_features?: string; // 特征
  
  // 性格
  personality?: string;
  strengths?: string;
  weaknesses?: string;
  hobbies?: string;
  habits?: string;
  
  // 声音
  voice?: string;
  voice_description?: string;
  speaking_style?: string;
  
  // 背景
  background?: string;
  occupation?: string;
  family?: string;
  relationships?: string;
  history?: string;
  
  // 目标/动机
  goals?: string;
  motivations?: string;
  fears?: string;
  
  // 其他
  tagline?: string; // 名言
  theme_color?: string; // 主题色
}

interface CharacterAttributesPanelProps {
  characterId: string;
  initialData?: Partial<CharacterAttributes>;
  onSave?: (data: CharacterAttributes) => Promise<void>;
  onAIEnhance?: (field: string, currentValue: string) => Promise<string>;
}

const defaultAttributes: CharacterAttributes = {
  name: "",
  age: undefined,
  gender: "未知",
  role: "配角",
  appearance: "",
  height: "",
  build: "",
  hair: "",
  eyes: "",
  distinguishing_features: "",
  personality: "",
  strengths: "",
  weaknesses: "",
  hobbies: "",
  habits: "",
  voice: "",
  voice_description: "",
  speaking_style: "",
  background: "",
  occupation: "",
  family: "",
  relationships: "",
  history: "",
  goals: "",
  motivations: "",
  fears: "",
  tagline: "",
  theme_color: "#8b5cf6",
};

const tabConfig = [
  { id: "basic", label: "基本信息", icon: User },
  { id: "appearance", label: "外貌", icon: Palette },
  { id: "personality", label: "性格", icon: Smile },
  { id: "voice", label: "声音", icon: Volume2 },
  { id: "background", label: "背景", icon: BookOpen },
  { id: "goals", label: "目标", icon: Star },
];

export function CharacterAttributesPanel({
  characterId,
  initialData,
  onSave,
  onAIEnhance,
}: CharacterAttributesPanelProps) {
  const [activeTab, setActiveTab] = useState("basic");
  const [saving, setSaving] = useState(false);
  const [enhancing, setEnhancing] = useState<string | null>(null);
  const [attributes, setAttributes] = useState<CharacterAttributes>({
    ...defaultAttributes,
    ...initialData,
  });

  useEffect(() => {
    if (initialData) {
      setAttributes({ ...defaultAttributes, ...initialData });
    }
  }, [initialData]);

  const handleChange = (field: keyof CharacterAttributes, value: any) => {
    setAttributes((prev) => ({ ...prev, [field]: value }));
  };

  const handleAIEnhance = async (field: keyof CharacterAttributes) => {
    if (!onAIEnhance) return;
    
    setEnhancing(field);
    try {
      const enhanced = await onAIEnhance(field, attributes[field] as string || "");
      handleChange(field, enhanced);
      toast({
        title: "AI完善完成",
        variant: "success",
      });
    } catch (error) {
      toast({
        title: "AI完善失败",
        variant: "error",
      });
    } finally {
      setEnhancing(null);
    }
  };

  const handleSave = async () => {
    if (!onSave) return;
    
    setSaving(true);
    try {
      await onSave(attributes);
      toast({
        title: "保存成功",
        variant: "success",
      });
    } catch (error) {
      toast({
        title: "保存失败",
        variant: "error",
      });
    } finally {
      setSaving(false);
    }
  };

  const renderField = (
    field: keyof CharacterAttributes,
    label: string,
    type: "text" | "number" | "textarea" | "select" = "text",
    options?: { value: string; label: string }[]
  ) => {
    const isEnhancing = enhancing === field;
    
    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-sm font-medium text-white/80">{label}</label>
          {onAIEnhance && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleAIEnhance(field)}
              disabled={isEnhancing}
              className="h-6 px-2 text-xs text-violet-400 hover:text-violet-300"
            >
              {isEnhancing ? (
                <Loader2 className="w-3 h-3 mr-1 animate-spin" />
              ) : (
                <Sparkles className="w-3 h-3 mr-1" />
              )}
              AI完善
            </Button>
          )}
        </div>
        
        {type === "textarea" ? (
          <textarea
            value={attributes[field] as string || ""}
            onChange={(e) => handleChange(field, e.target.value)}
            className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-white/40 focus:outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 min-h-[80px] resize-none"
            placeholder={`输入${label}...`}
          />
        ) : type === "select" && options ? (
          <select
            value={attributes[field] as string || ""}
            onChange={(e) => handleChange(field, e.target.value)}
            className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white focus:outline-none focus:border-violet-500/50"
          >
            {options.map((opt) => (
              <option key={opt.value} value={opt.value} className="bg-gray-900">
                {opt.label}
              </option>
            ))}
          </select>
        ) : type === "number" ? (
          <Input
            type="number"
            value={attributes[field] as number || ""}
            onChange={(e) => handleChange(field, parseInt(e.target.value) || undefined)}
            placeholder={`输入${label}...`}
          />
        ) : (
          <Input
            value={attributes[field] as string || ""}
            onChange={(e) => handleChange(field, e.target.value)}
            placeholder={`输入${label}...`}
          />
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Tabs */}
      <div className="border-b border-white/10">
        <div className="flex overflow-x-auto">
          {tabConfig.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 whitespace-nowrap",
                  activeTab === tab.id
                    ? "text-violet-400 border-violet-400"
                    : "text-white/60 border-transparent hover:text-white"
                )}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Content */}
      <div className="max-h-[400px] overflow-y-auto space-y-4 pr-2">
        {activeTab === "basic" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {renderField("name", "姓名 *", "text")}
            {renderField("age", "年龄", "number")}
            {renderField(
              "gender",
              "性别",
              "select",
              [
                { value: "未知", label: "未知" },
                { value: "男", label: "男" },
                { value: "女", label: "女" },
                { value: "其他", label: "其他" },
              ]
            )}
            {renderField(
              "role",
              "角色定位",
              "select",
              [
                { value: "主角", label: "主角" },
                { value: "配角", label: "配角" },
                { value: "反派", label: "反派" },
                { value: "客串", label: "客串" },
              ]
            )}
            {renderField("tagline", "名言/口头禅", "textarea")}
            {renderField("theme_color", "主题色", "text")}
          </div>
        )}

        {activeTab === "appearance" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {renderField("appearance", "整体外观", "textarea")}
            {renderField("height", "身高", "text")}
            {renderField("build", "体型", "text")}
            {renderField("hair", "发型", "text")}
            {renderField("eyes", "眼睛", "text")}
            {renderField("distinguishing_features", "显著特征", "textarea")}
          </div>
        )}

        {activeTab === "personality" && (
          <div className="grid grid-cols-1 gap-4">
            {renderField("personality", "性格描述", "textarea")}
            {renderField("strengths", "优点", "textarea")}
            {renderField("weaknesses", "缺点", "textarea")}
            {renderField("hobbies", "爱好", "textarea")}
            {renderField("habits", "习惯/癖好", "textarea")}
          </div>
        )}

        {activeTab === "voice" && (
          <div className="grid grid-cols-1 gap-4">
            {renderField("voice", "声音特点", "text")}
            {renderField("voice_description", "声音描述", "textarea")}
            {renderField("speaking_style", "说话风格", "textarea")}
          </div>
        )}

        {activeTab === "background" && (
          <div className="grid grid-cols-1 gap-4">
            {renderField("background", "背景故事", "textarea")}
            {renderField("occupation", "职业/身份", "text")}
            {renderField("family", "家庭", "textarea")}
            {renderField("relationships", "人际关系", "textarea")}
            {renderField("history", "经历", "textarea")}
          </div>
        )}

        {activeTab === "goals" && (
          <div className="grid grid-cols-1 gap-4">
            {renderField("goals", "目标", "textarea")}
            {renderField("motivations", "动机", "textarea")}
            {renderField("fears", "恐惧", "textarea")}
          </div>
        )}
      </div>

      {/* Save Button */}
      {onSave && (
        <div className="flex justify-end pt-4 border-t border-white/10">
          <Button onClick={handleSave} disabled={saving}>
            {saving ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Save className="w-4 h-4 mr-2" />
            )}
            保存属性
          </Button>
        </div>
      )}
    </div>
  );
}

export default CharacterAttributesPanel;
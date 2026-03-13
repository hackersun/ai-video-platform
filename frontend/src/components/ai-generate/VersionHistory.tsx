"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/toaster";
import {
  History,
  GitCompare,
  Clock,
  User,
  Eye,
  RotateCcw,
  ChevronDown,
  ChevronRight,
  Plus,
  Minus,
  ArrowRight,
  Check,
} from "lucide-react";
import { cn } from "@/lib/utils";

export interface ScriptVersion {
  id: string;
  version: number;
  created_at: string;
  created_by: string;
  description?: string;
  scenes_count: number;
  word_count: number;
  is_current: boolean;
}

interface VersionDiff {
  type: "add" | "remove" | "modify";
  scene_title?: string;
  old_content?: string;
  new_content?: string;
}

interface VersionHistoryProps {
  scriptId: string;
  scriptTitle: string;
  versions: ScriptVersion[];
  onRestore?: (versionId: string) => void;
  onCompare?: (versionA: string, versionB: string) => void;
}

export function VersionHistory({
  scriptId,
  scriptTitle,
  versions,
  onRestore,
  onCompare,
}: VersionHistoryProps) {
  const [selectedVersions, setSelectedVersions] = useState<string[]>([]);
  const [expandedVersion, setExpandedVersion] = useState<string | null>(null);
  const [showDiff, setShowDiff] = useState(false);
  const [restoring, setRestoring] = useState<string | null>(null);

  const handleVersionSelect = (versionId: string) => {
    setSelectedVersions((prev) => {
      if (prev.includes(versionId)) {
        return prev.filter((id) => id !== versionId);
      }
      if (prev.length >= 2) {
        return [prev[1], versionId];
      }
      return [...prev, versionId];
    });
  };

  const handleCompare = () => {
    if (selectedVersions.length === 2) {
      onCompare?.(selectedVersions[0], selectedVersions[1]);
      setShowDiff(true);
    }
  };

  const handleRestore = async (versionId: string) => {
    setRestoring(versionId);
    try {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      onRestore?.(versionId);
      toast({
        title: "版本已恢复",
        description: "当前剧本已恢复到选定版本",
        variant: "success",
      });
    } catch (error) {
      toast({
        title: "恢复失败",
        description: "无法恢复选定版本",
        variant: "error",
      });
    } finally {
      setRestoring(null);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString("zh-CN", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const mockDiffs: VersionDiff[] = [
    {
      type: "modify",
      scene_title: "场景3: 初次相遇",
      old_content: "【内景】咖啡馆-日\n\n主角走进一家古老的咖啡馆...",
      new_content: "【内景】咖啡馆-日\n\n主角推开那扇沉重的木质大门...",
    },
    {
      type: "add",
      scene_title: "场景8: 告白",
      new_content: "【外景】海滩-夜\n\n月光洒在海面上...",
    },
    {
      type: "remove",
      scene_title: "场景12: 分离",
      old_content: "【内景】车站-日\n\n两人在月台告别...",
    },
  ];

  return (
    <Card className="w-full">
      <CardHeader className="border-b border-white/10">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-lg">
            <History className="w-5 h-5 text-blue-400" />
            版本历史
          </CardTitle>
          {selectedVersions.length === 2 && (
            <Button size="sm" onClick={handleCompare}>
              <GitCompare className="w-4 h-4 mr-2" />
              对比版本
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="p-6">
        <div className="space-y-3">
          {versions.map((version, index) => (
            <div
              key={version.id}
              className={cn(
                "rounded-lg border transition-all",
                selectedVersions.includes(version.id)
                  ? "border-violet-500 bg-violet-500/5"
                  : "border-white/10 bg-white/5 hover:border-white/20"
              )}
            >
              <div
                className="flex items-center gap-4 p-4 cursor-pointer"
                onClick={() => handleVersionSelect(version.id)}
              >
                <div className="flex items-center justify-center w-6">
                  {selectedVersions.includes(version.id) ? (
                    <div className="w-5 h-5 rounded-full bg-violet-500 flex items-center justify-center">
                      <Check className="w-3 h-3 text-white" />
                    </div>
                  ) : (
                    <div className="w-5 h-5 rounded-full border border-white/20" />
                  )}
                </div>

                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">V{version.version}</span>
                    {version.is_current && (
                      <Badge className="text-xs bg-green-500/20 text-green-400 border-0">
                        当前版本
                      </Badge>
                    )}
                  </div>
                  <p className="text-sm text-white/60 mt-1">
                    {version.description || `生成了 ${version.scenes_count} 个场景 · ${version.word_count} 字`}
                  </p>
                </div>

                <div className="flex items-center gap-4 text-sm text-white/40">
                  <span className="flex items-center gap-1">
                    <Clock className="w-4 h-4" />
                    {formatDate(version.created_at)}
                  </span>
                  <span className="flex items-center gap-1">
                    <User className="w-4 h-4" />
                    {version.created_by}
                  </span>
                </div>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setExpandedVersion(
                      expandedVersion === version.id ? null : version.id
                    );
                  }}
                  className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                >
                  {expandedVersion === version.id ? (
                    <ChevronDown className="w-4 h-4" />
                  ) : (
                    <ChevronRight className="w-4 h-4" />
                  )}
                </button>
              </div>

              {expandedVersion === version.id && (
                <div className="px-4 pb-4 pt-0 border-t border-white/10 mt-0">
                  <div className="flex justify-end gap-2 pt-4">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {}}
                      disabled={version.is_current}
                    >
                      <Eye className="w-4 h-4 mr-1" />
                      预览
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleRestore(version.id)}
                      disabled={version.is_current || restoring === version.id}
                    >
                      <RotateCcw className="w-4 h-4 mr-1" />
                      {restoring === version.id ? "恢复中..." : "恢复此版本"}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        {showDiff && selectedVersions.length === 2 && (
          <div className="mt-6 pt-6 border-t border-white/10">
            <div className="flex items-center justify-between mb-4">
              <h4 className="font-medium flex items-center gap-2">
                <GitCompare className="w-4 h-4 text-violet-400" />
                版本对比 (V{versions.find(v => v.id === selectedVersions[0])?.version} → V{versions.find(v => v.id === selectedVersions[1])?.version})
              </h4>
              <Button size="sm" variant="ghost" onClick={() => setShowDiff(false)}>
                关闭
              </Button>
            </div>

            <div className="space-y-3">
              {mockDiffs.map((diff, index) => (
                <div
                  key={index}
                  className={cn(
                    "p-4 rounded-lg border",
                    diff.type === "add"
                      ? "border-green-500/30 bg-green-500/5"
                      : diff.type === "remove"
                      ? "border-red-500/30 bg-red-500/5"
                      : "border-yellow-500/30 bg-yellow-500/5"
                  )}
                >
                  <div className="flex items-center gap-2 mb-2">
                    {diff.type === "add" && (
                      <>
                        <Plus className="w-4 h-4 text-green-400" />
                        <span className="text-green-400 text-sm">新增</span>
                      </>
                    )}
                    {diff.type === "remove" && (
                      <>
                        <Minus className="w-4 h-4 text-red-400" />
                        <span className="text-red-400 text-sm">删除</span>
                      </>
                    )}
                    {diff.type === "modify" && (
                      <>
                        <ArrowRight className="w-4 h-4 text-yellow-400" />
                        <span className="text-yellow-400 text-sm">修改</span>
                      </>
                    )}
                    {diff.scene_title && (
                      <span className="text-white/80 font-medium">
                        {diff.scene_title}
                      </span>
                    )}
                  </div>

                  {diff.old_content && (
                    <div className="mt-2">
                      <p className="text-xs text-white/40 mb-1">原始内容:</p>
                      <pre className="text-sm text-white/60 bg-black/20 p-2 rounded overflow-x-auto">
                        {diff.old_content}
                      </pre>
                    </div>
                  )}

                  {diff.new_content && (
                    <div className="mt-2">
                      <p className="text-xs text-white/40 mb-1">新内容:</p>
                      <pre className="text-sm text-white/80 bg-black/20 p-2 rounded overflow-x-auto">
                        {diff.new_content}
                      </pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default VersionHistory;
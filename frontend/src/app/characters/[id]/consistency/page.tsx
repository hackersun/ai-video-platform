"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";
import { Sparkles, CheckCircle, AlertCircle, Loader2 } from "lucide-react";

export default function CharacterConsistencyPage() {
  const params = useParams();
  const characterId = params.id as string;
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [features, setFeatures] = useState<any>(null);
  const [consistencyPrompt, setConsistencyPrompt] = useState("");
  const { toast } = useToast();

  const handleExtractFeatures = async () => {
    if (!description.trim()) {
      toast({
        title: "请输入角色描述",
        variant: "destructive",
      });
      return;
    }

    setLoading(true);
    try {
      const response = await api.post(
        `/api/v1/characters/${characterId}/extract-features`,
        {
          character_id: characterId,
          name: "角色名称", // TODO: 从角色数据获取
          description,
        }
      );

      setFeatures(response.data.extracted_features);
      setConsistencyPrompt(response.data.consistency_prompt);

      toast({
        title: "特征提取成功",
        description: "角色特征已提取并保存",
      });
    } catch (error) {
      toast({
        title: "提取失败",
        description: "请稍后重试",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <Sparkles className="h-8 w-8" />
          角色一致性管理
        </h1>
        <p className="text-muted-foreground mt-2">
          提取角色特征，确保AI生成图像的一致性
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 特征提取 */}
        <Card>
          <CardHeader>
            <CardTitle>特征提取</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Textarea
              placeholder="请输入角色详细描述，包括外貌、服装、风格等特征..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={8}
              className="resize-none"
            />
            <Button
              onClick={handleExtractFeatures}
              disabled={loading || !description.trim()}
              className="w-full"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  提取中...
                </>
              ) : (
                <>
                  <Sparkles className="mr-2 h-4 w-4" />
                  提取特征
                </>
              )}
            </Button>
          </CardContent>
        </Card>

        {/* 提取结果 */}
        {features && (
          <Card>
            <CardHeader>
              <CardTitle>提取结果</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {features.appearance_keywords && (
                <div>
                  <h4 className="font-medium mb-2">外貌特征</h4>
                  <div className="flex flex-wrap gap-2">
                    {features.appearance_keywords.map((keyword: string) => (
                      <span
                        key={keyword}
                        className="px-2 py-1 bg-primary/10 rounded text-sm"
                      >
                        {keyword}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {features.clothing_keywords && (
                <div>
                  <h4 className="font-medium mb-2">服装特征</h4>
                  <div className="flex flex-wrap gap-2">
                    {features.clothing_keywords.map((keyword: string) => (
                      <span
                        key={keyword}
                        className="px-2 py-1 bg-primary/10 rounded text-sm"
                      >
                        {keyword}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {features.style_keywords && (
                <div>
                  <h4 className="font-medium mb-2">风格特征</h4>
                  <div className="flex flex-wrap gap-2">
                    {features.style_keywords.map((keyword: string) => (
                      <span
                        key={keyword}
                        className="px-2 py-1 bg-primary/10 rounded text-sm"
                      >
                        {keyword}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>

      {/* 一致性提示词 */}
      {consistencyPrompt && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle>一致性控制提示词</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="p-4 bg-muted rounded-lg">
              <p className="text-sm font-mono">{consistencyPrompt}</p>
            </div>
            <p className="text-sm text-muted-foreground mt-2">
              此提示词将在生成图像时自动注入，确保角色外观一致性
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

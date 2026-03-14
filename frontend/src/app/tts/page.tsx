"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";
import { Mic, Loader2 } from "lucide-react";
import { MainLayout } from "@/components/layout/main-layout";

export default function TTSPage() {
  const [text, setText] = useState("");
  const [voice, setVoice] = useState("zh-CN-XiaoxiaoNeural");
  const [speed, setSpeed] = useState(1.0);
  const [loading, setLoading] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const { toast } = useToast();

  const handleGenerate = async () => {
    if (!text.trim()) {
      toast({
        title: "请输入文本",
        description: "文本内容不能为空",
        variant: "destructive",
      });
      return;
    }

    setLoading(true);
    try {
      const response = await api.post("/api/v1/tts/generate", {
        text,
        voice,
        speed,
      });

      setAudioUrl(response.data.audio_url);
      toast({
        title: "生成成功",
        description: "语音已生成",
      });
    } catch (error) {
      toast({
        title: "生成失败",
        description: "请稍后重试",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Mic className="w-6 h-6" />
            AI 语音合成
          </h1>
          <p className="text-white/60 mt-1">将文本转换为自然流畅的语音</p>
        </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="text-white">文本输入</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Textarea
              placeholder="请输入要转换为语音的文本..."
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={8}
              className="resize-none bg-white/5 border-white/10 text-white"
            />
            <div className="text-sm text-white/40 text-right">
              {text.length} / 5000 字符
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="text-white">语音设置</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <label className="text-sm text-white/80">选择语音</label>
              <select 
                value={voice} 
                onChange={(e) => setVoice(e.target.value)}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
              >
                <option value="zh-CN-XiaoxiaoNeural">晓晓 - 温柔女声</option>
                <option value="zh-CN-YunxiNeural">云希 - 阳光男声</option>
                <option value="zh-CN-XiaoyiNeural">晓伊 - 甜美女声</option>
                <option value="zh-CN-YunyangNeural">云扬 - 专业男声</option>
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-sm text-white/80">
                语速: {speed.toFixed(1)}x
              </label>
              <input
                type="range"
                min={0.5}
                max={2.0}
                step={0.1}
                value={speed}
                onChange={(e) => setSpeed(parseFloat(e.target.value))}
                className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer accent-violet-500"
              />
              <div className="flex justify-between text-xs text-white/40">
                <span>慢</span>
                <span>正常</span>
                <span>快</span>
              </div>
            </div>

            <Button
              onClick={handleGenerate}
              disabled={loading || !text.trim()}
              className="w-full bg-violet-600 hover:bg-violet-700"
              size="lg"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  生成中...
                </>
              ) : (
                <>
                  <Mic className="mr-2 h-4 w-4" />
                  生成语音
                </>
              )}
            </Button>
          </CardContent>
        </Card>
      </div>

      {audioUrl && (
        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="text-white">生成结果</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <audio controls className="w-full">
              <source src={audioUrl} type="audio/mpeg" />
              您的浏览器不支持音频播放
            </audio>
          </CardContent>
        </Card>
      )}
    </MainLayout>
  );
}
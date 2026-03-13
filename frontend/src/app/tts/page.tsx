"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";
import { Mic, Play, Download, Loader2 } from "lucide-react";

interface Voice {
  id: string;
  name: string;
  gender: string;
  style: string;
}

export default function TTSPage() {
  const [text, setText] = useState("");
  const [voice, setVoice] = useState("zh-CN-XiaoxiaoNeural");
  const [speed, setSpeed] = useState([1.0]);
  const [loading, setLoading] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [voices, setVoices] = useState<Voice[]>([]);
  const { toast } = useToast();

  // 加载语音列表
  useEffect(() => {
    const loadVoices = async () => {
      try {
        const response = await api.get("/api/v1/tts/voices");
        setVoices(response.data);
      } catch (error) {
        console.error("加载语音列表失败:", error);
      }
    };
    loadVoices();
  }, []);

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
        speed: speed[0],
      });

      setAudioUrl(response.data.audio_url);
      toast({
        title: "生成成功",
        description: `语音已生成，时长约 ${Math.ceil(response.data.duration || 0)} 秒`,
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
    <div className="container mx-auto py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <Mic className="h-8 w-8" />
          AI 语音合成
        </h1>
        <p className="text-muted-foreground mt-2">
          将文本转换为自然流畅的语音，支持多种中文语音风格
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 输入区域 */}
        <Card>
          <CardHeader>
            <CardTitle>文本输入</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Textarea
              placeholder="请输入要转换为语音的文本..."
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={8}
              className="resize-none"
            />
            <div className="text-sm text-muted-foreground text-right">
              {text.length} / 5000 字符
            </div>
          </CardContent>
        </Card>

        {/* 设置区域 */}
        <Card>
          <CardHeader>
            <CardTitle>语音设置</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* 语音选择 */}
            <div className="space-y-2">
              <label className="text-sm font-medium">选择语音</label>
              <Select value={voice} onValueChange={setVoice}>
                <SelectTrigger>
                  <SelectValue placeholder="选择语音" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="zh-CN-XiaoxiaoNeural">
                    晓晓 - 温柔女声
                  </SelectItem>
                  <SelectItem value="zh-CN-YunxiNeural">
                    云希 - 阳光男声
                  </SelectItem>
                  <SelectItem value="zh-CN-XiaoyiNeural">
                    晓伊 - 甜美女声
                  </SelectItem>
                  <SelectItem value="zh-CN-YunyangNeural">
                    云扬 - 专业男声
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* 语速调节 */}
            <div className="space-y-2">
              <label className="text-sm font-medium">
                语速: {speed[0].toFixed(1)}x
              </label>
              <Slider
                value={speed}
                onValueChange={setSpeed}
                min={0.5}
                max={2.0}
                step={0.1}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>慢</span>
                <span>正常</span>
                <span>快</span>
              </div>
            </div>

            {/* 生成按钮 */}
            <Button
              onClick={handleGenerate}
              disabled={loading || !text.trim()}
              className="w-full"
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

      {/* 播放区域 */}
      {audioUrl && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle>生成结果</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <audio controls className="w-full">
              <source src={audioUrl} type="audio/mpeg" />
              您的浏览器不支持音频播放
            </audio>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => window.open(audioUrl)}>
                <Play className="mr-2 h-4 w-4" />
                新窗口播放
              </Button>
              <Button variant="outline" onClick={() => window.open(audioUrl + "?download=1")}>
                <Download className="mr-2 h-4 w-4" />
                下载音频
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

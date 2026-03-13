"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { 
  Settings, 
  Zap, 
  DollarSign, 
  Activity, 
  CheckCircle, 
  AlertCircle,
  ExternalLink,
  RefreshCw,
  Server,
  Cpu,
  Eye,
  Music,
  Mic,
  FileText,
  Image,
  Video
} from "lucide-react";
import { api } from "@/lib/api";

interface AIModel {
  id: string;
  name: string;
  display_name: string;
  description: string;
  provider: string;
  category: string;
  status: string;
  is_default: boolean;
  input_price: number;
  output_price: number;
  max_tokens?: number;
}

const categoryIcons: Record<string, any> = {
  text_generation: FileText,
  image_generation: Image,
  video_generation: Video,
  voice_synthesis: Mic,
  music_generation: Music,
  image_understanding: Eye,
};

const providerColors: Record<string, string> = {
  openai: "bg-green-500/20 text-green-400",
  anthropic: "bg-orange-500/20 text-orange-400",
  volcengine: "bg-blue-500/20 text-blue-400",
  midjourney: "bg-purple-500/20 text-purple-400",
  runway: "bg-pink-500/20 text-pink-400",
  elevenlabs: "bg-cyan-500/20 text-cyan-400",
};

export default function ModelSettingsPage() {
  const [models, setModels] = useState<AIModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState("all");

  useEffect(() => {
    loadModels();
  }, []);

  const loadModels = async () => {
    setLoading(true);
    try {
      const response = await api.get("/api/v1/models");
      setModels(response.data.items || []);
    } catch (error) {
      console.error("加载模型失败:", error);
    } finally {
      setLoading(false);
    }
  };

  const categories = [
    { id: "all", name: "全部" },
    { id: "text_generation", name: "文本生成" },
    { id: "image_generation", name: "图像生成" },
    { id: "video_generation", name: "视频生成" },
    { id: "voice_synthesis", name: "语音合成" },
    { id: "music_generation", name: "音乐生成" },
  ];

  const filteredModels = selectedCategory === "all" 
    ? models 
    : models.filter(m => m.category === selectedCategory);

  return (
    <div className="min-h-screen bg-slate-900">
      {/* 头部 */}
      <header className="glass border-b border-white/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <h1 className="text-xl font-bold text-white">AI模型配置</h1>
            <Button variant="outline" size="sm" onClick={loadModels}>
              <RefreshCw className="h-4 w-4 mr-2" />
              刷新
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* 统计概览 */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-white/60 text-sm">活跃模型</p>
                  <p className="text-2xl font-bold text-white">{models.filter(m => m.status === 'active').length}</p>
                </div>
                <Server className="h-8 w-8 text-green-400" />
              </div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-white/60 text-sm">本月请求</p>
                  <p className="text-2xl font-bold text-white">1,234</p>
                </div>
                <Activity className="h-8 w-8 text-blue-400" />
              </div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-white/60 text-sm">本月消费</p>
                  <p className="text-2xl font-bold text-white">¥23.45</p>
                </div>
                <DollarSign className="h-8 w-8 text-yellow-400" />
              </div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-white/60 text-sm">节省成本</p>
                  <p className="text-2xl font-bold text-white">¥12.3</p>
                </div>
                <Zap className="h-8 w-8 text-purple-400" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 分类标签 */}
        <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
          {categories.map((cat) => (
            <Button
              key={cat.id}
              variant={selectedCategory === cat.id ? "default" : "outline"}
              onClick={() => setSelectedCategory(cat.id)}
              className="bg-white/5 border-white/10 whitespace-nowrap"
            >
              {cat.name}
            </Button>
          ))}
        </div>

        {/* 模型列表 */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="animate-pulse">
                <div className="bg-white/5 rounded-xl h-48"></div>
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredModels.map((model) => {
              const IconComponent = categoryIcons[model.category] || Cpu;
              return (
                <Card key={model.id} className="bg-white/5 border-white/10 overflow-hidden">
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-white/10 flex items-center justify-center">
                          <IconComponent className="h-5 w-5 text-violet-400" />
                        </div>
                        <div>
                          <CardTitle className="text-white text-base">
                            {model.display_name}
                          </CardTitle>
                          <p className="text-white/40 text-xs">{model.name}</p>
                        </div>
                      </div>
                      {model.is_default && (
                        <Badge className="bg-violet-500/20 text-violet-400">
                          默认
                        </Badge>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="text-white/60 text-sm mb-4 line-clamp-2">
                      {model.description}
                    </p>
                    
                    <div className="flex items-center justify-between mb-4">
                      <span className={`px-2 py-1 rounded text-xs ${providerColors[model.provider] || 'bg-white/10'}`}>
                        {model.provider}
                      </span>
                      <div className="flex items-center gap-1">
                        {model.status === 'active' ? (
                          <CheckCircle className="h-4 w-4 text-green-400" />
                        ) : (
                          <AlertCircle className="h-4 w-4 text-yellow-400" />
                        )}
                        <span className="text-white/60 text-xs">
                          {model.status === 'active' ? '正常' : '维护中'}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between text-sm">
                      <div>
                        <span className="text-white/40">输入: </span>
                        <span className="text-white">¥{model.input_price}/1K</span>
                      </div>
                      <div>
                        <span className="text-white/40">输出: </span>
                        <span className="text-white">¥{model.output_price}/1K</span>
                      </div>
                      <Button size="sm" variant="outline" className="h-7">
                        配置
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}

        {/* 成本设置 */}
        <Card className="mt-8 bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <Settings className="h-5 w-5" />
              成本与路由设置
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <div className="space-y-2">
                <Label className="text-white/80">路由策略</Label>
                <select className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white">
                  <option value="balanced">平衡模式</option>
                  <option value="quality_first">质量优先</option>
                  <option value="cost_first">成本优先</option>
                  <option value="speed_first">速度优先</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label className="text-white/80">每日预算 (¥)</Label>
                <Input type="number" placeholder="0 = 不限" className="bg-white/5 border-white/10" />
              </div>
              <div className="space-y-2">
                <Label className="text-white/80">每月预算 (¥)</Label>
                <Input type="number" placeholder="0 = 不限" className="bg-white/5 border-white/10" />
              </div>
              <div className="space-y-2">
                <Label className="text-white/80">告警阈值</Label>
                <Input type="number" placeholder="80%" className="bg-white/5 border-white/10" />
              </div>
            </div>
            <div className="flex items-center gap-8 mt-6">
              <div className="flex items-center gap-2">
                <Switch id="auto-failover" defaultChecked />
                <Label htmlFor="auto-failover" className="text-white/80">自动故障切换</Label>
              </div>
              <div className="flex items-center gap-2">
                <Switch id="fallback-free" defaultChecked />
                <Label htmlFor="fallback-free" className="text-white/80">失败时切换免费模型</Label>
              </div>
              <Button className="ml-auto bg-violet-600">保存设置</Button>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
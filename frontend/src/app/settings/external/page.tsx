"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { 
  Plug, 
  Plus, 
  Settings, 
  CheckCircle, 
  AlertCircle, 
  ExternalLink,
  Zap,
  Image,
  Video,
  Music,
  Mic
} from "lucide-react";
import { api } from "@/lib/api";

interface ExternalAPI {
  id: string;
  name: string;
  type: string;
  is_configured: boolean;
  api_key_env: string;
  status: string;
}

const providerIcons: Record<string, any> = {
  image_generation: Image,
  video_generation: Video,
  music_generation: Music,
  voice_synthesis: Mic,
};

const providerColors: Record<string, string> = {
  midjourney: "from-purple-500 to-pink-500",
  runway: "from-pink-500 to-red-500",
  pika: "from-blue-500 to-cyan-500",
  suno: "from-yellow-500 to-orange-500",
  elevenlabs: "from-cyan-500 to-blue-500",
};

export default function ExternalAPIPage() {
  const [apis, setAPIs] = useState<ExternalAPI[]>([]);
  const [loading, setLoading] = useState(true);
  const [configDialogOpen, setConfigDialogOpen] = useState(false);
  const [selectedAPI, setSelectedAPI] = useState<ExternalAPI | null>(null);
  const [apiKey, setApiKey] = useState("");

  useEffect(() => {
    loadAPIs();
  }, []);

  const loadAPIs = async () => {
    setLoading(true);
    try {
      const response = await api.get("/api/v1/external/providers");
      setAPIs(response.data.items || []);
    } catch (error) {
      console.error("加载API列表失败:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleConfigure = async () => {
    if (!selectedAPI || !apiKey.trim()) return;
    
    try {
      await api.post(`/api/v1/external/config/${selectedAPI.id}`, {
        api_key: apiKey,
      });
      setConfigDialogOpen(false);
      setApiKey("");
      loadAPIs();
    } catch (error) {
      console.error("配置失败:", error);
    }
  };

  const openConfigDialog = (apiItem: ExternalAPI) => {
    setSelectedAPI(apiItem);
    setConfigDialogOpen(true);
  };

  const groupedAPIs = apis.reduce((acc, apiItem) => {
    if (!acc[apiItem.type]) {
      acc[apiItem.type] = [];
    }
    acc[apiItem.type].push(apiItem);
    return acc;
  }, {} as Record<string, ExternalAPI[]>);

  return (
    <div className="min-h-screen bg-slate-900">
      {/* 头部 */}
      <header className="glass border-b border-white/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              <Plug className="h-5 w-5" />
              外部API接入
            </h1>
            <Button variant="outline" size="sm" onClick={loadAPIs}>
              刷新
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* 说明 */}
        <Card className="bg-white/5 border-white/10 mb-8">
          <CardContent className="p-6">
            <h3 className="text-white font-medium mb-2">接入外部AI服务</h3>
            <p className="text-white/60 text-sm">
              连接Midjourney、Runway、Pika、Suno等外部AI服务，扩展平台能力。
              配置API密钥后即可使用对应的AI生成功能。
            </p>
          </CardContent>
        </Card>

        {/* API列表 */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="animate-pulse">
                <div className="bg-white/5 rounded-xl h-48"></div>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-8">
            {Object.entries(groupedAPIs).map(([type, items]) => {
              const IconComponent = providerIcons[type] || Zap;
              return (
                <div key={type}>
                  <h3 className="text-white/80 font-medium mb-4 flex items-center gap-2">
                    <IconComponent className="h-4 w-4" />
                    {type === 'image_generation' && '图像生成'}
                    {type === 'video_generation' && '视频生成'}
                    {type === 'music_generation' && '音乐生成'}
                    {type === 'voice_synthesis' && '语音合成'}
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {items.map((apiItem) => (
                      <Card 
                        key={apiItem.id} 
                        className="bg-white/5 border-white/10 overflow-hidden"
                      >
                        <CardHeader className="pb-2">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${providerColors[apiItem.id] || 'from-gray-500 to-gray-600'} flex items-center justify-center`}>
                                <IconComponent className="h-5 w-5 text-white" />
                              </div>
                              <div>
                                <CardTitle className="text-white text-base">
                                  {apiItem.name}
                                </CardTitle>
                                <p className="text-white/40 text-xs">{apiItem.api_key_env}</p>
                              </div>
                            </div>
                            {apiItem.is_configured ? (
                              <Badge className="bg-green-500/20 text-green-400">
                                <CheckCircle className="h-3 w-3 mr-1" />
                                已配置
                              </Badge>
                            ) : (
                              <Badge className="bg-yellow-500/20 text-yellow-400">
                                <AlertCircle className="h-3 w-3 mr-1" />
                                未配置
                              </Badge>
                            )}
                          </div>
                        </CardHeader>
                        <CardContent>
                          <p className="text-white/60 text-sm mb-4">
                            {apiItem.id === 'midjourney' && 'AI图像生成，业界领先的艺术风格'}
                            {apiItem.id === 'runway' && '专业级AI视频生成平台'}
                            {apiItem.id === 'pika' && '快速AI视频生成'}
                            {apiItem.id === 'suno' && 'AI音乐创作平台'}
                            {apiItem.id === 'elevenlabs' && '超真实语音合成'}
                          </p>
                          <div className="flex items-center gap-2">
                            <Button 
                              variant="outline" 
                              size="sm" 
                              className="flex-1 bg-white/5 border-white/10"
                              onClick={() => openConfigDialog(apiItem)}
                            >
                              <Settings className="h-4 w-4 mr-1" />
                              {apiItem.is_configured ? '重新配置' : '配置'}
                            </Button>
                            {apiItem.is_configured && (
                              <Button variant="outline" size="sm" className="flex-1 bg-white/5 border-white/10">
                                <ExternalLink className="h-4 w-4 mr-1" />
                                文档
                              </Button>
                            )}
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* 配置对话框 */}
        <Dialog open={configDialogOpen} onOpenChange={setConfigDialogOpen}>
          <DialogContent className="bg-slate-800 border-white/10">
            <DialogHeader>
              <DialogTitle className="text-white">
                配置 {selectedAPI?.name} API
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              <div>
                <label className="text-white/80 text-sm">API Key</label>
                <Input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="输入API Key"
                  className="bg-white/5 border-white/10 mt-1"
                />
                <p className="text-white/40 text-xs mt-1">
                  环境变量: {selectedAPI?.api_key_env}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
                <p className="text-blue-400 text-sm">
                  💡 提示: API密钥将加密存储，仅用于调用对应服务商的API。
                </p>
              </div>
              <Button onClick={handleConfigure} className="w-full bg-violet-600">
                保存配置
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
}
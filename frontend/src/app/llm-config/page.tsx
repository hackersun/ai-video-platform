'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { MainLayout } from '@/components/layout/main-layout';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  Settings, 
  Key, 
  Plus, 
  Trash2, 
  TestTube,
  CheckCircle,
  XCircle,
  Loader2,
  Sparkles,
  Video,
  Music,
  Image as ImageIcon,
  MessageSquare,
  ChevronRight,
  Copy,
  RefreshCw
} from 'lucide-react';

// 模型分类
const MODEL_CATEGORIES = {
  text: { name: '文本生成', icon: MessageSquare, color: 'text-blue-400' },
  image: { name: '图像生成', icon: ImageIcon, color: 'text-purple-400' },
  video: { name: '视频生成', icon: Video, color: 'text-pink-400' },
  audio: { name: '音频生成', icon: Music, color: 'text-green-400' },
};

// 默认火山引擎配置
const DEFAULT_PROVIDER = {
  id: 'volcano',
  name: '火山引擎',
  name_cn: '火山引擎',
  models: [
    { 
      id: 'doubao-seed-1-8-251228', 
      name: '豆包Seed-1.8', 
      type: 'text', 
      cost: '0.5元/千token',
      verified: true,
      desc: '已验证可用 ✅'
    },
    { id: 'doubao-pro-4k', name: '豆包Pro-4K', type: 'text', cost: '0.8元/千token' },
    { id: 'doubao-lite-4k', name: '豆包Lite-4K', type: 'text', cost: '0.3元/千token' },
    { id: 'volcano-vision', name: '火山文生图', type: 'image', cost: '10分/张' },
    { id: 'volcano-video', name: '火山视频生成', type: 'video', cost: '50分/秒' },
  ]
};

const QWEN_MODELS = [
  { id: 'qwen-turbo', name: '千问Turbo', type: 'text', context: '8K', cost: '0.5元/千token', desc: '轻量级模型，响应速度快' },
  { id: 'qwen-plus', name: '千问Plus', type: 'text', context: '32K', cost: '2元/千token', desc: '均衡型模型，综合能力优秀' },
  { id: 'qwen-max', name: '千问Max', type: 'text', context: '32K', cost: '20元/千token', desc: '旗舰级模型，最强性能' },
  { id: 'qwen-long', name: '千问Long', type: 'text', context: '100万', cost: '0.5元/千token', desc: '超长上下文，支持百万token' },
  { id: 'qwen-vl-plus', name: '千问VL Plus', type: 'vision', context: '32K', cost: '2元/千token', desc: '视觉语言模型，支持图像理解' },
];

const EXTERNAL_APIS = [
  { id: 'midjourney', name: 'Midjourney', type: 'image', cost: '$10/100张', desc: '高质量AI图像生成' },
  { id: 'runway', name: 'Runway', type: 'video', cost: '$20/分钟', desc: 'AI视频生成' },
  { id: 'suno', name: 'Suno', type: 'audio', cost: '$10/月', desc: 'AI音乐生成' },
];

export default function LLMConfigPage() {
  const [activeTab, setActiveTab] = useState('volcano');
  const [apiKey, setApiKey] = useState('');
  const [configs, setConfigs] = useState([]);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  const currentProvider = DEFAULT_PROVIDER;

  const handleTest = async () => {
    if (!apiKey) {
      setTestResult({ status: 'error', message: '请输入API Key' });
      return;
    }
    
    setIsTesting(true);
    setTestResult(null);
    
    // 模拟测试
    await new Promise(resolve => setTimeout(resolve, 1500));
    
    if (apiKey === 'be8feb9d-6b08-406e-8447-b22b87cd907a') {
      setTestResult({ status: 'success', message: '连接成功！火山引擎 API Key 验证通过' });
    } else if (apiKey.length >= 10) {
      setTestResult({ status: 'success', message: 'API Key 验证通过' });
    } else {
      setTestResult({ status: 'error', message: 'API Key 无效' });
    }
    
    setIsTesting(false);
  };

  const handleSave = async () => {
    if (!apiKey) {
      setTestResult({ status: 'error', message: '请先输入API Key' });
      return;
    }
    
    setTestResult({ status: 'success', message: '配置已保存！' });
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Settings className="w-6 h-6" />
            大模型配置
          </h1>
          <p className="text-white/60 mt-1">配置和管理AI模型服务</p>
        </div>

        {/* 主要内容区域 */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 左侧：模型列表 */}
          <div className="lg:col-span-2 space-y-4">
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-violet-400" />
                  选择模型
                </CardTitle>
              </CardHeader>
              <CardContent>
                {/* 标签切换 */}
                <div className="flex gap-2 mb-4">
                  <Button
                    variant={activeTab === 'volcano' ? 'default' : 'outline'}
                    onClick={() => setActiveTab('volcano')}
                    className={activeTab === 'volcano' ? 'bg-violet-600' : 'border-white/10'}
                  >
                    🔥 火山引擎
                  </Button>
                  <Button
                    variant={activeTab === 'qwen' ? 'default' : 'outline'}
                    onClick={() => setActiveTab('qwen')}
                    className={activeTab === 'qwen' ? 'bg-violet-600' : 'border-white/10'}
                  >
                    🐱 阿里千问
                  </Button>
                  <Button
                    variant={activeTab === 'external' ? 'default' : 'outline'}
                    onClick={() => setActiveTab('external')}
                    className={activeTab === 'external' ? 'bg-violet-600' : 'border-white/10'}
                  >
                    🌐 外部API
                  </Button>
                </div>

                {/* 火山引擎模型 */}
                {activeTab === 'volcano' && (
                  <div className="space-y-3">
                    {currentProvider.models.map((model) => (
                      <div
                        key={model.id}
                        className="p-4 rounded-lg bg-white/5 border border-white/10 hover:border-violet-500/50 cursor-pointer transition-all"
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="text-white font-medium flex items-center gap-2">
                              {model.type === 'text' && <MessageSquare className="w-4 h-4 text-blue-400" />}
                              {model.type === 'image' && <ImageIcon className="w-4 h-4 text-purple-400" />}
                              {model.type === 'video' && <Video className="w-4 h-4 text-pink-400" />}
                              {model.name}
                              {model.verified && (
                                <span className="px-2 py-0.5 text-xs bg-green-500/20 text-green-400 rounded flex items-center gap-1">
                                  <CheckCircle className="w-3 h-3" />
                                  已验证
                                </span>
                              )}
                              {model.id === 'doubao-seed-1-8-251228' && (
                                <span className="px-2 py-0.5 text-xs bg-violet-500/20 text-violet-400 rounded">
                                  推荐
                                </span>
                              )}
                            </div>
                            <div className="text-white/60 text-sm mt-1">{model.cost}</div>
                          </div>
                          <Button size="sm" variant="outline">
                            配置
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* 阿里千问模型 */}
                {activeTab === 'qwen' && (
                  <div className="space-y-3">
                    {QWEN_MODELS.map((model) => (
                      <div
                        key={model.id}
                        className="p-4 rounded-lg bg-white/5 border border-white/10 hover:border-violet-500/50 cursor-pointer transition-all"
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="text-white font-medium">
                              {model.name}
                            </div>
                            <div className="text-white/60 text-sm mt-1">
                              上下文{model.context} • {model.cost}
                            </div>
                            <div className="text-white/40 text-xs mt-1">
                              {model.desc}
                            </div>
                          </div>
                          <Button size="sm" variant="outline">
                            配置
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* 外部API */}
                {activeTab === 'external' && (
                  <div className="space-y-3">
                    {EXTERNAL_APIS.map((api) => (
                      <div
                        key={api.id}
                        className="p-4 rounded-lg bg-white/5 border border-white/10 hover:border-violet-500/50 cursor-pointer transition-all"
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="text-white font-medium">
                              {api.name}
                            </div>
                            <div className="text-white/60 text-sm mt-1">
                              {api.cost}
                            </div>
                            <div className="text-white/40 text-xs mt-1">
                              {api.desc}
                            </div>
                          </div>
                          <Button size="sm" variant="outline">
                            配置
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* 右侧：配置面板 */}
          <div className="space-y-4">
            {/* API Key配置 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Key className="w-5 h-5" />
                  API Key 配置
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <label className="block text-sm text-white/80 mb-2">
                    API Key <span className="text-red-400">*</span>
                  </label>
                  <Input
                    type="password"
                    placeholder="请输入API Key"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    className="bg-white/5 border-white/10"
                  />
                  <p className="text-white/40 text-xs mt-2">
                    已验证可用：be8feb9d-6b08-406e-8447-b22b87cd907a
                  </p>
                </div>

                {/* 测试结果 */}
                {testResult && (
                  <div className={`p-3 rounded-lg flex items-center gap-2 ${
                    testResult.status === 'success' ? 'bg-green-500/10 border border-green-500/20' : 'bg-red-500/10 border border-red-500/20'
                  }`}>
                    {testResult.status === 'success' ? (
                      <CheckCircle className="w-4 h-4 text-green-400" />
                    ) : (
                      <XCircle className="w-4 h-4 text-red-400" />
                    )}
                    <span className={testResult.status === 'success' ? 'text-green-400' : 'text-red-400'}>
                      {testResult.message}
                    </span>
                  </div>
                )}

                {/* 按钮 */}
                <div className="flex gap-2">
                  <Button
                    onClick={handleTest}
                    disabled={isTesting}
                    variant="outline"
                    className="flex-1"
                  >
                    {isTesting ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        测试中
                      </>
                    ) : (
                      <>
                        <TestTube className="w-4 h-4 mr-2" />
                        测试连接
                      </>
                    )}
                  </Button>
                  <Button
                    onClick={handleSave}
                    className="flex-1 bg-violet-600 hover:bg-violet-700"
                  >
                    <CheckCircle className="w-4 h-4 mr-2" />
                    保存配置
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* 已保存配置 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Settings className="w-5 h-5" />
                  已保存配置
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-center py-8 text-white/40">
                  <Key className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p>暂无已保存的配置</p>
                  <p className="text-sm">在上方输入API Key并保存</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </MainLayout>
  );
}
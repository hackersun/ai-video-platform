'use client';

import { useState, useEffect } from 'react';
import { MainLayout } from '@/components/layout/main-layout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Slider } from '@/components/ui/slider';
import { 
  Image as ImageIcon, 
  Video, 
  Settings, 
  Sparkles,
  Zap,
  Shield,
  AlertCircle,
  CheckCircle,
  Loader2
} from 'lucide-react';

// 提供商配置
const PROVIDERS = {
  image: [
    { id: 'volcano', name: '火山引擎', type: 'cloud', cost: 'paid', quality: 'high', desc: '高质量商业级文生图' },
    { id: 'sdxl', name: 'Stable Diffusion XL', type: 'local/cloud', cost: 'free', quality: 'high', desc: '开源高质量模型' },
    { id: 'fooocus', name: 'Fooocus', type: 'local', cost: 'free', quality: 'medium', desc: '简单易用的本地模型' },
    { id: 'huggingface', name: 'Hugging Face', type: 'cloud', cost: 'free', quality: 'medium', desc: '多种免费模型可选' },
  ],
  video: [
    { id: 'volcano', name: '火山引擎', type: 'cloud', cost: 'paid', quality: 'high', desc: '高质量商业级视频生成' },
    { id: 'svd', name: 'Stable Video Diffusion', type: 'local', cost: 'free', quality: 'medium', desc: '开源图生视频模型' },
    { id: 'modelscope', name: 'ModelScope', type: 'cloud', cost: 'free', quality: 'medium', desc: '阿里开源模型平台' },
  ]
};

export default function AIGenerationPage() {
  const [activeTab, setActiveTab] = useState<'image' | 'video'>('image');
  const [selectedProvider, setSelectedProvider] = useState('volcano');
  const [apiKey, setApiKey] = useState('');
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<'success' | 'error' | null>(null);
  
  // 图片生成参数
  const [imageParams, setImageParams] = useState({
    width: 1024,
    height: 1024,
    quality: 'high',
    style: 'anime'
  });
  
  // 视频生成参数
  const [videoParams, setVideoParams] = useState({
    duration: 4,
    fps: 24,
    motionStrength: 'medium'
  });

  const handleTest = async () => {
    setIsTesting(true);
    setTestResult(null);
    
    // 模拟测试
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    if (selectedProvider === 'volcano' && !apiKey) {
      setTestResult('error');
    } else {
      setTestResult('success');
    }
    
    setIsTesting(false);
  };

  const currentProviders = PROVIDERS[activeTab];
  const selectedProviderInfo = currentProviders.find(p => p.id === selectedProvider);

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-violet-400" />
            AI生成配置
          </h1>
          <p className="text-white/60 mt-1">配置图片和视频生成模型</p>
        </div>

        {/* 标签切换 */}
        <div className="flex gap-2">
          <Button
            variant={activeTab === 'image' ? 'default' : 'outline'}
            onClick={() => setActiveTab('image')}
            className={activeTab === 'image' ? 'bg-violet-600' : 'border-white/10'}
          >
            <ImageIcon className="w-4 h-4 mr-2" />
            图片生成
          </Button>
          <Button
            variant={activeTab === 'video' ? 'default' : 'outline'}
            onClick={() => setActiveTab('video')}
            className={activeTab === 'video' ? 'bg-violet-600' : 'border-white/10'}
          >
            <Video className="w-4 h-4 mr-2" />
            视频生成
          </Button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 左侧：提供商选择 */}
          <Card className="bg-white/5 border-white/10">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Settings className="w-5 h-5" />
                选择模型提供商
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {currentProviders.map((provider) => (
                <div
                  key={provider.id}
                  onClick={() => setSelectedProvider(provider.id)}
                  className={`p-4 rounded-lg border cursor-pointer transition-all ${
                    selectedProvider === provider.id
                      ? 'border-violet-500 bg-violet-500/10'
                      : 'border-white/10 hover:border-white/20'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-white font-medium flex items-center gap-2">
                        {provider.name}
                        {provider.cost === 'free' && (
                          <span className="px-2 py-0.5 text-xs bg-green-500/20 text-green-400 rounded">
                            免费
                          </span>
                        )}
                        {provider.cost === 'paid' && (
                          <span className="px-2 py-0.5 text-xs bg-amber-500/20 text-amber-400 rounded">
                            付费
                          </span>
                        )}
                      </div>
                      <div className="text-white/60 text-sm mt-1">{provider.desc}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-white/40 text-xs">质量</div>
                      <div className="text-white text-sm">
                        {provider.quality === 'high' ? '高' : '中'}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* 右侧：API配置和参数 */}
          <div className="space-y-4">
            {/* API密钥配置 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Shield className="w-5 h-5" />
                  API密钥配置
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {selectedProviderInfo?.cost === 'paid' && (
                  <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                    <div className="flex items-center gap-2 text-amber-400">
                      <AlertCircle className="w-4 h-4" />
                      <span className="text-sm">此提供商需要API密钥</span>
                    </div>
                  </div>
                )}
                
                <div>
                  <label className="block text-sm text-white/80 mb-2">
                    {selectedProviderInfo?.cost === 'paid' ? 'API密钥 *' : 'API密钥（可选）'}
                  </label>
                  <Input
                    type="password"
                    placeholder="输入API密钥"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    className="bg-white/5 border-white/10"
                  />
                </div>

                <Button
                  onClick={handleTest}
                  disabled={isTesting}
                  className="w-full"
                  variant="outline"
                >
                  {isTesting ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      测试中...
                    </>
                  ) : (
                    <>
                      <Zap className="w-4 h-4 mr-2" />
                      测试连接
                    </>
                  )}
                </Button>

                {testResult === 'success' && (
                  <div
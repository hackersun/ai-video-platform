'use client';

import { useEffect, useState } from 'react';
import { MainLayout } from '@/components/layout/main-layout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { ModelCapabilitySelector } from '@/components/model-capability-selector';
import {
  DEFAULT_IMAGE_STYLE_TEMPLATES,
  ImageStyleTemplatePicker,
  type ImageStyleTemplate,
} from '@/components/media/image-style-template-picker';
import { useToast } from '@/components/ui/toast';
import { 
  BookOpen, 
  ArrowLeft,
  Save,
  Eye,
  Image as ImageIcon,
  Tag,
  Users,
  FileText,
  Sparkles,
  Loader2
} from 'lucide-react';
import Link from 'next/link';
import { fetchWithAuth } from '@/lib/fetch-with-auth';
import { apiClient } from '@/lib/api-client';
import {
  getDefaultConfigForCapability,
  SavedModelConfig,
} from '@/lib/model-configs';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const API_ORIGIN = API_BASE.replace(/\/api\/v1\/?$/, '');

const toMediaUrl = (url?: string) => {
  if (!url) return '';
  return url.startsWith('/') ? `${API_ORIGIN}${url}` : url;
};

// 小说类型选项
const GENRE_OPTIONS = [
  { value: 'xianxia', label: '仙侠' },
  { value: 'urban', label: '都市' },
  { value: 'scifi', label: '科幻' },
  { value: 'historical', label: '历史' },
  { value: 'romance', label: '言情' },
  { value: 'mystery', label: '悬疑' },
  { value: 'fantasy', label: '奇幻' }
];

// 风格选项
const STYLE_OPTIONS = [
  { value: 'serious', label: '正剧' },
  { value: 'humor', label: '轻松' },
  { value: 'sad', label: '虐心' },
  { value: 'heroic', label: '热血' }
];

const FALLBACK_IMAGE_STYLES: ImageStyleTemplate[] = DEFAULT_IMAGE_STYLE_TEMPLATES;

export default function NewNovelPage() {
  const { toast } = useToast();
  const [isSaving, setIsSaving] = useState(false);
  const [isGeneratingIntro, setIsGeneratingIntro] = useState(false);
  const [isGeneratingCover, setIsGeneratingCover] = useState(false);
  const [modelConfigs, setModelConfigs] = useState<SavedModelConfig[]>([]);
  const [textModelConfigId, setTextModelConfigId] = useState('');
  const [imageModelConfigId, setImageModelConfigId] = useState('');
  const [imageStyle, setImageStyle] = useState('anime');
  const [styleTemplates, setStyleTemplates] = useState<ImageStyleTemplate[]>(FALLBACK_IMAGE_STYLES);
  const [novel, setNovel] = useState({
    title: '',
    description: '',
    genre: '',
    style: '',
    tags: '',
    cover: '',
    intro: ''
  });

  useEffect(() => {
    loadModelConfigs();
    loadStyleTemplates();
  }, []);

  const loadStyleTemplates = async () => {
    try {
      const data = await apiClient.getAssetStyleTemplates();
      const templates = Array.isArray(data?.templates) ? data.templates : FALLBACK_IMAGE_STYLES;
      setStyleTemplates(templates.length ? templates : FALLBACK_IMAGE_STYLES);
    } catch {
      setStyleTemplates(FALLBACK_IMAGE_STYLES);
    }
  };

  const loadModelConfigs = async () => {
    try {
      const response = await fetchWithAuth(`${API_BASE}/llm/configs?include_model_center_defaults=true`);
      if (!response.ok) return;
      const configs = await response.json();
      const list = Array.isArray(configs) ? configs : [];
      setModelConfigs(list);
      const textDefault = getDefaultConfigForCapability(list, 'text');
      const imageDefault = getDefaultConfigForCapability(list, 'image');
      if (textDefault) setTextModelConfigId(textDefault.id);
      if (imageDefault) setImageModelConfigId(imageDefault.id);
    } catch (error) {
      console.error('加载模型配置失败:', error);
    }
  };

  // 保存小说
  const handleSave = async (publish: boolean = false) => {
    if (!novel.title.trim()) {
      toast({ title: '请输入小说标题', type: 'info' });
      return;
    }
    if (!novel.genre) {
      toast({ title: '请选择小说题材', type: 'info' });
      return;
    }

    setIsSaving(true);
    try {
      // 保存到后端API
      const response = await fetchWithAuth(`${API_BASE}/novels`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: novel.title,
          description: novel.description,
          genre: GENRE_OPTIONS.find(g => g.value === novel.genre)?.label || novel.genre,
          tags: novel.tags.split(',').map(tag => tag.trim()).filter(Boolean),
          cover_url: novel.cover || undefined,
        })
      });
      
      if (!response.ok) {
        throw new Error('保存失败');
      }
      
      toast({ title: publish ? '发布成功' : '保存成功', type: 'success' });
      // 跳转到小说列表
      window.location.href = '/novels';
    } catch (error) {
      console.error('保存失败:', error);
      toast({ title: '保存失败', description: '请检查后端服务是否启动。', type: 'error' });
    } finally {
      setIsSaving(false);
    }
  };

  // AI 生成简介
  const handleAIGenerate = async () => {
    if (!novel.title || !novel.genre) {
      toast({ title: '请先填写标题和题材', type: 'info' });
      return;
    }

    setIsGeneratingIntro(true);
    try {
      const response = await fetchWithAuth(`${API_BASE}/novels/generate-intro`, {
        method: 'POST',
        body: JSON.stringify({
          title: novel.title,
          genre: novel.genre,
          style: novel.style,
          description: novel.description,
          model_config_id: textModelConfigId || undefined,
        }),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || error.message || `AI 简介生成失败：HTTP ${response.status}`);
      }

      const data = await response.json();
      const generatedIntro = data.intro;
      if (!generatedIntro) {
        throw new Error('AI 简介生成接口未返回简介内容');
      }
      setNovel({ ...novel, intro: generatedIntro });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'AI 简介生成失败';
      toast({ title: 'AI 简介生成失败', description: message, type: 'error' });
    } finally {
      setIsGeneratingIntro(false);
    }
  };

  // AI 生成封面
  const handleAIGenerateCover = async () => {
    if (!novel.title || !novel.genre) {
      toast({ title: '请先填写标题和题材', type: 'info' });
      return;
    }

    setIsGeneratingCover(true);
    try {
      const response = await fetchWithAuth(`${API_BASE}/novels/generate-cover`, {
        method: 'POST',
        body: JSON.stringify({
          title: novel.title,
          genre: GENRE_OPTIONS.find(g => g.value === novel.genre)?.label || novel.genre,
          style: imageStyle,
          description: novel.intro || novel.description,
          model_config_id: imageModelConfigId || undefined,
        }),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || error.message || `AI 封面生成失败：HTTP ${response.status}`);
      }

      const data = await response.json();
      if (!data.cover_url) {
        throw new Error('AI 封面生成接口未返回图片地址');
      }
      setNovel({ ...novel, cover: data.cover_url });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'AI 封面生成失败';
      toast({ title: 'AI 封面生成失败', description: message, type: 'error' });
    } finally {
      setIsGeneratingCover(false);
    }
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button asChild variant="ghost" size="icon" aria-label="返回小说列表" title="返回">
              <Link href="/novels">
                <ArrowLeft className="w-5 h-5" />
              </Link>
            </Button>
            <div>
              <h1 className="text-3xl font-bold text-white">创建小说</h1>
              <p className="text-white/60 mt-1">开始您的创作之旅</p>
            </div>
          </div>
          <div className="flex gap-3">
            <Button 
              variant="outline" 
              onClick={() => handleSave(false)}
              disabled={isSaving}
              className="border-white/20 text-white"
            >
              {isSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
              保存草稿
            </Button>
            <Button 
              onClick={() => handleSave(true)}
              disabled={isSaving}
              className="bg-violet-600 hover:bg-violet-700"
            >
              {isSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Eye className="w-4 h-4 mr-2" />}
              发布小说
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 主要内容 */}
          <div className="lg:col-span-2 space-y-6">
            {/* 基本信息 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <BookOpen className="w-5 h-5 text-violet-400" />
                  基本信息
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <label className="text-sm text-white/60 mb-2 block">小说标题 *</label>
                  <Input
                    placeholder="输入小说标题"
                    value={novel.title}
                    onChange={(e) => setNovel({ ...novel, title: e.target.value })}
                    className="bg-white/5 border-white/10 text-white placeholder:text-white/40"
                  />
                </div>
                
                <div>
                  <label className="text-sm text-white/60 mb-2 block">小说简介</label>
                  <Textarea
                    placeholder="简要介绍小说内容"
                    value={novel.description}
                    onChange={(e) => setNovel({ ...novel, description: e.target.value })}
                    rows={3}
                    className="bg-white/5 border-white/10 text-white placeholder:text-white/40"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm text-white/60 mb-2 block">题材分类 *</label>
                    <select
                      value={novel.genre}
                      onChange={(e) => setNovel({ ...novel, genre: e.target.value })}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                    >
                      <option value="">选择题材</option>
                      {GENRE_OPTIONS.map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-sm text-white/60 mb-2 block">小说风格</label>
                    <select
                      value={novel.style}
                      onChange={(e) => setNovel({ ...novel, style: e.target.value })}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                    >
                      <option value="">选择风格</option>
                      {STYLE_OPTIONS.map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <label className="text-sm text-white/60 mb-2 block">标签</label>
                  <Input
                    placeholder="用逗号分隔标签，如：修仙、热血、成长"
                    value={novel.tags}
                    onChange={(e) => setNovel({ ...novel, tags: e.target.value })}
                    className="bg-white/5 border-white/10 text-white placeholder:text-white/40"
                  />
                </div>
              </CardContent>
            </Card>

            {/* 详细简介 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <FileText className="w-5 h-5 text-blue-400" />
                    详细简介
                  </div>
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={handleAIGenerate}
                    disabled={isGeneratingIntro}
                    className="border-violet-500/50 text-violet-400 hover:bg-violet-600/20"
                  >
                    {isGeneratingIntro ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
                    AI 生成
                  </Button>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ModelCapabilitySelector
                  capability="text"
                  configs={modelConfigs}
                  value={textModelConfigId}
                  onChange={setTextModelConfigId}
                  disabled={isGeneratingIntro}
                  title="简介生成模型"
                  description="AI 简介会使用文本生成能力，提示词会带入标题、题材、风格和创作说明。"
                  className="mb-4"
                />
                <Textarea
                  placeholder="输入小说的详细简介、世界观、人物设定等…"
                  value={novel.intro}
                  onChange={(e) => setNovel({ ...novel, intro: e.target.value })}
                  rows={10}
                  className="bg-white/5 border-white/10 text-white placeholder:text-white/40"
                />
              </CardContent>
            </Card>
          </div>

          {/* 侧边栏 */}
          <div className="space-y-6">
            {/* 封面设置 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <ImageIcon className="w-5 h-5 text-pink-400" />
                    封面设置
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleAIGenerateCover}
                    disabled={isGeneratingCover}
                    className="border-pink-500/50 text-pink-300 hover:bg-pink-600/20"
                  >
                    {isGeneratingCover ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
                    AI 生成
                  </Button>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ModelCapabilitySelector
                  capability="image"
                  configs={modelConfigs}
                  value={imageModelConfigId}
                  onChange={setImageModelConfigId}
                  disabled={isGeneratingCover}
                  title="封面生成模型"
                  description="封面会使用图像生成能力，并结合题材、主角线索、关键场景和故事冲突生成。"
                  className="mb-4"
                />
                <div className="mb-4">
                  <ImageStyleTemplatePicker
                    templates={styleTemplates}
                    value={imageStyle}
                    onChange={setImageStyle}
                    toMediaUrl={toMediaUrl}
                    recommendedFor="cover"
                    title="封面画面风格"
                    compact
                  />
                </div>
                <div className="border-2 border-dashed border-white/20 rounded-lg p-4 text-center min-h-[220px] flex items-center justify-center">
                  {novel.cover ? (
                    <div className="relative w-full">
                      <img src={toMediaUrl(novel.cover)} alt="封面" width={300} height={400} loading="lazy" className="w-full aspect-[3/4] object-cover rounded-lg" />
                      <Button
                        variant="destructive"
                        size="sm"
                        className="absolute top-2 right-2"
                        onClick={() => setNovel({ ...novel, cover: '' })}
                      >
                        更换
                      </Button>
                    </div>
                  ) : (
                    <>
                      <ImageIcon className="w-12 h-12 mx-auto text-white/30" />
                      <p className="text-white/60 mt-2">点击或拖拽上传封面</p>
                      <p className="text-white/40 text-sm">建议尺寸: 1200x1600</p>
                    </>
                  )}
                </div>
                <Input
                  placeholder="或输入图片URL"
                  value={novel.cover}
                  onChange={(e) => setNovel({ ...novel, cover: e.target.value })}
                  className="mt-4 bg-white/5 border-white/10 text-white placeholder:text-white/40"
                />
              </CardContent>
            </Card>

            {/* 快速统计 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Users className="w-5 h-5 text-green-400" />
                  角色关联
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-white/60 text-sm mb-4">创建小说后可关联角色</p>
                <Button asChild variant="outline" className="w-full border-white/20 text-white">
                  <Link href="/characters">
                    管理角色库
                  </Link>
                </Button>
              </CardContent>
            </Card>

            {/* 提示 */}
            <Card className="bg-violet-600/10 border-violet-500/30">
              <CardContent className="p-4">
                <h4 className="font-medium text-violet-300 mb-2">💡 创作提示</h4>
                <ul className="text-sm text-white/60 space-y-1">
                  <li>• 好的标题能吸引读者注意</li>
                  <li>• 简介要能概括故事核心</li>
                  <li>• 选择合适的题材和风格</li>
                  <li>• 使用标签帮助读者发现</li>
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </MainLayout>
  );
}

'use client';

import { useState } from 'react';
import { MainLayout } from '@/components/layout/main-layout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
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

export default function NewNovelPage() {
  const [isSaving, setIsSaving] = useState(false);
  const [novel, setNovel] = useState({
    title: '',
    description: '',
    genre: '',
    style: '',
    tags: '',
    cover: '',
    intro: ''
  });

  // 保存小说
  const handleSave = async (publish: boolean = false) => {
    if (!novel.title.trim()) {
      alert('请输入小说标题');
      return;
    }
    if (!novel.genre) {
      alert('请选择小说题材');
      return;
    }

    setIsSaving(true);
    try {
      // 保存到 localStorage
      const existingNovels = typeof window !== 'undefined' 
        ? JSON.parse(localStorage.getItem('video-novels') || '[]') 
        : [];
      
      const now = new Date().toISOString().split('T')[0];
      const newNovel = {
        id: Date.now().toString(),
        title: novel.title,
        description: novel.description,
        genre: GENRE_OPTIONS.find(g => g.value === novel.genre)?.label || novel.genre,
        status: publish ? 'writing' as const : 'draft' as const,
        chapters: 0,
        characters: 0,
        createdAt: now,
        updatedAt: now
      };
      
      const updatedNovels = [newNovel, ...existingNovels];
      localStorage.setItem('video-novels', JSON.stringify(updatedNovels));
      
      // 模拟保存
      await new Promise(resolve => setTimeout(resolve, 1000));
      alert(publish ? '发布成功！' : '保存成功！');
      // 跳转到小说列表
      window.location.href = '/novels';
    } catch (error) {
      console.error('保存失败:', error);
      alert('保存失败，请重试');
    } finally {
      setIsSaving(false);
    }
  };

  // AI 生成简介
  const handleAIGenerate = async () => {
    if (!novel.title || !novel.genre) {
      alert('请先填写标题和题材');
      return;
    }
    
    // 模拟 AI 生成
    const generatedIntro = `这是一个关于${novel.title}的故事。\n\n${novel.description || '主人公在这个世界中展开了一段奇妙的冒险之旅，经历了种种挑战和考验，最终实现了自己的目标。'}\n\n故事背景设定独特，人物形象鲜明，情节跌宕起伏，值得期待。`;
    
    setNovel({ ...novel, intro: generatedIntro });
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/novels">
              <Button variant="ghost" size="icon">
                <ArrowLeft className="w-5 h-5" />
              </Button>
            </Link>
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
                    className="border-violet-500/50 text-violet-400 hover:bg-violet-600/20"
                  >
                    <Sparkles className="w-4 h-4 mr-2" />
                    AI 生成
                  </Button>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Textarea
                  placeholder="输入小说的详细简介、世界观、人物设定等..."
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
                <CardTitle className="text-white flex items-center gap-2">
                  <ImageIcon className="w-5 h-5 text-pink-400" />
                  封面设置
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="border-2 border-dashed border-white/20 rounded-lg p-8 text-center">
                  {novel.cover ? (
                    <div className="relative">
                      <img src={novel.cover} alt="封面" className="w-full rounded-lg" />
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
                <Link href="/characters">
                  <Button variant="outline" className="w-full border-white/20 text-white">
                    管理角色库
                  </Button>
                </Link>
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
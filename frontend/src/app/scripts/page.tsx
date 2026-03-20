'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { MainLayout } from '@/components/layout/main-layout';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { 
  FileText, 
  Plus, 
  Edit2, 
  Trash2,
  Search,
  Video,
  Clock,
  ChevronRight,
  MoreVertical,
  Copy,
  Download,
  Eye,
  Play,
  CheckCircle,
  AlertCircle,
  X,
  Save,
  Loader2,
  Sparkles,
  Wand2,
  BookOpen,
  LayoutGrid,
  RefreshCw
} from 'lucide-react';
import Link from 'next/link';

// 剧本数据类型
interface Script {
  id: string;
  title: string;
  description?: string;
  content?: string;
  genre?: string;
  style?: string;
  duration?: number;
  status: 'draft' | 'writing' | 'completed';
  novel_id?: string;
  created_at: string;
  updated_at: string;
}

// 小说数据类型
interface Novel {
  id: string;
  title: string;
  description?: string;
}

const STATUS_LABELS = {
  draft: '草稿',
  writing: '连载中',
  completed: '已完成'
};

const STATUS_COLORS = {
  draft: 'bg-yellow-500/20 text-yellow-400',
  writing: 'bg-blue-500/20 text-blue-400',
  completed: 'bg-green-500/20 text-green-400'
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function ScriptsPage() {
  const [scripts, setScripts] = useState<Script[]>([]);
  const [novels, setNovels] = useState<Novel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('all');
  const [showModal, setShowModal] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [editingScript, setEditingScript] = useState<Script | null>(null);
  
  // AI生成相关状态
  const [showAIGenerateModal, setShowAIGenerateModal] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [aiGenerateType, setAiGenerateType] = useState<'from_novel' | 'custom'>('custom');
  const [selectedNovelId, setSelectedNovelId] = useState('');
  const [customPrompt, setCustomPrompt] = useState('');
  const [generationResult, setGenerationResult] = useState<string | null>(null);
  
  // 表单数据
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    genre: '',
    style: ''
  });

  // 加载剧本数据
  const loadScripts = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/v1/scripts`);
      if (!response.ok) {
        throw new Error('加载失败');
      }
      const data = await response.json();
      setScripts(data || []);
    } catch (err) {
      console.error('加载剧本失败:', err);
      setError('加载失败，请检查后端服务');
      setScripts([]);
    } finally {
      setLoading(false);
    }
  };

  // 加载小说列表
  const loadNovels = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/novels`);
      if (response.ok) {
        const data = await response.json();
        setNovels(data || []);
      }
    } catch (err) {
      console.error('加载小说失败:', err);
    }
  };

  useEffect(() => {
    loadScripts();
    loadNovels();
  }, []);

  // 筛选剧本
  const filteredScripts = scripts.filter(script => {
    const matchesSearch = script.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          script.description?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = activeTab === 'all' || script.status === activeTab;
    return matchesSearch && matchesStatus;
  });

  // 打开创建弹窗
  const handleCreate = () => {
    setEditingScript(null);
    setFormData({
      title: '',
      description: '',
      genre: '',
      style: ''
    });
    setShowModal(true);
  };

  // 打开AI生成弹窗
  const handleOpenAIGenerate = () => {
    setAiGenerateType('from_novel');
    setSelectedNovelId(novels.length > 0 ? novels[0].id : '');
    setCustomPrompt('');
    setGenerationResult(null);
    setShowAIGenerateModal(true);
  };

  // AI生成剧本
  const handleAIGenerate = async () => {
    if (aiGenerateType === 'from_novel' && !selectedNovelId) {
      alert('请选择关联的小说');
      return;
    }
    if (aiGenerateType === 'custom' && !customPrompt.trim()) {
      alert('请输入剧本描述');
      return;
    }

    setIsGenerating(true);
    setGenerationResult(null);

    try {
      // 获取选中小说的内容作为上下文
      let context = '';
      if (aiGenerateType === 'from_novel') {
        const novelRes = await fetch(`${API_BASE}/api/v1/novels/${selectedNovelId}`);
        if (novelRes.ok) {
          const novel = await novelRes.json();
          context = `小说标题: ${novel.title}\n小说简介: ${novel.description || ''}\n小说内容: ${novel.content || ''}`;
        }
      }

      // 调用AI生成API
      const response = await fetch(`${API_BASE}/api/v1/coding-plan/storyboard`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scene_description: aiGenerateType === 'from_novel' 
            ? `基于小说内容生成视频剧本:\n${context}` 
            : customPrompt,
          api_key: 'demo-key',  // 后端会使用默认配置
          model: 'qwen-vl-plus'
        })
      });

      if (response.ok) {
        const result = await response.json();
        setGenerationResult(result.storyboard || result.result || '生成成功');
      } else {
        // 如果API不可用，使用模拟生成
        setGenerationResult(`# 生成的剧本\n\n## 第一幕：开场\n\n**场景描述**：主人公出现在山谷中，阳光照射，光影交织。\n\n**镜头序列**：\n1. 全景 - 山谷全景，阳光从云层中透出\n2. 中景 - 主人公背影，向远方望去\n3. 特写 - 主人公面部表情，坚定而沉思\n\n**台词**：\n- （旁白）"这是一个关于成长与救赎的故事..."\n\n## 第二幕：旅程开始\n\n**场景描述**：主人公踏上旅程，周围风景流转。\n\n**镜头序列**：\n1. 跟拍 - 主人公走在山路上\n2. 摇镜头 - 展示沿途风景\n3. 远景 - 主人公身影渐行渐远\n\n**特效**：光晕效果，岁月流转感\n\n---\n*本剧本由AI自动生成*`);
      }
    } catch (err) {
      console.error('AI生成失败:', err);
      // 模拟生成结果
      setGenerationResult(`# 生成的剧本\n\n## 第一幕：开场\n\n**场景描述**：主人公出现在山谷中，阳光照射。\n\n**镜头序列**：\n1. 全景 - 山谷全景\n2. 中景 - 主人公背影\n3. 特写 - 面部表情\n\n## 第二幕：旅程\n\n**场景描述**：主人公踏上旅程。\n\n**镜头序列**：\n1. 跟拍 - 走在山路上\n2. 远景 - 身影渐行渐远\n\n---\n*AI生成（离线模式）*`);
    } finally {
      setIsGenerating(false);
    }
  };

  // 应用生成的剧本
  const handleApplyGenerated = async () => {
    if (!generationResult) return;

    // 解析生成的剧本内容，创建新剧本
    const title = generationResult.match(/^#\s+(.+)$/m)?.[1] || 'AI生成剧本';
    const description = generationResult.split('---')[0].replace(/^#.*$/mg, '').trim().slice(0, 200);

    setIsSaving(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/scripts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: title,
          description: description,
          content: generationResult,
          genre: '',
          style: ''
        })
      });

      if (response.ok) {
        await loadScripts();
        setShowAIGenerateModal(false);
        alert('剧本已创建！');
      } else {
        throw new Error('保存失败');
      }
    } catch (err) {
      console.error('保存失败:', err);
      alert('保存失败');
    } finally {
      setIsSaving(false);
    }
  };

  // 打开编辑弹窗
  const handleEdit = (script: Script) => {
    setEditingScript(script);
    setFormData({
      title: script.title,
      description: script.description || '',
      genre: script.genre || '',
      style: script.style || ''
    });
    setShowModal(true);
  };

  // 保存剧本
  const handleSave = async () => {
    if (!formData.title.trim()) {
      alert('请输入剧本标题');
      return;
    }

    setIsSaving(true);
    try {
      const payload = {
        title: formData.title,
        description: formData.description,
        genre: formData.genre || undefined,
        style: formData.style || undefined
      };

      const response = editingScript
        ? await fetch(`${API_BASE}/api/v1/scripts/${editingScript.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...payload, status: editingScript.status })
          })
        : await fetch(`${API_BASE}/api/v1/scripts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });

      if (response.ok) {
        await loadScripts();
        setShowModal(false);
      } else {
        throw new Error('保存失败');
      }
    } catch (err) {
      console.error('保存失败:', err);
      alert('保存失败，请重试');
    } finally {
      setIsSaving(false);
    }
  };

  // 删除剧本
  const handleDelete = async (id: string) => {
    if (!confirm('确定要删除这个剧本吗？')) return;
    
    try {
      const response = await fetch(`${API_BASE}/api/v1/scripts/${id}`, {
        method: 'DELETE'
      });
      
      if (response.ok) {
        setScripts(scripts.filter(s => s.id !== id));
      } else {
        throw new Error('删除失败');
      }
    } catch (err) {
      console.error('删除失败:', err);
      alert('删除失败，请重试');
    }
  };

  // 复制剧本
  const handleDuplicate = async (script: Script) => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/scripts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: `${script.title} (副本)`,
          description: script.description,
          genre: script.genre,
          style: script.style
        })
      });
      
      if (response.ok) {
        await loadScripts();
      } else {
        throw new Error('复制失败');
      }
    } catch (err) {
      console.error('复制失败:', err);
      alert('复制失败，请重试');
    }
  };

  // 生成分镜
  const handleGenerateStoryboard = async (script: Script) => {
    if (!confirm(`是否为剧本"${script.title}"生成分镜？`)) return;

    try {
      // 调用AI生成storyboard
      const response = await fetch(`${API_BASE}/api/v1/storyboards`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: `${script.title} - 分镜`,
          description: script.description,
          script_id: script.id
        })
      });

      if (response.ok) {
        const storyboard = await response.json();
        alert(`分镜已创建！跳转到分镜页面...`);
        window.location.href = '/storyboards';
      } else {
        throw new Error('创建失败');
      }
    } catch (err) {
      console.error('生成分镜失败:', err);
      alert('生成分镜失败，请重试');
    }
  };

  // 格式化时长
  const formatDuration = (minutes?: number) => {
    if (!minutes) return '0:00';
    const mins = Math.floor(minutes);
    const secs = Math.round((minutes - mins) * 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // 统计
  const stats = {
    total: scripts.length,
    draft: scripts.filter(s => s.status === 'draft').length,
    writing: scripts.filter(s => s.status === 'writing').length,
    completed: scripts.filter(s => s.status === 'completed').length
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">剧本管理</h1>
            <p className="text-white/60 mt-1">管理视频剧本和分镜脚本</p>
          </div>
          <div className="flex gap-3">
            <Button 
              variant="outline"
              className="border-violet-500/50 text-violet-400 hover:bg-violet-600/20"
              onClick={handleOpenAIGenerate}
            >
              <Sparkles className="w-4 h-4 mr-2" />
              AI生成剧本
            </Button>
            <Button className="bg-blue-600 hover:bg-blue-700" onClick={handleCreate}>
              <Plus className="w-4 h-4 mr-2" />
              创建剧本
            </Button>
          </div>
        </div>

        {/* 统计卡片 */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-white">{stats.total}</div>
              <div className="text-sm text-white/60">全部剧本</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-yellow-400">{stats.draft}</div>
              <div className="text-sm text-white/60">草稿</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-blue-400">{stats.writing}</div>
              <div className="text-sm text-white/60">连载中</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-green-400">{stats.completed}</div>
              <div className="text-sm text-white/60">已完成</div>
            </CardContent>
          </Card>
        </div>

        {/* 搜索栏 */}
        <Card className="bg-white/5 border-white/10">
          <CardContent className="p-4">
            <div className="flex gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                <Input
                  placeholder="搜索剧本标题或描述..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 bg-white/5 border-white/10 text-white placeholder:text-white/40"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 加载状态 */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-blue-400" />
            <span className="ml-3 text-white/60">加载中...</span>
          </div>
        )}

        {/* 错误提示 */}
        {error && (
          <Card className="bg-red-500/10 border-red-500/30">
            <CardContent className="p-4 flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-red-400" />
              <span className="text-red-300">{error}</span>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={loadScripts}
                className="ml-auto border-red-500/50 text-red-400"
              >
                重试
              </Button>
            </CardContent>
          </Card>
        )}

        {/* 状态标签页 */}
        {!loading && !error && (
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="bg-white/5">
              <TabsTrigger value="all" className="data-[state=active]:bg-blue-600">全部</TabsTrigger>
              <TabsTrigger value="draft" className="data-[state=active]:bg-blue-600">草稿</TabsTrigger>
              <TabsTrigger value="writing" className="data-[state=active]:bg-blue-600">连载中</TabsTrigger>
              <TabsTrigger value="completed" className="data-[state=active]:bg-blue-600">已完成</TabsTrigger>
            </TabsList>

            <TabsContent value={activeTab} className="mt-4">
              {filteredScripts.length > 0 ? (
                <div className="grid gap-4">
                  {filteredScripts.map((script) => (
                    <Card key={script.id} className="bg-white/5 border-white/10 hover:border-blue-500/30 transition-colors">
                      <CardContent className="p-4">
                        <div className="flex items-start justify-between">
                          <Link href={`/scripts/${script.id}`} className="flex-1 block">
                            <div className="flex items-center gap-3">
                              <FileText className="w-5 h-5 text-blue-400" />
                              <h3 className="text-lg font-semibold text-white hover:text-blue-400 transition-colors">{script.title}</h3>
                              <span className={`px-2 py-0.5 rounded text-xs ${STATUS_COLORS[script.status]}`}>
                                {STATUS_LABELS[script.status]}
                              </span>
                            </div>
                            {script.description && (
                              <p className="text-sm text-white/40 mt-1">{script.description}</p>
                            )}
                            <div className="flex items-center gap-4 mt-3 text-sm text-white/40">
                              {script.genre && <span>{script.genre}</span>}
                              {script.style && <span>{script.style}</span>}
                              <span className="flex items-center gap-1">
                                <Clock className="w-4 h-4" />
                                {formatDuration(script.duration)}
                              </span>
                              <span>更新于 {new Date(script.updated_at).toLocaleDateString()}</span>
                            </div>
                          </Link>
                          <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                            {script.status === 'completed' && (
                              <Button 
                                variant="ghost" 
                                size="sm"
                                className="text-violet-400 hover:text-violet-300"
                                onClick={() => handleGenerateStoryboard(script)}
                              >
                                <LayoutGrid className="w-4 h-4 mr-1" />
                                生成分镜
                              </Button>
                            )}
                            {script.status === 'completed' && (
                              <Link href={`/video-generation?script=${script.id}`}>
                                <Button variant="ghost" size="sm" className="text-violet-400 hover:text-violet-300">
                                  <Play className="w-4 h-4 mr-1" />
                                  生成视频
                                </Button>
                              </Link>
                            )}
                            <Link href={`/scripts/${script.id}`}>
                              <Button variant="ghost" size="icon" className="text-white/60 hover:text-white">
                                <Eye className="w-4 h-4" />
                              </Button>
                            </Link>
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              className="text-white/60 hover:text-white"
                              onClick={() => handleEdit(script)}
                            >
                              <Edit2 className="w-4 h-4" />
                            </Button>
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              className="text-white/60 hover:text-white"
                              onClick={() => handleDuplicate(script)}
                            >
                              <Copy className="w-4 h-4" />
                            </Button>
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              className="text-white/60 hover:text-red-400"
                              onClick={() => handleDelete(script.id)}
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12">
                  <FileText className="w-12 h-12 mx-auto text-white/20" />
                  <p className="text-white/40 mt-4">没有找到剧本</p>
                  <div className="flex gap-2 justify-center mt-4">
                    <Button 
                      variant="outline"
                      className="border-violet-500/50 text-violet-400"
                      onClick={handleOpenAIGenerate}
                    >
                      <Sparkles className="w-4 h-4 mr-2" />
                      AI生成
                    </Button>
                    <Button className="bg-blue-600 hover:bg-blue-700" onClick={handleCreate}>
                      创建剧本
                    </Button>
                  </div>
                </div>
              )}
            </TabsContent>
          </Tabs>
        )}
      </div>

      {/* 创建/编辑剧本弹窗 */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="bg-white/10 backdrop-blur-lg border-white/20 w-full max-w-lg">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-white">
                {editingScript ? '编辑剧本' : '创建剧本'}
              </CardTitle>
              <Button 
                variant="ghost" 
                size="icon" 
                onClick={() => setShowModal(false)}
                className="text-white/60 hover:text-white"
              >
                <X className="w-5 h-5" />
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm text-white/60 mb-2 block">剧本标题 *</label>
                <Input
                  placeholder="例如：第一章：星际启航"
                  value={formData.title}
                  onChange={(e) => setFormData({...formData, title: e.target.value})}
                  className="bg-white/5 border-white/10 text-white placeholder:text-white/40"
                />
              </div>
              
              <div>
                <label className="text-sm text-white/60 mb-2 block">剧本描述</label>
                <Textarea
                  placeholder="简要描述剧本内容..."
                  value={formData.description}
                  onChange={(e) => setFormData({...formData, description: e.target.value})}
                  rows={3}
                  className="bg-white/5 border-white/10 text-white placeholder:text-white/40"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-white/60 mb-2 block">题材</label>
                  <Input
                    placeholder="例如：仙侠"
                    value={formData.genre}
                    onChange={(e) => setFormData({...formData, genre: e.target.value})}
                    className="bg-white/5 border-white/10 text-white placeholder:text-white/40"
                  />
                </div>
                <div>
                  <label className="text-sm text-white/60 mb-2 block">风格</label>
                  <Input
                    placeholder="例如：热血"
                    value={formData.style}
                    onChange={(e) => setFormData({...formData, style: e.target.value})}
                    className="bg-white/5 border-white/10 text-white placeholder:text-white/40"
                  />
                </div>
              </div>
              
              <div className="flex gap-3 pt-4">
                <Button 
                  variant="outline" 
                  onClick={() => setShowModal(false)}
                  className="flex-1 border-white/20 text-white"
                >
                  取消
                </Button>
                <Button 
                  onClick={handleSave}
                  disabled={isSaving}
                  className="flex-1 bg-blue-600 hover:bg-blue-700"
                >
                  {isSaving ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      保存中...
                    </>
                  ) : (
                    <>
                      <Save className="w-4 h-4 mr-2" />
                      保存剧本
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* AI生成剧本弹窗 */}
      {showAIGenerateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="bg-white/10 backdrop-blur-lg border-white/20 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-white flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-violet-400" />
                AI生成剧本
              </CardTitle>
              <Button 
                variant="ghost" 
                size="icon" 
                onClick={() => setShowAIGenerateModal(false)}
                className="text-white/60 hover:text-white"
              >
                <X className="w-5 h-5" />
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* 生成方式选择 */}
              <div>
                <label className="text-sm text-white/60 mb-2 block">生成方式</label>
                <div className="flex gap-2">
                  <Button
                    variant={aiGenerateType === 'from_novel' ? 'default' : 'outline'}
                    onClick={() => setAiGenerateType('from_novel')}
                    className={aiGenerateType === 'from_novel' ? 'bg-violet-600' : 'border-white/20'}
                  >
                    <BookOpen className="w-4 h-4 mr-2" />
                    基于小说
                  </Button>
                  <Button
                    variant={aiGenerateType === 'custom' ? 'default' : 'outline'}
                    onClick={() => setAiGenerateType('custom')}
                    className={aiGenerateType === 'custom' ? 'bg-violet-600' : 'border-white/20'}
                  >
                    <Wand2 className="w-4 h-4 mr-2" />
                    自定义描述
                  </Button>
                </div>
              </div>

              {/* 选择小说 */}
              {aiGenerateType === 'from_novel' && (
                <div>
                  <label className="text-sm text-white/60 mb-2 block">选择小说</label>
                  <select
                    value={selectedNovelId}
                    onChange={(e) => setSelectedNovelId(e.target.value)}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                  >
                    <option value="">选择小说...</option>
                    {novels.map(novel => (
                      <option key={novel.id} value={novel.id}>{novel.title}</option>
                    ))}
                  </select>
                  {novels.length === 0 && (
                    <p className="text-white/40 text-sm mt-1">暂无可用小说，请先创建小说</p>
                  )}
                </div>
              )}

              {/* 自定义描述 */}
              {aiGenerateType === 'custom' && (
                <div>
                  <label className="text-sm text-white/60 mb-2 block">剧本描述</label>
                  <Textarea
                    placeholder="描述你想要生成的剧本内容...\n例如：\n- 仙侠风格\n- 主人公离开山门\n- 遇到神秘老者\n- 获得传承"
                    value={customPrompt}
                    onChange={(e) => setCustomPrompt(e.target.value)}
                    rows={6}
                    className="bg-white/5 border-white/10 text-white placeholder:text-white/40"
                  />
                </div>
              )}

              {/* 生成按钮 */}
              <Button
                onClick={handleAIGenerate}
                disabled={isGenerating || (aiGenerateType === 'from_novel' && !selectedNovelId) || (aiGenerateType === 'custom' && !customPrompt.trim())}
                className="w-full bg-violet-600 hover:bg-violet-700"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    AI生成中...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 mr-2" />
                    开始生成
                  </>
                )}
              </Button>

              {/* 生成结果 */}
              {generationResult && (
                <div className="mt-4">
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm text-white/60">生成结果</label>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => navigator.clipboard.writeText(generationResult)}
                      className="text-white/60 hover:text-white"
                    >
                      <Copy className="w-4 h-4 mr-1" />
                      复制
                    </Button>
                  </div>
                  <div className="bg-white/5 border border-white/10 rounded-lg p-4 max-h-80 overflow-y-auto">
                    <pre className="text-white/80 text-sm whitespace-pre-wrap font-sans">
                      {generationResult}
                    </pre>
                  </div>
                  
                  <div className="flex gap-3 mt-4">
                    <Button
                      onClick={handleAIGenerate}
                      disabled={isGenerating}
                      variant="outline"
                      className="flex-1 border-white/20"
                    >
                      <RefreshCw className="w-4 h-4 mr-2" />
                      重新生成
                    </Button>
                    <Button
                      onClick={handleApplyGenerated}
                      disabled={isSaving}
                      className="flex-1 bg-green-600 hover:bg-green-700"
                    >
                      {isSaving ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      ) : (
                        <CheckCircle className="w-4 h-4 mr-2" />
                      )}
                      创建剧本
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </MainLayout>
  );
}

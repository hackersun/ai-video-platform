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
  Loader2
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('all');
  const [showModal, setShowModal] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [editingScript, setEditingScript] = useState<Script | null>(null);
  
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

  useEffect(() => {
    loadScripts();
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
          <Button className="bg-blue-600 hover:bg-blue-700" onClick={handleCreate}>
            <Plus className="w-4 h-4 mr-2" />
            创建剧本
          </Button>
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
                          <div className="flex-1">
                            <div className="flex items-center gap-3">
                              <FileText className="w-5 h-5 text-blue-400" />
                              <h3 className="text-lg font-semibold text-white">{script.title}</h3>
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
                          </div>
                          <div className="flex items-center gap-2">
                            {script.status === 'completed' && (
                              <Link href={`/video-generation?script=${script.id}`}>
                                <Button variant="ghost" size="sm" className="text-violet-400 hover:text-violet-300">
                                  <Play className="w-4 h-4 mr-1" />
                                  生成视频
                                </Button>
                              </Link>
                            )}
                            <Button variant="ghost" size="icon" className="text-white/60 hover:text-white">
                              <Eye className="w-4 h-4" />
                            </Button>
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
                  <Button className="mt-4 bg-blue-600 hover:bg-blue-700" onClick={handleCreate}>
                    创建第一个剧本
                  </Button>
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
    </MainLayout>
  );
}

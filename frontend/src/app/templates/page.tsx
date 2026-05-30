'use client';

import { useEffect, useMemo, useState } from 'react';
import { MainLayout } from '@/components/layout/main-layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Book, Film, MessageSquare, Users, Mountain,
  Search, Plus, Edit2, Trash2, Save, Copy, Check,
  Sparkles, Star, RefreshCw, X, Eye, CopyIcon
} from 'lucide-react';
import apiClient from '@/lib/api-client';
import { useToast } from '@/components/ui/toast';

// 分类配置
const CATEGORY_CONFIG = [
  { id: 'genre', name: '题材模板', icon: Book, color: 'violet' },
  { id: 'shot', name: '镜头模板', icon: Film, color: 'blue' },
  { id: 'prompt', name: '提示词模板', icon: MessageSquare, color: 'green' },
  { id: 'character', name: '角色模板', icon: Users, color: 'orange' },
  { id: 'scene', name: '场景模板', icon: Mountain, color: 'pink' },
];

// 模板类型定义
interface Template {
  id: string;
  user_id: string;
  name: string;
  description?: string;
  category?: string;
  tags: string[];
  content: any;
  usage_count: number;
  rating: number;
  is_public: boolean;
  is_featured: boolean;
  created_at: string;
  updated_at: string;
}

// 创建模板表单
interface TemplateForm {
  name: string;
  description: string;
  category: string;
  tags: string;
  content: any;
  is_public: boolean;
}

const emptyForm: TemplateForm = {
  name: '',
  description: '',
  category: 'genre',
  tags: '',
  content: {},
  is_public: false,
};

export default function TemplatesPage() {
  const { toast } = useToast();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [categories, setCategories] = useState(CATEGORY_CONFIG);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [editingTemplate, setEditingTemplate] = useState<Template | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [formData, setFormData] = useState<TemplateForm>(emptyForm);

  // 加载模板列表
  const loadTemplates = async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (activeCategory !== 'all') {
        params.category = activeCategory;
      }
      if (searchQuery.trim()) {
        params.search = searchQuery.trim();
      }
      params.include_presets = true;

      const data = await apiClient.getTemplates(params);
      setTemplates(Array.isArray(data) ? data : []);
    } catch (err: any) {
      toast({ title: '加载失败', description: err?.message || '请稍后重试', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTemplates();
  }, [activeCategory, searchQuery]);

  // 筛选模板
  const filteredTemplates = useMemo(() => {
    return templates.filter(t => {
      if (activeCategory !== 'all' && t.category !== activeCategory) return false;
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        return (
          t.name.toLowerCase().includes(query) ||
          (t.description && t.description.toLowerCase().includes(query)) ||
          t.tags.some(tag => tag.toLowerCase().includes(query))
        );
      }
      return true;
    });
  }, [templates, activeCategory, searchQuery]);

  // 按分类分组
  const groupedTemplates = useMemo(() => {
    const groups: Record<string, Template[]> = {
      preset: [],
      user: [],
    };
    filteredTemplates.forEach(t => {
      if (t.id.startsWith('preset_')) {
        groups.preset.push(t);
      } else {
        groups.user.push(t);
      }
    });
    return groups;
  }, [filteredTemplates]);

  // 开始创建
  const handleStartCreate = () => {
    setFormData(emptyForm);
    setEditingTemplate(null);
    setShowCreateForm(true);
  };

  // 编辑模板
  const handleEdit = (template: Template) => {
    if (template.id.startsWith('preset_')) {
      // 预置模板，复制一份到用户库
      setFormData({
        name: `${template.name} (副本)`,
        description: template.description || '',
        category: template.category || 'genre',
        tags: template.tags.join('，'),
        content: { ...template.content },
        is_public: false,
      });
      setEditingTemplate(null);
    } else {
      setFormData({
        name: template.name,
        description: template.description || '',
        category: template.category || 'genre',
        tags: template.tags.join('，'),
        content: { ...template.content },
        is_public: template.is_public,
      });
      setEditingTemplate(template);
    }
    setShowCreateForm(true);
  };

  // 保存模板
  const handleSave = async () => {
    if (!formData.name.trim()) {
      toast({ title: '请输入模板名称', type: 'error' });
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: formData.name.trim(),
        description: formData.description.trim() || undefined,
        category: formData.category,
        tags: formData.tags.split(/[，,]/).map(t => t.trim()).filter(Boolean),
        content: formData.content,
        is_public: formData.is_public,
      };

      if (editingTemplate) {
        await apiClient.updateTemplate(editingTemplate.id, payload);
        toast({ title: '模板已更新', type: 'success' });
      } else {
        await apiClient.createTemplate(payload);
        toast({ title: '模板已创建', type: 'success' });
      }

      setShowCreateForm(false);
      setEditingTemplate(null);
      setFormData(emptyForm);
      await loadTemplates();
    } catch (err: any) {
      toast({ title: '保存失败', description: err?.message || '请稍后重试', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  // 删除模板
  const handleDelete = async (template: Template) => {
    if (template.id.startsWith('preset_')) return;
    try {
      await apiClient.deleteTemplate(template.id);
      toast({ title: '模板已删除', type: 'success' });
      await loadTemplates();
    } catch (err: any) {
      toast({ title: '删除失败', description: err?.message || '请稍后重试', type: 'error' });
    }
  };

  // 复制预置模板
  const handleClone = async (template: Template) => {
    try {
      await apiClient.cloneTemplate(template.id);
      toast({ title: '模板已复制到您的模板库', type: 'success' });
      await loadTemplates();
    } catch (err: any) {
      toast({ title: '复制失败', description: err?.message || '请稍后重试', type: 'error' });
    }
  };

  // 使用模板（增加计数）
  const handleUse = async (template: Template) => {
    try {
      await apiClient.useTemplate(template.id);
    } catch (err) {
      // 使用计数失败不影响用户体验
    }
    // 根据模板类型跳转或应用
    toast({
      title: '模板已应用',
      description: `已使用 "${template.name}" 模板`,
      type: 'success'
    });
  };

  // 取消编辑
  const handleCancel = () => {
    setShowCreateForm(false);
    setEditingTemplate(null);
    setFormData(emptyForm);
  };

  // 渲染模板卡片
  const renderTemplateCard = (template: Template, showActions = true) => {
    const isPreset = template.id.startsWith('preset_');
    const categoryConfig = CATEGORY_CONFIG.find(c => c.id === template.category);
    const IconComponent = categoryConfig?.icon || Book;

    return (
      <Card
        key={template.id}
        className="bg-white/5 border-white/10 hover:bg-white/10 transition-colors"
      >
        <CardHeader className="pb-2">
          <CardTitle className="text-white flex items-center gap-2 text-base">
            <IconComponent className={`w-5 h-5 ${
              categoryConfig?.color === 'violet' ? 'text-violet-400' :
              categoryConfig?.color === 'blue' ? 'text-blue-400' :
              categoryConfig?.color === 'green' ? 'text-green-400' :
              categoryConfig?.color === 'orange' ? 'text-orange-400' :
              'text-pink-400'
            }`} />
            {template.name}
            {isPreset && (
              <Badge variant="outline" className="text-yellow-400 border-yellow-400/50">
                预置
              </Badge>
            )}
            {template.is_public && !isPreset && (
              <Badge variant="success" className="bg-green-500/20 text-green-400 border-green-500/30">
                公开
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-white/60 min-h-[40px] line-clamp-2">
            {template.description || '暂无描述'}
          </p>

          {/* 标签 */}
          <div className="flex flex-wrap gap-2">
            {template.tags.slice(0, 4).map((tag, idx) => (
              <Badge key={idx} variant="outline" className="text-white/60 border-white/20">
                {tag}
              </Badge>
            ))}
          </div>

          {/* 统计信息 */}
          <div className="flex items-center justify-between text-sm text-white/50">
            <span>{template.usage_count} 次使用</span>
            {showActions && (
              <div className="flex items-center gap-1">
                {isPreset ? (
                  <>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-white/60 hover:text-white"
                      onClick={() => handleEdit(template)}
                      title="复制并编辑"
                    >
                      <Copy className="w-4 h-4 mr-1" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-green-400 hover:text-green-300"
                      onClick={() => handleClone(template)}
                      title="复制到我的模板库"
                    >
                      <CopyIcon className="w-4 h-4 mr-1" />
                    </Button>
                  </>
                ) : (
                  <>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-white/60 hover:text-white"
                      onClick={() => handleEdit(template)}
                    >
                      <Edit2 className="w-4 h-4 mr-1" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-300 hover:text-red-200"
                      onClick={() => handleDelete(template)}
                    >
                      <Trash2 className="w-4 h-4 mr-1" />
                    </Button>
                  </>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    );
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 标题区 */}
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-white flex items-center gap-3">
              <Sparkles className="w-8 h-8 text-violet-400" />
              模板市场
            </h1>
            <p className="text-white/60 mt-1">公共资产和提示词模板，快速开始创作</p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="border-white/20 text-white"
              onClick={() => loadTemplates()}
              disabled={loading}
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              刷新
            </Button>
            <Button
              className="bg-violet-600 hover:bg-violet-700"
              onClick={handleStartCreate}
            >
              <Plus className="w-4 h-4 mr-2" />
              创建模板
            </Button>
          </div>
        </div>

        {/* 创建/编辑表单 */}
        {showCreateForm && (
          <Card className="bg-white/5 border-white/10">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                {editingTemplate ? <Edit2 className="w-5 h-5" /> : <Plus className="w-5 h-5 text-violet-400" />}
                {editingTemplate ? '编辑模板' : '创建新模板'}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-white/60 mb-1">模板名称 *</label>
                  <Input
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="输入模板名称"
                    className="bg-white/5 border-white/10 text-white"
                  />
                </div>
                <div>
                  <label className="block text-sm text-white/60 mb-1">模板分类</label>
                  <select
                    value={formData.category}
                    onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                  >
                    {CATEGORY_CONFIG.map(cat => (
                      <option key={cat.id} value={cat.id}>{cat.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm text-white/60 mb-1">模板描述</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="简要描述模板的用途和适用场景"
                  rows={2}
                  className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-white/40 resize-none"
                />
              </div>

              <div>
                <label className="block text-sm text-white/60 mb-1">标签</label>
                <Input
                  value={formData.tags}
                  onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
                  placeholder="用逗号分隔，如：都市,爱情,现代"
                  className="bg-white/5 border-white/10 text-white"
                />
              </div>

              <div>
                <label className="block text-sm text-white/60 mb-1">模板内容 (JSON)</label>
                <Textarea
                  value={JSON.stringify(formData.content, null, 2)}
                  onChange={(e) => {
                    try {
                      setFormData({ ...formData, content: JSON.parse(e.target.value) });
                    } catch {
                      // 暂时保留原始输入
                    }
                  }}
                  placeholder='{"key": "value"}'
                  rows={8}
                  className="bg-white/5 border-white/10 text-white placeholder:text-white/40 font-mono text-sm"
                />
              </div>

              <label className="flex items-center gap-2 text-sm text-white/70">
                <input
                  type="checkbox"
                  checked={formData.is_public}
                  onChange={(e) => setFormData({ ...formData, is_public: e.target.checked })}
                  className="w-4 h-4 accent-violet-500"
                />
                设为公开模板（其他用户可使用）
              </label>

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={handleCancel} className="border-white/20 text-white">
                  取消
                </Button>
                <Button
                  className="bg-violet-600 hover:bg-violet-700"
                  onClick={handleSave}
                  disabled={saving}
                >
                  <Save className="w-4 h-4 mr-2" />
                  {saving ? '保存中…' : '保存模板'}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* 分类过滤 */}
        <div className="flex flex-wrap gap-2">
          <Button
            variant={activeCategory === 'all' ? 'default' : 'outline'}
            className={activeCategory === 'all' ? 'bg-violet-600' : 'border-white/20 text-white'}
            onClick={() => setActiveCategory('all')}
          >
            全部
          </Button>
          {CATEGORY_CONFIG.map(cat => {
            const Icon = cat.icon;
            return (
              <Button
                key={cat.id}
                variant={activeCategory === cat.id ? 'default' : 'outline'}
                className={`${activeCategory === cat.id ? 'bg-violet-600' : 'border-white/20 text-white'}`}
                onClick={() => setActiveCategory(cat.id)}
              >
                <Icon className="w-4 h-4 mr-1" />
                {cat.name}
              </Button>
            );
          })}
        </div>

        {/* 搜索框 */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索模板名称、描述或标签…"
            className="pl-10 bg-white/5 border-white/10 text-white placeholder:text-white/40"
          />
        </div>

        {/* 模板列表 */}
        {loading ? (
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-8 text-center text-white/50">
              加载中…
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-6">
            {/* 预置模板 */}
            {groupedTemplates.preset.length > 0 && (
              <section className="space-y-3">
                <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                  <Star className="w-5 h-5 text-yellow-400" />
                  公共模板
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {groupedTemplates.preset.map(t => renderTemplateCard(t))}
                </div>
              </section>
            )}

            {/* 用户模板 */}
            {groupedTemplates.user.length > 0 && (
              <section className="space-y-3">
                <h2 className="text-lg font-semibold text-white">我的模板</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {groupedTemplates.user.map(t => renderTemplateCard(t))}
                </div>
              </section>
            )}

            {/* 空状态 */}
            {filteredTemplates.length === 0 && (
              <Card className="bg-white/5 border-white/10">
                <CardContent className="p-8 text-center text-white/50">
                  <Sparkles className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p className="text-lg">暂无模板</p>
                  <p className="text-sm mt-2">点击「创建模板」开始，或选择上方分类浏览预置模板</p>
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </div>
    </MainLayout>
  );
}
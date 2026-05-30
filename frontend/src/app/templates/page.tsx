'use client';

import { useEffect, useMemo, useState } from 'react';
import { MainLayout } from '@/components/layout/main-layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Check, Edit3, LayoutTemplate, Search, Star, Trash2, Plus, Save, RefreshCw, Sparkles, X } from 'lucide-react';
import apiClient from '@/lib/api-client';

interface SystemTemplate {
  id: string;
  name: string;
  description: string;
  genre_tags: string[];
  keywords: string[];
  shot_count: number;
  is_system?: boolean;
  is_overridden?: boolean;
  override_asset_id?: string;
  prompt_template?: string;
  shot_template?: { system_template_id?: string; shot_count?: number; template_type?: string; keywords?: string[]; shots?: any[] };
}

interface AssetTemplate {
  id: string;
  name: string;
  description?: string;
  tags?: string[];
  style_tags?: string[];
  prompt_template?: string;
  shot_template?: { system_template_id?: string; shot_count?: number; template_type?: string; shots?: any[] };
  is_public?: boolean;
}

const templateTypes = [
  { value: 'storyboard', label: '分镜模板' },
  { value: 'shot', label: '镜头模板' },
  { value: 'prompt', label: '提示词模板' },
];

const emptyTemplateForm = {
  name: '',
  template_type: 'storyboard',
  tags: '',
  description: '',
  prompt_template: '',
  shot_count: 4,
  is_public: false,
};

function parseTags(value: string) {
  return value.split(/[，,]/).map((item) => item.trim()).filter(Boolean);
}

function clampShotCount(value: number) {
  return Math.max(1, Math.min(20, Number(value) || 4));
}

function normalizeTemplateType(styleTags?: string[], fallback = 'storyboard') {
  return styleTags?.find((tag) => tag && tag !== 'system_override' && !tag.startsWith('system_template:')) || fallback;
}

function isSystemOverrideAsset(template: AssetTemplate) {
  return Boolean(template.shot_template?.system_template_id || template.style_tags?.includes('system_override'));
}

function buildTemplateShots(shotCount: number, existingShots: any[] = []) {
  return Array.from({ length: shotCount }).map((_, index) => ({
    duration: 4,
    shot_type: index === 0 ? 'establishing' : index === shotCount - 1 ? 'summary' : 'detail',
    camera_angle: index === 0 ? 'wide' : 'medium',
    camera_movement: index === 0 ? 'static' : 'zoom_in',
    emotion: 'tense',
    lighting: 'natural',
    color_grading: 'cinematic',
    visual_focus: '承接当前情节点，保持人物、场景和道具连续',
    dialogue_role: index === 0 || index === shotCount - 1 ? '旁白' : '角色',
    ...(existingShots[index] || {}),
    shot_number: index + 1,
  }));
}

export default function TemplatesPage() {
  const [systemTemplates, setSystemTemplates] = useState<SystemTemplate[]>([]);
  const [customTemplates, setCustomTemplates] = useState<AssetTemplate[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState<'all' | 'system' | 'custom'>('all');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState(emptyTemplateForm);
  const [form, setForm] = useState(emptyTemplateForm);

  const loadTemplates = async (resetMessage = true) => {
    setLoading(true);
    if (resetMessage) {
      setMessage(null);
    }
    try {
      const [system, custom] = await Promise.all([
        apiClient.getStoryboardTemplates(),
        apiClient.getAssets({ category: 'template', include_public: false, limit: 100 }),
      ]);
      setSystemTemplates(system || []);
      setCustomTemplates((custom || []).filter((template) => !isSystemOverrideAsset(template)));
    } catch (err: any) {
      setMessage(err?.message || '模板加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTemplates();
  }, []);

  const filteredSystemTemplates = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (activeFilter === 'custom') return [];
    return systemTemplates.filter((template) => {
      if (!query) return true;
      return [template.name, template.description, ...(template.genre_tags || []), ...(template.keywords || [])]
        .join(' ')
        .toLowerCase()
        .includes(query);
    });
  }, [activeFilter, searchQuery, systemTemplates]);

  const filteredCustomTemplates = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (activeFilter === 'system') return [];
    return customTemplates.filter((template) => {
      if (!query) return true;
      return [template.name, template.description || '', ...(template.tags || []), ...(template.style_tags || [])]
        .join(' ')
        .toLowerCase()
        .includes(query);
    });
  }, [activeFilter, customTemplates, searchQuery]);

  const createTemplate = async () => {
    if (!form.name.trim()) {
      setMessage('请输入模板名称');
      return;
    }
    setSaving(true);
    setMessage(null);
    try {
      const tags = parseTags(form.tags);
      const shotCount = clampShotCount(form.shot_count);
      await apiClient.createAsset({
        category: 'template',
        asset_type: 'text',
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        tags,
        style_tags: [form.template_type],
        prompt_template: form.prompt_template.trim() || '{{角色}}在{{场景}}中推进{{事件}}',
        shot_template: {
          shot_count: shotCount,
          template_type: form.template_type,
          shots: buildTemplateShots(shotCount),
        },
        is_public: form.is_public,
      });
      setForm(emptyTemplateForm);
      setMessage('模板已保存');
      await loadTemplates(false);
    } catch (err: any) {
      setMessage(err?.message || '模板保存失败');
    } finally {
      setSaving(false);
    }
  };

  const deleteTemplate = async (templateId: string) => {
    setMessage(null);
    try {
      await apiClient.deleteAsset(templateId);
      setCustomTemplates((prev) => prev.filter((item) => item.id !== templateId));
      setMessage('模板已归档');
    } catch (err: any) {
      setMessage(err?.message || '模板删除失败');
    }
  };

  const startEdit = (template: AssetTemplate) => {
    const templateType = normalizeTemplateType(template.style_tags, template.shot_template?.template_type || 'storyboard');
    setEditingId(template.id);
    setEditForm({
      name: template.name,
      template_type: templateType,
      tags: (template.tags || []).join('，'),
      description: template.description || '',
      prompt_template: template.prompt_template || '',
      shot_count: template.shot_template?.shot_count || template.shot_template?.shots?.length || 4,
      is_public: Boolean(template.is_public),
    });
    setMessage(null);
  };

  const startEditSystem = (template: SystemTemplate) => {
    setEditingId(`system:${template.id}`);
    setEditForm({
      name: template.name,
      template_type: template.shot_template?.template_type || 'storyboard',
      tags: (template.genre_tags || []).join('，'),
      description: template.description || '',
      prompt_template: template.prompt_template || '',
      shot_count: template.shot_template?.shot_count || template.shot_template?.shots?.length || template.shot_count || 4,
      is_public: false,
    });
    setMessage(null);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditForm(emptyTemplateForm);
  };

  const saveTemplateEdit = async (templateId: string, existingShots: any[] = []) => {
    if (!editForm.name.trim()) {
      setMessage('请输入模板名称');
      return;
    }
    setSaving(true);
    setMessage(null);
    try {
      const tags = parseTags(editForm.tags);
      const shotCount = clampShotCount(editForm.shot_count);
      const updated = await apiClient.updateAsset(templateId, {
        name: editForm.name.trim(),
        description: editForm.description.trim() || undefined,
        tags,
        style_tags: [editForm.template_type],
        prompt_template: editForm.prompt_template.trim() || undefined,
        shot_template: {
          shot_count: shotCount,
          template_type: editForm.template_type,
          shots: buildTemplateShots(shotCount, existingShots),
        },
        is_public: editForm.is_public,
      });
      setCustomTemplates((prev) => prev.map((template) => template.id === templateId ? updated : template));
      setMessage('模板已更新');
      cancelEdit();
    } catch (err: any) {
      setMessage(err?.message || '模板更新失败');
    } finally {
      setSaving(false);
    }
  };

  const saveSystemTemplateEdit = async (template: SystemTemplate) => {
    if (!editForm.name.trim()) {
      setMessage('请输入模板名称');
      return;
    }
    setSaving(true);
    setMessage(null);
    try {
      const tags = parseTags(editForm.tags);
      const shotCount = clampShotCount(editForm.shot_count);
      const existingShots = template.shot_template?.shots || [];
      const payload = {
        name: editForm.name.trim(),
        description: editForm.description.trim() || undefined,
        tags,
        style_tags: [editForm.template_type, 'system_override', `system_template:${template.id}`],
        prompt_template: editForm.prompt_template.trim() || undefined,
        shot_template: {
          system_template_id: template.id,
          shot_count: shotCount,
          template_type: editForm.template_type,
          keywords: tags,
          shots: buildTemplateShots(shotCount, existingShots),
        },
        is_public: false,
      };

      if (template.override_asset_id) {
        await apiClient.updateAsset(template.override_asset_id, payload);
      } else {
        await apiClient.createAsset({
          category: 'template',
          asset_type: 'text',
          ...payload,
        });
      }
      setMessage('系统模板已定制');
      cancelEdit();
      await loadTemplates(false);
    } catch (err: any) {
      setMessage(err?.message || '系统模板保存失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-white">模板库</h1>
            <p className="text-white/60 mt-1">系统预制模板与项目自定义模板统一管理</p>
          </div>
          <Button variant="outline" className="border-white/20 text-white" onClick={() => loadTemplates()} disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </Button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-6">
          <Card className="bg-white/5 border-white/10">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Plus className="w-5 h-5 text-violet-400" />
                新建自定义模板
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="模板名称" className="bg-white/5 border-white/10 text-white" />
              <Select value={form.template_type} onChange={(event) => setForm({ ...form, template_type: event.target.value })} options={templateTypes} />
              <Input value={form.tags} onChange={(event) => setForm({ ...form, tags: event.target.value })} placeholder="标签，用逗号分隔" className="bg-white/5 border-white/10 text-white" />
              <Input type="number" min={1} max={20} value={form.shot_count} onChange={(event) => setForm({ ...form, shot_count: Number(event.target.value) })} className="bg-white/5 border-white/10 text-white" />
              <Textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="模板用途和适用场景" />
              <Textarea value={form.prompt_template} onChange={(event) => setForm({ ...form, prompt_template: event.target.value })} placeholder="提示词模板，例如：{{角色}}在{{场景}}中{{动作}}" />
              <label className="flex items-center gap-2 text-sm text-white/70">
                <input type="checkbox" checked={form.is_public} onChange={(event) => setForm({ ...form, is_public: event.target.checked })} />
                发布为团队/公开可复用模板
              </label>
              <Button className="w-full bg-violet-600 hover:bg-violet-700" onClick={createTemplate} disabled={saving}>
                <Save className="w-4 h-4 mr-2" />
                {saving ? '保存中…' : '保存模板'}
              </Button>
              {message && <div className="text-sm text-white/70">{message}</div>}
            </CardContent>
          </Card>

          <div className="space-y-4">
            <div className="flex flex-col md:flex-row gap-3">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                <Input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="搜索模板…" className="pl-10 bg-white/5 border-white/10 text-white placeholder:text-white/40" />
              </div>
              <Button variant="outline" className="border-white/20 text-white" onClick={() => setActiveFilter('all')}>全部</Button>
              <Button variant="outline" className="border-white/20 text-white" onClick={() => setActiveFilter('system')}>系统</Button>
              <Button variant="outline" className="border-white/20 text-white" onClick={() => setActiveFilter('custom')}>自定义</Button>
            </div>

            {loading ? (
              <Card className="bg-white/5 border-white/10"><CardContent className="p-8 text-center text-white/50">加载中…</CardContent></Card>
            ) : (
              <>
                {filteredSystemTemplates.length > 0 && (
                  <section className="space-y-3">
                    <h2 className="text-lg font-semibold text-white flex items-center gap-2"><Sparkles className="w-5 h-5 text-violet-400" />系统预制模板</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                      {filteredSystemTemplates.map((template) => (
                        <Card key={template.id} className="bg-white/5 border-white/10 hover:bg-white/10 transition-colors">
                          {editingId === `system:${template.id}` ? (
                            <CardContent className="space-y-3 p-4">
                              <Input value={editForm.name} onChange={(event) => setEditForm({ ...editForm, name: event.target.value })} placeholder="模板名称" className="bg-white/5 border-white/10 text-white" />
                              <Select value={editForm.template_type} onChange={(event) => setEditForm({ ...editForm, template_type: event.target.value })} options={templateTypes} />
                              <Input value={editForm.tags} onChange={(event) => setEditForm({ ...editForm, tags: event.target.value })} placeholder="标签，用逗号分隔" className="bg-white/5 border-white/10 text-white" />
                              <Input type="number" min={1} max={20} value={editForm.shot_count} onChange={(event) => setEditForm({ ...editForm, shot_count: Number(event.target.value) })} className="bg-white/5 border-white/10 text-white" />
                              <Textarea value={editForm.description} onChange={(event) => setEditForm({ ...editForm, description: event.target.value })} placeholder="模板用途和适用场景" />
                              <Textarea value={editForm.prompt_template} onChange={(event) => setEditForm({ ...editForm, prompt_template: event.target.value })} placeholder="提示词模板" />
                              <div className="flex gap-2">
                                <Button size="sm" className="bg-violet-600 hover:bg-violet-700" onClick={() => saveSystemTemplateEdit(template)} disabled={saving}>
                                  <Check className="w-4 h-4 mr-1" />保存
                                </Button>
                                <Button size="sm" variant="ghost" className="text-white/60" onClick={cancelEdit}>
                                  <X className="w-4 h-4 mr-1" />取消
                                </Button>
                              </div>
                            </CardContent>
                          ) : (
                            <>
                              <CardHeader>
                                <CardTitle className="text-white flex items-center gap-2 text-base">
                                  <LayoutTemplate className="w-5 h-5 text-violet-400" />
                                  {template.name}
                                </CardTitle>
                              </CardHeader>
                              <CardContent className="space-y-3">
                                <p className="text-sm text-white/60 min-h-[40px]">{template.description}</p>
                                <div className="flex flex-wrap gap-2">
                                  {(template.genre_tags || []).slice(0, 4).map((tag) => <Badge key={tag} variant="outline" className="text-white/60">{tag}</Badge>)}
                                  {template.is_overridden && <Badge variant="warning">已定制</Badge>}
                                </div>
                                {(template.keywords || []).length > 0 && (
                                  <div className="text-xs text-white/40 line-clamp-2">
                                    关键词：{template.keywords.slice(0, 8).join('、')}
                                  </div>
                                )}
                                <div className="flex items-center justify-between text-sm text-white/50">
                                  <span>{template.shot_count} 个镜头</span>
                                  <div className="flex items-center gap-1">
                                    <span className="flex items-center gap-1"><Star className="w-4 h-4 text-yellow-400" />系统</span>
                                    <Button title={`编辑系统模板${template.name}`} variant="ghost" size="sm" className="text-white/60 hover:text-white" onClick={() => startEditSystem(template)}>
                                      <Edit3 className="w-4 h-4 mr-1" />编辑
                                    </Button>
                                  </div>
                                </div>
                              </CardContent>
                            </>
                          )}
                        </Card>
                      ))}
                    </div>
                  </section>
                )}

                {filteredCustomTemplates.length > 0 && (
                  <section className="space-y-3">
                    <h2 className="text-lg font-semibold text-white">自定义模板</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                      {filteredCustomTemplates.map((template) => (
                        <Card key={template.id} className="bg-white/5 border-white/10 hover:bg-white/10 transition-colors">
                          {editingId === template.id ? (
                            <CardContent className="space-y-3 p-4">
                              <Input value={editForm.name} onChange={(event) => setEditForm({ ...editForm, name: event.target.value })} placeholder="模板名称" className="bg-white/5 border-white/10 text-white" />
                              <Select value={editForm.template_type} onChange={(event) => setEditForm({ ...editForm, template_type: event.target.value })} options={templateTypes} />
                              <Input value={editForm.tags} onChange={(event) => setEditForm({ ...editForm, tags: event.target.value })} placeholder="标签，用逗号分隔" className="bg-white/5 border-white/10 text-white" />
                              <Input type="number" min={1} max={20} value={editForm.shot_count} onChange={(event) => setEditForm({ ...editForm, shot_count: Number(event.target.value) })} className="bg-white/5 border-white/10 text-white" />
                              <Textarea value={editForm.description} onChange={(event) => setEditForm({ ...editForm, description: event.target.value })} placeholder="模板用途和适用场景" />
                              <Textarea value={editForm.prompt_template} onChange={(event) => setEditForm({ ...editForm, prompt_template: event.target.value })} placeholder="提示词模板" />
                              <label className="flex items-center gap-2 text-sm text-white/70">
                                <input type="checkbox" checked={editForm.is_public} onChange={(event) => setEditForm({ ...editForm, is_public: event.target.checked })} />
                                发布为团队/公开可复用模板
                              </label>
                              <div className="flex gap-2">
                                <Button size="sm" className="bg-violet-600 hover:bg-violet-700" onClick={() => saveTemplateEdit(template.id, template.shot_template?.shots || [])} disabled={saving}>
                                  <Check className="w-4 h-4 mr-1" />保存
                                </Button>
                                <Button size="sm" variant="ghost" className="text-white/60" onClick={cancelEdit}>
                                  <X className="w-4 h-4 mr-1" />取消
                                </Button>
                              </div>
                            </CardContent>
                          ) : (
                            <>
                              <CardHeader>
                                <CardTitle className="text-white flex items-center gap-2 text-base">
                                  <LayoutTemplate className="w-5 h-5 text-blue-400" />
                                  {template.name}
                                </CardTitle>
                              </CardHeader>
                              <CardContent className="space-y-3">
                                <p className="text-sm text-white/60 min-h-[40px]">{template.description || '未填写描述'}</p>
                                <div className="flex flex-wrap gap-2">
                                  {(template.tags || []).slice(0, 4).map((tag) => <Badge key={tag} variant="outline" className="text-white/60">{tag}</Badge>)}
                                  {template.is_public && <Badge variant="success">公开</Badge>}
                                </div>
                                <div className="flex items-center justify-between text-sm text-white/50">
                                  <span>{template.shot_template?.shot_count || template.shot_template?.shots?.length || 0} 个镜头</span>
                                  <div className="flex gap-1">
                                    <Button title={`编辑${template.name}`} variant="ghost" size="sm" className="text-white/60 hover:text-white" onClick={() => startEdit(template)}>
                                      <Edit3 className="w-4 h-4 mr-1" />编辑
                                    </Button>
                                    <Button variant="ghost" size="sm" className="text-red-300 hover:text-red-200" onClick={() => deleteTemplate(template.id)}>
                                      <Trash2 className="w-4 h-4 mr-1" />归档
                                    </Button>
                                  </div>
                                </div>
                              </CardContent>
                            </>
                          )}
                        </Card>
                      ))}
                    </div>
                  </section>
                )}

                {filteredSystemTemplates.length === 0 && filteredCustomTemplates.length === 0 && (
                  <Card className="bg-white/5 border-white/10"><CardContent className="p-8 text-center text-white/50">暂无匹配模板</CardContent></Card>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </MainLayout>
  );
}

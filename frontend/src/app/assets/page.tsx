'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Archive,
  Boxes,
  Edit3,
  ExternalLink,
  Image as ImageIcon,
  Loader2,
  Lock,
  Unlock,
  Music,
  Plus,
  RefreshCw,
  Save,
  Search,
  Shield,
  Trash2,
  Video,
  Volume2,
  X,
  History,
} from 'lucide-react';
import { MainLayout } from '@/components/layout/main-layout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { apiClient } from '@/lib/api-client';

type AssetCategory = {
  id: string;
  name: string;
  name_cn?: string;
  asset_count?: number;
};

type Project = {
  id: string;
  name: string;
};

type Novel = {
  id: string;
  title: string;
};

type Chapter = {
  id: string;
  title: string;
  chapter_number?: number;
};

type ScriptItem = {
  id: string;
  title: string;
};

type StoryEntity = {
  id: string;
  name: string;
  entity_type: string;
};

type Asset = {
  id: string;
  category: string;
  name: string;
  description?: string;
  asset_type?: string;
  url?: string;
  thumbnail_url?: string;
  project_id?: string;
  novel_id?: string;
  chapter_id?: string;
  script_id?: string;
  entity_id?: string;
  tags?: string[];
  style_tags?: string[];
  is_public?: boolean;
  likes?: number;
  usage_count?: number;
  version?: number;
  is_locked?: boolean;
  is_final?: boolean;
  created_at?: string;
};

const FALLBACK_CATEGORIES: AssetCategory[] = [
  { id: 'character', name: 'character', name_cn: '角色' },
  { id: 'scene', name: 'scene', name_cn: '场景' },
  { id: 'prop', name: 'prop', name_cn: '道具' },
  { id: 'costume', name: 'costume', name_cn: '服装' },
  { id: 'music', name: 'music', name_cn: '音乐' },
  { id: 'sfx', name: 'sfx', name_cn: '音效' },
  { id: 'template', name: 'template', name_cn: '模板' },
  { id: 'prompt', name: 'prompt', name_cn: '提示词' },
];

const ASSET_TYPE_OPTIONS = [
  { value: 'image', label: '图片 / 参考图' },
  { value: 'video', label: '视频 / 关键帧' },
  { value: 'audio', label: '音频 / 配音素材' },
  { value: 'text', label: '文本 / 提示词' },
  { value: 'lora', label: 'LoRA / 角色模型' },
  { value: 'ipadapter', label: 'IP-Adapter / 参考适配' },
];

const typeIcon = (assetType?: string) => {
  if (assetType === 'video') return Video;
  if (assetType === 'audio') return Volume2;
  if (assetType === 'music') return Music;
  return ImageIcon;
};

const splitTags = (value: string) => value.split(/[，,]/).map((item) => item.trim()).filter(Boolean);

const emptyForm = {
  name: '',
  category: 'character',
  asset_type: 'image',
  project_id: '',
  novel_id: '',
  chapter_id: '',
  script_id: '',
  entity_id: '',
  url: '',
  thumbnail_url: '',
  tags: '',
  style_tags: '',
  description: '',
  is_public: false,
};

export default function AssetsPage() {
  const formSectionRef = useRef<HTMLDivElement | null>(null);
  const nameInputRef = useRef<HTMLInputElement | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [categories, setCategories] = useState<AssetCategory[]>(FALLBACK_CATEGORIES);
  const [projects, setProjects] = useState<Project[]>([]);
  const [novels, setNovels] = useState<Novel[]>([]);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [scripts, setScripts] = useState<ScriptItem[]>([]);
  const [entities, setEntities] = useState<StoryEntity[]>([]);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedProjectId, setSelectedProjectId] = useState('all');
  const [selectedNovelId, setSelectedNovelId] = useState('');
  const [selectedChapterId, setSelectedChapterId] = useState('');
  const [selectedScriptId, setSelectedScriptId] = useState('');
  const [selectedEntityId, setSelectedEntityId] = useState('');
  const [selectedScope, setSelectedScope] = useState('');
  const [selectedEntityType, setSelectedEntityType] = useState('');
  const [includePublic, setIncludePublic] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [selectedAssets, setSelectedAssets] = useState<Set<string>>(new Set());
  const [showVersionHistory, setShowVersionHistory] = useState(false);
  const [versionHistoryEntity, setVersionHistoryEntity] = useState<{id: string; type: string; name: string} | null>(null);
  const [versionHistory, setVersionHistory] = useState<Asset[]>([]);

  const categoryOptions = useMemo(() => [
    { value: 'all', label: '全部分类' },
    ...categories.map((category) => ({
      value: category.name,
      label: `${category.name_cn || category.name}${category.asset_count ? ` (${category.asset_count})` : ''}`,
    })),
  ], [categories]);

  const projectOptions = useMemo(() => [
    { value: 'all', label: '全部资产' },
    { value: 'global', label: '仅全局资产' },
    ...projects.map((project) => ({ value: project.id, label: project.name })),
  ], [projects]);

  const formProjectOptions = useMemo(() => [
    { value: '', label: '全局资产' },
    ...projects.map((project) => ({ value: project.id, label: project.name })),
  ], [projects]);

  const scopeOptions = [
    { value: '', label: '全部范围（含全局）' },
    { value: 'global', label: '仅全局' },
    { value: 'project', label: '仅项目' },
    { value: 'novel', label: '仅小说' },
    { value: 'chapter', label: '仅章节' },
    { value: 'script', label: '仅剧本' },
    { value: 'entity', label: '仅实体' },
  ];

  const categoryLabel = (categoryName: string) => (
    categories.find((category) => category.name === categoryName)?.name_cn || categoryName
  );

  const projectLabel = (projectId?: string) => {
    if (!projectId) return '全局资产';
    return projects.find((project) => project.id === projectId)?.name || '项目资产';
  };

  const scopeLabel = (asset: Asset) => {
    if (asset.entity_id) return '实体资产';
    if (asset.script_id) return '剧本资产';
    if (asset.chapter_id) return '章节资产';
    if (asset.novel_id) return '小说资产';
    if (asset.project_id) return '项目资产';
    return '全局资产';
  };

  const toMediaUrl = (url?: string) => {
    if (!url) return '';
    if (/^https?:\/\//.test(url)) return url;
    const base = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1').replace(/\/api\/v1$/, '');
    return `${base}${url.startsWith('/') ? url : `/${url}`}`;
  };

  const loadAssets = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const [categoryList, projectList, assetList] = await Promise.all([
        apiClient.getAssetCategories().catch(() => FALLBACK_CATEGORIES),
        apiClient.getProjects().catch(() => []),
        apiClient.getAssets({
          category: selectedCategory === 'all' ? undefined : selectedCategory,
          project_id: selectedProjectId === 'all' || selectedProjectId === 'global' ? undefined : selectedProjectId,
          novel_id: selectedNovelId || undefined,
          chapter_id: selectedChapterId || undefined,
          script_id: selectedScriptId || undefined,
          entity_id: selectedEntityId || undefined,
          scope: selectedScope || undefined,
          search: searchQuery.trim() || undefined,
          include_public: includePublic,
          limit: 200,
        }),
      ]);
      setCategories(categoryList?.length ? categoryList : FALLBACK_CATEGORIES);
      setProjects(projectList || []);
      setAssets(assetList || []);
    } catch (err: any) {
      setAssets([]);
      setMessage(err?.message || '资产加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAssets();
  }, [selectedCategory, selectedProjectId, selectedScope, selectedNovelId, selectedChapterId, selectedScriptId, selectedEntityId, includePublic]);

  useEffect(() => {
    const loadNovels = async () => {
      try {
        const data = await apiClient.getNovels();
        setNovels(Array.isArray(data) ? data : []);
      } catch {
        setNovels([]);
      }
    };
    loadNovels();
  }, []);

  useEffect(() => {
    const loadLineageOptions = async () => {
      const formNovelId = formOpen && form.novel_id ? form.novel_id : '';
      const activeNovelId = selectedNovelId || formNovelId;
      if (!activeNovelId) {
        setChapters([]);
        setScripts([]);
        setEntities([]);
        return;
      }
      try {
        const [chapterList, scriptList, entityList] = await Promise.all([
          apiClient.getChapters(activeNovelId).catch(() => []),
          apiClient.getScripts({ novel_id: activeNovelId, page_size: 100 }).catch(() => []),
          apiClient.getStoryEntities({ novel_id: activeNovelId, limit: 200 }).catch(() => []),
        ]);
        setChapters(Array.isArray(chapterList) ? chapterList : []);
        setScripts(Array.isArray(scriptList) ? scriptList : []);
        setEntities(Array.isArray(entityList) ? entityList : []);
      } catch {
        setChapters([]);
        setScripts([]);
        setEntities([]);
      }
    };
    setSelectedChapterId('');
    setSelectedScriptId('');
    setSelectedEntityId('');
    loadLineageOptions();
  }, [selectedNovelId, formOpen, form.novel_id]);

  const visibleAssets = useMemo(() => {
    if (selectedProjectId !== 'global') return assets;
    return assets.filter((asset) => !asset.project_id && !asset.novel_id && !asset.chapter_id && !asset.script_id && !asset.entity_id);
  }, [assets, selectedProjectId]);

  const startCreate = () => {
    setEditingId(null);
    setForm({
      ...emptyForm,
      category: selectedCategory === 'all' ? 'character' : selectedCategory,
      project_id: selectedProjectId === 'all' || selectedProjectId === 'global' ? '' : selectedProjectId,
      novel_id: selectedNovelId,
      chapter_id: selectedChapterId,
      script_id: selectedScriptId,
      entity_id: selectedEntityId,
    });
    setFormOpen(true);
    setMessage(null);
    requestAnimationFrame(() => {
      formSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      nameInputRef.current?.focus({ preventScroll: true });
    });
  };

  const startEdit = (asset: Asset) => {
    setEditingId(asset.id);
    setFormOpen(true);
    setForm({
      name: asset.name || '',
      category: asset.category || 'character',
      asset_type: asset.asset_type || 'image',
      project_id: asset.project_id || '',
      novel_id: asset.novel_id || '',
      chapter_id: asset.chapter_id || '',
      script_id: asset.script_id || '',
      entity_id: asset.entity_id || '',
      url: asset.url || '',
      thumbnail_url: asset.thumbnail_url || '',
      tags: (asset.tags || []).join('，'),
      style_tags: (asset.style_tags || []).join('，'),
      description: asset.description || '',
      is_public: Boolean(asset.is_public),
    });
    setMessage(null);
    requestAnimationFrame(() => {
      formSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      nameInputRef.current?.focus({ preventScroll: true });
    });
  };

  const resetForm = () => {
    setEditingId(null);
    setFormOpen(false);
    setForm(emptyForm);
  };

  const saveAsset = async () => {
    if (!form.name.trim()) {
      setMessage('请输入资产名称');
      return;
    }
    setSaving(true);
    setMessage(null);
    const payload = {
      category: form.category,
      name: form.name.trim(),
      description: form.description.trim() || undefined,
      asset_type: form.asset_type,
      url: form.url.trim() || undefined,
      thumbnail_url: form.thumbnail_url.trim() || undefined,
      project_id: form.project_id || undefined,
      novel_id: form.novel_id || undefined,
      chapter_id: form.chapter_id || undefined,
      script_id: form.script_id || undefined,
      entity_id: form.entity_id || undefined,
      tags: splitTags(form.tags),
      style_tags: splitTags(form.style_tags),
      is_public: form.is_public,
    };
    try {
      const isEditing = Boolean(editingId);
      if (editingId) {
        const updated = await apiClient.updateAsset(editingId, payload);
        setAssets((prev) => prev.map((asset) => asset.id === editingId ? updated : asset));
      } else {
        const created = await apiClient.createAsset(payload);
        setAssets((prev) => [created, ...prev]);
      }
      resetForm();
      await loadAssets();
      setMessage(isEditing ? '资产已更新' : '资产已保存');
    } catch (err: any) {
      setMessage(err?.message || '资产保存失败');
    } finally {
      setSaving(false);
    }
  };

  const archiveAsset = async (assetId: string) => {
    setMessage(null);
    try {
      await apiClient.deleteAsset(assetId);
      setAssets((prev) => prev.filter((asset) => asset.id !== assetId));
      setMessage('资产已归档');
    } catch (err: any) {
      setMessage(err?.message || '资产归档失败');
    }
  };

  const lockAsset = async (assetId: string) => {
    setMessage(null);
    try {
      const updated = await apiClient.lockAsset(assetId);
      setAssets((prev) => prev.map((asset) => asset.id === assetId ? { ...asset, is_locked: true, is_final: true } : asset));
      setMessage('资产已锁定为定稿');
    } catch (err: any) {
      setMessage(err?.message || '资产锁定失败');
    }
  };

  const unlockAsset = async (assetId: string) => {
    setMessage(null);
    try {
      const updated = await apiClient.unlockAsset(assetId);
      setAssets((prev) => prev.map((asset) => asset.id === assetId ? { ...asset, is_locked: false, is_final: false } : asset));
      setMessage('资产已解锁');
    } catch (err: any) {
      setMessage(err?.message || '资产解锁失败');
    }
  };

  const batchLockAssets = async () => {
    if (selectedAssets.size === 0) {
      setMessage('请先选择要锁定的资产');
      return;
    }
    setMessage(null);
    try {
      const result = await apiClient.batchLockAssets(Array.from(selectedAssets));
      setAssets((prev) => prev.map((asset) =>
        selectedAssets.has(asset.id) ? { ...asset, is_locked: true, is_final: true } : asset
      ));
      setSelectedAssets(new Set());
      setMessage(`已锁定 ${result.locked_count} 个资产`);
    } catch (err: any) {
      setMessage(err?.message || '批量锁定失败');
    }
  };

  const loadVersionHistory = async (entityId: string, entityType: string) => {
    setMessage(null);
    try {
      const versions = await apiClient.getEntityAssetVersions(entityId, entityType);
      setVersionHistory(versions || []);
      setShowVersionHistory(true);
    } catch (err: any) {
      setMessage(err?.message || '版本历史加载失败');
    }
  };

  const toggleAssetSelection = (assetId: string) => {
    setSelectedAssets((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(assetId)) {
        newSet.delete(assetId);
      } else {
        newSet.add(assetId);
      }
      return newSet;
    });
  };

  const bindAssetScope = async (asset: Asset, scope: 'global' | 'novel' | 'chapter' | 'script' | 'entity') => {
    setMessage(null);
    if (scope === 'novel' && !(selectedNovelId || asset.novel_id)) {
      setMessage('请先选择小说，或选择已有小说资产');
      return;
    }
    if (scope === 'chapter' && !(selectedChapterId || asset.chapter_id)) {
      setMessage('请先选择章节，或选择已有章节资产');
      return;
    }
    if (scope === 'script' && !(selectedScriptId || asset.script_id)) {
      setMessage('请先选择剧本，或选择已有剧本资产');
      return;
    }
    if (scope === 'entity' && !(selectedEntityId || asset.entity_id)) {
      setMessage('请先选择实体，或选择已有实体资产');
      return;
    }
    try {
      const updated = await apiClient.updateAssetScope(asset.id, {
        scope,
        novel_id: selectedNovelId || asset.novel_id || undefined,
        chapter_id: selectedChapterId || asset.chapter_id || undefined,
        script_id: selectedScriptId || asset.script_id || undefined,
        entity_id: selectedEntityId || asset.entity_id || undefined,
      });
      setAssets((prev) => prev.map((item) => item.id === asset.id ? updated : item));
      setMessage(`已调整「${asset.name}」作用域`);
      await loadAssets();
    } catch (err: any) {
      setMessage(err?.message || '资产作用域调整失败');
    }
  };

  const stats = useMemo(() => ({
    total: visibleAssets.length,
    global: visibleAssets.filter((asset) => !asset.project_id && !asset.novel_id && !asset.chapter_id && !asset.script_id && !asset.entity_id).length,
    public: visibleAssets.filter((asset) => asset.is_public).length,
    referenced: visibleAssets.filter((asset) => (asset.usage_count || 0) > 0).length,
    locked: visibleAssets.filter((asset) => asset.is_locked).length,
    final: visibleAssets.filter((asset) => asset.is_final).length,
  }), [visibleAssets]);

  return (
    <MainLayout>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-white">资产库</h1>
            <p className="mt-1 text-white/60">统一管理角色、场景、道具、服装、音效、关键帧和提示词资产</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" className="border-white/20 text-white" onClick={loadAssets} disabled={loading}>
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
              刷新
            </Button>
            <Button className="bg-violet-600 hover:bg-violet-700" onClick={startCreate}>
              <Plus className="mr-2 h-4 w-4" />
              新建资产
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
          {[
            ['资产总数', stats.total],
            ['全局资产', stats.global],
            ['公开资产', stats.public],
            ['已被引用', stats.referenced],
            ['已锁定', stats.locked],
            ['定稿', stats.final],
          ].map(([label, value]) => (
            <Card key={label} className="bg-white/5 border-white/10">
              <CardContent className="p-4">
                <div className="text-2xl font-semibold text-white">{value}</div>
                <div className="mt-1 text-sm text-white/50">{label}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        <Card className="bg-white/5 border-white/10">
          <CardContent className="p-4 space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-[1fr_180px_180px_150px_auto_auto] gap-3">
              <div className="relative">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-white/40" />
                <Input
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') loadAssets();
                  }}
                  placeholder="搜索资产名称、描述、标签"
                  className="pl-9 bg-white/5 border-white/10 text-white"
                />
              </div>
              <Select value={selectedCategory} onChange={(event) => setSelectedCategory(event.target.value)} options={categoryOptions} />
              <Select value={selectedProjectId} onChange={(event) => setSelectedProjectId(event.target.value)} options={projectOptions} />
              <Select value={selectedScope} onChange={(event) => setSelectedScope(event.target.value)} options={scopeOptions} />
              <label className="flex items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-white/70">
                <input type="checkbox" checked={includePublic} onChange={(event) => setIncludePublic(event.target.checked)} />
                包含公开
              </label>
              <Button variant="outline" className="border-white/20 text-white" onClick={loadAssets}>
                搜索
              </Button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <Select
                value={selectedNovelId}
                onChange={(event) => setSelectedNovelId(event.target.value)}
                options={[{ value: '', label: '全部小说' }, ...novels.map((novel) => ({ value: novel.id, label: novel.title }))]}
              />
              <Select
                value={selectedChapterId}
                onChange={(event) => setSelectedChapterId(event.target.value)}
                options={[
                  { value: '', label: '全部章节' },
                  ...chapters.map((chapter) => ({
                    value: chapter.id,
                    label: `${chapter.chapter_number ? `第${chapter.chapter_number}章 ` : ''}${chapter.title}`,
                  })),
                ]}
              />
              <Select
                value={selectedScriptId}
                onChange={(event) => setSelectedScriptId(event.target.value)}
                options={[{ value: '', label: '全部剧本' }, ...scripts.map((script) => ({ value: script.id, label: script.title }))]}
              />
              <Select
                value={selectedEntityId}
                onChange={(event) => setSelectedEntityId(event.target.value)}
                options={[
                  { value: '', label: '全部实体' },
                  ...entities.map((entity) => ({ value: entity.id, label: `${entity.name} · ${entity.entity_type}` })),
                ]}
              />
            </div>
            <div className="text-xs text-white/45">
              选择小说、章节、剧本或实体时，会同时展示可复用的全局资产；需要只看绑定资产时，使用“仅小说/仅章节/仅剧本/仅实体”范围。
            </div>
          </CardContent>
        </Card>

        {message && (
          <div className="rounded-md border border-white/10 bg-white/5 px-4 py-3 text-sm text-white/75">
            {message}
          </div>
        )}

        {formOpen && (
          <Card ref={formSectionRef} className="scroll-mt-6 bg-white/5 border-white/10">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-white">
                <Boxes className="h-5 w-5 text-violet-300" />
                {editingId ? '编辑资产' : '新建资产'}
              </CardTitle>
              <Button variant="ghost" size="sm" className="text-white/60" onClick={resetForm}>
                <X className="h-4 w-4" />
              </Button>
            </CardHeader>
            <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Input ref={nameInputRef} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="资产名称" className="bg-white/5 border-white/10 text-white" />
              <Select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} options={categories.map((category) => ({ value: category.name, label: category.name_cn || category.name }))} />
              <Select value={form.asset_type} onChange={(event) => setForm({ ...form, asset_type: event.target.value })} options={ASSET_TYPE_OPTIONS} />
              <Select value={form.project_id} onChange={(event) => setForm({ ...form, project_id: event.target.value })} options={formProjectOptions} />
              <Select value={form.novel_id} onChange={(event) => setForm({ ...form, novel_id: event.target.value, chapter_id: '', script_id: '', entity_id: '' })} options={[{ value: '', label: '不绑定小说' }, ...novels.map((novel) => ({ value: novel.id, label: novel.title }))]} />
              <Select value={form.chapter_id} onChange={(event) => setForm({ ...form, chapter_id: event.target.value })} options={[{ value: '', label: '不绑定章节' }, ...chapters.map((chapter) => ({ value: chapter.id, label: chapter.title }))]} />
              <Select value={form.script_id} onChange={(event) => setForm({ ...form, script_id: event.target.value })} options={[{ value: '', label: '不绑定剧本' }, ...scripts.map((script) => ({ value: script.id, label: script.title }))]} />
              <Select value={form.entity_id} onChange={(event) => setForm({ ...form, entity_id: event.target.value })} options={[{ value: '', label: '不绑定实体' }, ...entities.map((entity) => ({ value: entity.id, label: `${entity.name} · ${entity.entity_type}` }))]} />
              <Input value={form.url} onChange={(event) => setForm({ ...form, url: event.target.value })} placeholder="资源 URL 或 /static/... 路径" className="bg-white/5 border-white/10 text-white md:col-span-2" />
              <Input value={form.thumbnail_url} onChange={(event) => setForm({ ...form, thumbnail_url: event.target.value })} placeholder="缩略图 URL，可选" className="bg-white/5 border-white/10 text-white md:col-span-2" />
              <Input value={form.tags} onChange={(event) => setForm({ ...form, tags: event.target.value })} placeholder="业务标签，例如：主角，夜景，法器" className="bg-white/5 border-white/10 text-white" />
              <Input value={form.style_tags} onChange={(event) => setForm({ ...form, style_tags: event.target.value })} placeholder="风格标签，例如：anime，玄幻，冷色" className="bg-white/5 border-white/10 text-white" />
              <Textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="资产用途、视觉 DNA、适用镜头或一致性说明" className="md:col-span-2" />
              <label className="flex items-center gap-2 text-sm text-white/70">
                <input type="checkbox" checked={form.is_public} onChange={(event) => setForm({ ...form, is_public: event.target.checked })} />
                允许公开复用
              </label>
              <div className="flex justify-end gap-2 md:col-span-2">
                <Button variant="outline" className="border-white/20 text-white" onClick={resetForm}>取消</Button>
                <Button className="bg-violet-600 hover:bg-violet-700" onClick={saveAsset} disabled={saving}>
                  {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                  保存资产
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {loading ? (
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-8 text-center text-white/60">
              <Loader2 className="mx-auto mb-3 h-6 w-6 animate-spin" />
              正在加载资产...
            </CardContent>
          </Card>
        ) : visibleAssets.length === 0 ? (
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-8 text-center">
              <Archive className="mx-auto mb-3 h-8 w-8 text-white/30" />
              <div className="text-white">暂无资产</div>
              <div className="mt-1 text-sm text-white/50">可先登记角色参考图、场景参考图、道具图或音效素材。</div>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {visibleAssets.map((asset) => {
              const Icon = typeIcon(asset.asset_type);
              const previewUrl = toMediaUrl(asset.thumbnail_url || asset.url);
              return (
                <Card key={asset.id} className="bg-white/5 border-white/10 overflow-hidden">
                  <div className="h-36 bg-black/30">
                    {previewUrl && (asset.asset_type || 'image') === 'image' ? (
                      <img src={previewUrl} alt="" width={384} height={144} loading="lazy" className="h-full w-full object-cover" />
                    ) : (
                      <div className="flex h-full items-center justify-center">
                        <Icon className="h-10 w-10 text-white/30" />
                      </div>
                    )}
                  </div>
                  <CardContent className="p-4 space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate font-medium text-white">{asset.name}</div>
                        <div className="mt-1 text-xs text-white/45">{categoryLabel(asset.category)} · {projectLabel(asset.project_id)} · {scopeLabel(asset)}</div>
                        <div className="mt-1 text-[11px] text-white/30">
                          {asset.novel_id ? `小说 ${asset.novel_id.slice(0, 8)}` : ''}
                          {asset.chapter_id ? ` · 章节 ${asset.chapter_id.slice(0, 8)}` : ''}
                          {asset.script_id ? ` · 剧本 ${asset.script_id.slice(0, 8)}` : ''}
                          {asset.entity_id ? ` · 实体 ${asset.entity_id.slice(0, 8)}` : ''}
                        </div>
                      </div>
                      <Badge variant="outline" className="text-white/70 border-white/30 shrink-0">
                        {asset.asset_type || 'image'}
                      </Badge>
                    </div>
                    {asset.description && (
                      <p className="line-clamp-2 text-sm text-white/60">{asset.description}</p>
                    )}
                    <div className="flex flex-wrap gap-1">
                      {(asset.tags || []).slice(0, 4).map((tag) => (
                        <Badge key={tag} variant="outline" className="border-violet-300/40 text-violet-100">{tag}</Badge>
                      ))}
                      {(asset.style_tags || []).slice(0, 3).map((tag) => (
                        <Badge key={tag} variant="outline" className="border-cyan-300/40 text-cyan-100">{tag}</Badge>
                      ))}
                    </div>
                    <div className="flex items-center justify-between text-xs text-white/45">
                      <span>引用 {asset.usage_count || 0}</span>
                      <div className="flex items-center gap-2">
                        {(asset as Asset).is_locked && (
                          <span className="flex items-center gap-1 text-violet-400">
                            <Lock className="h-3 w-3" />
                            锁定
                          </span>
                        )}
                        {(asset as Asset).is_final && (
                          <Badge variant="outline" className="border-emerald-500/40 text-emerald-300 text-[10px]">定稿</Badge>
                        )}
                        <span>{(asset as Asset).is_public ? '公开' : '私有'}</span>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <div className="flex items-center gap-1">
                        <input
                          type="checkbox"
                          checked={selectedAssets.has(asset.id)}
                          onChange={() => toggleAssetSelection(asset.id)}
                          className="rounded border-white/20"
                        />
                      </div>
                      {asset.url && (
                        <Button variant="outline" size="sm" className="border-white/20 text-white" onClick={() => window.open(toMediaUrl(asset.url), '_blank')}>
                          <ExternalLink className="mr-1 h-3 w-3" />
                          打开
                        </Button>
                      )}
                      <Button variant="outline" size="sm" title="编辑资产" className="border-white/20 text-white" onClick={() => startEdit(asset)}>
                        <Edit3 className="mr-1 h-3 w-3" />
                        编辑
                      </Button>
                      {(asset as Asset).is_locked ? (
                        <Button variant="outline" size="sm" title="解锁资产" className="border-amber-500/50 text-amber-300" onClick={() => unlockAsset(asset.id)}>
                          <Unlock className="mr-1 h-3 w-3" />
                          解锁
                        </Button>
                      ) : (
                        <Button variant="outline" size="sm" title="锁定为定稿" className="border-emerald-500/50 text-emerald-300" onClick={() => lockAsset(asset.id)}>
                          <Lock className="mr-1 h-3 w-3" />
                          锁定
                        </Button>
                      )}
                      {asset.entity_id && (
                        <Button variant="outline" size="sm" title="版本历史" className="border-cyan-500/50 text-cyan-300" onClick={() => loadVersionHistory(asset.entity_id!, asset.category)}>
                          <History className="mr-1 h-3 w-3" />
                          历史
                        </Button>
                      )}
                      <Button variant="outline" size="sm" title="升为全局资产" className="border-white/20 text-white" onClick={() => bindAssetScope(asset, 'global')}>
                        全局
                      </Button>
                      <Button variant="outline" size="sm" title="归档资产" className="border-red-300/30 text-red-200" onClick={() => archiveAsset(asset.id)}>
                        <Trash2 className="mr-1 h-3 w-3" />
                        归档
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </MainLayout>
  );
}

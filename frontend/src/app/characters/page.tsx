'use client';

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { MainLayout } from '@/components/layout/main-layout';
import { ModelCapabilitySelector } from '@/components/model-capability-selector';
import {
  DEFAULT_IMAGE_STYLE_TEMPLATES,
  ImageStyleTemplatePicker,
  type ImageStyleTemplate,
} from '@/components/media/image-style-template-picker';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/components/ui/toast';
import {
  Users,
  Plus,
  Edit2,
  Trash2,
  Search,
  User,
  Palette,
  Mic,
  Sparkles,
  Save,
  X,
  ChevronRight,
  Image as ImageIcon,
  Loader2,
  AlertCircle,
  BookOpen,
  FileText
} from 'lucide-react';
import { fetchJsonWithAuth, fetchWithAuth } from '@/lib/fetch-with-auth';
import { apiClient } from '@/lib/api-client';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import {
  getDefaultConfigForCapability,
  SavedModelConfig,
} from '@/lib/model-configs';
import { formatChapterLabel } from '@/lib/chapter-label';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const API_ORIGIN = API_BASE.replace(/\/api\/v1\/?$/, '');

const toMediaUrl = (url?: string | null) => {
  if (!url) return '';
  return url.startsWith('/') ? `${API_ORIGIN}${url}` : url;
};

const FALLBACK_IMAGE_STYLES: ImageStyleTemplate[] = DEFAULT_IMAGE_STYLE_TEMPLATES;

// 小说类型
interface Novel {
  id: string;
  title: string;
  description?: string;
}

// 章节类型
interface Chapter {
  id: string;
  title: string;
  chapter_number: number;
  word_count?: number;
}

interface Character {
  id: string;
  novel_id?: string;
  chapter_id?: string;
  name: string;
  description: string;
  appearance: string;
  personality: string;
  voice: string;
  avatar?: string;
  tags: string[];
  source?: 'legacy' | 'story_entity';
  source_label?: string;
  read_only?: boolean;
  production_entity_id?: string;
  created_at?: string;
  updated_at?: string;
}

type StoryEntityCharacter = {
  id: string;
  novel_id?: string | null;
  chapter_id?: string | null;
  name?: string;
  description?: string | null;
  appearance?: string | null;
  attributes?: Record<string, any>;
  tags?: string[];
};

const normalizeCharacterName = (name?: string | null) => (name || '').replace(/\s+/g, '').toLowerCase();

const productionCharacterFromEntity = (entity: StoryEntityCharacter): Character => {
  const attrs = entity.attributes || {};
  const visualDna = attrs.visual_dna && typeof attrs.visual_dna === 'object' ? attrs.visual_dna : {};
  const dnaSummary = Object.entries(visualDna)
    .slice(0, 4)
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join('；');
  return {
    id: entity.id,
    production_entity_id: entity.id,
    novel_id: entity.novel_id || undefined,
    chapter_id: entity.chapter_id || undefined,
    name: entity.name || '未命名生产角色',
    description: entity.description || 'StoryEntity 生产角色',
    appearance: entity.appearance || dnaSummary || '',
    personality: attrs.personality || '',
    voice: attrs.voice || attrs.voice_id || attrs.voice_profile || '',
    avatar: attrs.avatar || attrs.avatar_url || undefined,
    tags: Array.from(new Set(['StoryEntity', ...((entity.tags || []).filter(Boolean))])),
    source: 'story_entity',
    source_label: 'StoryEntity',
    read_only: true,
  };
};

function CharactersPageContent() {
  const { toast } = useToast();
  const searchParams = useSearchParams();
  const initialNovelId = searchParams.get('novel_id') || '';
  const [characters, setCharacters] = useState<Character[]>([]);
  const [legacyCharacterCount, setLegacyCharacterCount] = useState(0);
  const [productionEntityCount, setProductionEntityCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCharacter, setSelectedCharacter] = useState<Character | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [extractingCharacters, setExtractingCharacters] = useState(false);
  const [generatingAvatar, setGeneratingAvatar] = useState<string | null>(null);
  const [autoGenerateAvatar, setAutoGenerateAvatar] = useState(true);
  const [generatingAvatarId, setGeneratingAvatarId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Character | null>(null);
  const [deletingCharacterId, setDeletingCharacterId] = useState<string | null>(null);

  // Extracted characters list (shows avatars from backend)
  const [extractedChars, setExtractedChars] = useState<Array<{ id: string; name: string; avatar?: string }>>([]);

  // AI提取弹窗相关
  const [showExtractModal, setShowExtractModal] = useState(false);
  const [extractTab, setExtractTab] = useState<'novel' | 'chapter' | 'text'>('novel');
  const [novels, setNovels] = useState<Novel[]>([]);
  const [scopeNovelId, setScopeNovelId] = useState(initialNovelId);
  const [selectedNovelId, setSelectedNovelId] = useState('');
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [selectedChapterId, setSelectedChapterId] = useState('');
  const [manualText, setManualText] = useState('');
  const [extractCount, setExtractCount] = useState(5);
  const [extractError, setExtractError] = useState<string | null>(null);
  const [modelConfigs, setModelConfigs] = useState<SavedModelConfig[]>([]);
  const [textModelConfigId, setTextModelConfigId] = useState('');
  const [imageModelConfigId, setImageModelConfigId] = useState('');
  const [imageStyle, setImageStyle] = useState('anime');
  const [styleTemplates, setStyleTemplates] = useState<ImageStyleTemplate[]>(FALLBACK_IMAGE_STYLES);

  // Sync selectedCharacter when characters array changes (e.g., after avatar generation)
  useEffect(() => {
    if (selectedCharacter && characters) {
      const updated = characters.find((c: Character) => c.id === selectedCharacter.id);
      if (updated && updated.avatar !== selectedCharacter.avatar) {
        setSelectedCharacter(updated);
      }
    }
  }, [characters]);

  // Clear extracted chars when modal closes
  useEffect(() => {
    if (!showExtractModal) {
      setExtractedChars([]);
    }
  }, [showExtractModal]);

  const loadCharacters = async (novelId = scopeNovelId) => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (novelId) params.set('novel_id', novelId);
      const [legacyData, productionData] = await Promise.all([
        fetchJsonWithAuth(`${API_BASE}/characters${params.toString() ? `?${params}` : ''}`),
        novelId
          ? apiClient.getStoryEntities({ novel_id: novelId, entity_type: 'character', limit: 200 }).catch(() => [])
          : Promise.resolve([]),
      ]);
      const legacyCharacters = Array.isArray(legacyData)
        ? legacyData.map((item: Character) => ({ ...item, source: 'legacy' as const, source_label: 'Character' }))
        : [];
      const legacyNames = new Set(legacyCharacters.map((item) => normalizeCharacterName(item.name)).filter(Boolean));
      const productionNames = new Set<string>();
      const productionCharacters = Array.isArray(productionData)
        ? productionData
          .filter((entity: StoryEntityCharacter) => normalizeCharacterName(entity.name))
          .filter((entity: StoryEntityCharacter) => !novelId || entity.novel_id === novelId)
          .filter((entity: StoryEntityCharacter) => !legacyNames.has(normalizeCharacterName(entity.name)))
          .filter((entity: StoryEntityCharacter) => {
            const name = normalizeCharacterName(entity.name);
            if (productionNames.has(name)) return false;
            productionNames.add(name);
            return true;
          })
          .map(productionCharacterFromEntity)
        : [];
      setLegacyCharacterCount(legacyCharacters.length);
      setProductionEntityCount(productionCharacters.length);
      setCharacters([...legacyCharacters, ...productionCharacters]);
    } catch (err: any) {
      setError(err.message || '加载失败');
      setLegacyCharacterCount(0);
      setProductionEntityCount(0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadNovels();
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
      const res = await fetchWithAuth(`${API_BASE}/llm/configs?include_model_center_defaults=true`);
      if (!res.ok) return;
      const configs = await res.json();
      const list = Array.isArray(configs) ? configs : [];
      setModelConfigs(list);
      const textDefault = getDefaultConfigForCapability(list, 'text');
      const imageDefault = getDefaultConfigForCapability(list, 'image');
      if (textDefault) setTextModelConfigId(textDefault.id);
      if (imageDefault) setImageModelConfigId(imageDefault.id);
    } catch (err) {
      console.error('加载模型配置失败:', err);
    }
  };

  useEffect(() => {
    setSelectedCharacter(null);
    setIsEditing(false);
    setIsCreating(false);
    loadCharacters(scopeNovelId);
  }, [scopeNovelId]);

  // 加载小说列表
  const loadNovels = async () => {
    try {
      const data = await fetchJsonWithAuth(`${API_BASE}/novels`);
      setNovels(Array.isArray(data) ? data : []);
    } catch {
      setNovels([]);
    }
  };

  // 加载指定小说的章节列表
  const loadChapters = async (novelId: string) => {
    try {
      const data = await fetchJsonWithAuth(`${API_BASE}/chapters/novel/${novelId}`);
      setChapters(Array.isArray(data) ? data : []);
    } catch {
      setChapters([]);
    }
  };

  // 打开AI提取弹窗
  const handleOpenExtract = async () => {
    setExtractTab('novel');
    setSelectedNovelId(scopeNovelId);
    setSelectedChapterId('');
    setManualText('');
    setExtractCount(5);
    setExtractError(null);
    setChapters([]);
    setExtractedChars([]);
    await loadNovels();
    if (scopeNovelId) {
      await loadChapters(scopeNovelId);
    }
    setShowExtractModal(true);
  };

  // 小说选择变化时加载章节
  const handleNovelChange = (novelId: string) => {
    setSelectedNovelId(novelId);
    setSelectedChapterId('');
    if (novelId) {
      loadChapters(novelId);
    } else {
      setChapters([]);
    }
  };

  // 执行AI提取
  const handleDoExtract = async () => {
    setExtractError(null);

    let payload: Record<string, unknown> = { character_count: extractCount };

    if (extractTab === 'novel') {
      if (!selectedNovelId) { setExtractError('请选择一部小说'); return; }
      payload = { ...payload, novel_id: selectedNovelId };
    } else if (extractTab === 'chapter') {
      if (!selectedChapterId) { setExtractError('请选择一个章节'); return; }
      payload = { ...payload, chapter_id: selectedChapterId };
    } else {
      if (!manualText || manualText.trim().length < 10) { setExtractError('文本至少需要10个字符'); return; }
      payload = { ...payload, text: manualText.trim() };
      if (scopeNovelId) {
        payload = { ...payload, novel_id: scopeNovelId };
      }
    }

    setExtractingCharacters(true);
    try {
      const result = await fetchJsonWithAuth(`${API_BASE}/characters/extract`, {
        method: 'POST',
        body: JSON.stringify({
          ...payload,
          model_config_id: textModelConfigId || undefined,
          image_model_config_id: imageModelConfigId || undefined,
        })
      }) as any;
      const extracted = Array.isArray(result) ? result : [];
      if (extracted.length > 0) {
        const nextScopeNovelId = selectedNovelId || scopeNovelId;
        if (nextScopeNovelId && nextScopeNovelId !== scopeNovelId) {
          setScopeNovelId(nextScopeNovelId);
        } else {
          await loadCharacters(nextScopeNovelId);
        }
        setExtractedChars(extracted.map((c: Character) => ({ id: c.id, name: c.name, avatar: c.avatar })));
        setExtractingCharacters(false);
      } else {
        setExtractError('未提取到角色，请检查输入内容');
        setExtractingCharacters(false);
      }
    } catch (err: any) {
      const msg = err?.message || err?.detail || '提取失败，请稍后重试';
      setExtractError(msg);
      setExtractingCharacters(false);
    }
  };

  const filteredCharacters = characters.filter(char =>
    char.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    char.description?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const [formData, setFormData] = useState<Partial<Character>>({
    novel_id: initialNovelId || undefined, name: '', description: '', appearance: '', personality: '', voice: '', tags: []
  });

  useEffect(() => {
    if (selectedCharacter && !isCreating) {
      setFormData(selectedCharacter);
    }
  }, [selectedCharacter, isCreating]);

  const handleSelectCharacter = (char: Character) => {
    setSelectedCharacter(char);
    setIsEditing(false);
    setIsCreating(false);
  };

  const handleCreate = () => {
    setIsCreating(true);
    setIsEditing(true);
    setSelectedCharacter(null);
    setFormData({ novel_id: scopeNovelId || undefined, name: '', description: '', appearance: '', personality: '', voice: '', tags: [] });
    setAutoGenerateAvatar(true);
  };

  const handleEdit = () => {
    if (selectedCharacter && !selectedCharacter.read_only) setIsEditing(true);
  };

  const handleSave = async () => {
    try {
      const payload = {
        novel_id: formData.novel_id || null,
        chapter_id: formData.chapter_id || null,
        name: formData.name || '',
        description: formData.description || '',
        appearance: formData.appearance || '',
        personality: formData.personality || '',
        voice: formData.voice || '',
        tags: formData.tags || []
      };
      if (isCreating) {
        const newChar = await fetchJsonWithAuth(`${API_BASE}/characters`, {
          method: 'POST', body: JSON.stringify(payload)
        }) as Character;
        if (!scopeNovelId || newChar.novel_id === scopeNovelId) {
          setCharacters([...characters, newChar]);
        }
        setSelectedCharacter(newChar);
        setIsEditing(false);
        setIsCreating(false);
        toast({ title: '角色已创建', type: 'success' });

        if (autoGenerateAvatar) {
          setGeneratingAvatarId(newChar.id);
          try {
            const data = await fetchJsonWithAuth(`${API_BASE}/characters/${newChar.id}/generate-avatar`, {
              method: 'POST',
              body: JSON.stringify({
                style: imageStyle,
                model_config_id: imageModelConfigId || undefined,
              })
            }) as any;
            const updatedCharacter = data.character as Character | undefined;
            if (updatedCharacter) {
              setSelectedCharacter(updatedCharacter);
            }
            await loadCharacters();
          } catch (err: any) {
            toast({
              title: '头像生成失败',
              description: err?.message || '角色已保存，可在角色详情页重试生成头像。',
              type: 'error',
            });
          } finally {
            setGeneratingAvatarId(null);
          }
        }
      } else if (selectedCharacter) {
        const updated = await fetchJsonWithAuth(`${API_BASE}/characters/${selectedCharacter.id}`, {
          method: 'PUT', body: JSON.stringify(payload)
        });
        setCharacters(characters.map(c => c.id === (updated as Character).id ? updated as Character : c));
        setSelectedCharacter(updated as Character);
        setIsEditing(false);
        toast({ title: '角色已保存', type: 'success' });
      }
    } catch (err: any) {
      toast({ title: '保存失败', description: err?.message || '请重试。', type: 'error' });
    }
  };

  const handleDelete = async (id: string) => {
    setDeletingCharacterId(id);
    try {
      const response = await fetchWithAuth(`${API_BASE}/characters/${id}`, { method: 'DELETE' });
      if (response.ok) {
        setCharacters(characters.filter(c => c.id !== id));
        if (selectedCharacter?.id === id) setSelectedCharacter(null);
        toast({ title: '角色已删除', type: 'success' });
      }
    } catch (err: any) {
      toast({ title: '删除失败', description: err?.message || '请稍后重试。', type: 'error' });
    } finally {
      setDeletingCharacterId(null);
    }
  };

  // 删除旧的提取函数
  const handleExtractCharacters = async () => {};

  const handleGenerateAvatar = async (characterId: string) => {
    const char = characters.find(c => c.id === characterId);
    if (!char) return;
    setGeneratingAvatar(characterId);
    try {
      const data = await fetchJsonWithAuth(`${API_BASE}/characters/${characterId}/generate-avatar`, {
        method: 'POST',
        body: JSON.stringify({
          style: imageStyle,
          model_config_id: imageModelConfigId || undefined,
        })
      }) as any;
      const updatedCharacter = data.character as Character | undefined;
      if (updatedCharacter) {
        setCharacters(characters.map(c => c.id === updatedCharacter.id ? updatedCharacter : c));
        setSelectedCharacter(updatedCharacter);
      }
      await loadCharacters();
      toast({ title: '头像已生成', description: data.message || '已按角色设定和小说上下文生成。', type: 'success' });
    } catch (err: any) {
      toast({
        title: '生成头像失败',
        description: err?.message || err?.detail || '请检查火山引擎 API 配置。',
        type: 'error',
      });
    } finally {
      setGeneratingAvatar(null);
    }
  };

  const handleCancel = () => { setIsEditing(false); setIsCreating(false); };

  return (
    <MainLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <Users className="w-6 h-6" />
              角色管理
            </h1>
            <p className="text-white/60 mt-1">创建和管理您的角色库</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={handleOpenExtract}
              disabled={extractingCharacters}
              className="border-violet-500/50 text-violet-400 hover:bg-violet-500/10">
              {extractingCharacters ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Sparkles className="w-4 h-4 mr-1" />}
              AI 提取角色
            </Button>
            <Button onClick={handleCreate} className="bg-violet-600 hover:bg-violet-700">
              <Plus className="w-4 h-4 mr-2" />新建角色
            </Button>
          </div>
        </div>

        {error && (
          <Card className="bg-red-500/10 border-red-500/30">
            <CardContent className="p-4 flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-red-400" />
              <span className="text-red-300">{error}</span>
              <Button variant="outline" size="sm" onClick={() => loadCharacters()}
                className="ml-auto border-red-500/50 text-red-400">重试</Button>
            </CardContent>
          </Card>
        )}

        {loading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-violet-400" />
            <span className="ml-3 text-white/60">加载中…</span>
          </div>
        )}

        {!loading && !error && (
          <>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <ModelCapabilitySelector
              capability="text"
              configs={modelConfigs}
              value={textModelConfigId}
              onChange={setTextModelConfigId}
              disabled={extractingCharacters}
              title="角色提取模型"
              description="AI 提取角色会绑定当前小说/章节，识别人物关系、外貌、性格、声音和标签。"
            />
            <ModelCapabilitySelector
              capability="image"
              configs={modelConfigs}
              value={imageModelConfigId}
              onChange={setImageModelConfigId}
              disabled={Boolean(generatingAvatar || generatingAvatarId)}
              title="角色形象模型"
              description="头像与角色立绘会使用图像生成能力，并把角色外观、性格和小说归属写入提示词。"
            />
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-1 space-y-4">
              <div>
                <label className="block text-sm text-white/60 mb-1">小说范围</label>
                <select
                  value={scopeNovelId}
                  onChange={(e) => setScopeNovelId(e.target.value)}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                >
                  <option value="">全部/全局角色</option>
                  {novels.map((novel) => (
                    <option key={novel.id} value={novel.id}>{novel.title}</option>
                  ))}
                </select>
              </div>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                <Input placeholder="搜索角色…" value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 bg-white/5 border-white/10 text-white" />
              </div>
              <div
                data-testid="character-source-summary"
                className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/60"
              >
                角色总数 {legacyCharacterCount + productionEntityCount} · 手工角色 {legacyCharacterCount} · 生产实体 {productionEntityCount}
              </div>
              <div className="space-y-2">
                {filteredCharacters.map((char) => (
                  <div key={char.id}
                    onClick={() => handleSelectCharacter(char)}
                    className={`p-4 rounded-lg border cursor-pointer transition-all ${selectedCharacter?.id === char.id ? 'border-violet-500 bg-violet-500/10' : 'border-white/10 hover:border-white/20 bg-white/5'}`}>
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center overflow-hidden">
                        {generatingAvatarId === char.id ? (
                          <Loader2 className="w-5 h-5 text-white animate-spin" />
                        ) : char.avatar ? (
                          <img src={toMediaUrl(char.avatar)} alt={char.name} width={40} height={40} loading="lazy" className="w-10 h-10 rounded-full object-cover" />
                        ) : (
                          <User className="w-5 h-5 text-white" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-white font-medium truncate">{char.name}</div>
                        <div className="text-white/60 text-sm truncate">{char.description}</div>
                        <div className="text-white/35 text-xs truncate">
                          {char.novel_id ? novels.find((novel) => novel.id === char.novel_id)?.title || '已绑定小说' : '全局角色'}
                        </div>
                      </div>
                      {char.source_label && (
                        <span className="rounded-full border border-white/10 bg-white/10 px-2 py-0.5 text-[10px] text-white/60">
                          {char.source_label}
                        </span>
                      )}
                      <ChevronRight className="w-4 h-4 text-white/40" />
                    </div>
                    <div className="flex gap-1 mt-2">
                      {(char.tags || []).slice(0, 3).map((tag, idx) => (
                        <span key={idx} className="px-2 py-0.5 text-xs bg-white/10 text-white/70 rounded">{tag}</span>
                      ))}
                    </div>
                  </div>
                ))}
                {filteredCharacters.length === 0 && (
                  <div className="text-center py-8 text-white/40">
                    <Users className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>暂无角色</p>
                    <p className="text-sm">点击上方按钮创建</p>
                  </div>
                )}
              </div>
            </div>

            <div className="lg:col-span-2">
              {selectedCharacter || isCreating ? (
                <Card className="bg-white/5 border-white/10">
                  <CardHeader className="flex flex-row items-center justify-between">
                    <CardTitle className="text-white flex items-center gap-2">
                      {isCreating ? (
                        <><Plus className="w-5 h-5" />新建角色</>
                      ) : (
                        <><User className="w-5 h-5" />{isEditing ? '编辑角色' : '角色详情'}</>
                      )}
                    </CardTitle>
                    <div className="flex gap-2">
                      {!isEditing && selectedCharacter && !selectedCharacter.read_only && (
                        <>
                          <Button variant="outline" size="sm" onClick={handleEdit}>
                            <Edit2 className="w-4 h-4 mr-1" />编辑
                          </Button>
                          <Button variant="outline" size="sm" onClick={() => setDeleteTarget(selectedCharacter)}
                            disabled={deletingCharacterId === selectedCharacter.id}
                            className="text-red-400 hover:text-red-300">
                            <Trash2 className="w-4 h-4 mr-1" />删除
                          </Button>
                        </>
                      )}
                      {isEditing && (
                        <>
                          <div className="flex items-center gap-2 mb-4 px-1">
                            <input
                              type="checkbox"
                              id="autoGenerateAvatar"
                              checked={autoGenerateAvatar}
                              onChange={(e) => setAutoGenerateAvatar(e.target.checked)}
                              className="w-4 h-4 accent-violet-500"
                            />
                            <label htmlFor="autoGenerateAvatar" className="text-sm text-white/70">
                              创建后自动生成形象图
                            </label>
                          </div>
                          <div className="flex gap-2">
                            <Button variant="outline" size="sm" onClick={handleCancel}><X className="w-4 h-4 mr-1" />取消</Button>
                            <Button size="sm" onClick={handleSave} className="bg-violet-600 hover:bg-violet-700">
                              <Save className="w-4 h-4 mr-1" />保存
                            </Button>
                          </div>
                        </>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    {selectedCharacter?.read_only && (
                      <div className="rounded-lg border border-cyan-400/20 bg-cyan-500/10 p-3 text-sm leading-6 text-cyan-50">
                        该角色来自 StoryEntity / Story Bible 生产实体，已纳入剧集一致性、定稿卡和镜头引用链路。需要修改时请到 Story Bible 实体管理或定稿卡页面处理。
                      </div>
                    )}
                    <div className="space-y-4">
                      <div className="flex items-center gap-2 text-white/80 mb-2">
                        <User className="w-4 h-4" /><span className="font-medium">基本信息</span>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm text-white/60 mb-1">所属小说</label>
                          {isEditing ? (
                            <select
                              value={formData.novel_id || ''}
                              onChange={(e) => setFormData({ ...formData, novel_id: e.target.value || undefined, chapter_id: undefined })}
                              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                            >
                              <option value="">全局角色</option>
                              {novels.map((novel) => (
                                <option key={novel.id} value={novel.id}>{novel.title}</option>
                              ))}
                            </select>
                          ) : (
                            <div className="text-white p-2 bg-white/5 rounded">
                              {selectedCharacter?.novel_id
                                ? novels.find((novel) => novel.id === selectedCharacter.novel_id)?.title || '已绑定小说'
                                : '全局角色'}
                            </div>
                          )}
                        </div>
                        <div>
                          <label className="block text-sm text-white/60 mb-1">角色名称 *</label>
                          {isEditing ? (
                            <Input value={formData.name || ''}
                              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                              placeholder="输入角色名称" className="bg-white/5 border-white/10" />
                          ) : (
                            <div className="text-white p-2 bg-white/5 rounded">{selectedCharacter?.name}</div>
                          )}
                        </div>
                        <div>
                          <label className="block text-sm text-white/60 mb-1">标签</label>
                          {isEditing ? (
                            <Input value={(formData.tags || []).join(', ')}
                              onChange={(e) => setFormData({ ...formData, tags: e.target.value.split(',').map(t => t.trim()) })}
                              placeholder="用逗号分隔，如：主角,武侠,正派" className="bg-white/5 border-white/10" />
                          ) : (
                            <div className="flex gap-1 flex-wrap">
                              {(selectedCharacter?.tags || []).map((tag, idx) => (
                                <span key={idx} className="px-2 py-1 text-sm bg-violet-500/20 text-violet-300 rounded">{tag}</span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                      <div>
                        <label className="block text-sm text-white/60 mb-1">角色简介</label>
                        {isEditing ? (
                          <textarea value={formData.description || ''}
                            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                            placeholder="简要描述角色的定位和特点" rows={2}
                            className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-white/40 resize-none" />
                        ) : (
                          <div className="text-white p-3 bg-white/5 rounded min-h-[60px]">{selectedCharacter?.description}</div>
                        )}
                      </div>
                    </div>

                    <div className="space-y-4">
                      <div className="flex items-center gap-2 text-white/80 mb-2">
                        <Palette className="w-4 h-4" /><span className="font-medium">外观特征</span>
                      </div>
                      {isEditing ? (
                        <textarea value={formData.appearance || ''}
                          onChange={(e) => setFormData({ ...formData, appearance: e.target.value })}
                          placeholder="描述角色的外貌特征" rows={3}
                          className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-white/40 resize-none" />
                      ) : (
                        <div className="text-white p-3 bg-white/5 rounded min-h-[80px]">{selectedCharacter?.appearance || '未设置'}</div>
                      )}
                    </div>

                    <div className="space-y-4">
                      <div className="flex items-center gap-2 text-white/80 mb-2">
                        <Sparkles className="w-4 h-4" /><span className="font-medium">性格特征</span>
                      </div>
                      {isEditing ? (
                        <textarea value={formData.personality || ''}
                          onChange={(e) => setFormData({ ...formData, personality: e.target.value })}
                          placeholder="描述角色的性格特点" rows={3}
                          className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-white/40 resize-none" />
                      ) : (
                        <div className="text-white p-3 bg-white/5 rounded min-h-[80px]">{selectedCharacter?.personality || '未设置'}</div>
                      )}
                    </div>

                    <div className="space-y-4">
                      <div className="flex items-center gap-2 text-white/80 mb-2">
                        <Mic className="w-4 h-4" /><span className="font-medium">声音特征</span>
                      </div>
                      {isEditing ? (
                        <textarea value={formData.voice || ''}
                          onChange={(e) => setFormData({ ...formData, voice: e.target.value })}
                          placeholder="描述角色的声音特点" rows={2}
                          className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-white/40 resize-none" />
                      ) : (
                        <div className="text-white p-3 bg-white/5 rounded min-h-[60px]">{selectedCharacter?.voice || '未设置'}</div>
                      )}
                    </div>

                    <div className="space-y-4">
                      <div className="flex items-center gap-2 text-white/80 mb-2">
                        <ImageIcon className="w-4 h-4" /><span className="font-medium">角色头像</span>
                      </div>
                      <ImageStyleTemplatePicker
                        templates={styleTemplates}
                        value={imageStyle}
                        onChange={setImageStyle}
                        toMediaUrl={toMediaUrl}
                        recommendedFor="avatar"
                        title="头像画面风格"
                        compact
                      />
                      <div className="flex items-center gap-4">
                        {selectedCharacter?.avatar ? (
                          <img src={toMediaUrl(selectedCharacter.avatar)} alt={selectedCharacter.name} width={80} height={80} loading="lazy"
                            className="w-20 h-20 rounded-full object-cover" />
                        ) : (
                          <div className="w-20 h-20 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
                            <User className="w-10 h-10 text-white" />
                          </div>
                        )}
                        {selectedCharacter && !isEditing && !selectedCharacter.read_only && (
                          <Button variant="outline" size="sm"
                            onClick={() => handleGenerateAvatar(selectedCharacter.id)}
                            disabled={generatingAvatar === selectedCharacter.id}
                            className="border-violet-500/50 text-violet-400 hover:bg-violet-500/10">
                            {generatingAvatar === selectedCharacter.id
                              ? <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                              : <Sparkles className="w-4 h-4 mr-1" />}
                            AI 生成头像
                          </Button>
                        )}
                        {isEditing && (
                          <Button variant="outline" size="sm">上传图片</Button>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ) : (
                <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-white/40">
                  <Users className="w-16 h-16 mb-4 opacity-50" />
                  <p className="text-lg">选择一个角色查看详情</p>
                  <p className="text-sm mt-2">或点击"新建角色"创建新角色</p>
                </div>
              )}
            </div>
          </div>
          </>
        )}
      </div>

      {/* AI提取角色弹窗 */}
      <Dialog open={showExtractModal} onOpenChange={setShowExtractModal}>
        <DialogContent className="bg-[#1a1a2e] border-white/10 text-white max-w-md">
          <DialogHeader>
            <DialogTitle className="text-white flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-violet-400" />
              AI 提取角色
            </DialogTitle>
            <DialogDescription className="text-white/60">
              选择小说、章节或输入文本来提取角色
            </DialogDescription>
          </DialogHeader>

          <Tabs value={extractTab} onValueChange={(v) => setExtractTab(v as any)} className="mt-2">
            <TabsList className="bg-white/5 border border-white/10 w-full">
              <TabsTrigger value="novel" className="flex-1 data-[state=active]:bg-violet-600 text-white">
                <BookOpen className="w-4 h-4 mr-1" />从小说
              </TabsTrigger>
              <TabsTrigger value="chapter" className="flex-1 data-[state=active]:bg-violet-600 text-white">
                <FileText className="w-4 h-4 mr-1" />从章节
              </TabsTrigger>
              <TabsTrigger value="text" className="flex-1 data-[state=active]:bg-violet-600 text-white">
                <Edit2 className="w-4 h-4 mr-1" />手动输入
              </TabsTrigger>
            </TabsList>

            <div className="mt-4 space-y-4">
              <ModelCapabilitySelector
                capability="text"
                configs={modelConfigs}
                value={textModelConfigId}
                onChange={setTextModelConfigId}
                disabled={extractingCharacters}
                title="角色提取文本模型"
                description="提取时会优先使用该文本模型配置。"
                compact
              />
              {autoGenerateAvatar && (
                <ModelCapabilitySelector
                  capability="image"
                  configs={modelConfigs}
                  value={imageModelConfigId}
                  onChange={setImageModelConfigId}
                  disabled={extractingCharacters}
                  title="自动头像图像模型"
                  description="勾选自动生成头像时使用该图像模型。"
                  compact
                />
              )}
              <div className="flex items-center gap-2">
                <span className="text-sm text-white/60 whitespace-nowrap">提取数量：</span>
                <select
                  value={extractCount}
                  onChange={(e) => setExtractCount(Number(e.target.value))}
                  className="bg-white/5 border border-white/10 rounded px-3 py-1.5 text-white text-sm"
                >
                  {[3, 5, 8, 10, 15, 20].map(n => (
                    <option key={n} value={n}>{n} 个角色</option>
                  ))}
                </select>
              </div>

              <TabsContent value="novel" className="mt-0 space-y-3">
                <select
                  value={selectedNovelId}
                  onChange={(e) => handleNovelChange(e.target.value)}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                >
                  <option value="">选择小说...</option>
                  {novels.map(n => (
                    <option key={n.id} value={n.id}>{n.title}</option>
                  ))}
                </select>
                {novels.length === 0 && (
                  <p className="text-white/40 text-sm text-center py-4">暂无小说，请先创建小说</p>
                )}
              </TabsContent>

              <TabsContent value="chapter" className="mt-0 space-y-3">
                <select
                  value={selectedNovelId}
                  onChange={(e) => handleNovelChange(e.target.value)}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                >
                  <option value="">先选择小说...</option>
                  {novels.map(n => (
                    <option key={n.id} value={n.id}>{n.title}</option>
                  ))}
                </select>
                {selectedNovelId && (
                  <select
                    value={selectedChapterId}
                    onChange={(e) => setSelectedChapterId(e.target.value)}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                  >
                    <option value="">选择章节...</option>
                    {chapters.map(ch => (
                      <option key={ch.id} value={ch.id}>
                        {formatChapterLabel(ch)}（{ch.word_count || 0}字）
                      </option>
                    ))}
                  </select>
                )}
              </TabsContent>

              <TabsContent value="text" className="mt-0 space-y-3">
                <textarea
                  value={manualText}
                  onChange={(e) => setManualText(e.target.value)}
                  placeholder="在此粘贴小说或章节文本，AI将从中提取角色信息…"
                  rows={8}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white placeholder:text-white/40 resize-none"
                />
                <p className="text-xs text-white/40">建议粘贴1000字以上的文本以获得更准确的角色提取结果</p>
              </TabsContent>

              {extractError && (
                <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2 text-red-300 text-sm">
                  {extractError}
                </div>
              )}

              {extractedChars.length > 0 && !extractingCharacters && (
                <div className="space-y-3">
                  <div className="text-sm text-white/60">已提取角色（{extractedChars.length}个）：</div>
                  {extractedChars.map(char => (
                    <div key={char.id} className="flex items-center gap-3 p-2 bg-white/5 rounded-lg">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center overflow-hidden flex-shrink-0">
                        {char.avatar ? (
                          <img src={toMediaUrl(char.avatar)} alt={char.name} width={32} height={32} loading="lazy" className="w-8 h-8 rounded-full object-cover" />
                        ) : (
                          <User className="w-4 h-4 text-white" />
                        )}
                      </div>
                      <span className="text-sm text-white flex-1">{char.name}</span>
                      {char.avatar ? (
                        <span className="text-xs text-green-400">头像已生成</span>
                      ) : (
                        <span className="text-xs text-yellow-400">无头像</span>
                      )}
                    </div>
                  ))}
                  <p className="text-xs text-white/40">角色已保存到角色库，可在角色详情页手动生成头像</p>
                  <div className="flex justify-end gap-2 pt-2">
                    <Button variant="outline" onClick={() => setShowExtractModal(false)}
                      className="border-white/20 text-white">关闭</Button>
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={() => setShowExtractModal(false)}
                  className="border-white/20 text-white">取消</Button>
                <Button onClick={handleDoExtract}
                  disabled={extractingCharacters || extractedChars.length > 0}
                  className="bg-violet-600 hover:bg-violet-700">
                  {extractingCharacters ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Sparkles className="w-4 h-4 mr-1" />}
                  {extractingCharacters ? '提取中...' : extractedChars.length > 0 ? '已完成' : '开始提取'}
                </Button>
              </div>
            </div>
          </Tabs>
        </DialogContent>
      </Dialog>
      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="删除角色"
        description={`确定要删除${deleteTarget ? `「${deleteTarget.name}」` : '这个角色'}？删除后相关角色库列表会立即更新。`}
        confirmText="删除角色"
        destructive
        loading={Boolean(deleteTarget && deletingCharacterId === deleteTarget.id)}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        onConfirm={async () => {
          if (!deleteTarget) return;
          await handleDelete(deleteTarget.id);
          setDeleteTarget(null);
        }}
      />
    </MainLayout>
  );
}

export default function CharactersPage() {
  return (
    <Suspense fallback={<MainLayout><div className="p-6 text-white/60">加载中…</div></MainLayout>}>
      <CharactersPageContent />
    </Suspense>
  );
}

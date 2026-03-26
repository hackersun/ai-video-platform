'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { MainLayout } from '@/components/layout/main-layout';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

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
  name: string;
  description: string;
  appearance: string;
  personality: string;
  voice: string;
  avatar?: string;
  tags: string[];
  created_at?: string;
  updated_at?: string;
}

export default function CharactersPage() {
  const [characters, setCharacters] = useState<Character[]>([]);
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

  // Extracted character avatar generation tracking
  const [extractedChars, setExtractedChars] = useState<Array<{ id: string; name: string; avatar_status: 'pending' | 'generating' | 'succeeded' | 'failed' }>>([]);

  // AI提取弹窗相关
  const [showExtractModal, setShowExtractModal] = useState(false);
  const [extractTab, setExtractTab] = useState<'novel' | 'chapter' | 'text'>('novel');
  const [novels, setNovels] = useState<Novel[]>([]);
  const [selectedNovelId, setSelectedNovelId] = useState('');
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [selectedChapterId, setSelectedChapterId] = useState('');
  const [manualText, setManualText] = useState('');
  const [extractCount, setExtractCount] = useState(5);
  const [extractError, setExtractError] = useState<string | null>(null);

  const loadCharacters = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchJsonWithAuth(`${API_BASE}/characters`);
      setCharacters(Array.isArray(data) ? data : []);
    } catch (err: any) {
      setError(err.message || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadCharacters(); }, []);

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
    setSelectedNovelId('');
    setSelectedChapterId('');
    setManualText('');
    setExtractCount(5);
    setExtractError(null);
    setChapters([]);
    setExtractedChars([]);
    await loadNovels();
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
    }

    setExtractingCharacters(true);
    setExtractedChars([]);
    try {
      const result = await fetchJsonWithAuth(`${API_BASE}/characters/extract`, {
        method: 'POST', body: JSON.stringify(payload)
      }) as any;
      const extracted = Array.isArray(result) ? result : [];
      if (extracted.length > 0) {
        await loadCharacters();
        // Track extracted characters for avatar generation UI
        setExtractedChars(extracted.map((c: Character) => ({ id: c.id, name: c.name, avatar_status: 'pending' as const })));
        // Auto-generate avatars for extracted characters
        for (const char of extracted) {
          setExtractedChars(prev => prev.map(c => c.id === char.id ? { ...c, avatar_status: 'generating' } : c));
          try {
            const imgResult = await fetchJsonWithAuth(`${API_BASE}/images/generate`, {
              method: 'POST', body: JSON.stringify({ prompt: buildAvatarPrompt(char), character_id: char.id })
            }) as any;
            pollAvatarStatus(char.id, imgResult.task_id);
          } catch {
            setExtractedChars(prev => prev.map(c => c.id === char.id ? { ...c, avatar_status: 'failed' } : c));
          }
        }
        setExtractedChars([]); // Clear after all started
        await loadCharacters();
      } else {
        await loadCharacters();
        setShowExtractModal(false);
      }
    } catch (err: any) {
      setExtractError(err.message || '提取角色失败，请稍后重试');
    } finally {
      setExtractingCharacters(false);
    }
  };

  const filteredCharacters = characters.filter(char =>
    char.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    char.description?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const [formData, setFormData] = useState<Partial<Character>>({
    name: '', description: '', appearance: '', personality: '', voice: '', tags: []
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
    setFormData({ name: '', description: '', appearance: '', personality: '', voice: '', tags: [] });
    setAutoGenerateAvatar(true);
  };

  const handleEdit = () => { if (selectedCharacter) setIsEditing(true); };

  const handleSave = async () => {
    try {
      const payload = {
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
        setCharacters([...characters, newChar]);
        setSelectedCharacter(newChar);
        setIsEditing(false);
        setIsCreating(false);

        if (autoGenerateAvatar) {
          setGeneratingAvatarId(newChar.id);
          try {
            const result = await fetchJsonWithAuth(`${API_BASE}/images/generate`, {
              method: 'POST', body: JSON.stringify({ prompt: buildAvatarPrompt(newChar), character_id: newChar.id })
            }) as any;
            pollAvatarStatus(newChar.id, result.task_id);
          } catch (err) {
            console.error("Avatar generation failed:", err);
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
      }
    } catch (err) { alert('保存失败，请重试'); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('确定要删除这个角色吗？')) return;
    try {
      const response = await fetchWithAuth(`${API_BASE}/characters/${id}`, { method: 'DELETE' });
      if (response.ok) {
        setCharacters(characters.filter(c => c.id !== id));
        if (selectedCharacter?.id === id) setSelectedCharacter(null);
      }
    } catch { alert('删除失败'); }
  };

  // 删除旧的提取函数
  const handleExtractCharacters = async () => {};

  const handleGenerateAvatar = async (characterId: string) => {
    const char = characters.find(c => c.id === characterId);
    if (!char) return;
    setGeneratingAvatar(characterId);
    try {
      const data = await fetchJsonWithAuth(`${API_BASE}/images/generate`, {
        method: 'POST', body: JSON.stringify({ prompt: `character portrait, ${char.name}, ${char.appearance}`, character_id: characterId })
      });
      await fetchJsonWithAuth(`${API_BASE}/characters/${characterId}`, {
        method: 'PUT', body: JSON.stringify({ avatar: (data as any).image_url })
      });
      await loadCharacters();
    } catch { alert('生成头像失败'); }
    finally { setGeneratingAvatar(null); }
  };

  const handleCancel = () => { setIsEditing(false); setIsCreating(false); };

  function buildAvatarPrompt(char: Character): string {
    const parts: string[] = [];
    if (char.name) parts.push(`character: ${char.name}`);
    if (char.appearance) parts.push(`appearance: ${char.appearance}`);
    if (char.personality) parts.push(`personality: ${char.personality}`);
    parts.push("anime style, high quality, portrait");
    return parts.join(", ");
  }

  const pollAvatarStatus = async (charId: string, taskId: string) => {
    const maxAttempts = 30;
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise(r => setTimeout(r, 2000));
      try {
        const status = await fetchJsonWithAuth(`${API_BASE}/images/jobs/${taskId}`) as any;
        if (status.status === "succeeded") {
          const avatarUrl = status.image_url;
          await fetchJsonWithAuth(`${API_BASE}/characters/${charId}`, {
            method: 'PUT', body: JSON.stringify({ avatar: avatarUrl })
          });
          setCharacters(prev => prev.map(c => c.id === charId ? { ...c, avatar: avatarUrl } : c));
          setExtractedChars(prev => prev.map(c => c.id === charId ? { ...c, avatar_status: 'succeeded' } : c));
          setGeneratingAvatarId(null);
          return;
        } else if (status.status === "failed") {
          setExtractedChars(prev => prev.map(c => c.id === charId ? { ...c, avatar_status: 'failed' } : c));
          setGeneratingAvatarId(null);
          return;
        }
      } catch {
        // continue polling
      }
    }
    setGeneratingAvatarId(null);
  };

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
              <Button variant="outline" size="sm" onClick={loadCharacters}
                className="ml-auto border-red-500/50 text-red-400">重试</Button>
            </CardContent>
          </Card>
        )}

        {loading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-violet-400" />
            <span className="ml-3 text-white/60">加载中...</span>
          </div>
        )}

        {!loading && !error && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-1 space-y-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                <Input placeholder="搜索角色..." value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 bg-white/5 border-white/10 text-white" />
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
                          <img src={char.avatar} alt={char.name} className="w-10 h-10 rounded-full object-cover" />
                        ) : (
                          <User className="w-5 h-5 text-white" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-white font-medium truncate">{char.name}</div>
                        <div className="text-white/60 text-sm truncate">{char.description}</div>
                      </div>
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
                      {!isEditing && selectedCharacter && (
                        <>
                          <Button variant="outline" size="sm" onClick={handleEdit}>
                            <Edit2 className="w-4 h-4 mr-1" />编辑
                          </Button>
                          <Button variant="outline" size="sm" onClick={() => handleDelete(selectedCharacter.id)}
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
                    <div className="space-y-4">
                      <div className="flex items-center gap-2 text-white/80 mb-2">
                        <User className="w-4 h-4" /><span className="font-medium">基本信息</span>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                      <div className="flex items-center gap-4">
                        {selectedCharacter?.avatar ? (
                          <img src={selectedCharacter.avatar} alt={selectedCharacter.name}
                            className="w-20 h-20 rounded-full object-cover" />
                        ) : (
                          <div className="w-20 h-20 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
                            <User className="w-10 h-10 text-white" />
                          </div>
                        )}
                        {selectedCharacter && !isEditing && (
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
                        第{ch.chapter_number}章：{ch.title}（{ch.word_count || 0}字）
                      </option>
                    ))}
                  </select>
                )}
              </TabsContent>

              <TabsContent value="text" className="mt-0 space-y-3">
                <textarea
                  value={manualText}
                  onChange={(e) => setManualText(e.target.value)}
                  placeholder="在此粘贴小说或章节文本，AI将从中提取角色信息..."
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

              {extractedChars.length > 0 && (
                <div className="space-y-3">
                  <div className="text-sm text-white/60">头像生成状态：</div>
                  {extractedChars.map(char => (
                    <div key={char.id} className="flex items-center gap-3 p-2 bg-white/5 rounded-lg">
                      {char.avatar_status === 'generating' ? (
                        <Loader2 className="w-4 h-4 text-violet-400 animate-spin" />
                      ) : char.avatar_status === 'succeeded' ? (
                        <span className="w-4 h-4 rounded-full bg-green-500 flex items-center justify-center">
                          <span className="w-2 h-2 bg-white rounded-full" />
                        </span>
                      ) : char.avatar_status === 'failed' ? (
                        <AlertCircle className="w-4 h-4 text-red-400" />
                      ) : (
                        <div className="w-4 h-4 rounded-full border border-white/30" />
                      )}
                      <span className="text-sm text-white flex-1">{char.name}</span>
                      <span className="text-xs text-white/50">
                        {char.avatar_status === 'generating' ? '生成中...' : char.avatar_status === 'succeeded' ? '完成' : char.avatar_status === 'failed' ? '失败' : '等待'}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={() => setShowExtractModal(false)}
                  className="border-white/20 text-white">取消</Button>
                <Button onClick={handleDoExtract} disabled={extractingCharacters}
                  className="bg-violet-600 hover:bg-violet-700">
                  {extractingCharacters ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Sparkles className="w-4 h-4 mr-1" />}
                  {extractingCharacters ? '提取中...' : '开始提取'}
                </Button>
              </div>
            </div>
          </Tabs>
        </DialogContent>
      </Dialog>
    </MainLayout>
  );
}

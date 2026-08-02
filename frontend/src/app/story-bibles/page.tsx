'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import { ExpertToolBanner } from '@/components/layout/main-layout';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  Plus,
  BookOpen,
  Users,
  MapPin,
  Box,
  Zap,
  Edit,
  Save,
  X,
  ChevronRight,
  AlertCircle,
} from 'lucide-react';
import Link from 'next/link';
import { apiClient } from '@/lib/api-client';

interface StoryBible {
  id: string;
  user_id: string;
  project_id?: string;
  novel_id?: string;
  title: string;
  style?: string;
  worldview?: string;
  character_rules: any[];
  scene_rules: any[];
  prop_rules: any[];
  event_timeline: any[];
  negative_prompt?: string;
  extra_data: Record<string, any>;
  created_at: string;
  updated_at: string;
}

interface NovelOption {
  id: string;
  title: string;
  genre?: string;
  tags?: string[];
}

interface ConsistencyIssue {
  code: string;
  entity_type: string;
  name: string;
  severity: string;
  message: string;
  evidence?: string;
  resolved?: boolean;
  resolution?: string;
  suggested_action?: string;
}

interface Conflict {
  code: string;
  entity_type: string;
  name: string;
  severity: string;
  message: string;
  evidence?: string;
  resolved?: boolean;
  resolution?: string;
  incoming_data?: Record<string, any>;
}

const storyBibleToEditForm = (bible: StoryBible) => ({
  title: bible.title,
  style: bible.style || '',
  worldview: bible.worldview || '',
  negative_prompt: bible.negative_prompt || '',
  character_rules: bible.character_rules || [],
  scene_rules: bible.scene_rules || [],
  prop_rules: bible.prop_rules || [],
  event_timeline: bible.event_timeline || [],
});

const entityTypeLabel = (type: string) => {
  switch (type) {
    case 'character': return '角色';
    case 'scene': return '场景';
    case 'prop': return '道具';
    case 'event': return '事件';
    default: return type;
  }
};

const formatCheckedAt = (value?: string) => {
  if (!value) return '刚刚';
  try {
    return new Date(value).toLocaleString('zh-CN', { hour12: false });
  } catch {
    return value;
  }
};

const resolveNovelStyle = (novel?: NovelOption | null) => {
  return novel?.genre?.trim() || novel?.tags?.[0]?.trim() || 'anime';
};

export default function StoryBiblesPage() {
  const { toast } = useToast();
  const [storyBibles, setStoryBibles] = useState<StoryBible[]>([]);
  const [novels, setNovels] = useState<NovelOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingNovels, setLoadingNovels] = useState(true);
  const [selectedBible, setSelectedBible] = useState<StoryBible | null>(null);
  const [activeTab, setActiveTab] = useState('characters');

  // Editing state
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({
    title: '',
    style: '',
    worldview: '',
    negative_prompt: '',
    character_rules: [] as any[],
    scene_rules: [] as any[],
    prop_rules: [] as any[],
    event_timeline: [] as any[],
  });

  // Generate dialog
  const [generateDialogOpen, setGenerateDialogOpen] = useState(false);
  const [generateForm, setGenerateForm] = useState({
    novel_id: '',
    title: '',
    negative_prompt: '',
  });
  const [generating, setGenerating] = useState(false);

  const selectedGenerateNovel = novels.find((novel) => novel.id === generateForm.novel_id) || null;
  const generatedStyle = resolveNovelStyle(selectedGenerateNovel);
  const novelOptions = novels.map((novel) => ({
    value: novel.id,
    label: `${novel.title || '未命名小说'}${novel.genre ? ` · ${novel.genre}` : ''}`,
  }));

  // Consistency check
  const [checking, setChecking] = useState(false);
  const [resolvingIssueCode, setResolvingIssueCode] = useState<string | null>(null);
  const [checkResults, setCheckResults] = useState<{
    issues: ConsistencyIssue[];
    story_bible_id: string;
    checked_entity_count: number;
    issue_count?: number;
    pending_count?: number;
    resolved_count?: number;
    last_checked_at?: string;
  } | null>(null);

  useEffect(() => {
    loadStoryBibles();
    loadNovels();
  }, []);

  const loadStoryBibles = async () => {
    setLoading(true);
    try {
      const data = await apiClient.getStoryBibles();
      setStoryBibles(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('加载 Story Bible 失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadNovels = async () => {
    setLoadingNovels(true);
    try {
      const data = await apiClient.getNovels();
      setNovels(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('加载小说失败:', error);
    } finally {
      setLoadingNovels(false);
    }
  };

  const handleSelectBible = (bible: StoryBible) => {
    setSelectedBible(bible);
    setEditForm(storyBibleToEditForm(bible));
    setCheckResults(null);
    setActiveTab('characters');
  };

  const handleGenerateFromNovel = async () => {
    const novelId = generateForm.novel_id.trim();
    const title = generateForm.title.trim();
    const negativePrompt = generateForm.negative_prompt.trim();

    if (!novelId || !title) {
      toast({
        title: '请补齐必填项',
        description: '请选择小说并填写标题。',
        type: 'error',
      });
      return;
    }

    setGenerating(true);
    try {
      const result = await apiClient.generateStoryBible({
        novel_id: novelId,
        title,
        style: generatedStyle,
        negative_prompt: negativePrompt || undefined,
      });
      setGenerateDialogOpen(false);
      setGenerateForm({ novel_id: '', title: '', negative_prompt: '' });
      loadStoryBibles();
      if (result?.id) {
        handleSelectBible(result);
      }
    } catch (error) {
      console.error('生成 Story Bible 失败:', error);
    } finally {
      setGenerating(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!selectedBible) return;
    try {
      await apiClient.updateStoryBible(selectedBible.id, {
        title: editForm.title,
        style: editForm.style || null,
        worldview: editForm.worldview || null,
        negative_prompt: editForm.negative_prompt || null,
        character_rules: editForm.character_rules,
        scene_rules: editForm.scene_rules,
        prop_rules: editForm.prop_rules,
        event_timeline: editForm.event_timeline,
      });
      setEditing(false);
      loadStoryBibles();
    } catch (error) {
      console.error('保存 Story Bible 失败:', error);
    }
  };

  const handleCheckConsistency = async () => {
    if (!selectedBible) return;
    setChecking(true);
    try {
      const result = await apiClient.checkStoryBible({
        story_bible_id: selectedBible.id,
        novel_id: selectedBible.novel_id,
      });
      setCheckResults(result);
      const pendingCount = result?.pending_count ?? result?.issue_count ?? result?.issues?.length ?? 0;
      toast({
        title: pendingCount > 0 ? `发现 ${pendingCount} 个待处理项` : '一致性检查通过',
        description: `已检查 ${result?.checked_entity_count ?? 0} 个实体。`,
        type: pendingCount > 0 ? 'info' : 'success',
      });
    } catch (error) {
      console.error('一致性检查失败:', error);
      const message = error instanceof Error ? error.message : '请稍后重试。';
      toast({ title: '一致性检查失败', description: message, type: 'error' });
    } finally {
      setChecking(false);
    }
  };

  const handleResolveConflict = async (issueCode: string, resolution: string) => {
    if (!selectedBible) return;
    setResolvingIssueCode(issueCode);
    try {
      const result = await apiClient.resolveStoryBibleConflict({
        story_bible_id: selectedBible.id,
        issue_code: issueCode,
        resolution,
      });
      const updatedBible = result?.updated_story_bible;
      if (updatedBible?.id) {
        setSelectedBible(updatedBible);
        setEditForm(storyBibleToEditForm(updatedBible));
        setStoryBibles((items) => items.map((item) => item.id === updatedBible.id ? updatedBible : item));
      }
      setCheckResults((prev) => {
        if (!prev) return prev;
        const nextIssues = prev.issues.filter((issue) => issue.code !== issueCode);
        return {
          ...prev,
          issues: nextIssues,
          issue_count: nextIssues.length,
          pending_count: nextIssues.length,
          resolved_count: (prev.resolved_count || 0) + 1,
        };
      });
      toast({
        title: resolution === 'accept_incoming' ? '已收录/更新' : '已忽略本次问题',
        type: 'success',
      });
    } catch (error) {
      console.error('解决冲突失败:', error);
      const message = error instanceof Error ? error.message : '请稍后重试。';
      toast({ title: '处理失败', description: message, type: 'error' });
    } finally {
      setResolvingIssueCode(null);
    }
  };

  const renderRuleCard = (rule: any, index: number) => (
    <Card key={index} className="bg-white/5 border-white/10">
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <h4 className="text-white font-medium">{rule.name}</h4>
            {rule.description && (
              <p className="text-white/60 text-sm mt-1">{rule.description}</p>
            )}
            {rule.attributes && (
              <div className="flex flex-wrap gap-1 mt-2">
                {Object.entries(rule.attributes).map(([key, value]) => (
                  <Badge key={key} variant="outline" className="text-xs border-white/20 text-white/60">
                    {key}: {String(value)}
                  </Badge>
                ))}
              </div>
            )}
          </div>
          {editing && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0 text-red-400 hover:text-red-300"
              onClick={() => {
                const key = getActiveKey();
                setEditForm({
                  ...editForm,
                  [key]: editForm[key].filter((_, i) => i !== index),
                });
              }}
            >
              <X className="w-4 h-4" />
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );

  const getActiveKey = () => {
    switch (activeTab) {
      case 'characters': return 'character_rules';
      case 'scenes': return 'scene_rules';
      case 'props': return 'prop_rules';
      case 'events': return 'event_timeline';
      default: return 'character_rules';
    }
  };

  const getActiveRules = () => {
    return editForm[getActiveKey()] || [];
  };

  const handleAddRule = () => {
    const newRule = { name: '新规则', description: '', attributes: {} };
    setEditForm({
      ...editForm,
      [getActiveKey()]: [...getActiveRules(), newRule],
    });
  };

  const renderTab = (type: string, label: string, Icon: any) => (
    <TabsTrigger
      key={type}
      value={type}
      className="data-[state=active]:bg-white/10 data-[state=active]:text-white"
    >
      <Icon className="w-4 h-4 mr-2" />
      {label}
    </TabsTrigger>
  );

  const pendingIssues = checkResults?.issues || [];
  const pendingCount = checkResults
    ? (checkResults.pending_count ?? checkResults.issue_count ?? pendingIssues.length)
    : 0;
  const resolvedCount = checkResults?.resolved_count || 0;

  if (loading) {
    return (
      <div className="min-h-screen bg-background p-6 text-foreground">
        <div className="max-w-7xl mx-auto space-y-6">
          <Skeleton className="h-12 w-64" />
          <div className="grid grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-48" />)}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="max-w-7xl mx-auto p-4 space-y-6 sm:p-6">
        <ExpertToolBanner />
        {/* Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <h1 className="flex items-center gap-3 text-xl font-bold text-white sm:text-2xl">
              <BookOpen className="w-7 h-7 shrink-0 text-violet-400" />
              Story Bible 管理
            </h1>
            <p className="text-white/60 mt-1">管理角色、场景、道具和事件的跨章节一致性</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              className="border-white/20 text-white hover:bg-white/10"
              onClick={loadStoryBibles}
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              刷新
            </Button>
            <Button
              size="sm"
              className="bg-violet-600 hover:bg-violet-700"
              onClick={() => setGenerateDialogOpen(true)}
            >
              <Plus className="w-4 h-4 mr-2" />
              从小说生成
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
          {/* Sidebar: Story Bible List */}
          <div className="space-y-4 lg:col-span-1">
            <h3 className="text-sm font-medium text-white/60 uppercase tracking-wider">Story Bibles</h3>
            <div className="space-y-2">
              {storyBibles.length === 0 ? (
                <Card className="bg-white/5 border-white/10">
                  <CardContent className="p-4 text-center">
                    <p className="text-white/40 text-sm">还没有 Story Bible</p>
                    <Button
                      size="sm"
                      variant="link"
                      className="mt-2 text-violet-400"
                      onClick={() => setGenerateDialogOpen(true)}
                    >
                      从小说生成
                    </Button>
                  </CardContent>
                </Card>
              ) : (
                storyBibles.map((bible) => (
                  <Card
                    key={bible.id}
                    className={`bg-white/5 border-white/10 cursor-pointer transition-colors hover:border-white/20 ${
                      selectedBible?.id === bible.id ? 'border-violet-500 bg-violet-500/10' : ''
                    }`}
                    onClick={() => handleSelectBible(bible)}
                  >
                    <CardContent className="p-4">
                      <h4 className="text-white font-medium truncate">{bible.title}</h4>
                      <div className="flex flex-wrap items-center gap-2 mt-2 text-xs text-white/40">
                        <span>角色 {bible.character_rules?.length || 0}</span>
                        <span>|</span>
                        <span>场景 {bible.scene_rules?.length || 0}</span>
                      </div>
                      <div className="text-xs text-white/30 mt-1">
                        {new Date(bible.updated_at).toLocaleDateString()}
                      </div>
                    </CardContent>
                  </Card>
                ))
              )}
            </div>
          </div>

          {/* Main Content: Selected Bible */}
          <div className="min-w-0 lg:col-span-3">
            {selectedBible ? (
              <div className="space-y-6">
                {/* Bible Header */}
                <Card className="bg-white/5 border-white/10">
                  <CardContent className="p-6">
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0 flex-1">
                        {editing ? (
                          <div className="space-y-4">
                            <Input
                              value={editForm.title}
                              onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                              className="bg-white/5 border-white/10 text-white text-xl font-bold"
                              placeholder="Story Bible 标题"
                            />
                            <Input
                              value={editForm.style}
                              onChange={(e) => setEditForm({ ...editForm, style: e.target.value })}
                              className="bg-white/5 border-white/10 text-white"
                              placeholder="风格 (如 anime, realistic)"
                            />
                            <Textarea
                              value={editForm.worldview}
                              onChange={(e) => setEditForm({ ...editForm, worldview: e.target.value })}
                              className="bg-white/5 border-white/10 text-white"
                              placeholder="世界观设定"
                              rows={3}
                            />
                          </div>
                        ) : (
                          <>
                            <h2 className="break-words text-xl font-bold text-white">{selectedBible.title}</h2>
                            <div className="flex flex-wrap items-center gap-2 mt-2 sm:gap-4">
                              {selectedBible.style && (
                                <Badge variant="outline" className="border-white/20 text-white/60">
                                  {selectedBible.style}
                                </Badge>
                              )}
                              <span className="text-white/40 text-sm">
                                角色 {selectedBible.character_rules?.length || 0} |
                                场景 {selectedBible.scene_rules?.length || 0} |
                                道具 {selectedBible.prop_rules?.length || 0}
                              </span>
                            </div>
                            {selectedBible.worldview && (
                              <p className="text-white/60 text-sm mt-3">{selectedBible.worldview}</p>
                            )}
                          </>
                        )}
                      </div>
                      <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                        {editing ? (
                          <>
                            <Button
                              variant="outline"
                              size="sm"
                              className="border-white/20 text-white"
                              onClick={() => setEditing(false)}
                            >
                              <X className="w-4 h-4 mr-2" />
                              取消
                            </Button>
                            <Button
                              size="sm"
                              className="bg-violet-600 hover:bg-violet-700"
                              onClick={handleSaveEdit}
                            >
                              <Save className="w-4 h-4 mr-2" />
                              保存
                            </Button>
                          </>
                        ) : (
                          <>
                            <Button
                              variant="outline"
                              size="sm"
                              className="border-white/20 text-white hover:bg-white/10"
                              onClick={() => setEditing(true)}
                            >
                              <Edit className="w-4 h-4 mr-2" />
                              编辑
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              className="border-amber-500/50 text-amber-400 hover:bg-amber-500/10"
                              onClick={handleCheckConsistency}
                              disabled={checking}
                            >
                              {checking ? (
                                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                              ) : (
                                <AlertTriangle className="w-4 h-4 mr-2" />
                              )}
                              一致性检查
                            </Button>
                          </>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Consistency Check Results */}
                {checkResults && (
                  <Card className={pendingCount > 0 ? 'bg-amber-500/10 border-amber-500/30' : 'bg-emerald-500/10 border-emerald-500/30'}>
                    <CardHeader className="space-y-4">
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                        <div className="min-w-0">
                          <CardTitle className={`flex items-center gap-2 ${pendingCount > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
                            {pendingCount > 0 ? (
                              <AlertTriangle className="w-5 h-5 shrink-0" />
                            ) : (
                              <CheckCircle className="w-5 h-5 shrink-0" />
                            )}
                            一致性检查
                          </CardTitle>
                          <p className="mt-1 text-sm text-white/60">
                            待处理 {pendingCount} 项 · 已处理 {resolvedCount} 项 · 已检查 {checkResults.checked_entity_count} 个实体
                          </p>
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          className="w-full border-white/20 text-white hover:bg-white/10 sm:w-auto"
                          onClick={handleCheckConsistency}
                          disabled={checking}
                        >
                          <RefreshCw className={`w-4 h-4 mr-2 ${checking ? 'animate-spin' : ''}`} />
                          重新检查
                        </Button>
                      </div>
                      <div className="grid gap-2 sm:grid-cols-3">
                        <div className="rounded-lg border border-white/10 bg-white/5 px-3 py-2">
                          <p className="text-xs text-white/40">检查时间</p>
                          <p className="text-sm text-white">{formatCheckedAt(checkResults.last_checked_at)}</p>
                        </div>
                        <div className="rounded-lg border border-white/10 bg-white/5 px-3 py-2">
                          <p className="text-xs text-white/40">待处理</p>
                          <p className="text-sm text-white">{pendingCount} 项</p>
                        </div>
                        <div className="rounded-lg border border-white/10 bg-white/5 px-3 py-2">
                          <p className="text-xs text-white/40">推荐动作</p>
                          <p className="text-sm text-white">{pendingCount > 0 ? '逐项收录或忽略' : '无需处理'}</p>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {pendingIssues.length === 0 ? (
                        <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-4">
                          <div className="flex items-center gap-2 text-emerald-300">
                            <CheckCircle className="w-5 h-5" />
                            <span className="font-medium">当前没有待处理的一致性问题</span>
                          </div>
                          <p className="mt-1 text-sm text-white/60">已忽略或已收录的问题会保留在 Story Bible 的处理记录中。</p>
                        </div>
                      ) : (
                        pendingIssues.map((issue) => (
                          <div
                            key={issue.code}
                            className="flex flex-col gap-3 rounded-lg bg-white/5 p-3 sm:flex-row sm:items-start"
                          >
                            <AlertCircle className={`w-5 h-5 shrink-0 sm:mt-0.5 ${
                              issue.severity === 'error' ? 'text-red-400' : 'text-amber-400'
                            }`} />
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <Badge variant="outline" className="text-xs border-white/20 text-white/70">
                                  {entityTypeLabel(issue.entity_type)}
                                </Badge>
                                <span className="break-words text-white font-medium">{issue.name}</span>
                                {issue.suggested_action && (
                                  <Badge variant="outline" className="text-xs border-emerald-500/30 text-emerald-300">
                                    {issue.suggested_action}
                                  </Badge>
                                )}
                              </div>
                              <p className="mt-1 break-words text-sm text-white/65">{issue.message}</p>
                              {issue.evidence && (
                                <p className="mt-1 break-words text-xs italic text-white/40">证据：{issue.evidence}</p>
                              )}
                            </div>
                            <div className="flex shrink-0 flex-wrap gap-2 sm:justify-end">
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-8 border-green-500/50 px-3 text-xs text-green-400 hover:bg-green-500/10"
                                onClick={() => handleResolveConflict(issue.code, 'accept_incoming')}
                                disabled={resolvingIssueCode === issue.code}
                              >
                                收录/更新
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-8 border-red-500/50 px-3 text-xs text-red-400 hover:bg-red-500/10"
                                onClick={() => handleResolveConflict(issue.code, 'reject_incoming')}
                                disabled={resolvingIssueCode === issue.code}
                              >
                                忽略本次
                              </Button>
                            </div>
                          </div>
                        ))
                      )}
                    </CardContent>
                  </Card>
                )}

                {/* Rules Tabs */}
                <Tabs value={activeTab} onValueChange={setActiveTab}>
                  <TabsList className="bg-white/5 border border-white/10">
                    {renderTab('characters', '角色', Users)}
                    {renderTab('scenes', '场景', MapPin)}
                    {renderTab('props', '道具', Box)}
                    {renderTab('events', '事件', Zap)}
                  </TabsList>

                  <TabsContent value={activeTab} className="mt-6">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-white font-medium">
                        {activeTab === 'characters' && `角色规则 (${getActiveRules().length})`}
                        {activeTab === 'scenes' && `场景规则 (${getActiveRules().length})`}
                        {activeTab === 'props' && `道具规则 (${getActiveRules().length})`}
                        {activeTab === 'events' && `事件时间线 (${getActiveRules().length})`}
                      </h3>
                      {editing && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="border-white/20 text-white"
                          onClick={handleAddRule}
                        >
                          <Plus className="w-4 h-4 mr-2" />
                          添加规则
                        </Button>
                      )}
                    </div>

                    {getActiveRules().length > 0 ? (
                      <div className="space-y-3">
                        {getActiveRules().map((rule, index) => renderRuleCard(rule, index))}
                      </div>
                    ) : (
                      <Card className="bg-white/5 border-white/10">
                        <CardContent className="p-8 text-center">
                          <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-white/5 flex items-center justify-center">
                            <Users className="w-6 h-6 text-white/40" />
                          </div>
                          <p className="text-white/60">还没有规则</p>
                          {editing && (
                            <Button
                              size="sm"
                              variant="link"
                              className="mt-2 text-violet-400"
                              onClick={handleAddRule}
                            >
                              添加第一条规则
                            </Button>
                          )}
                        </CardContent>
                      </Card>
                    )}
                  </TabsContent>
                </Tabs>
              </div>
            ) : (
              <Card className="bg-white/5 border-white/10">
                <CardContent className="p-12 text-center">
                  <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-white/5 flex items-center justify-center">
                    <BookOpen className="w-8 h-8 text-white/40" />
                  </div>
                  <h3 className="text-lg font-medium text-white mb-2">选择或创建一个 Story Bible</h3>
                  <p className="text-white/60 mb-4">
                    Story Bible 用于保持角色、场景、道具和事件在跨章节中的一致性
                  </p>
                  <Button
                    className="bg-violet-600 hover:bg-violet-700"
                    onClick={() => setGenerateDialogOpen(true)}
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    从小说生成
                  </Button>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>

      {/* Generate Dialog */}
      <Dialog open={generateDialogOpen} onOpenChange={setGenerateDialogOpen}>
        <DialogContent className="bg-gray-900 border-white/10 text-white">
          <DialogHeader>
            <DialogTitle>从小说生成 Story Bible</DialogTitle>
            <DialogDescription>
              从小说章节中抽取角色、场景、道具和事件，生成一致性圣经
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <label className="text-sm text-white/60 mb-1 block">小说 *</label>
              <Select
                value={generateForm.novel_id}
                onChange={(e) => {
                  const novel = novels.find((item) => item.id === e.target.value);
                  setGenerateForm({
                    ...generateForm,
                    novel_id: e.target.value,
                    title: novel ? `${novel.title || '未命名小说'} Story Bible` : '',
                  });
                }}
                options={novelOptions}
                placeholder={loadingNovels ? '正在加载小说...' : '选择小说'}
                disabled={loadingNovels || novelOptions.length === 0}
              />
            </div>
            <div>
              <label className="text-sm text-white/60 mb-1 block">标题 *</label>
              <Input
                value={generateForm.title}
                onChange={(e) => setGenerateForm({ ...generateForm, title: e.target.value })}
                className="bg-white/5 border-white/10 text-white"
                placeholder="Story Bible 标题"
              />
            </div>
            <div>
              <label className="text-sm text-white/60 mb-1 block">风格</label>
              <div className="min-h-10 rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-white">
                {selectedGenerateNovel ? generatedStyle : '选择小说后自动带出'}
              </div>
            </div>
            <div>
              <label className="text-sm text-white/60 mb-1 block">负面提示词</label>
              <Textarea
                value={generateForm.negative_prompt}
                onChange={(e) => setGenerateForm({ ...generateForm, negative_prompt: e.target.value })}
                className="bg-white/5 border-white/10 text-white"
                placeholder="不希望出现的元素..."
                rows={2}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setGenerateDialogOpen(false)}
              className="border-white/10 text-white"
            >
              取消
            </Button>
            <Button
              onClick={handleGenerateFromNovel}
              disabled={
                !generateForm.novel_id.trim() ||
                !generateForm.title.trim() ||
                generating
              }
              className="bg-violet-600 hover:bg-violet-700"
            >
              {generating ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  生成中...
                </>
              ) : (
                <>
                  <Plus className="w-4 h-4 mr-2" />
                  生成
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

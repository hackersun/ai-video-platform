'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
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

interface ConsistencyIssue {
  entity_type: string;
  name: string;
  severity: string;
  message: string;
  evidence?: string;
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

export default function StoryBiblesPage() {
  const [storyBibles, setStoryBibles] = useState<StoryBible[]>([]);
  const [loading, setLoading] = useState(true);
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
    style: 'anime',
    negative_prompt: '',
  });
  const [generating, setGenerating] = useState(false);

  // Consistency check
  const [checking, setChecking] = useState(false);
  const [checkResults, setCheckResults] = useState<{ issues: ConsistencyIssue[]; story_bible_id: string; checked_entity_count: number } | null>(null);

  useEffect(() => {
    loadStoryBibles();
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

  const handleSelectBible = (bible: StoryBible) => {
    setSelectedBible(bible);
    setEditForm({
      title: bible.title,
      style: bible.style || '',
      worldview: bible.worldview || '',
      negative_prompt: bible.negative_prompt || '',
      character_rules: bible.character_rules || [],
      scene_rules: bible.scene_rules || [],
      prop_rules: bible.event_timeline || [],
      event_timeline: bible.event_timeline || [],
    });
    setCheckResults(null);
    setActiveTab('characters');
  };

  const handleGenerateFromNovel = async () => {
    if (!generateForm.novel_id || !generateForm.title) return;
    setGenerating(true);
    try {
      const result = await apiClient.generateStoryBible({
        novel_id: generateForm.novel_id,
        title: generateForm.title,
        style: generateForm.style,
        negative_prompt: generateForm.negative_prompt,
      });
      setGenerateDialogOpen(false);
      setGenerateForm({ novel_id: '', title: '', style: 'anime', negative_prompt: '' });
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
    } catch (error) {
      console.error('一致性检查失败:', error);
    } finally {
      setChecking(false);
    }
  };

  const handleResolveConflict = async (issueCode: string, resolution: string) => {
    if (!selectedBible) return;
    try {
      await apiClient.resolveStoryBibleConflict({
        story_bible_id: selectedBible.id,
        issue_code: issueCode,
        resolution,
      });
      // Refresh check results
      handleCheckConsistency();
    } catch (error) {
      console.error('解决冲突失败:', error);
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

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 p-6">
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
    <div className="min-h-screen bg-gray-950">
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-3">
              <BookOpen className="w-7 h-7 text-violet-400" />
              Story Bible 管理
            </h1>
            <p className="text-white/60 mt-1">管理角色、场景、道具和事件的跨章节一致性</p>
          </div>
          <div className="flex items-center gap-3">
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

        <div className="grid grid-cols-4 gap-6">
          {/* Sidebar: Story Bible List */}
          <div className="col-span-1 space-y-4">
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
                      <div className="flex items-center gap-2 mt-2 text-xs text-white/40">
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
          <div className="col-span-3">
            {selectedBible ? (
              <div className="space-y-6">
                {/* Bible Header */}
                <Card className="bg-white/5 border-white/10">
                  <CardContent className="p-6">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
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
                            <h2 className="text-xl font-bold text-white">{selectedBible.title}</h2>
                            <div className="flex items-center gap-4 mt-2">
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
                      <div className="flex items-center gap-2">
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
                {checkResults && checkResults.issues.length > 0 && (
                  <Card className="bg-amber-500/10 border-amber-500/30">
                    <CardHeader>
                      <CardTitle className="text-amber-400 flex items-center gap-2">
                        <AlertTriangle className="w-5 h-5" />
                        一致性问题 ({checkResults.issues.length})
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {checkResults.issues.map((issue, idx) => (
                        <div
                          key={idx}
                          className="flex items-start gap-3 p-3 bg-white/5 rounded-lg"
                        >
                          <AlertCircle className={`w-5 h-5 mt-0.5 ${
                            issue.severity === 'error' ? 'text-red-400' : 'text-amber-400'
                          }`} />
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <Badge variant="outline" className="text-xs border-white/20">
                                {issue.entity_type}
                              </Badge>
                              <span className="text-white font-medium">{issue.name}</span>
                            </div>
                            <p className="text-white/60 text-sm mt-1">{issue.message}</p>
                            {issue.evidence && (
                              <p className="text-white/40 text-xs mt-1 italic">证据: {issue.evidence}</p>
                            )}
                          </div>
                          <div className="flex gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 text-xs border-green-500/50 text-green-400"
                              onClick={() => handleResolveConflict(`${issue.entity_type}_${issue.name}`, 'accept_incoming')}
                            >
                              接受
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 text-xs border-red-500/50 text-red-400"
                              onClick={() => handleResolveConflict(`${issue.entity_type}_${issue.name}`, 'reject_incoming')}
                            >
                              忽略
                            </Button>
                          </div>
                        </div>
                      ))}
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
              <label className="text-sm text-white/60 mb-1 block">小说 ID *</label>
              <Input
                value={generateForm.novel_id}
                onChange={(e) => setGenerateForm({ ...generateForm, novel_id: e.target.value })}
                className="bg-white/5 border-white/10 text-white"
                placeholder="输入小说 ID"
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
              <Input
                value={generateForm.style}
                onChange={(e) => setGenerateForm({ ...generateForm, style: e.target.value })}
                className="bg-white/5 border-white/10 text-white"
                placeholder="anime, realistic, etc."
              />
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
              disabled={!generateForm.novel_id || !generateForm.title || generating}
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
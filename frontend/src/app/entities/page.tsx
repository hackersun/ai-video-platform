'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Skeleton } from '@/components/ui/skeleton';
import { MainLayout } from '@/components/layout/main-layout';
import {
  Users,
  MapPin,
  Box,
  Zap,
  CheckCircle,
  XCircle,
  Search,
  Merge,
  Trash2,
  Edit,
  Eye,
  MoreVertical,
  RefreshCw,
} from 'lucide-react';
import Link from 'next/link';

interface StoryEntity {
  id: string;
  entity_type: string;
  name: string;
  canonical_name?: string;
  description?: string;
  aliases: string[];
  appearance?: string;
  visual_prompt?: string;
  first_seen_chapter_id?: string;
  relations: any[];
  state_changes: any[];
  attributes: Record<string, any>;
  tags: string[];
  version: number;
  is_approved: boolean;
  consistency_score: number;
  evidence?: string;
  confidence: number;
  source: string;
  novel_id?: string;
  chapter_id?: string;
  created_at: string;
  updated_at: string;
}

interface EntityStats {
  total: number;
  counts: Record<string, number>;
}

const ENTITY_TYPE_CONFIG = {
  character: { label: '角色', icon: Users, color: 'text-green-400', bgColor: 'bg-green-500/20' },
  scene: { label: '场景', icon: MapPin, color: 'text-blue-400', bgColor: 'bg-blue-500/20' },
  prop: { label: '道具', icon: Box, color: 'text-amber-400', bgColor: 'bg-amber-500/20' },
  event: { label: '事件', icon: Zap, color: 'text-purple-400', bgColor: 'bg-purple-500/20' },
};

export default function EntitiesPage() {
  const [entities, setEntities] = useState<StoryEntity[]>([]);
  const [stats, setStats] = useState<EntityStats>({ total: 0, counts: {} });
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEntities, setSelectedEntities] = useState<Set<string>>(new Set());
  const [activeTab, setActiveTab] = useState('all');

  // Edit dialog state
  const [editingEntity, setEditingEntity] = useState<StoryEntity | null>(null);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editForm, setEditForm] = useState({
    name: '',
    canonical_name: '',
    description: '',
    aliases: '',
    appearance: '',
  });

  // Merge dialog state
  const [mergeDialogOpen, setMergeDialogOpen] = useState(false);
  const [mergeTarget, setMergeTarget] = useState<string | null>(null);

  // Detail dialog state
  const [detailEntity, setDetailEntity] = useState<StoryEntity | null>(null);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);

  useEffect(() => {
    loadEntities();
    loadStats();
  }, [activeTab]);

  const loadEntities = async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = { limit: '100' };
      if (activeTab !== 'all') {
        params.entity_type = activeTab;
      }
      const searchParams = new URLSearchParams(params);
      const response = await fetch(`/api/v1/story-bibles/entities?${searchParams}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setEntities(Array.isArray(data) ? data : []);
      }
    } catch (error) {
      console.error('加载实体失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const response = await fetch('/api/v1/story-bibles/entities/stats', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error('加载统计失败:', error);
    }
  };

  const filteredEntities = entities.filter((entity) => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      return (
        entity.name.toLowerCase().includes(query) ||
        entity.description?.toLowerCase().includes(query) ||
        entity.aliases.some((a) => a.toLowerCase().includes(query))
      );
    }
    return true;
  });

  const handleSelectEntity = (entityId: string) => {
    const newSelected = new Set(selectedEntities);
    if (newSelected.has(entityId)) {
      newSelected.delete(entityId);
    } else {
      newSelected.add(entityId);
    }
    setSelectedEntities(newSelected);
  };

  const handleSelectAll = (entityIds: string[]) => {
    if (selectedEntities.size === entityIds.length) {
      setSelectedEntities(new Set());
    } else {
      setSelectedEntities(new Set(entityIds));
    }
  };

  const handleEditEntity = (entity: StoryEntity) => {
    setEditingEntity(entity);
    setEditForm({
      name: entity.name,
      canonical_name: entity.canonical_name || '',
      description: entity.description || '',
      aliases: entity.aliases.join(', '),
      appearance: entity.appearance || '',
    });
    setEditDialogOpen(true);
  };

  const handleSaveEdit = async () => {
    if (!editingEntity) return;
    try {
      const response = await fetch(`/api/v1/story-bibles/entities/${editingEntity.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
        },
        body: JSON.stringify({
          name: editForm.name,
          canonical_name: editForm.canonical_name || null,
          description: editForm.description || null,
          aliases: editForm.aliases.split(',').map((a) => a.trim()).filter(Boolean),
          appearance: editForm.appearance || null,
        }),
      });
      if (response.ok) {
        setEditDialogOpen(false);
        loadEntities();
        loadStats();
      }
    } catch (error) {
      console.error('更新实体失败:', error);
    }
  };

  const handleDeleteEntity = async (entityId: string) => {
    if (!confirm('确定要删除这个实体吗？')) return;
    try {
      const response = await fetch(`/api/v1/story-bibles/entities/${entityId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
        },
      });
      if (response.ok) {
        loadEntities();
        loadStats();
      }
    } catch (error) {
      console.error('删除实体失败:', error);
    }
  };

  const handleBulkApprove = async (approved: boolean) => {
    if (selectedEntities.size === 0) return;
    try {
      const response = await fetch('/api/v1/story-bibles/entities/bulk-approve', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
        },
        body: JSON.stringify({
          entity_ids: Array.from(selectedEntities),
          approved,
        }),
      });
      if (response.ok) {
        setSelectedEntities(new Set());
        loadEntities();
        loadStats();
      }
    } catch (error) {
      console.error('批量确认失败:', error);
    }
  };

  const handleMergeEntities = async () => {
    if (selectedEntities.size < 2 || !mergeTarget) return;
    try {
      const response = await fetch('/api/v1/story-bibles/entities/merge', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
        },
        body: JSON.stringify({
          source_entity_ids: Array.from(selectedEntities).filter((id) => id !== mergeTarget),
          target_entity_id: mergeTarget,
        }),
      });
      if (response.ok) {
        setMergeDialogOpen(false);
        setMergeTarget(null);
        setSelectedEntities(new Set());
        loadEntities();
        loadStats();
      }
    } catch (error) {
      console.error('合并实体失败:', error);
    }
  };

  const handleViewDetail = (entity: StoryEntity) => {
    setDetailEntity(entity);
    setDetailDialogOpen(true);
  };

  const renderEntityCard = (entity: StoryEntity) => {
    const config = ENTITY_TYPE_CONFIG[entity.entity_type as keyof typeof ENTITY_TYPE_CONFIG] || ENTITY_TYPE_CONFIG.character;
    const Icon = config.icon;

    return (
      <Card
        key={entity.id}
        className={`bg-white/5 border-white/10 transition-colors hover:border-white/20 ${
          selectedEntities.has(entity.id) ? 'border-violet-500 bg-violet-500/10' : ''
        }`}
      >
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <Checkbox
              checked={selectedEntities.has(entity.id)}
              onCheckedChange={() => handleSelectEntity(entity.id)}
              className="mt-1"
            />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-2">
                <div className={`w-8 h-8 rounded ${config.bgColor} flex items-center justify-center`}>
                  <Icon className={`w-4 h-4 ${config.color}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="text-white font-medium truncate">{entity.name}</h3>
                  {entity.canonical_name && entity.canonical_name !== entity.name && (
                    <p className="text-white/40 text-xs truncate">{entity.canonical_name}</p>
                  )}
                </div>
                {entity.is_approved ? (
                  <Badge variant="default" className="bg-green-500/20 text-green-400 border-green-500/30">
                    <CheckCircle className="w-3 h-3 mr-1" />
                    已确认
                  </Badge>
                ) : (
                  <Badge variant="secondary" className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30">
                    <XCircle className="w-3 h-3 mr-1" />
                    待审阅
                  </Badge>
                )}
              </div>

              {entity.description && (
                <p className="text-white/60 text-sm mb-2 line-clamp-2">{entity.description}</p>
              )}

              {entity.aliases.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-2">
                  {entity.aliases.slice(0, 3).map((alias, idx) => (
                    <Badge key={idx} variant="outline" className="text-xs border-white/20 text-white/60">
                      {alias}
                    </Badge>
                  ))}
                  {entity.aliases.length > 3 && (
                    <Badge variant="outline" className="text-xs border-white/20 text-white/60">
                      +{entity.aliases.length - 3}
                    </Badge>
                  )}
                </div>
              )}

              <div className="flex items-center justify-between mt-3">
                <div className="flex items-center gap-2 text-xs text-white/40">
                  <span>置信度: {entity.confidence}%</span>
                  {entity.source && <span>来源: {entity.source}</span>}
                </div>
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0 text-white/60 hover:text-white"
                    onClick={() => handleViewDetail(entity)}
                  >
                    <Eye className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0 text-white/60 hover:text-white"
                    onClick={() => handleEditEntity(entity)}
                  >
                    <Edit className="w-4 h-4" />
                  </Button>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 text-white/60 hover:text-white"
                      >
                        <MoreVertical className="w-4 h-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent>
                      <DropdownMenuItem onClick={() => handleDeleteEntity(entity.id)}>
                        <Trash2 className="w-4 h-4 mr-2" />
                        删除
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  };

  const renderTab = (type: string) => {
    const config = type === 'all' ? null : ENTITY_TYPE_CONFIG[type as keyof typeof ENTITY_TYPE_CONFIG];
    const Icon = config?.icon || Users;
    const count = type === 'all' ? stats.total : stats.counts[type] || 0;
    const label = config?.label || '全部';

    return (
      <TabsTrigger
        key={type}
        value={type}
        className="data-[state=active]:bg-white/10 data-[state=active]:text-white"
      >
        <Icon className="w-4 h-4 mr-2" />
        {label}
        <span className="ml-2 px-1.5 py-0.5 rounded-full bg-white/10 text-xs">{count}</span>
      </TabsTrigger>
    );
  };

  if (loading) {
    return (
      <MainLayout>
        <div className="space-y-6 p-6">
          <div className="flex items-center justify-between">
            <Skeleton className="h-8 w-32" />
            <Skeleton className="h-10 w-40" />
          </div>
          <Skeleton className="h-12 w-full" />
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <Skeleton key={i} className="h-48" />
            ))}
          </div>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="space-y-6 p-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">实体审阅台</h1>
            <p className="text-white/60 mt-1">管理角色、场景、道具和事件实体</p>
          </div>
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              className="border-white/20 text-white hover:bg-white/10"
              onClick={() => {
                loadEntities();
                loadStats();
              }}
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              刷新
            </Button>
            <Button asChild size="sm" className="bg-violet-600 hover:bg-violet-700">
              <Link href="/novels">
                <Users className="w-4 h-4 mr-2" />
                导入小说
              </Link>
            </Button>
          </div>
        </div>

        {/* Stats cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Object.entries(ENTITY_TYPE_CONFIG).map(([type, config]) => {
            const Icon = config.icon;
            const count = stats.counts[type] || 0;
            return (
              <Card
                key={type}
                className={`bg-white/5 border-white/10 cursor-pointer transition-colors hover:border-white/20`}
                onClick={() => setActiveTab(type)}
              >
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className={`w-10 h-10 rounded ${config.bgColor} flex items-center justify-center`}>
                      <Icon className={`w-5 h-5 ${config.color}`} />
                    </div>
                    <span className="text-2xl font-bold text-white">{count}</span>
                  </div>
                  <div className="text-white/60 text-sm mt-2">{config.label}</div>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Actions bar */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
              <Input
                placeholder="搜索实体..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 w-64 bg-white/5 border-white/10 text-white placeholder:text-white/40"
              />
            </div>
            {selectedEntities.size > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-white/60 text-sm">已选择 {selectedEntities.size} 个</span>
                <Button
                  variant="outline"
                  size="sm"
                  className="border-green-500/50 text-green-400 hover:bg-green-500/10"
                  onClick={() => handleBulkApprove(true)}
                >
                  <CheckCircle className="w-4 h-4 mr-2" />
                  批量确认
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="border-yellow-500/50 text-yellow-400 hover:bg-yellow-500/10"
                  onClick={() => handleBulkApprove(false)}
                >
                  <XCircle className="w-4 h-4 mr-2" />
                  批量取消确认
                </Button>
                {selectedEntities.size >= 2 && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="border-purple-500/50 text-purple-400 hover:bg-purple-500/10"
                    onClick={() => {
                      setMergeTarget(Array.from(selectedEntities)[0]);
                      setMergeDialogOpen(true);
                    }}
                  >
                    <Merge className="w-4 h-4 mr-2" />
                    合并
                  </Button>
                )}
              </div>
            )}
          </div>
          <div className="text-white/40 text-sm">
            共 {filteredEntities.length} 个实体
          </div>
        </div>

        {/* Tabs and content */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-white/5 border border-white/10">
            {renderTab('all')}
            {Object.keys(ENTITY_TYPE_CONFIG).map((type) => renderTab(type))}
          </TabsList>

          <TabsContent value={activeTab} className="mt-6">
            {filteredEntities.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredEntities.map(renderEntityCard)}
              </div>
            ) : (
              <Card className="bg-white/5 border-white/10">
                <CardContent className="p-12 text-center">
                  <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-white/5 flex items-center justify-center">
                    <Users className="w-8 h-8 text-white/40" />
                  </div>
                  <h3 className="text-lg font-medium text-white mb-2">暂无实体</h3>
                  <p className="text-white/60 mb-4">
                    {activeTab === 'all'
                      ? '从小说中抽取角色、场景、道具和事件'
                      : `还没有${ENTITY_TYPE_CONFIG[activeTab as keyof typeof ENTITY_TYPE_CONFIG]?.label}实体`}
                  </p>
                  <Button asChild className="bg-violet-600 hover:bg-violet-700">
                    <Link href="/novels">
                      去导入小说
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            )}
          </TabsContent>
        </Tabs>

        {/* Edit Dialog */}
        <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
          <DialogContent className="bg-gray-900 border-white/10 text-white">
            <DialogHeader>
              <DialogTitle>编辑实体</DialogTitle>
              <DialogDescription>修改实体信息</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div>
                <label className="text-sm text-white/60 mb-1 block">名称</label>
                <Input
                  value={editForm.name}
                  onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                  className="bg-white/5 border-white/10 text-white"
                />
              </div>
              <div>
                <label className="text-sm text-white/60 mb-1 block">规范名称</label>
                <Input
                  value={editForm.canonical_name}
                  onChange={(e) => setEditForm({ ...editForm, canonical_name: e.target.value })}
                  className="bg-white/5 border-white/10 text-white"
                  placeholder="用于保持一致性的标准名称"
                />
              </div>
              <div>
                <label className="text-sm text-white/60 mb-1 block">别名 (逗号分隔)</label>
                <Input
                  value={editForm.aliases}
                  onChange={(e) => setEditForm({ ...editForm, aliases: e.target.value })}
                  className="bg-white/5 border-white/10 text-white"
                  placeholder="张三, 小三, 三哥"
                />
              </div>
              <div>
                <label className="text-sm text-white/60 mb-1 block">描述</label>
                <Textarea
                  value={editForm.description}
                  onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                  className="bg-white/5 border-white/10 text-white min-h-[100px]"
                />
              </div>
              <div>
                <label className="text-sm text-white/60 mb-1 block">外观描述</label>
                <Textarea
                  value={editForm.appearance}
                  onChange={(e) => setEditForm({ ...editForm, appearance: e.target.value })}
                  className="bg-white/5 border-white/10 text-white min-h-[80px]"
                  placeholder="用于生成角色图的视觉描述"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditDialogOpen(false)} className="border-white/10 text-white">
                取消
              </Button>
              <Button onClick={handleSaveEdit} className="bg-violet-600 hover:bg-violet-700">
                保存
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Merge Dialog */}
        <Dialog open={mergeDialogOpen} onOpenChange={setMergeDialogOpen}>
          <DialogContent className="bg-gray-900 border-white/10 text-white">
            <DialogHeader>
              <DialogTitle>合并实体</DialogTitle>
              <DialogDescription>将多个实体合并为一个，保留的将成为主实体</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div>
                <label className="text-sm text-white/60 mb-1 block">选择主实体</label>
                <select
                  value={mergeTarget || ''}
                  onChange={(e) => setMergeTarget(e.target.value)}
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-md text-white"
                >
                  <option value="">选择主实体...</option>
                  {Array.from(selectedEntities).map((id) => {
                    const entity = entities.find((e) => e.id === id);
                    if (!entity) return null;
                    return (
                      <option key={id} value={id}>
                        {entity.name} ({ENTITY_TYPE_CONFIG[entity.entity_type as keyof typeof ENTITY_TYPE_CONFIG]?.label})
                      </option>
                    );
                  })}
                </select>
              </div>
              <div className="text-sm text-white/60">
                其他 {selectedEntities.size - 1} 个实体将被合并到主实体中，它们的名称和别名将作为主实体的别名保留。
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setMergeDialogOpen(false)} className="border-white/10 text-white">
                取消
              </Button>
              <Button onClick={handleMergeEntities} disabled={!mergeTarget} className="bg-violet-600 hover:bg-violet-700">
                合并
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Detail Dialog */}
        <Dialog open={detailDialogOpen} onOpenChange={setDetailDialogOpen}>
          <DialogContent className="bg-gray-900 border-white/10 text-white max-w-2xl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-3">
                {detailEntity && (
                  <>
                    <div className={`w-10 h-10 rounded ${
                      ENTITY_TYPE_CONFIG[detailEntity.entity_type as keyof typeof ENTITY_TYPE_CONFIG]?.bgColor
                    } flex items-center justify-center`}>
                      {(ENTITY_TYPE_CONFIG[detailEntity.entity_type as keyof typeof ENTITY_TYPE_CONFIG]?.icon || Users)({
                        className: `w-5 h-5 ${
                          ENTITY_TYPE_CONFIG[detailEntity.entity_type as keyof typeof ENTITY_TYPE_CONFIG]?.color
                        }`,
                      })}
                    </div>
                    <div>
                      <div className="text-lg font-medium">{detailEntity.name}</div>
                      {detailEntity.canonical_name && detailEntity.canonical_name !== detailEntity.name && (
                        <div className="text-sm text-white/60 font-normal">{detailEntity.canonical_name}</div>
                      )}
                    </div>
                  </>
                )}
              </DialogTitle>
            </DialogHeader>
            {detailEntity && (
              <div className="space-y-6 py-4 max-h-[60vh] overflow-y-auto">
                {/* Status */}
                <div className="flex items-center gap-4">
                  {detailEntity.is_approved ? (
                    <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
                      <CheckCircle className="w-3 h-3 mr-1" />
                      已确认
                    </Badge>
                  ) : (
                    <Badge className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30">
                      <XCircle className="w-3 h-3 mr-1" />
                      待审阅
                    </Badge>
                  )}
                  <Badge variant="outline" className="border-white/20 text-white/60">
                    {ENTITY_TYPE_CONFIG[detailEntity.entity_type as keyof typeof ENTITY_TYPE_CONFIG]?.label}
                  </Badge>
                  <Badge variant="outline" className="border-white/20 text-white/60">
                    置信度: {detailEntity.confidence}%
                  </Badge>
                </div>

                {/* Description */}
                {detailEntity.description && (
                  <div>
                    <h4 className="text-sm text-white/60 mb-2">描述</h4>
                    <p className="text-white leading-relaxed">{detailEntity.description}</p>
                  </div>
                )}

                {/* Aliases */}
                {detailEntity.aliases.length > 0 && (
                  <div>
                    <h4 className="text-sm text-white/60 mb-2">别名</h4>
                    <div className="flex flex-wrap gap-2">
                      {detailEntity.aliases.map((alias, idx) => (
                        <Badge key={idx} variant="outline" className="border-white/20 text-white/80">
                          {alias}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {/* Appearance */}
                {detailEntity.appearance && (
                  <div>
                    <h4 className="text-sm text-white/60 mb-2">外观描述</h4>
                    <p className="text-white leading-relaxed">{detailEntity.appearance}</p>
                  </div>
                )}

                {/* Visual Prompt */}
                {detailEntity.visual_prompt && (
                  <div>
                    <h4 className="text-sm text-white/60 mb-2">视觉提示词</h4>
                    <p className="text-white/80 text-sm bg-white/5 p-3 rounded-md">{detailEntity.visual_prompt}</p>
                  </div>
                )}

                {/* State Changes */}
                {detailEntity.state_changes.length > 0 && (
                  <div>
                    <h4 className="text-sm text-white/60 mb-2">状态变化</h4>
                    <div className="space-y-2">
                      {detailEntity.state_changes.map((change: any, idx: number) => (
                        <div key={idx} className="bg-white/5 p-3 rounded-md">
                          <div className="text-white text-sm">状态: {change.state}</div>
                          <div className="text-white/60 text-xs mt-1">{change.description}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Relations */}
                {detailEntity.relations.length > 0 && (
                  <div>
                    <h4 className="text-sm text-white/60 mb-2">关系</h4>
                    <div className="space-y-2">
                      {detailEntity.relations.map((rel: any, idx: number) => (
                        <div key={idx} className="flex items-center gap-2 bg-white/5 p-3 rounded-md">
                          <span className="text-white text-sm">{rel.type}</span>
                          <span className="text-white/40">-</span>
                          <span className="text-white/80 text-sm">{rel.entity_id || rel.target}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Tags */}
                {detailEntity.tags.length > 0 && (
                  <div>
                    <h4 className="text-sm text-white/60 mb-2">标签</h4>
                    <div className="flex flex-wrap gap-2">
                      {detailEntity.tags.map((tag, idx) => (
                        <Badge key={idx} variant="outline" className="border-white/20 text-white/80">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {/* Evidence */}
                {detailEntity.evidence && (
                  <div>
                    <h4 className="text-sm text-white/60 mb-2">原文证据</h4>
                    <p className="text-white/60 text-sm bg-white/5 p-3 rounded-md">{detailEntity.evidence}</p>
                  </div>
                )}

                {/* Meta info */}
                <div className="text-xs text-white/40 pt-4 border-t border-white/10">
                  <div>版本: v{detailEntity.version}</div>
                  <div>来源: {detailEntity.source}</div>
                  <div>一致性评分: {detailEntity.consistency_score}</div>
                  <div>创建时间: {new Date(detailEntity.created_at).toLocaleString()}</div>
                  <div>更新时间: {new Date(detailEntity.updated_at).toLocaleString()}</div>
                </div>
              </div>
            )}
            <DialogFooter>
              <Button variant="outline" onClick={() => setDetailDialogOpen(false)} className="border-white/10 text-white">
                关闭
              </Button>
              <Button
                onClick={() => {
                  if (detailEntity) {
                    setDetailDialogOpen(false);
                    handleEditEntity(detailEntity);
                  }
                }}
                className="bg-violet-600 hover:bg-violet-700"
              >
                <Edit className="w-4 h-4 mr-2" />
                编辑
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </MainLayout>
  );
}
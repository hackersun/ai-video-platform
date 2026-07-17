'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft,
  BadgeCheck,
  Bot,
  Boxes,
  Check,
  CircleSlash,
  Loader2,
  Merge,
  RefreshCw,
  Search,
  Sparkles,
  Wand2,
  X,
} from 'lucide-react';

import { MainLayout } from '@/components/layout/main-layout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/toast';
import { apiClient } from '@/lib/api-client';

type EntityType = 'character' | 'scene' | 'prop' | 'event';
type EntityFilter = 'all' | EntityType | 'pending' | 'approved';

type StoryEntity = {
  id: string;
  entity_type: EntityType;
  name: string;
  description?: string | null;
  appearance?: string | null;
  visual_prompt?: string | null;
  evidence?: string | null;
  aliases?: string[];
  relations?: any[];
  state_changes?: any[];
  is_approved?: boolean;
  source?: string;
  extra_data?: Record<string, any>;
  updated_at?: string;
};

type ReviewSummary = {
  counts?: Record<string, number>;
  by_type?: Record<string, number>;
  candidate_count?: number;
  approved_count?: number;
  rejected_count?: number;
  duplicate_risk_count?: number;
  missing_evidence_count?: number;
  asset_gap_count?: number;
  recommended_next_action?: string;
};

type Novel = {
  id: string;
  title: string;
  description?: string;
};

const ENTITY_TYPES: Array<{ value: EntityType; label: string }> = [
  { value: 'character', label: '角色' },
  { value: 'scene', label: '场景' },
  { value: 'prop', label: '道具' },
  { value: 'event', label: '事件' },
];

const FILTERS: Array<{ value: EntityFilter; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'character', label: '角色' },
  { value: 'scene', label: '场景' },
  { value: 'prop', label: '道具' },
  { value: 'event', label: '事件' },
  { value: 'pending', label: '待处理' },
  { value: 'approved', label: '已定稿' },
];

const FIELD_OPTIONS = [
  { value: 'description', label: '描述' },
  { value: 'appearance', label: '外貌' },
  { value: 'visual_prompt', label: '视觉DNA' },
  { value: 'aliases', label: '别名' },
  { value: 'relations', label: '关系' },
  { value: 'state_changes', label: '状态' },
  { value: 'evidence', label: '证据' },
];

const statusLabel: Record<string, string> = {
  legacy_active: '旧数据',
  candidate: '待审核',
  approved: '已定稿',
  rejected: '已拒绝',
  archived: '已归档',
};

const statusClass: Record<string, string> = {
  legacy_active: 'border-slate-400/40 text-slate-200',
  candidate: 'border-amber-400/50 text-amber-200',
  approved: 'border-emerald-400/50 text-emerald-200',
  rejected: 'border-rose-400/50 text-rose-200',
  archived: 'border-white/20 text-white/50',
};

const getReviewStatus = (entity?: StoryEntity | null) => {
  if (!entity) return 'candidate';
  const lifecycle = entity.extra_data?.lifecycle;
  if (lifecycle?.status) return String(lifecycle.status);
  if (entity.is_approved) return 'approved';
  return 'legacy_active';
};

const getQuality = (entity?: StoryEntity | null) => entity?.extra_data?.quality || {};

const getTypeLabel = (type?: string) => ENTITY_TYPES.find((item) => item.value === type)?.label || type || '';

const actionLabel: Record<string, string> = {
  run_analysis: '运行分析',
  review_candidates: '审核候选',
  review_merge_suggestions: '查看合并',
  generate_missing_assets: '生成资产',
};

export default function NovelAssetAnalysisPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const novelId = params.id as string;

  const [novel, setNovel] = useState<Novel | null>(null);
  const [entities, setEntities] = useState<StoryEntity[]>([]);
  const [summary, setSummary] = useState<ReviewSummary>({});
  const [mergeSuggestions, setMergeSuggestions] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [filter, setFilter] = useState<EntityFilter>('pending');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [busyEntityId, setBusyEntityId] = useState('');
  const [lastRunId, setLastRunId] = useState('');
  const [targetType, setTargetType] = useState<EntityType>('character');
  const [targetName, setTargetName] = useState('');
  const [sourceText, setSourceText] = useState('');
  const [selectedFields, setSelectedFields] = useState(['description', 'appearance', 'visual_prompt', 'evidence']);
  const [enriching, setEnriching] = useState(false);
  const [bulkApproving, setBulkApproving] = useState(false);
  const [mergingSuggestionKey, setMergingSuggestionKey] = useState('');

  const selectedEntity = useMemo(
    () => entities.find((item) => item.id === selectedId) || entities[0] || null,
    [entities, selectedId]
  );

  const duplicateRiskEntityIds = useMemo(
    () => new Set(mergeSuggestions.flatMap((item) => Array.isArray(item?.entity_ids) ? item.entity_ids : [])),
    [mergeSuggestions]
  );

  const selectedDuplicateSuggestion = useMemo(
    () => mergeSuggestions.find((item) => Array.isArray(item?.entity_ids) && item.entity_ids.includes(selectedEntity?.id)),
    [mergeSuggestions, selectedEntity?.id]
  );

  const safeBulkCandidateIds = useMemo(
    () => entities
      .filter((entity) => {
        const quality = getQuality(entity);
        const flags = Array.isArray(quality.flags) ? quality.flags : [];
        const hasEvidence = entity.source === 'manual' || Boolean(entity.evidence?.trim());
        return getReviewStatus(entity) === 'candidate'
          && hasEvidence
          && !flags.includes('missing_evidence')
          && !duplicateRiskEntityIds.has(entity.id);
      })
      .map((entity) => entity.id),
    [duplicateRiskEntityIds, entities]
  );

  const filteredEntities = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    return entities.filter((entity) => {
      const status = getReviewStatus(entity);
      const matchesFilter =
        filter === 'all' ||
        entity.entity_type === filter ||
        (filter === 'pending' && status === 'candidate') ||
        (filter === 'approved' && status === 'approved');
      const matchesKeyword = !keyword || `${entity.name} ${entity.description || ''} ${entity.evidence || ''}`.toLowerCase().includes(keyword);
      return matchesFilter && matchesKeyword;
    });
  }, [entities, filter, search]);

  const healthScore = useMemo(() => {
    const total = entities.length || 1;
    const approved = summary.approved_count || 0;
    const penalty = (summary.missing_evidence_count || 0) + (summary.duplicate_risk_count || 0) + (summary.asset_gap_count || 0);
    return Math.max(0, Math.min(100, Math.round((approved / total) * 80 + 20 - penalty * 4)));
  }, [entities.length, summary]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [novelData, entityData, summaryData, mergeData] = await Promise.all([
        apiClient.getNovel(novelId),
        apiClient.getStoryEntities({ novel_id: novelId, limit: 500 }),
        apiClient.getEntityReviewSummary({ novel_id: novelId }),
        apiClient.getEntityMergeSuggestions({ novel_id: novelId }),
      ]);
      const nextEntities = Array.isArray(entityData) ? entityData : [];
      setNovel(novelData);
      setEntities(nextEntities);
      setSummary(summaryData || {});
      setMergeSuggestions(Array.isArray(mergeData?.items) ? mergeData.items : []);
      if (!selectedId && nextEntities[0]) setSelectedId(nextEntities[0].id);
      if (!sourceText) setSourceText(novelData?.description || '');
    } catch (err: any) {
      toast({ title: '资产分析加载失败', description: err?.message || '请稍后重试', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (novelId) loadData();
  }, [novelId]);

  useEffect(() => {
    if (!selectedEntity) return;
    setTargetType(selectedEntity.entity_type);
    setTargetName(selectedEntity.name || '');
    setSourceText(selectedEntity.evidence || novel?.description || sourceText);
  }, [selectedEntity?.id]);

  const runAnalysis = async () => {
    setRunning(true);
    try {
      const result = await apiClient.analyzeStoryEntities({
        novel_id: novelId,
        entity_types: ENTITY_TYPES.map((item) => item.value),
        persist: true,
        persist_rejected: true,
      });
      setLastRunId(result.run_id || '');
      toast({ title: 'AI 分析已完成', description: `新增/刷新 ${result?.stats?.created || 0} 个候选`, type: 'success' });
      await loadData();
    } catch (err: any) {
      toast({ title: 'AI 分析失败', description: err?.message || '请检查小说正文和模型配置', type: 'error' });
    } finally {
      setRunning(false);
    }
  };

  const updateEntityStatus = async (entity: StoryEntity, action: 'approve' | 'reject') => {
    setBusyEntityId(entity.id);
    try {
      if (action === 'approve') {
        await apiClient.promoteStoryEntityCandidate(entity.id, '资产分析页确认');
      } else {
        await apiClient.rejectStoryEntityCandidate(entity.id, '资产分析页拒绝');
      }
      toast({ title: action === 'approve' ? '已定稿' : '已拒绝', description: entity.name, type: 'success' });
      await loadData();
    } catch (err: any) {
      toast({ title: '状态更新失败', description: err?.message || '请稍后重试', type: 'error' });
    } finally {
      setBusyEntityId('');
    }
  };

  const approveSafeCandidates = async () => {
    if (safeBulkCandidateIds.length === 0) {
      toast({ title: '没有可安全批量定稿的候选', description: '缺少证据或存在重复风险的实体需要逐条处理', type: 'info' });
      return;
    }
    setBulkApproving(true);
    try {
      const result = await apiClient.bulkActionStoryEntities({
        entity_ids: safeBulkCandidateIds,
        action: 'approve',
        approved: true,
      });
      const skipped = Array.isArray(result?.skipped) ? result.skipped.length : 0;
      toast({
        title: `已安全定稿 ${result?.updated_count || 0} 项`,
        description: skipped ? `${skipped} 项因证据或重复风险被跳过` : '无风险候选已进入生产范围',
        type: 'success',
      });
      await loadData();
    } catch (err: any) {
      toast({ title: '批量定稿失败', description: err?.message || '请逐条检查证据和重复风险', type: 'error' });
    } finally {
      setBulkApproving(false);
    }
  };

  const runTargetedEnrichment = async () => {
    if (!targetName.trim() || !sourceText.trim()) {
      toast({ title: '补全信息不足', description: '需要名称和来源文本', type: 'info' });
      return;
    }
    setEnriching(true);
    try {
      const result = await apiClient.enrichTargetStoryEntity({
        novel_id: novelId,
        target_entity_id: selectedEntity?.name === targetName ? selectedEntity.id : undefined,
        text: sourceText,
        entity_type: targetType,
        entity_name: targetName,
        fields: selectedFields,
        mode: 'merge_candidate',
      });
      toast({ title: '定向补全已完成', description: result?.merge_policy === 'pending_for_approved' ? '已保存为待确认补丁' : targetName, type: 'success' });
      await loadData();
    } catch (err: any) {
      toast({ title: '定向补全失败', description: err?.message || '请稍后重试', type: 'error' });
    } finally {
      setEnriching(false);
    }
  };

  const mergeSuggestedEntities = async (suggestion: any) => {
    const entityIds = Array.isArray(suggestion?.entity_ids) ? suggestion.entity_ids : [];
    const targetEntityId = String(suggestion?.target_entity_id || '');
    if (!targetEntityId || entityIds.length < 2) {
      toast({ title: '合并建议不完整', description: '至少需要一个目标实体和一个来源实体', type: 'info' });
      return;
    }
    setMergingSuggestionKey(String(suggestion.canonical_key || targetEntityId));
    try {
      const result = await apiClient.mergeStoryEntities({
        source_entity_ids: entityIds,
        target_entity_id: targetEntityId,
        keep_source_as_alias: true,
      });
      toast({
        title: `已合并 ${result?.merged_count || entityIds.length - 1} 项`,
        description: '来源实体名称已保留为目标实体别名，来源记录已移除',
        type: 'success',
      });
      setSelectedId(targetEntityId);
      await loadData();
    } catch (err: any) {
      toast({ title: '实体合并失败', description: err?.message || '请检查目标实体和来源实体', type: 'error' });
    } finally {
      setMergingSuggestionKey('');
    }
  };

  const toggleField = (value: string) => {
    setSelectedFields((current) => (
      current.includes(value) ? current.filter((item) => item !== value) : [...current, value]
    ));
  };

  if (loading) {
    return (
      <MainLayout>
        <div className="space-y-4">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-[520px] w-full" />
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="space-y-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <Button variant="ghost" onClick={() => router.push(`/novels/${novelId}`)}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              返回
            </Button>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline" className="border-cyan-400/45 text-cyan-100">AI 资产分析</Badge>
                {lastRunId ? <Badge variant="outline" className="border-white/20 text-white/60">Run {lastRunId.slice(0, 8)}</Badge> : null}
              </div>
              <h1 className="mt-2 break-words text-2xl font-bold text-white">{novel?.title || '小说资产分析'}</h1>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 lg:justify-end">
            <Button variant="outline" className="border-white/15" onClick={loadData} disabled={running || enriching}>
              <RefreshCw className="mr-2 h-4 w-4" />
              刷新
            </Button>
            <Button className="bg-cyan-600 hover:bg-cyan-700" onClick={runAnalysis} disabled={running}>
              {running ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Bot className="mr-2 h-4 w-4" />}
              AI 分析制作资产
            </Button>
            <Button
              variant="outline"
              className="border-emerald-500/40 text-emerald-100"
              onClick={approveSafeCandidates}
              disabled={bulkApproving || safeBulkCandidateIds.length === 0}
            >
              {bulkApproving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <BadgeCheck className="mr-2 h-4 w-4" />}
              安全批量定稿 {safeBulkCandidateIds.length}
            </Button>
          </div>
        </div>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          {[
            { label: '健康分', value: healthScore, tone: 'text-cyan-200' },
            { label: '待处理', value: summary.candidate_count || 0, tone: 'text-amber-200' },
            { label: '已定稿', value: summary.approved_count || 0, tone: 'text-emerald-200' },
            { label: '资产缺口', value: summary.asset_gap_count || 0, tone: 'text-rose-200' },
            { label: '下一步', value: actionLabel[summary.recommended_next_action || ''] || '运行分析', tone: 'text-white' },
          ].map((item) => (
            <div key={item.label} className="rounded-lg border border-white/10 bg-white/[0.045] px-4 py-3">
              <div className="text-xs text-white/45">{item.label}</div>
              <div className={`mt-2 truncate text-xl font-semibold ${item.tone}`}>{item.value}</div>
            </div>
          ))}
        </section>

        <section className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(360px,0.65fr)]">
          <div className="min-w-0 rounded-lg border border-white/10 bg-black/20">
            <div className="flex flex-col gap-3 border-b border-white/10 p-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex max-w-full gap-1 overflow-x-auto rounded-md bg-white/[0.045] p-1">
                {FILTERS.map((item) => (
                  <button
                    key={item.value}
                    type="button"
                    onClick={() => setFilter(item.value)}
                    className={`h-8 shrink-0 rounded px-3 text-sm ${filter === item.value ? 'bg-cyan-600 text-white' : 'text-white/62 hover:bg-white/10'}`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              <div className="relative w-full lg:w-64">
                <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-white/35" />
                <Input value={search} onChange={(event) => setSearch(event.target.value)} className="pl-9" placeholder="搜索名称或证据" />
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="border-b border-white/10 text-xs text-white/45">
                  <tr>
                    <th className="px-4 py-3 font-medium">实体</th>
                    <th className="px-4 py-3 font-medium">类型</th>
                    <th className="px-4 py-3 font-medium">质量</th>
                    <th className="px-4 py-3 font-medium">状态</th>
                    <th className="px-4 py-3 font-medium">证据</th>
                    <th className="px-4 py-3 text-right font-medium">动作</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredEntities.map((entity) => {
                    const status = getReviewStatus(entity);
                    const quality = getQuality(entity);
                    const active = selectedEntity?.id === entity.id;
                    return (
                      <tr
                        key={entity.id}
                        className={`border-b border-white/5 align-top hover:bg-white/[0.035] ${active ? 'bg-cyan-500/10' : ''}`}
                        onClick={() => setSelectedId(entity.id)}
                      >
                        <td className="px-4 py-3">
                          <div className="max-w-[180px] truncate font-medium text-white">{entity.name}</div>
                          <div className="mt-1 max-w-[220px] truncate text-xs text-white/45">{entity.description || entity.appearance || '待补全'}</div>
                        </td>
                        <td className="px-4 py-3 text-white/70">{getTypeLabel(entity.entity_type)}</td>
                        <td className="px-4 py-3">
                          <div className="text-white">{quality.score ?? '-'}</div>
                          <div className="mt-1 max-w-[120px] truncate text-xs text-white/42">{quality.auto_decision || 'legacy'}</div>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant="outline" className={statusClass[status] || 'border-white/20 text-white/60'}>{statusLabel[status] || status}</Badge>
                        </td>
                        <td className="px-4 py-3">
                          <div className="max-h-10 max-w-[260px] overflow-hidden break-words text-white/60">{entity.evidence || '缺少证据'}</div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex justify-end gap-1">
                            <Button size="sm" variant="ghost" onClick={(event) => { event.stopPropagation(); updateEntityStatus(entity, 'approve'); }} disabled={busyEntityId === entity.id} title="定稿：进入生产圣经、定稿卡与生成提示词">
                              {busyEntityId === entity.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                              <span className="ml-1">定稿</span>
                            </Button>
                            <Button size="sm" variant="ghost" onClick={(event) => { event.stopPropagation(); updateEntityStatus(entity, 'reject'); }} disabled={busyEntityId === entity.id} title="拒绝：从生产消费者中排除">
                              <X className="h-4 w-4" />
                              <span className="ml-1">拒绝</span>
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                  {filteredEntities.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-12 text-center text-white/50">暂无匹配资产实体</td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </div>

          <aside className="space-y-4">
            <div className="rounded-lg border border-white/10 bg-white/[0.045] p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-xs text-white/45">当前实体</div>
                  <h2 className="mt-1 truncate text-lg font-semibold text-white">{selectedEntity?.name || '未选择'}</h2>
                </div>
                {selectedEntity ? <Badge variant="outline" className={statusClass[getReviewStatus(selectedEntity)]}>{statusLabel[getReviewStatus(selectedEntity)]}</Badge> : null}
              </div>
              <div className="mt-4 space-y-3 text-sm text-white/66">
                <p className="break-words leading-6">{selectedEntity?.description || selectedEntity?.appearance || '等待 AI 补全资产信息'}</p>
                <div className="rounded border border-white/10 bg-black/20 p-3 text-white/70">
                  <div className="mb-1 text-xs text-white/40">原文证据</div>
                  <div className="break-words leading-6">{selectedEntity?.evidence || '暂无证据'}</div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded border border-white/10 p-2">
                    <div className="text-xs text-white/40">别名</div>
                    <div className="mt-1 truncate text-white">{selectedEntity?.aliases?.join('、') || '-'}</div>
                  </div>
                  <div className="rounded border border-white/10 p-2">
                    <div className="text-xs text-white/40">关系/状态</div>
                    <div className="mt-1 text-white">{(selectedEntity?.relations?.length || 0) + (selectedEntity?.state_changes?.length || 0)}</div>
                  </div>
                </div>
                <div className="rounded border border-white/10 bg-black/20 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-xs text-white/40">重复风险</div>
                    <Badge
                      variant="outline"
                      className={selectedDuplicateSuggestion ? 'border-amber-400/50 text-amber-200' : 'border-emerald-400/40 text-emerald-200'}
                    >
                      {selectedDuplicateSuggestion ? '高风险 · 需合并判断' : '未发现明显重复'}
                    </Badge>
                  </div>
                  {selectedDuplicateSuggestion ? (
                    <div className="mt-2 break-words text-xs leading-5 text-white/55">
                      相似实体：{selectedDuplicateSuggestion.names?.join(' / ')}
                    </div>
                  ) : null}
                </div>
                <div className="rounded border border-white/10 bg-black/20 p-3">
                  <div className="mb-2 text-xs text-white/40">质量分项</div>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-3">
                    {[
                      ['证据', getQuality(selectedEntity).components?.evidence],
                      ['命名', getQuality(selectedEntity).components?.name_shape],
                      ['类型边界', getQuality(selectedEntity).components?.type_boundary],
                      ['制作价值', getQuality(selectedEntity).components?.production_usefulness],
                      ['置信度', getQuality(selectedEntity).components?.confidence],
                    ].map(([label, value]) => (
                      <div key={String(label)} className="flex items-center justify-between gap-2">
                        <span className="text-white/42">{label}</span>
                        <span className="font-medium text-white/80">{value ?? '-'}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="rounded border border-cyan-400/20 bg-cyan-500/[0.06] p-3">
                  <div className="text-xs text-cyan-100/60">定稿后的下游影响</div>
                  <div className="mt-1 break-words text-xs leading-5 text-cyan-50/85">
                    将进入 Production Bible、Production Cards、提示词上下文、资产生成与镜头生产合约；拒绝后不会进入任何生产消费者。
                  </div>
                </div>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2">
                <Button variant="outline" className="border-emerald-500/40" disabled={!selectedEntity} onClick={() => selectedEntity && updateEntityStatus(selectedEntity, 'approve')}>
                  <BadgeCheck className="mr-2 h-4 w-4" />
                  定稿
                </Button>
                <Button variant="outline" className="border-rose-500/40" disabled={!selectedEntity} onClick={() => selectedEntity && updateEntityStatus(selectedEntity, 'reject')}>
                  <CircleSlash className="mr-2 h-4 w-4" />
                  拒绝
                </Button>
                <Button
                  variant="outline"
                  className="border-amber-500/40"
                  disabled={!selectedDuplicateSuggestion || Boolean(mergingSuggestionKey)}
                  onClick={() => selectedDuplicateSuggestion && mergeSuggestedEntities(selectedDuplicateSuggestion)}
                >
                  {mergingSuggestionKey ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Merge className="mr-2 h-4 w-4" />}
                  合并重复项
                </Button>
                <Button
                  variant="outline"
                  className="border-cyan-500/40"
                  disabled={!selectedEntity}
                  onClick={() => document.getElementById('targeted-enrichment')?.scrollIntoView({ behavior: 'smooth', block: 'center' })}
                >
                  <Wand2 className="mr-2 h-4 w-4" />
                  补全候选
                </Button>
              </div>
            </div>

            <div id="targeted-enrichment" className="rounded-lg border border-white/10 bg-black/20 p-4">
              <div className="flex items-center gap-2 text-white">
                <Wand2 className="h-4 w-4 text-amber-200" />
                <h2 className="font-semibold">定向补全</h2>
              </div>
              <div className="mt-4 grid grid-cols-[120px_minmax(0,1fr)] gap-2">
                <Select value={targetType} onValueChange={(value) => setTargetType(value as EntityType)} options={ENTITY_TYPES} />
                <Input value={targetName} onChange={(event) => setTargetName(event.target.value)} placeholder="名称" />
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
                {FIELD_OPTIONS.map((field) => (
                  <label key={field.value} className="flex h-8 items-center gap-2 rounded border border-white/10 px-2 text-xs text-white/70">
                    <Checkbox checked={selectedFields.includes(field.value)} onCheckedChange={() => toggleField(field.value)} />
                    <span className="truncate">{field.label}</span>
                  </label>
                ))}
              </div>
              <Textarea className="mt-3 min-h-[112px]" value={sourceText} onChange={(event) => setSourceText(event.target.value)} placeholder="粘贴相关原文片段" />
              <Button className="mt-3 w-full bg-amber-600 hover:bg-amber-700" onClick={runTargetedEnrichment} disabled={enriching}>
                {enriching ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                补全候选（不自动定稿）
              </Button>
              <p className="mt-2 text-xs leading-5 text-white/45">补全只更新候选信息；已定稿实体会生成待确认补丁，不会静默覆盖生产事实。</p>
            </div>

            <div id="merge-suggestions" className="rounded-lg border border-white/10 bg-white/[0.035] p-4">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-white">
                  <Merge className="h-4 w-4 text-cyan-200" />
                  <h2 className="font-semibold">合并建议</h2>
                </div>
                <Badge variant="outline" className="border-white/20 text-white/60">{mergeSuggestions.length}</Badge>
              </div>
              <div className="mt-3 space-y-2">
                {mergeSuggestions.slice(0, 3).map((item) => (
                  <div key={item.canonical_key} className="rounded border border-white/10 p-3 text-sm text-white/65">
                    <div className="truncate text-white">{item.names?.join(' / ')}</div>
                    <div className="mt-1 text-xs text-white/42">{item.reason}</div>
                    <div className="mt-2 text-xs leading-5 text-amber-100/65">执行后保留目标实体，来源名称转为别名并移除来源记录。</div>
                    <Button
                      size="sm"
                      variant="outline"
                      className="mt-2 w-full border-amber-500/35"
                      disabled={Boolean(mergingSuggestionKey)}
                      onClick={() => mergeSuggestedEntities(item)}
                    >
                      {mergingSuggestionKey === String(item.canonical_key) ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Merge className="mr-2 h-4 w-4" />}
                      执行合并到「{entities.find((entity) => entity.id === item.target_entity_id)?.name || '目标实体'}」
                    </Button>
                  </div>
                ))}
                {mergeSuggestions.length === 0 ? <div className="rounded border border-white/10 p-3 text-sm text-white/45">暂无明显重复</div> : null}
              </div>
            </div>

            <div className="rounded-lg border border-white/10 bg-white/[0.035] p-4">
              <div className="flex items-center gap-2 text-white">
                <Boxes className="h-4 w-4 text-emerald-200" />
                <h2 className="font-semibold">制作入口</h2>
              </div>
              <div className="mt-3 grid gap-2">
                <Button asChild variant="outline" className="justify-start border-white/15">
                  <Link href={`/assets?novel_id=${novelId}`}>生成缺失资产</Link>
                </Button>
                <Button asChild variant="outline" className="justify-start border-white/15">
                  <Link href={`/novels/${novelId}?tab=story-bible`}>同步 Story Bible</Link>
                </Button>
              </div>
            </div>
          </aside>
        </section>
      </div>
    </MainLayout>
  );
}

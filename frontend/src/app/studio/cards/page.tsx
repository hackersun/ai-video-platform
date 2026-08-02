'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { AlertCircle, ArrowLeft, ArrowUpRight, CheckCircle2, ClipboardCheck, ImageIcon, Layers3, Loader2, Map, Mic2, Package, UserRound, Wand2 } from 'lucide-react';
import { MainLayout } from '@/components/layout/main-layout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import apiClient, { AssetBindingHealthItem, BatchFinalizeSupportingRequest, BatchFinalizeSupportingResponse, ProductionCard, ProductionCardsResponse } from '@/lib/api-client';
import { cn } from '@/lib/utils';

const ENTITY_LABELS: Record<ProductionCard['entity_type'], string> = {
  character: '角色',
  scene: '场景',
  prop: '道具',
};

const ENTITY_META: Record<ProductionCard['entity_type'], { icon: any; tone: string; rail: string; chip: string }> = {
  character: {
    icon: UserRound,
    tone: 'border-cyan-300/25 bg-cyan-400/10 text-cyan-100',
    rail: 'from-cyan-300 to-blue-400',
    chip: 'bg-cyan-300/10 text-cyan-100',
  },
  scene: {
    icon: Map,
    tone: 'border-violet-300/25 bg-violet-400/10 text-violet-100',
    rail: 'from-violet-300 to-fuchsia-400',
    chip: 'bg-violet-300/10 text-violet-100',
  },
  prop: {
    icon: Package,
    tone: 'border-emerald-300/25 bg-emerald-400/10 text-emerald-100',
    rail: 'from-emerald-300 to-teal-400',
    chip: 'bg-emerald-300/10 text-emerald-100',
  },
};

const VIEW_LABELS: Record<string, string> = {
  front: '正面',
  side: '侧面',
  back: '背面',
  establishing: '全景定场',
  wide: '全景',
  layout: '空间布局',
  detail: '细节',
  lighting: '光影氛围',
  main: '主视图',
  scale: '比例参考',
};

function scoreValue(card: ProductionCard) {
  return Math.max(0, Math.min(100, Math.round(card.readiness?.score ?? 0)));
}

function firstView(card: ProductionCard) {
  return card.visual?.views?.find((view) => view.url) || card.visual?.views?.[0];
}

function viewKeyFromGap(code?: string) {
  const match = code?.match(/^view_missing:(.+)$/);
  return match?.[1] || '';
}

function viewLabel(card: ProductionCard, viewKey: string) {
  return card.visual?.views?.find((view) => view.view_key === viewKey)?.view_label || VIEW_LABELS[viewKey] || viewKey;
}

function missingViewKeys(card: ProductionCard) {
  const visualKeys = (card.visual?.missing_views || []).filter(Boolean);
  const gapKeys = (card.readiness?.gaps || []).map((gap) => viewKeyFromGap(gap.code)).filter(Boolean);
  return Array.from(new Set([...visualKeys, ...gapKeys]));
}

function completionKey(card: ProductionCard, viewKeys: string[]) {
  return `${card.entity_id}:${viewKeys.join(',')}`;
}

function assetContextHref(card: ProductionCard, viewKey?: string) {
  const params = new URLSearchParams();
  params.set('novel_id', card.novel_id);
  params.set('entity_type', card.entity_type);
  params.set('entity_id', card.entity_id);
  if (viewKey) params.set('view_key', viewKey);
  params.set('action', 'generate-missing');
  params.set('source', 'production-card');
  return `/assets?${params.toString()}`;
}

function studioHref(workflowId: string) {
  if (!workflowId) return '/studio';
  const params = new URLSearchParams({ workflow_id: workflowId });
  return `/studio?${params.toString()}`;
}

function finalQualityStudioHref(workflowId: string, providerId: string, modelId: string) {
  const params = new URLSearchParams({
    provider_id: providerId,
    model_id: modelId,
    production_strategy: 'final_quality',
  });
  if (workflowId) params.set('workflow_id', workflowId);
  return `/studio?${params.toString()}`;
}

function modelLabel(modelId: string) {
  if (modelId === 'seedance-2.0') return 'Seedance 2.0';
  return modelId;
}

function MetricTile({ label, value, detail, tone }: { label: string; value: string | number; detail: string; tone: string }) {
  return (
    <div className={cn('rounded-xl border px-4 py-3', tone)}>
      <div className="text-xs text-white/50">{label}</div>
      <div className="mt-2 text-2xl font-semibold leading-none text-white">{value}</div>
      <div className="mt-2 text-xs leading-5 text-white/55">{detail}</div>
    </div>
  );
}

function ProductionCardItem({
  card,
  completingKey,
  onCompleteViews,
  bindingHealth,
  selectedProviderId,
  selectedModelId,
  bindingAssetId,
  onCreateBinding,
  workflowId,
}: {
  card: ProductionCard;
  completingKey: string | null;
  onCompleteViews: (card: ProductionCard, viewKeys: string[]) => void;
  bindingHealth: Record<string, AssetBindingHealthItem>;
  selectedProviderId: string;
  selectedModelId: string;
  bindingAssetId: string | null;
  onCreateBinding: (assetId: string, assetVersion: number) => void;
  workflowId: string;
}) {
  const score = scoreValue(card);
  const gaps = card.readiness?.gaps || [];
  const preview = firstView(card);
  const isReady = Boolean(card.readiness?.final_ready);
  const isCharacter = card.entity_type === 'character';
  const missingViews = missingViewKeys(card);
  const cardCompletionKey = completionKey(card, missingViews);
  const isCompletingCard = Boolean(completingKey) && (completingKey === 'all' || completingKey === cardCompletionKey);
  const meta = ENTITY_META[card.entity_type];
  const EntityIcon = meta.icon;
  const canonicalViews = (card.visual?.views || []).filter((view) => view.asset_id);
  const healthItems = canonicalViews.map((view) => bindingHealth[view.asset_id!]).filter(Boolean);
  const missingBindingView = canonicalViews.find((view) => {
    const health = bindingHealth[view.asset_id!];
    return health?.binding_required && !health.binding_ready;
  });
  const providerReady = healthItems.length === canonicalViews.length && healthItems.every((item) => !item.binding_required || item.binding_ready);
  const finalQualityReady = isReady && canonicalViews.length > 0 && providerReady;

  return (
    <Card data-testid={`production-card-${card.entity_id}`} className="group overflow-hidden border-white/10 bg-[#151a22] text-white shadow-[0_18px_60px_rgba(0,0,0,0.22)] transition-colors hover:border-white/20">
      <div className={cn('h-1 bg-gradient-to-r', meta.rail)} />
      <div className="relative aspect-[16/10] bg-slate-950">
        {preview?.url ? (
          <img
            src={preview.url}
            alt={`${card.name} ${preview.view_label || preview.view_key || '定稿图'}`}
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.02]"
          />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-white/35">
            <ImageIcon className="h-9 w-9" aria-hidden="true" />
            <span className="text-xs">等待定稿参考图</span>
          </div>
        )}
        <div className="absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-slate-950/90 to-transparent" />
        <div className="absolute left-3 top-3 flex items-center gap-2">
          <Badge variant={isReady ? 'success' : 'warning'}>{isReady ? '终稿就绪' : '待补齐'}</Badge>
          <span className={cn('inline-flex items-center gap-1 rounded-full border px-2 py-1 text-xs', meta.tone)}>
            <EntityIcon className="h-3.5 w-3.5" aria-hidden="true" />
            {ENTITY_LABELS[card.entity_type]}
          </span>
        </div>
        <div className="absolute bottom-3 left-3 right-3 flex items-end justify-between gap-3">
          <div className="min-w-0">
            <div className="truncate text-lg font-semibold leading-6 text-white">{card.name}</div>
            <div className="mt-1 text-xs text-white/55">出镜 {card.usage?.shot_count ?? 0} · 锁定视图 {card.visual?.locked_count ?? 0}</div>
          </div>
          <div className={cn('shrink-0 rounded-lg border px-2.5 py-2 text-center', isReady ? 'border-emerald-300/35 bg-emerald-300/15' : 'border-amber-300/35 bg-amber-300/15')}>
            <div className="text-lg font-semibold leading-none">{score}%</div>
            <div className="mt-1 text-[10px] text-white/55">完整度</div>
          </div>
        </div>
      </div>

      <CardHeader className="space-y-3 p-4">
        <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]" aria-label={`完整度 ${score}%`}>
          <div className={cn('h-full rounded-full bg-gradient-to-r', meta.rail)} style={{ width: `${score}%` }} />
        </div>
        <div className="grid grid-cols-3 gap-2 text-xs text-white/70">
          <div className="rounded-md bg-white/[0.05] px-2 py-2">
            <div className="text-white/40">锁定视图</div>
            <div className="mt-1 font-medium text-white">{card.visual?.locked_count ?? 0}</div>
          </div>
          <div className="rounded-md bg-white/[0.05] px-2 py-2">
            <div className="text-white/40">出镜</div>
            <div className="mt-1 font-medium text-white">{card.usage?.shot_count ?? 0}</div>
          </div>
          {isCharacter ? (
            <div className="rounded-md bg-white/[0.05] px-2 py-2">
              <div className="text-white/40">声线</div>
              <div className="mt-1 flex items-center gap-1 font-medium text-white">
                <Mic2 className="h-3.5 w-3.5" aria-hidden="true" />
                {card.voice?.locked ? '已锁' : '未锁'}
              </div>
            </div>
          ) : (
            <div className="rounded-md bg-white/[0.05] px-2 py-2">
              <div className="text-white/40">类型</div>
              <div className="mt-1 font-medium text-white">{ENTITY_LABELS[card.entity_type]}</div>
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-3 p-4 pt-0">
        <p className="line-clamp-2 min-h-[2.5rem] text-sm leading-5 text-white/65">
          {card.profile?.description || '暂无档案描述'}
        </p>

        <div className="flex flex-wrap gap-2 text-xs">
          <span className={cn('rounded-full px-2.5 py-1', meta.chip)}>完整度 {score}%</span>
          {missingViews.map((view) => (
            <span key={view} className="rounded-full bg-amber-400/10 px-2.5 py-1 text-amber-100">
              缺 {viewLabel(card, view)}
            </span>
          ))}
        </div>

        <div className="space-y-2 rounded-md border border-white/10 bg-slate-950/35 p-3 text-xs" data-testid={`binding-health-${card.entity_id}`}>
          <div className="flex items-center justify-between gap-2">
            <span className="text-white/55">Canonical</span>
            <span className={isReady ? 'text-emerald-200' : 'text-amber-200'}>
              {preview?.version ? `Canonical v${preview.version} ${isReady ? '已就绪' : '待补齐'}` : `Canonical ${isReady ? '已就绪' : '待补齐'}`}
            </span>
          </div>
          <div className="flex items-center justify-between gap-2">
            <span className="text-white/55">{selectedProviderId}</span>
            <span className={providerReady ? 'text-emerald-200' : 'text-amber-200'}>
              {modelLabel(selectedModelId)} 引用{providerReady ? '已验证' : '未就绪'}
            </span>
          </div>
          <div className="flex flex-wrap gap-2 pt-1">
            {missingBindingView?.asset_id ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-7 border-cyan-200/30 bg-transparent px-2 text-xs text-cyan-50 hover:bg-cyan-300/15"
                disabled={Boolean(bindingAssetId)}
                onClick={() => onCreateBinding(missingBindingView.asset_id!, missingBindingView.version || 1)}
              >
                {bindingAssetId === missingBindingView.asset_id ? <Loader2 className="mr-1 h-3 w-3 animate-spin" aria-hidden="true" /> : null}
                生成模型引用
              </Button>
            ) : null}
            {finalQualityReady ? (
              <Button
                type="button"
                size="sm"
                className="h-7 px-2 text-xs"
                onClick={() => { window.location.href = finalQualityStudioHref(workflowId, selectedProviderId, selectedModelId); }}
              >
                终稿生成
              </Button>
            ) : (
              <Button type="button" size="sm" className="h-7 px-2 text-xs" disabled>终稿生成</Button>
            )}
          </div>
        </div>

        {missingViews.length ? (
          <div className="flex flex-wrap items-center gap-2 rounded-md border border-amber-300/20 bg-amber-400/10 p-2">
            <Button
              type="button"
              size="sm"
              className="h-8 bg-amber-500 text-slate-950 hover:bg-amber-400"
              disabled={Boolean(completingKey)}
              onClick={() => onCompleteViews(card, missingViews)}
            >
              {isCompletingCard ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : <Wand2 className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />}
              {isCompletingCard ? '补齐中' : `补齐${card.name}缺口`}
            </Button>
            <Link href={assetContextHref(card, missingViews[0])} className="inline-flex items-center gap-1 text-xs text-amber-100 hover:text-white">
              打开资产库定位
              <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
            </Link>
          </div>
        ) : null}

        {gaps.length ? (
          <div className="space-y-2">
            {gaps.slice(0, 3).map((gap) => {
              const gapViewKey = viewKeyFromGap(gap.code);
              const targetViewKey = gapViewKey || missingViews[0];
              const gapCompletionKey = targetViewKey ? completionKey(card, [targetViewKey]) : '';
              const isCompletingGap = Boolean(completingKey) && (completingKey === 'all' || completingKey === gapCompletionKey);
              const href = targetViewKey ? assetContextHref(card, targetViewKey) : (gap.fix_url || assetContextHref(card));
              return (
                <div key={`${card.entity_id}-${gap.code || gap.message}`} className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-amber-400/10 px-3 py-2 text-sm text-amber-50">
                  <span className="min-w-0 flex-1 truncate">{gap.message}</span>
                  <div className="flex shrink-0 items-center gap-2">
                    {gapViewKey ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        className="h-7 border-amber-200/30 bg-transparent px-2 text-xs text-amber-50 hover:bg-amber-300/15"
                        disabled={Boolean(completingKey)}
                        onClick={() => onCompleteViews(card, [gapViewKey])}
                      >
                        {isCompletingGap ? <Loader2 className="mr-1 h-3 w-3 animate-spin" aria-hidden="true" /> : <Wand2 className="mr-1 h-3 w-3" aria-hidden="true" />}
                        补齐{viewLabel(card, gapViewKey)}
                      </Button>
                    ) : null}
                    <Link href={href} className="inline-flex items-center gap-1 text-amber-100 hover:text-white">
                      去资产库补齐
                      <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="flex items-center gap-2 rounded-md bg-emerald-400/10 px-3 py-2 text-sm text-emerald-100">
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            所需定稿信息已齐备
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function CardsContent() {
  const searchParams = useSearchParams();
  const novelId = searchParams.get('novel_id') || '';
  const workflowId = searchParams.get('workflow_id') || '';
  const fromStudio = searchParams.get('source') === 'studio' || Boolean(workflowId);
  const selectedProviderId = searchParams.get('provider_id') || 'volcano';
  const selectedModelId = searchParams.get('model_id') || 'seedance-2.0';
  const [data, setData] = useState<ProductionCardsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [completingKey, setCompletingKey] = useState<string | null>(null);
  const [completionMessage, setCompletionMessage] = useState<string | null>(null);
  const [finalizeResult, setFinalizeResult] = useState<BatchFinalizeSupportingResponse | null>(null);
  const [minOccurrences, setMinOccurrences] = useState('2');
  const [imageModelConfigId, setImageModelConfigId] = useState('');
  const [voicePoolInput, setVoicePoolInput] = useState('');
  const [bindingHealth, setBindingHealth] = useState<Record<string, AssetBindingHealthItem>>({});
  const [bindingAssetId, setBindingAssetId] = useState<string | null>(null);

  const refreshBindingHealth = async (cards: ProductionCard[]) => {
    const assetIds = Array.from(new Set(cards.flatMap((card) => (card.visual?.views || []).map((view) => view.asset_id).filter(Boolean) as string[])));
    if (!assetIds.length) {
      setBindingHealth({});
      return;
    }
    const response = await apiClient.getAssetBindingHealth(assetIds, selectedProviderId, selectedModelId);
    setBindingHealth(Object.fromEntries((response.assets || []).map((item) => [item.asset_id, item])));
  };

  useEffect(() => {
    if (!novelId) return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    apiClient.getProductionCards(novelId)
      .then(async (response) => {
        if (!cancelled) {
          setData(response);
          await refreshBindingHealth(response.cards || []);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err?.message || '定稿卡加载失败');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [novelId, selectedProviderId, selectedModelId]);

  const refreshCards = async () => {
    if (!novelId) return;
    const response = await apiClient.getProductionCards(novelId);
    setData(response);
    await refreshBindingHealth(response.cards || []);
  };

  const handleCreateBinding = async (assetId: string, assetVersion: number) => {
    setBindingAssetId(assetId);
    setError(null);
    try {
      await apiClient.createAssetProviderBinding(assetId, {
        provider_id: selectedProviderId,
        model_id: selectedModelId,
        binding_kind: 'reference_image',
        asset_version: assetVersion,
        verify: true,
      });
      await refreshBindingHealth(data?.cards || []);
    } catch (err: any) {
      setError(err?.message || '模型引用生成失败');
    } finally {
      setBindingAssetId(null);
    }
  };

  const handleFinalizeSupporting = async () => {
    if (!novelId) return;
    setFinalizing(true);
    setError(null);
    setFinalizeResult(null);
    try {
      const parsedMinOccurrences = Number.parseInt(minOccurrences, 10);
      const voicePool = voicePoolInput
        .split(',')
        .map((voice) => voice.trim())
        .filter(Boolean);
      const payload: BatchFinalizeSupportingRequest = {
        min_occurrences: Number.isFinite(parsedMinOccurrences) && parsedMinOccurrences > 0 ? parsedMinOccurrences : 2,
      };

      if (imageModelConfigId.trim()) {
        payload.image_model_config_id = imageModelConfigId.trim();
      }
      if (voicePool.length) {
        payload.voice_pool = voicePool;
      }

      const result = await apiClient.batchFinalizeSupportingCharacters(novelId, payload);
      setFinalizeResult(result);
      await refreshCards();
    } catch (err: any) {
      setError(err?.message || '配角补齐失败');
    } finally {
      setFinalizing(false);
    }
  };

  const generateViewsForCard = async (card: ProductionCard, viewKeys: string[]) => {
    const payload: {
      entity_id: string;
      view_keys: string[];
      style: string;
      model_config_id?: string;
    } = {
      entity_id: card.entity_id,
      view_keys: viewKeys,
      style: 'anime',
    };
    if (imageModelConfigId.trim()) {
      payload.model_config_id = imageModelConfigId.trim();
    }
    const result = await apiClient.generateEntityViewAssets(payload);
    const assetIds = Object.values(result?.assets || {})
      .map((asset: any) => asset?.id)
      .filter(Boolean);
    if (assetIds.length > 0) {
      await apiClient.batchLockAssets(assetIds);
    }
    return typeof result?.total === 'number' ? result.total : viewKeys.length;
  };

  const handleCompleteViews = async (card: ProductionCard, viewKeys: string[]) => {
    const keys = Array.from(new Set(viewKeys.filter(Boolean)));
    if (!keys.length) return;
    const key = completionKey(card, keys);
    setCompletingKey(key);
    setCompletionMessage(`正在补齐 ${card.name}：${keys.map((view) => viewLabel(card, view)).join('、')}`);
    setError(null);
    try {
      const generatedCount = await generateViewsForCard(card, keys);
      await refreshCards();
      setCompletionMessage(`已补齐 ${generatedCount} 项缺失视图`);
    } catch (err: any) {
      setError(err?.message || `${card.name} 缺失视图补齐失败`);
    } finally {
      setCompletingKey(null);
    }
  };

  const handleCompleteAllMissingViews = async () => {
    const targets = (data?.cards || [])
      .map((card) => ({ card, viewKeys: missingViewKeys(card) }))
      .filter((item) => item.viewKeys.length > 0);
    if (!targets.length) {
      setCompletionMessage('当前定稿卡没有缺失视图需要补齐');
      return;
    }

    setCompletingKey('all');
    setError(null);
    let generatedTotal = 0;
    try {
      for (const target of targets) {
        setCompletionMessage(`正在补齐 ${target.card.name}：${target.viewKeys.map((view) => viewLabel(target.card, view)).join('、')}`);
        generatedTotal += await generateViewsForCard(target.card, target.viewKeys);
      }
      await refreshCards();
      setCompletionMessage(`已补齐 ${generatedTotal} 项缺失视图`);
    } catch (err: any) {
      setError(err?.message || '批量补齐缺失视图失败');
    } finally {
      setCompletingKey(null);
    }
  };

  const groups = useMemo(() => {
    const cards = data?.cards || [];
    return {
      character: cards.filter((card) => card.entity_type === 'character'),
      scene: cards.filter((card) => card.entity_type === 'scene'),
      prop: cards.filter((card) => card.entity_type === 'prop'),
    };
  }, [data]);

  const totalMissingViewCount = useMemo(
    () => (data?.cards || []).reduce((total, card) => total + missingViewKeys(card).length, 0),
    [data]
  );
  const totalCards = data?.cards?.length ?? 0;
  const readyCount = data?.summary?.ready ?? 0;
  const incompleteCount = data?.summary?.incomplete ?? 0;

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        {fromStudio ? (
          <div className="flex flex-col gap-3 rounded-xl border border-cyan-300/20 bg-cyan-400/[0.08] px-4 py-3 text-sm text-cyan-50 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <ClipboardCheck className="mt-0.5 h-4 w-4 shrink-0 text-cyan-200" aria-hidden="true" />
              <div>
                <div className="font-medium">已从工作台进入定稿卡</div>
                <div className="mt-1 text-xs leading-5 text-cyan-100/70">
                  当前保留了工作流上下文，补齐定稿图或声线后可返回工作台继续执行快捷操作和质量门禁检查。
                </div>
              </div>
            </div>
            <Button asChild size="sm" variant="outline" className="shrink-0 border-cyan-100/30 text-cyan-50 hover:bg-cyan-200/10">
              <Link href={studioHref(workflowId)}>
                <ArrowLeft className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                返回工作台
              </Link>
            </Button>
          </div>
        ) : null}

        <header className="rounded-2xl border border-white/10 bg-white/[0.04] p-5 shadow-[0_20px_80px_rgba(0,0,0,0.24)]">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="flex items-center gap-2 text-sm text-white/50">
                <Layers3 className="h-4 w-4 text-cyan-200" aria-hidden="true" />
                终稿前资产核对
              </div>
              <h1 className="mt-2 text-2xl font-semibold tracking-normal">定稿卡检查台</h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-white/60">
                聚合角色、场景和道具的视图锁、声线和使用证据，方便进入终稿前快速补齐。
              </p>
            </div>
            <div className="grid gap-2 sm:grid-cols-3 lg:w-[520px]">
              <MetricTile label="定稿卡" value={totalCards} detail="角色、场景、道具总数" tone="border-white/10 bg-slate-950/35" />
              <MetricTile label="终稿就绪" value={readyCount} detail="可进入终稿门禁" tone="border-emerald-300/20 bg-emerald-400/10" />
              <MetricTile label="待补齐" value={incompleteCount} detail={`缺失视图 ${totalMissingViewCount}`} tone="border-amber-300/20 bg-amber-400/10" />
            </div>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-2 text-sm">
            {novelId ? (
              <div className="flex flex-wrap items-end gap-2 rounded-xl border border-white/10 bg-slate-950/35 p-3">
                <label className="flex flex-col gap-1 text-xs text-white/55">
                  最低出镜次数
                  <input
                    type="number"
                    min="1"
                    step="1"
                    value={minOccurrences}
                    onChange={(event) => setMinOccurrences(event.target.value)}
                    disabled={finalizing || loading}
                    className="h-9 w-20 rounded-md border border-white/10 bg-slate-950/70 px-2 text-sm text-white outline-none focus:border-cyan-300/60 disabled:cursor-not-allowed disabled:opacity-60"
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs text-white/55">
                  图像模型配置 ID
                  <input
                    type="text"
                    value={imageModelConfigId}
                    onChange={(event) => setImageModelConfigId(event.target.value)}
                    disabled={finalizing || loading}
                    placeholder="可选"
                    className="h-9 w-40 rounded-md border border-white/10 bg-slate-950/70 px-2 text-sm text-white outline-none placeholder:text-white/30 focus:border-cyan-300/60 disabled:cursor-not-allowed disabled:opacity-60"
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs text-white/55">
                  声线池
                  <input
                    type="text"
                    value={voicePoolInput}
                    onChange={(event) => setVoicePoolInput(event.target.value)}
                    disabled={finalizing || loading}
                    placeholder="voice_a, voice_b"
                    className="h-9 w-44 rounded-md border border-white/10 bg-slate-950/70 px-2 text-sm text-white outline-none placeholder:text-white/30 focus:border-cyan-300/60 disabled:cursor-not-allowed disabled:opacity-60"
                  />
                </label>
                <Button
                  type="button"
                  onClick={handleFinalizeSupporting}
                  disabled={finalizing || loading || Boolean(completingKey)}
                  className="h-9 bg-cyan-600 text-white hover:bg-cyan-700"
                >
                  <Wand2 className="mr-2 h-4 w-4" aria-hidden="true" />
                  {finalizing ? '补齐中' : '一键补齐配角'}
                </Button>
                <Button
                  type="button"
                  onClick={handleCompleteAllMissingViews}
                  disabled={loading || finalizing || Boolean(completingKey) || totalMissingViewCount === 0}
                  className="h-9 bg-amber-500 text-slate-950 hover:bg-amber-400"
                >
                  {completingKey === 'all' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" /> : <Wand2 className="mr-2 h-4 w-4" aria-hidden="true" />}
                  一键补齐全部缺口
                </Button>
              </div>
            ) : null}
          </div>
        </header>

        {!novelId ? (
          <div className="rounded-md border border-white/10 bg-white/[0.04] p-6 text-sm text-white/65">
            请从工作台或资产页进入定稿卡，并带上 novel_id。
          </div>
        ) : null}

        {loading ? (
          <div className="grid gap-4 md:grid-cols-3">
            {[0, 1, 2].map((item) => (
              <div key={item} className="h-72 animate-pulse rounded-lg bg-white/[0.05]" />
            ))}
          </div>
        ) : null}

        {error ? (
          <div className="flex items-center gap-2 rounded-md border border-red-300/30 bg-red-400/10 px-4 py-3 text-sm text-red-100">
            <AlertCircle className="h-4 w-4" aria-hidden="true" />
            {error}
          </div>
        ) : null}

        {completionMessage ? (
          <div className="flex items-center gap-2 rounded-md border border-amber-300/25 bg-amber-400/10 px-4 py-3 text-sm text-amber-50">
            {completingKey ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <CheckCircle2 className="h-4 w-4" aria-hidden="true" />}
            {completionMessage}
          </div>
        ) : null}

        {finalizeResult ? (
          <div className="rounded-md border border-cyan-300/25 bg-cyan-400/10 p-4 text-sm text-cyan-50">
            <div className="flex items-center gap-2 font-medium">
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              已补齐 {finalizeResult.finalized.length} 个配角
            </div>
            {finalizeResult.finalized.length ? (
              <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {finalizeResult.finalized.map((item) => (
                  <div key={item.entity_id} className="rounded-md bg-white/[0.08] px-3 py-2">
                    <div className="font-medium text-white">{item.name}</div>
                    <div className="mt-1 text-xs text-cyan-100/70">{item.voice} · {item.asset_id}</div>
                  </div>
                ))}
              </div>
            ) : null}
            {finalizeResult.skipped.length ? (
              <div className="mt-3 border-t border-cyan-100/15 pt-3">
                <div className="text-cyan-100/70">跳过 {finalizeResult.skipped.length} 个角色</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {finalizeResult.skipped.map((item) => (
                    <span key={item.entity_id} className="rounded-full bg-white/[0.06] px-3 py-1 text-xs text-cyan-100/70">
                      {item.name || item.entity_id} · {item.reason}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}

        {data && !loading ? (
          <div className="grid gap-6 lg:grid-cols-3">
            {(['character', 'scene', 'prop'] as const).map((type) => {
              const meta = ENTITY_META[type];
              const EntityIcon = meta.icon;
              return (
              <section key={type} className="min-w-0 rounded-2xl border border-white/10 bg-white/[0.025] p-3">
                <div className="mb-3 flex items-center justify-between px-1">
                  <h2 className="flex items-center gap-2 text-base font-semibold">
                    <span className={cn('inline-flex h-8 w-8 items-center justify-center rounded-lg border', meta.tone)}>
                      <EntityIcon className="h-4 w-4" aria-hidden="true" />
                    </span>
                    {ENTITY_LABELS[type]}
                  </h2>
                  <Badge variant="outline" className="border-white/15 text-white/70">{groups[type].length}</Badge>
                </div>
                <div className="space-y-4">
                  {groups[type].length ? (
                    groups[type].map((card) => (
                      <ProductionCardItem
                        key={card.entity_id}
                        card={card}
                        completingKey={completingKey}
                        onCompleteViews={handleCompleteViews}
                        bindingHealth={bindingHealth}
                        selectedProviderId={selectedProviderId}
                        selectedModelId={selectedModelId}
                        bindingAssetId={bindingAssetId}
                        onCreateBinding={handleCreateBinding}
                        workflowId={workflowId}
                      />
                    ))
                  ) : (
                    <div className="rounded-xl border border-dashed border-white/15 bg-slate-950/25 p-5 text-sm text-white/45">
                      暂无{ENTITY_LABELS[type]}定稿卡
                    </div>
                  )}
                </div>
              </section>
              );
            })}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default function StudioProductionCardsPage() {
  return (
    <MainLayout>
      <Suspense fallback={<div className="p-6 text-white/60">正在加载定稿卡…</div>}>
        <CardsContent />
      </Suspense>
    </MainLayout>
  );
}

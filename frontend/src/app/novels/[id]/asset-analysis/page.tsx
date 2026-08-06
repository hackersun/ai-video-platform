'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, Bot, Loader2 } from 'lucide-react';
import { MainLayout } from '@/components/layout/main-layout';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import { apiClient } from '@/lib/api-client';
import { EntityReviewInspector } from '@/features/entity-review/entity-review-inspector';
import { EntityReviewTable } from '@/features/entity-review/entity-review-table';
import { EntityReviewToolbar } from '@/features/entity-review/entity-review-toolbar';
import { useEntityReviewWorkbench } from '@/features/entity-review/use-entity-review-workbench';

export default function NovelAssetAnalysisPage() {
  const params = useParams();
  const router = useRouter();
  const novelId = params.id as string;
  const { toast } = useToast();
  const workbench = useEntityReviewWorkbench(novelId);
  const [title, setTitle] = useState('小说资产审核');
  const [rebuilding, setRebuilding] = useState(false);

  useEffect(() => { apiClient.getNovel(novelId).then((novel) => setTitle(novel.title)).catch(() => undefined); }, [novelId]);
  useEffect(() => { if (workbench.error) toast({ title: '操作提示', description: workbench.error, type: 'error' }); }, [toast, workbench.error]);

  if (workbench.initialLoading) return <MainLayout><div data-testid="entity-review-initial-loading" className="space-y-4"><Skeleton className="h-20 w-full" /><Skeleton className="h-[640px] w-full" /></div></MainLayout>;
  const summary = workbench.data.summary;
  const review = (ids: string[], action: 'approve' | 'reject') => void workbench.review(ids, action).then((result) => toast({ title: action === 'approve' ? '审核完成' : '拒绝完成', description: `成功 ${result.updated.length} 项，跳过 ${result.skipped.length} 项`, type: 'success' }));
  const startRebuild = async () => { setRebuilding(true); try { await workbench.previewRebuild(); } catch (error: any) { toast({ title: '重新分析失败', description: error?.message, type: 'error' }); } finally { setRebuilding(false); } };
  const applyRebuild = async () => { setRebuilding(true); try { await workbench.applyRebuild(); toast({ title: '候选已重建', description: '旧候选已归档，定稿资产未改变', type: 'success' }); } finally { setRebuilding(false); } };

  return <MainLayout><div className="space-y-4">
    <header className="flex flex-wrap items-start justify-between gap-3"><div className="flex items-start gap-3"><Button variant="ghost" onClick={() => router.push(`/novels/${novelId}`)}><ArrowLeft className="mr-2 h-4 w-4" />返回</Button><div><div className="flex items-center gap-2 text-xs text-cyan-200"><Bot className="h-4 w-4" />AI 资产审核工作台</div><h1 className="mt-1 text-2xl font-bold text-white">{title}</h1><p className="mt-1 text-sm text-white/45">分页审核、跨页批量、直接修改、模型重分析，所有操作保持当前位置。</p></div></div>{workbench.refreshing ? <div className="flex items-center text-sm text-white/45"><Loader2 className="mr-2 h-4 w-4 animate-spin" />后台刷新</div> : null}</header>
    <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">{[
      ['总实体', summary.total], ['待审核', summary.candidate_count], ['已定稿', summary.approved_count], ['已拒绝', summary.rejected_count], ['缺少证据', summary.missing_evidence_count || 0],
    ].map(([label, value]) => <div key={String(label)} className="rounded-lg border border-white/10 bg-white/[0.04] p-3"><div className="text-xs text-white/45">{label}</div><div className="mt-2 text-xl font-semibold text-white">{value}</div></div>)}</section>
    {workbench.rebuild ? <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-500/35 bg-amber-500/10 p-3"><div><div className="font-medium text-amber-100">模型找到 {workbench.rebuild.proposed.length} 个新候选</div><div className="text-xs text-amber-100/60">模型 {String(workbench.rebuild.model_execution.provider || '-')} / {String(workbench.rebuild.model_execution.model_id || '-')}；确认后仅归档旧候选与旧拒绝项。</div></div><Button className="bg-amber-600" disabled={rebuilding} onClick={applyRebuild}>确认重建候选</Button></div> : null}
    <section className="grid min-h-0 gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(360px,0.65fr)]"><div className="flex min-h-0 flex-col rounded-lg border border-white/10 bg-black/20"><EntityReviewToolbar query={workbench.query} selectedCount={workbench.selectedIds.size} refreshing={workbench.refreshing} rebuilding={rebuilding} onQuery={workbench.setQuery} onReview={(action) => review(Array.from(workbench.selectedIds), action)} onRefresh={() => void workbench.load(true)} onRebuild={startRebuild} /><EntityReviewTable data={workbench.data} selectedIds={workbench.selectedIds} activeId={workbench.activeEntity?.id} busyIds={workbench.busyIds} onSelected={workbench.setSelectedIds} onActive={(entity) => workbench.setQuery({ entity })} onReview={review} onPage={(page) => workbench.setQuery({ page })} onPageSize={(page_size) => workbench.setQuery({ page_size, page: 1 })} /></div><EntityReviewInspector entity={workbench.activeEntity} preview={workbench.reanalysis} onSave={(patch) => workbench.save(workbench.activeEntity!.id, patch)} onPreview={() => workbench.previewEntity(workbench.activeEntity!.id)} onApply={workbench.applyEntity} /></section>
  </div></MainLayout>;
}

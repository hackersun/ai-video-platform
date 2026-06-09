'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { AlertCircle, Loader2, PlayCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Select } from '@/components/ui/select';
import { useToast } from '@/components/ui/toast';
import { getStudioSnapshot, getStudioWorkflows, runStudioAction } from '@/lib/studio-api';
import type { StudioAction, StudioActionResult, StudioIssue, StudioRunMode, StudioSnapshot, StudioWorkflowOption } from '@/lib/studio-types';
import { StudioAgentPanel } from './studio-agent-panel';
import { StudioContextPanel } from './studio-context-panel';
import { StudioModeBanner } from './studio-mode-banner';
import { StudioProductionBoard } from './studio-production-board';

function workflowIdOf(item: StudioWorkflowOption) {
  return item.workflow_id || item.id || '';
}

export function StudioShell() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const [mode, setMode] = useState<StudioRunMode>('production');
  const [workflows, setWorkflows] = useState<StudioWorkflowOption[]>([]);
  const [workflowId, setWorkflowId] = useState(searchParams.get('workflow_id') || '');
  const [snapshot, setSnapshot] = useState<StudioSnapshot | null>(null);
  const [bypassReason, setBypassReason] = useState('');
  const [lastAction, setLastAction] = useState<StudioActionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const workflowOptions = useMemo(
    () => workflows.map((item) => ({ value: workflowIdOf(item), label: item.title || workflowIdOf(item) })),
    [workflows]
  );

  const loadWorkflows = useCallback(async () => {
    try {
      const data = await getStudioWorkflows();
      const list = Array.isArray(data) ? data : [];
      setWorkflows(list);
      if (!workflowId && list.length) {
        const firstId = workflowIdOf(list[0]);
        setWorkflowId(firstId);
        router.replace(`/studio?workflow_id=${firstId}`);
      }
    } catch (err: any) {
      setError(err.message || '加载工作流失败');
    }
  }, [router, workflowId]);

  const loadSnapshot = useCallback(async (
    targetWorkflowId = workflowId,
    nextMode = mode,
    policy?: { allow_test_bypass?: boolean; bypass_reason?: string }
  ) => {
    if (!targetWorkflowId) return;
    setLoading(true);
    setError('');
    try {
      const data = await getStudioSnapshot(targetWorkflowId, { mode: nextMode, ...policy });
      setSnapshot(data);
    } catch (err: any) {
      setError(err.message || '加载工作台快照失败');
    } finally {
      setLoading(false);
    }
  }, [mode, workflowId]);

  useEffect(() => {
    loadWorkflows();
  }, [loadWorkflows]);

  useEffect(() => {
    if (workflowId) loadSnapshot(workflowId, mode);
  }, [workflowId, mode, loadSnapshot]);

  const handleWorkflowChange = (value: string) => {
    setWorkflowId(value);
    router.replace(`/studio?workflow_id=${value}`);
  };

  const handleModeChange = (nextMode: StudioRunMode) => {
    setMode(nextMode);
  };

  const handleAction = async (action: StudioAction, issue: StudioIssue) => {
    if (!workflowId) return;
    const isSkip = action.code === 'skip_issue';
    const reason = bypassReason.trim();
    if (isSkip && mode !== 'test') {
      toast({ title: '生产模式不能跳过', description: '请按修复入口补齐后再继续。', type: 'error' });
      return;
    }
    if (isSkip && reason.length < 8) {
      toast({ title: '需要填写跳过原因', description: '测试模式跳过需要至少 8 个字符，并说明后续修复路径。', type: 'error' });
      return;
    }
    setLoading(true);
    try {
      const result = await runStudioAction(workflowId, {
        code: action.code,
        mode,
        allow_test_bypass: isSkip,
        bypass_reason: isSkip ? reason : undefined,
        source_issue_code: issue.code,
      });
      setLastAction(result);
      toast({
        title: result.status === 'skipped' ? '已记录测试跳过' : `${result.label || action.label}已执行`,
        description: isSkip ? '该跳过只适用于测试验证模式，生产出片仍需修复。' : '已刷新工作台检查结果。',
        type: 'success',
      });
      await loadSnapshot(
        workflowId,
        mode,
        isSkip ? { allow_test_bypass: true, bypass_reason: reason } : undefined
      );
    } catch (err: any) {
      setError(err.message || '执行修复动作失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-cyan-200">
            <PlayCircle className="h-4 w-4" />
            统一创作工作台
          </div>
          <h1 className="mt-2 text-2xl font-semibold text-white">从上下文到出片检查，一屏推进</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-white/55">
            选择本集工程后，工作台会聚合 Story Bible、镜头、资产锁、任务和时间线，并给出明确修复路径。
          </p>
        </div>
        <div className="w-full lg:w-80">
          <Select
            value={workflowId}
            onChange={(event) => handleWorkflowChange(event.target.value)}
            options={workflowOptions}
            placeholder={workflowOptions.length ? '选择本集工程' : '暂无本集工程'}
            disabled={loading || !workflowOptions.length}
          />
        </div>
      </div>

      <StudioModeBanner mode={mode} onModeChange={handleModeChange} />

      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-red-500/25 bg-red-500/10 p-3 text-sm text-red-50">
          <AlertCircle className="mt-0.5 h-4 w-4" />
          {error}
        </div>
      )}

      {!workflowId && !loading ? (
        <Card className="border-white/10 bg-white/5">
          <CardContent className="p-8 text-center">
            <div className="text-lg font-medium text-white">先创建或选择本集工程</div>
            <div className="mx-auto mt-2 max-w-xl text-sm leading-6 text-white/55">
              工作台不会自动创建工程。你可以从工作流页面选择小说、章节、剧本和分镜，再回到这里进行统一检查。
            </div>
            <Button className="mt-5 bg-cyan-600 hover:bg-cyan-700" onClick={() => router.push('/workflow')}>
              去创建工作流
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          {loading && !snapshot ? (
            <div className="rounded-lg border border-white/10 bg-white/5 p-8 text-center text-white/60">
              <Loader2 className="mx-auto mb-3 h-5 w-5 animate-spin" />
              正在加载工作台快照…
            </div>
          ) : null}
          <StudioContextPanel snapshot={snapshot} />
          <StudioProductionBoard snapshot={snapshot} />
          <StudioAgentPanel
            snapshot={snapshot}
            mode={mode}
            loading={loading}
            bypassReason={bypassReason}
            lastAction={lastAction}
            onBypassReasonChange={setBypassReason}
            onRefresh={() => loadSnapshot(workflowId, mode)}
            onAction={handleAction}
          />
        </>
      )}
    </div>
  );
}

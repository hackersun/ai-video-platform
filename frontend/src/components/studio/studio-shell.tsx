'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  AlertCircle,
  AlertTriangle,
  BookOpen,
  Captions,
  CheckCircle2,
  Loader2,
  Map,
  Mic2,
  Package,
  Palette,
  UserRound,
  XCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Select } from '@/components/ui/select';
import { useToast } from '@/components/ui/toast';
import { getStudioSnapshot, getStudioWorkflows, runStudioAction } from '@/lib/studio-api';
import type { StudioAction, StudioActionResult, StudioIssue, StudioRunMode, StudioSnapshot, StudioWorkflowOption } from '@/lib/studio-types';
import { StudioAgentPanel } from './studio-agent-panel';
import { StudioContextPanel } from './studio-context-panel';
import { StudioModeBanner } from './studio-mode-banner';
import { StudioProductionBoard } from './studio-production-board';
import { StudioSeriesBoard } from './studio-series-board';
import { PromptSkillPanel } from './prompt-skill-panel';

function workflowIdOf(item: StudioWorkflowOption) {
  return item.workflow_id || item.id || '';
}

type ContinuityTone = 'green' | 'yellow' | 'red';

type ContinuityItem = {
  key: string;
  label: string;
  status: ContinuityTone;
  value: string;
  nextStep: string;
  icon: any;
};

function statusCopy(status: ContinuityTone) {
  if (status === 'green') return '稳定';
  if (status === 'yellow') return '待确认';
  return '需处理';
}

function statusClass(status: ContinuityTone) {
  if (status === 'green') return 'border-emerald-400/25 bg-emerald-500/10 text-emerald-50';
  if (status === 'yellow') return 'border-amber-400/25 bg-amber-500/10 text-amber-50';
  return 'border-red-400/25 bg-red-500/10 text-red-50';
}

function statusIcon(status: ContinuityTone) {
  if (status === 'green') return CheckCircle2;
  if (status === 'yellow') return AlertTriangle;
  return XCircle;
}

function toneFromCount(count: number, warningFloor = 1): ContinuityTone {
  if (count > warningFloor) return 'green';
  if (count === warningFloor) return 'yellow';
  return 'red';
}

function buildContinuityItems(snapshot: StudioSnapshot | null): ContinuityItem[] {
  const bible = snapshot?.story_bible || {};
  const productionBible = snapshot?.production_bible_summary;
  const counts = productionBible?.counts || {};
  const production = snapshot?.production || {};
  const assets = snapshot?.assets || {};
  const jobs = snapshot?.jobs?.summary || {};
  const shots = snapshot?.shots || [];
  const timeline = snapshot?.timeline;
  const missingAssetCount = productionBible?.asset_readiness?.missing_asset_count;
  const characterCount = counts.characters || bible.character_rule_count || productionBible?.characters?.length || 0;
  const sceneCount = counts.scenes || bible.scene_rule_count || productionBible?.scenes?.length || 0;
  const propCount = counts.props || bible.prop_rule_count || productionBible?.props?.length || 0;
  const voiceCount = productionBible?.voices?.length || 0;
  const styleReady = Boolean(productionBible?.style && Object.keys(productionBible.style).length) || Boolean(bible.style || bible.worldview);
  const assetCoverage = production.asset_lock_coverage || 0;
  const entityCoverage = production.entity_ref_coverage || 0;
  const dialogueCount = shots.filter((shot) => Boolean(shot.dialogue)).length;
  const mediaCount = (jobs.video_count || 0) + (jobs.media_count || 0) + (jobs.tts_count || 0) + (jobs.synthesis_count || 0);
  const timelineClipCount = timeline?.clip_count || 0;

  return [
    {
      key: 'characters',
      label: '角色',
      icon: UserRound,
      status: characterCount > 1 && assetCoverage >= 0.8 ? 'green' : characterCount > 0 ? 'yellow' : 'red',
      value: `${characterCount} 个角色锚点 · 资产锁 ${Math.round(assetCoverage * 100)}%`,
      nextStep:
        characterCount > 1 && assetCoverage >= 0.8
          ? '继续沿用角色设定和参考资产，出片前抽查主角镜头。'
          : characterCount > 0
            ? '补齐主角定稿参考图并应用资产锁，避免跨镜头漂移。'
            : '先从小说/章节生成角色设定，再绑定参考图。',
    },
    {
      key: 'scenes',
      label: '场景',
      icon: Map,
      status: sceneCount > 1 && entityCoverage >= 0.7 ? 'green' : sceneCount > 0 ? 'yellow' : 'red',
      value: `${sceneCount} 个场景锚点 · 实体引用 ${Math.round(entityCoverage * 100)}%`,
      nextStep:
        sceneCount > 1 && entityCoverage >= 0.7
          ? '保持场景锚点随镜头复用，重点检查转场前后空间关系。'
          : sceneCount > 0
            ? '为低引用镜头补上场景实体，明确地点、时段和光线。'
            : '先生成场景规则，避免分镜只依赖自由文本。',
    },
    {
      key: 'props',
      label: '道具',
      icon: Package,
      status: propCount > 1 && (missingAssetCount === 0 || assets.locked_count > 0) ? 'green' : propCount > 0 ? 'yellow' : 'red',
      value: `${propCount} 个道具锚点 · 缺资产 ${missingAssetCount ?? '未知'}`,
      nextStep:
        propCount > 1 && (missingAssetCount === 0 || assets.locked_count > 0)
          ? '继续复用关键道具锁，检查特写镜头的形态一致性。'
          : propCount > 0
            ? '为关键道具补参考图或资产锁，优先处理反复出现的物件。'
            : '从 Story Bible 提取关键道具，避免后续镜头临时生成。',
    },
    {
      key: 'voices',
      label: '声线',
      icon: Mic2,
      status: voiceCount > 1 ? 'green' : voiceCount === 1 || (jobs.tts_count || 0) > 0 ? 'yellow' : 'red',
      value: `${voiceCount} 个 voice profile · TTS ${jobs.tts_count || 0} 个任务`,
      nextStep:
        voiceCount > 1
          ? '角色声线已有基础覆盖，终稿前抽听主角和旁白片段。'
          : voiceCount === 1 || (jobs.tts_count || 0) > 0
            ? '补齐主要角色 voice profile，避免同集内音色混用。'
            : '先为主角、旁白和高频配角定义声线。',
    },
    {
      key: 'style',
      label: '风格',
      icon: Palette,
      status: styleReady && assetCoverage >= 0.8 ? 'green' : styleReady ? 'yellow' : 'red',
      value: styleReady ? '已读取视觉风格设定' : '未检测到风格锚点',
      nextStep:
        styleReady && assetCoverage >= 0.8
          ? '继续用统一风格提示词生产，重点审查异常镜头。'
          : styleReady
            ? '把风格设定同步到资产锁和镜头提示词，减少画风跳变。'
            : '补齐系列画风、色彩、镜头语言和负面约束。',
    },
    {
      key: 'captions',
      label: '字幕/节奏',
      icon: Captions,
      status: toneFromCount(timelineClipCount || mediaCount || dialogueCount, 1),
      value: `${dialogueCount} 条对白 · ${timelineClipCount} 个时间线片段`,
      nextStep:
        timelineClipCount > 1
          ? '对照时间线检查字幕断句、停顿和镜头节奏。'
          : dialogueCount > 0 || mediaCount > 0
            ? '生成或同步时间线后，再校准字幕入点和节奏。'
            : '先补齐对白/旁白，再进入时间线节奏校验。',
    },
  ];
}

function StudioContinuityBoard({ snapshot }: { snapshot: StudioSnapshot | null }) {
  const items = buildContinuityItems(snapshot);
  const summary = items.reduce(
    (acc, item) => {
      acc[item.status] += 1;
      return acc;
    },
    { green: 0, yellow: 0, red: 0 }
  );

  return (
    <Card className="border-white/10 bg-white/5">
      <CardContent className="space-y-4 p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm font-medium text-white">
              <CheckCircle2 className="h-4 w-4 text-cyan-300" />
              连续性/一致性状态看板
            </div>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-white/55">
              基于当前工作台快照预览角色、场景、道具、声线、风格、字幕/节奏的一致性风险；这里只做前端提示，不改变生产门禁。
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2 text-xs">
            <Badge variant="outline" className="border-emerald-400/30 bg-emerald-500/10 text-emerald-100">
              绿 {summary.green}
            </Badge>
            <Badge variant="outline" className="border-amber-400/30 bg-amber-500/10 text-amber-100">
              黄 {summary.yellow}
            </Badge>
            <Badge variant="outline" className="border-red-400/30 bg-red-500/10 text-red-100">
              红 {summary.red}
            </Badge>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {items.map((item) => {
            const ItemIcon = item.icon;
            const StatusIcon = statusIcon(item.status);
            return (
              <div key={item.key} className={`rounded-xl border p-4 ${statusClass(item.status)}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-2">
                    <ItemIcon className="h-4 w-4 shrink-0" />
                    <div className="font-medium text-white">{item.label}</div>
                  </div>
                  <Badge variant="outline" className="shrink-0 border-current text-current">
                    <StatusIcon className="mr-1 h-3 w-3" />
                    {statusCopy(item.status)}
                  </Badge>
                </div>
                <div className="mt-3 text-sm text-white/75">{item.value}</div>
                <div className="mt-2 text-xs leading-5 text-white/55">下一步：{item.nextStep}</div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
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
            <BookOpen className="h-4 w-4" />
            连续动漫工作台
          </div>
          <h1 className="mt-2 text-2xl font-semibold text-white">从小说章节到本集草片</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-white/55">
            选择小说/章节生成本集工程后，这里会聚合动漫设定本、剧本分镜、资产/声音锁、草片任务和质量门禁；高级制作流程仍保留给精修使用。
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
            <div className="text-lg font-medium text-white">先从小说创建本集工程</div>
            <div className="mx-auto mt-2 max-w-xl text-sm leading-6 text-white/55">
              还没有可继续制作的本集工程。建议先打开连续动漫向导，导入小说章节并生成动漫设定本和第一集；完成后会带着本集工程回到这里继续一键草片、资产锁和质量门禁。
            </div>
            <div className="mt-5 flex flex-col justify-center gap-2 sm:flex-row">
              <Button className="bg-cyan-600 hover:bg-cyan-700" onClick={() => router.push('/quick-start')}>
                连续动漫向导：小说到第一集
              </Button>
              <Button variant="outline" className="border-white/20 text-white" onClick={() => router.push('/producer')}>
                一键成片：创建本集工程
              </Button>
            </div>
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
          <PromptSkillPanel />
          <StudioSeriesBoard snapshot={snapshot} workflowId={workflowId} />
          <StudioContextPanel snapshot={snapshot} />
          <StudioProductionBoard snapshot={snapshot} workflowId={workflowId} />
          <StudioContinuityBoard snapshot={snapshot} />
          <div id="studio-agent-panel">
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
          </div>
        </>
      )}
    </div>
  );
}

'use client';

import { useEffect, useMemo, useState } from 'react';
import { MainLayout } from '@/components/layout/main-layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import apiClient from '@/lib/api-client';
import {
  AlertCircle,
  BarChart3,
  BookOpen,
  Bot,
  CheckCircle,
  Clock,
  Coins,
  FileText,
  Image as ImageIcon,
  Layers3,
  Loader2,
  Mic,
  RefreshCw,
  Sparkles,
  TrendingUp,
  Users,
  Video,
  Zap
} from 'lucide-react';

type ContentStats = {
  novels_count: number;
  chapters_count: number;
  scripts_count: number;
  storyboards_count: number;
  shots_count: number;
  characters_count: number;
  assets_count: number;
};

type UsageSummary = {
  total_requests: number;
  total_tokens: number;
  total_cost: number;
  today_requests: number;
  today_cost: number;
};

type TaskSummary = {
  total: number;
  pending: number;
  running: number;
  completed: number;
  failed: number;
  cancelled: number;
  completion_rate: number;
};

type TaskTypeStats = TaskSummary & {
  type: string;
  label: string;
};

type DailyStats = {
  date: string;
  created_tasks: number;
  completed_tasks: number;
  ai_requests: number;
  token_count: number;
  cost: number;
};

type ModelUsage = {
  model_id: string;
  model_name: string;
  request_count: number;
  total_tokens: number;
  total_cost: number;
  avg_response_time: number;
};

type RecentActivity = {
  id: string;
  type: string;
  title: string;
  description: string;
  timestamp: string;
};

type AnalyticsData = {
  data_source: 'database';
  is_mock: boolean;
  generated_at: string;
  period_days: number;
  content_stats: ContentStats;
  usage_summary: UsageSummary;
  task_summary: TaskSummary;
  task_by_type: TaskTypeStats[];
  daily_series: DailyStats[];
  model_usage: ModelUsage[];
  recent_activities: RecentActivity[];
  production_metrics?: {
    counts?: { planned_shots?: number; accepted_final_shots?: number; failed_attempts?: number; abandoned_attempts?: number };
    first_pass_shot_acceptance_rate?: number;
    main_character_hard_failure_rate?: number;
    state_continuity_conflict_rate?: number;
    voice_lipsync_hard_failure_rate?: number;
    regenerated_shots_per_accepted_shot?: number | null;
    rmb_per_accepted_final_minute?: number | null;
    wall_clock_minutes_per_accepted_final_minute?: number | null;
    human_review_repair_minutes_per_accepted_final_minute?: number | null;
    failed_abandoned?: { attempt_count?: number; cost_rmb?: number };
    readiness?: { current_tier?: string; tiers?: Record<string, boolean> };
    attribution?: Array<Record<string, any>>;
  };
};

const formatNumber = (value: number) => new Intl.NumberFormat('zh-CN').format(value || 0);
const formatCost = (value: number) => `¥${Number(value || 0).toFixed(4)}`;
const formatRate = (value?: number | null) => value == null ? '不可用' : `${(value * 100).toFixed(1)}%`;
const readinessLabels: Record<string, string> = {
  not_ready: '尚未就绪',
  deterministic_ready: '确定性验证就绪',
  internal_trial_ready: '内部试制就绪',
  series_production_candidate: '系列生产候选',
  commercial_series_ready: '商业系列就绪',
};

const formatShortDate = (date: string) => {
  const parsed = new Date(date);
  if (Number.isNaN(parsed.getTime())) return date;
  return `${parsed.getMonth() + 1}/${parsed.getDate()}`;
};

const taskIcons: Record<string, typeof Video> = {
  video: Video,
  tts: Mic,
  image: ImageIcon,
  synthesis: Layers3,
  media: Sparkles,
};

export default function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAnalytics = async (silent = false) => {
    if (silent) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      const data = await apiClient.getAnalyticsDashboard(14);
      if (data?.is_mock) {
        throw new Error('后端返回了模拟数据，数据分析页要求正式数据库统计。');
      }
      setAnalytics(data);
    } catch (err: any) {
      setAnalytics(null);
      setError(err.message || '正式数据加载失败，请检查后端统计接口。');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadAnalytics();
  }, []);

  const dailyMax = useMemo(() => {
    return Math.max(1, ...(analytics?.daily_series || []).map((item) => item.created_tasks || 0));
  }, [analytics]);

  const modelMax = useMemo(() => {
    return Math.max(1, ...(analytics?.model_usage || []).map((item) => item.request_count || 0));
  }, [analytics]);

  const contentCards = analytics ? [
    {
      label: '小说',
      value: analytics.content_stats.novels_count,
      detail: 'novels 表',
      icon: BookOpen,
      tone: 'from-violet-500/20 to-indigo-500/10',
    },
    {
      label: '章节',
      value: analytics.content_stats.chapters_count,
      detail: 'chapters 表',
      icon: FileText,
      tone: 'from-cyan-500/20 to-blue-500/10',
    },
    {
      label: '剧本',
      value: analytics.content_stats.scripts_count,
      detail: 'scripts 表',
      icon: Layers3,
      tone: 'from-blue-500/20 to-sky-500/10',
    },
    {
      label: '分镜 / 镜头',
      value: analytics.content_stats.storyboards_count,
      detail: `${formatNumber(analytics.content_stats.shots_count)} 个镜头`,
      icon: Video,
      tone: 'from-rose-500/20 to-orange-500/10',
    },
    {
      label: '角色',
      value: analytics.content_stats.characters_count,
      detail: 'characters 表',
      icon: Users,
      tone: 'from-emerald-500/20 to-teal-500/10',
    },
    {
      label: '资产',
      value: analytics.content_stats.assets_count,
      detail: 'assets 活跃记录',
      icon: ImageIcon,
      tone: 'from-amber-500/20 to-yellow-500/10',
    },
  ] : [];

  if (loading) {
    return (
      <MainLayout>
        <div className="flex min-h-[420px] items-center justify-center">
          <div className="text-center">
            <Loader2 className="mx-auto h-8 w-8 animate-spin text-violet-300" />
            <p className="mt-3 text-sm text-white/60">正在读取数据库正式统计...</p>
          </div>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-sm text-emerald-200">
              <CheckCircle className="h-4 w-4" />
              数据源：后端数据库正式统计
            </div>
            <h1 className="mt-3 text-3xl font-bold text-white">数据分析</h1>
            <p className="mt-1 text-white/60">
              所有指标来自 `/api/v1/dashboard/analytics`，不使用前端模拟数据。
            </p>
            {analytics && (
              <p className="mt-2 text-xs text-white/40">
                生成时间：{new Date(analytics.generated_at).toLocaleString('zh-CN')} · 统计周期：近 {analytics.period_days} 天 · is_mock={String(analytics.is_mock)}
              </p>
            )}
          </div>
          <Button
            onClick={() => loadAnalytics(true)}
            disabled={refreshing}
            variant="outline"
            className="border-white/15 bg-white/5 text-white hover:bg-white/10"
          >
            {refreshing ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4" />
            )}
            刷新正式数据
          </Button>
        </div>

        {error && (
          <Card className="border-red-500/30 bg-red-500/10">
            <CardContent className="flex items-start gap-3 p-4">
              <AlertCircle className="mt-0.5 h-5 w-5 text-red-300" />
              <div>
                <p className="font-medium text-red-100">正式统计加载失败</p>
                <p className="mt-1 text-sm text-red-200/80">{error}</p>
              </div>
            </CardContent>
          </Card>
        )}

        {!analytics ? (
          <EmptyAnalyticsState
            title="暂无可展示数据"
            description="页面没有使用模拟数据。请先确认后端 `/dashboard/analytics` 返回 200，或重新登录后刷新。"
          />
        ) : (
          <>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
              {contentCards.map((stat) => {
                const Icon = stat.icon;
                return (
                  <Card key={stat.label} className={`overflow-hidden border-white/10 bg-gradient-to-br ${stat.tone}`}>
                    <CardContent className="p-5">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="text-sm text-white/55">{stat.label}</p>
                          <p className="mt-2 text-3xl font-semibold text-white">{formatNumber(stat.value)}</p>
                          <p className="mt-2 text-sm text-white/45">{stat.detail}</p>
                        </div>
                        <div className="rounded-2xl border border-white/10 bg-white/10 p-3">
                          <Icon className="h-5 w-5 text-white/80" />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>

            <Card className="border-cyan-300/20 bg-cyan-400/[0.04]" data-testid="production-metrics">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="flex items-center gap-2 text-white">
                  <BarChart3 className="h-5 w-5 text-cyan-300" />
                  连续动漫生产指标
                </CardTitle>
                <Badge variant="outline" className="border-cyan-300/40 text-cyan-100">
                  {readinessLabels[analytics.production_metrics?.readiness?.current_tier || 'not_ready'] || analytics.production_metrics?.readiness?.current_tier}
                </Badge>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <MetricBox label="首轮镜头接收率" value={formatRate(analytics.production_metrics?.first_pass_shot_acceptance_rate)} />
                  <MetricBox label="主角硬失败率" value={formatRate(analytics.production_metrics?.main_character_hard_failure_rate)} />
                  <MetricBox label="状态连续性冲突率" value={formatRate(analytics.production_metrics?.state_continuity_conflict_rate)} />
                  <MetricBox label="声音/口型硬失败率" value={formatRate(analytics.production_metrics?.voice_lipsync_hard_failure_rate)} />
                  <MetricBox label="每接收镜头返修数" value={analytics.production_metrics?.regenerated_shots_per_accepted_shot?.toFixed(2) || '不可用'} />
                  <MetricBox label="每终稿分钟成本" value={analytics.production_metrics?.rmb_per_accepted_final_minute == null ? '不可用' : formatCost(analytics.production_metrics.rmb_per_accepted_final_minute)} />
                  <MetricBox label="每终稿分钟墙钟耗时" value={analytics.production_metrics?.wall_clock_minutes_per_accepted_final_minute == null ? '不可用' : `${analytics.production_metrics.wall_clock_minutes_per_accepted_final_minute.toFixed(1)} 分钟`} />
                  <MetricBox label="每终稿分钟人工审修" value={analytics.production_metrics?.human_review_repair_minutes_per_accepted_final_minute == null ? '不可用' : `${analytics.production_metrics.human_review_repair_minutes_per_accepted_final_minute.toFixed(1)} 分钟`} />
                </div>
                <div className="rounded-xl border border-red-300/15 bg-red-400/5 px-4 py-3 text-sm text-red-100">
                  失败/放弃尝试保持可见：{formatNumber(analytics.production_metrics?.failed_abandoned?.attempt_count || 0)} 次，成本 {formatCost(analytics.production_metrics?.failed_abandoned?.cost_rmb || 0)}。
                </div>
              </CardContent>
            </Card>

            <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.2fr_1fr]">
              <Card className="border-white/10 bg-white/5">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-white">
                    <Zap className="h-5 w-5 text-amber-300" />
                    AI 调用与成本
                  </CardTitle>
                </CardHeader>
                <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-4">
                  <MetricBox label="总请求" value={formatNumber(analytics.usage_summary.total_requests)} />
                  <MetricBox label="今日请求" value={formatNumber(analytics.usage_summary.today_requests)} />
                  <MetricBox label="Token" value={formatNumber(analytics.usage_summary.total_tokens)} />
                  <MetricBox label="总成本" value={formatCost(analytics.usage_summary.total_cost)} />
                </CardContent>
              </Card>

              <Card className="border-white/10 bg-white/5">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-white">
                    <CheckCircle className="h-5 w-5 text-emerald-300" />
                    任务完成率
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-5">
                    <div className="flex items-end justify-between">
                      <div>
                        <p className="text-sm text-white/55">全部生成任务</p>
                        <p className="mt-2 text-4xl font-semibold text-white">{analytics.task_summary.completion_rate}%</p>
                      </div>
                      <TrendingUp className="h-8 w-8 text-emerald-300" />
                    </div>
                    <div className="mt-5 h-3 overflow-hidden rounded-full bg-white/10">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-cyan-300"
                        style={{ width: `${analytics.task_summary.completion_rate}%` }}
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
              <StatusPill label="总任务" value={analytics.task_summary.total} icon={Clock} />
              <StatusPill label="待处理" value={analytics.task_summary.pending} icon={Clock} />
              <StatusPill label="进行中" value={analytics.task_summary.running} icon={Loader2} />
              <StatusPill label="已完成" value={analytics.task_summary.completed} icon={CheckCircle} />
              <StatusPill label="失败" value={analytics.task_summary.failed} icon={AlertCircle} />
              <StatusPill label="已取消" value={analytics.task_summary.cancelled} icon={AlertCircle} />
            </div>

            <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.4fr_1fr]">
              <Card className="border-white/10 bg-white/5">
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle className="flex items-center gap-2 text-white">
                    <BarChart3 className="h-5 w-5 text-cyan-300" />
                    近 {analytics.period_days} 天任务趋势
                  </CardTitle>
                  <Badge variant="outline" className="border-cyan-300/40 text-cyan-200">
                    数据库按日聚合
                  </Badge>
                </CardHeader>
                <CardContent>
                  {analytics.daily_series.length === 0 ? (
                    <EmptyAnalyticsState title="暂无任务趋势" description="数据库当前没有该周期内任务记录。" />
                  ) : (
                    <div className="flex h-72 items-end gap-2 rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                      {analytics.daily_series.map((item) => {
                        const height = Math.max(5, Math.round(((item.created_tasks || 0) / dailyMax) * 100));
                        return (
                          <div key={item.date} className="flex min-w-0 flex-1 flex-col items-center gap-2">
                            <div className="flex h-52 w-full items-end">
                              <div
                                className="w-full rounded-t-lg bg-gradient-to-t from-cyan-500 to-violet-400 shadow-lg shadow-cyan-500/10"
                                style={{ height: `${height}%` }}
                                title={`${item.date}: 创建 ${item.created_tasks} 个任务，完成 ${item.completed_tasks} 个任务，AI 请求 ${item.ai_requests} 次`}
                              />
                            </div>
                            <span className="max-w-full truncate text-xs text-white/45">{formatShortDate(item.date)}</span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card className="border-white/10 bg-white/5">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-white">
                    <Layers3 className="h-5 w-5 text-emerald-300" />
                    任务类型分布
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {analytics.task_by_type.map((item) => {
                    const Icon = taskIcons[item.type] || Layers3;
                    return (
                      <div key={item.type} className="rounded-2xl border border-white/10 bg-slate-950/35 p-4">
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex items-center gap-3">
                            <Icon className="h-5 w-5 text-cyan-200" />
                            <div>
                              <p className="font-medium text-white">{item.label}</p>
                              <p className="text-xs text-white/45">
                                完成 {formatNumber(item.completed)} · 失败 {formatNumber(item.failed)}
                              </p>
                            </div>
                          </div>
                          <Badge variant="outline" className="border-white/20 text-white/70">
                            {formatNumber(item.total)}
                          </Badge>
                        </div>
                      </div>
                    );
                  })}
                </CardContent>
              </Card>
            </div>

            <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
              <Card className="border-white/10 bg-white/5">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-white">
                    <Bot className="h-5 w-5 text-violet-300" />
                    模型使用排行
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {analytics.model_usage.length === 0 ? (
                    <EmptyAnalyticsState title="暂无模型调用记录" description="llm_usage_logs 表暂无当前用户调用数据。" />
                  ) : (
                    analytics.model_usage.map((model) => (
                      <div key={model.model_id} className="space-y-2 rounded-2xl border border-white/10 bg-slate-950/35 p-4">
                        <div className="flex items-center justify-between gap-3">
                          <div className="min-w-0">
                            <p className="truncate font-medium text-white">{model.model_name || model.model_id}</p>
                            <p className="text-xs text-white/45">
                              {formatNumber(model.total_tokens)} tokens · {formatCost(model.total_cost)}
                            </p>
                          </div>
                          <Badge variant="outline" className="border-white/20 text-white/70">
                            {formatNumber(model.request_count)} 次
                          </Badge>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-white/10">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-violet-400 to-cyan-300"
                            style={{ width: `${Math.max(8, (model.request_count / modelMax) * 100)}%` }}
                          />
                        </div>
                        <p className="text-xs text-white/40">平均响应 {Math.round(model.avg_response_time || 0)}ms</p>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>

              <Card className="border-white/10 bg-white/5">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-white">
                    <Clock className="h-5 w-5 text-amber-300" />
                    最近创作活动
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {!analytics.recent_activities?.length ? (
                    <EmptyAnalyticsState title="暂无近期活动" description="创建小说、剧本、角色或视频后，会在这里形成创作时间线。" />
                  ) : (
                    <div className="space-y-3">
                      {analytics.recent_activities.map((activity) => (
                        <div key={activity.id} className="flex gap-3 rounded-2xl border border-white/10 bg-slate-950/35 p-4">
                          <div className="mt-1 h-2.5 w-2.5 rounded-full bg-cyan-300 shadow-lg shadow-cyan-300/40" />
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                              <p className="font-medium text-white">{activity.title}</p>
                              <span className="text-xs text-white/40">{new Date(activity.timestamp).toLocaleString('zh-CN')}</span>
                            </div>
                            <p className="mt-1 truncate text-sm text-white/55">{activity.description || '未填写描述'}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </>
        )}
      </div>
    </MainLayout>
  );
}

function MetricBox({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/35 p-4">
      <p className="text-sm text-white/45">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

function StatusPill({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: number;
  icon: typeof Clock;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
      <Icon className="mb-3 h-4 w-4 text-white/45" />
      <p className="text-2xl font-semibold text-white">{formatNumber(value)}</p>
      <p className="text-sm text-white/45">{label}</p>
    </div>
  );
}

function EmptyAnalyticsState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="flex min-h-[220px] flex-col items-center justify-center rounded-2xl border border-dashed border-white/15 bg-slate-950/30 p-6 text-center">
      <BarChart3 className="h-10 w-10 text-white/25" />
      <p className="mt-3 font-medium text-white">{title}</p>
      <p className="mt-1 max-w-sm text-sm text-white/45">{description}</p>
    </div>
  );
}

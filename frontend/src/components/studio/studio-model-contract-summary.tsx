import Link from 'next/link';
import { Card, CardContent } from '@/components/ui/card';

export type ModelContract = {
  id?: string;
  name?: string;
  display_name?: string;
  contract_status?: string;
  verified?: boolean;
  verification_gaps?: string[];
  adapter_status?: string;
  is_configured?: boolean;
  test_status?: string | null;
};

const CONTRACT_STATUS_LABELS: Record<string, string> = {
  active: '可用',
  configured: '已配置',
  experimental: '实验中',
  production: '生产可用',
  unknown: '状态未知',
};

const VERIFICATION_GAP_LABELS: Record<string, string> = {
  failure_retry_evidence: '缺少失败重试证据',
  live_canary_job_id: '缺少实模验收任务编号',
  model_contract_not_registered: '尚未登记模型契约',
};

export function contractSummary(model: ModelContract) {
  const verified = model.verified ?? model.test_status === 'success';
  const status = model.contract_status || model.adapter_status || (model.is_configured ? 'configured' : 'unknown');
  return {
    name: model.name || model.display_name || model.id || '未命名模型',
    status: CONTRACT_STATUS_LABELS[status] || status,
    verified,
    gaps: (model.verification_gaps || []).map((gap) => VERIFICATION_GAP_LABELS[gap] || gap),
  };
}

export function StudioModelContractSummary({ models, unavailable }: { models: ModelContract[]; unavailable: boolean }) {
  const verifiedCount = models.filter((model) => model.verified ?? model.test_status === 'success').length;
  const readiness = models.length ? Math.round(verifiedCount / models.length * 100) : 0;

  return (
    <Card className="border-white/10 bg-white/[0.04]" data-testid="studio-model-contracts">
      <CardContent className="space-y-3 p-4">
        <h3 className="text-sm font-semibold text-white">模型就绪度</h3>
        {unavailable ? <div className="text-xs text-amber-100/70">契约目录暂不可用</div> : (
          <>
            <div className={`text-lg font-semibold ${readiness === 100 ? 'text-emerald-300' : 'text-amber-200'}`}>{models.length ? (readiness === 100 ? '良好' : '需检查') : '暂无契约'}</div>
            <div className="h-1.5 overflow-hidden rounded-full bg-white/10"><div className={`h-full ${readiness === 100 ? 'bg-emerald-400' : 'bg-amber-400'}`} style={{ width: `${readiness}%` }} /></div>
            <div className="text-xs text-white/50">{verifiedCount}/{models.length} 模型就绪</div>
            {models.slice(0, 2).map((model) => {
              const summary = contractSummary(model);
              return (
                <div key={model.id || model.name} className="rounded-md border border-white/10 bg-black/15 px-2.5 py-2 text-xs">
                  <div className="truncate text-white/80">{summary.name}</div>
                  <div className={summary.verified ? 'mt-1 text-emerald-200/75' : 'mt-1 text-amber-100/75'}>{summary.status} · {summary.verified ? '已验证' : '未验证'}</div>
                  {summary.gaps.length ? <div className="mt-1 leading-5 text-amber-100/60">{summary.gaps.join('；')}</div> : null}
                </div>
              );
            })}
            <Link href="/production-adapters" className="inline-block text-xs text-violet-300 hover:text-violet-200">查看模型状态 →</Link>
          </>
        )}
      </CardContent>
    </Card>
  );
}

'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import apiClient from '@/lib/api-client';

type ModelContract = {
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

export function StudioModelContracts({ compact = false }: { compact?: boolean }) {
  const [models, setModels] = useState<ModelContract[]>([]);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    let cancelled = false;
    apiClient.getVideoModelContracts()
      .then((payload) => {
        if (cancelled) return;
        const items = Array.isArray(payload) ? payload : Array.isArray(payload?.models) ? payload.models : [];
        setModels(items);
        setUnavailable(false);
      })
      .catch(() => {
        if (!cancelled) setUnavailable(true);
      });
    return () => { cancelled = true; };
  }, []);

  const verifiedCount = models.filter((model) => model.verified ?? model.test_status === 'success').length;
  const readiness = models.length ? Math.round(verifiedCount / models.length * 100) : 0;

  if (compact) {
    return (
      <Card className="border-white/10 bg-white/[0.04]" data-testid="studio-model-contracts">
        <CardContent className="space-y-3 p-4">
          <h3 className="text-sm font-semibold text-white">模型就绪度</h3>
          {unavailable ? <div className="text-xs text-amber-100/70">契约目录暂不可用</div> : (
            <>
              <div className={`text-lg font-semibold ${readiness === 100 ? 'text-emerald-300' : 'text-amber-200'}`}>{models.length ? (readiness === 100 ? '良好' : '需检查') : '暂无契约'}</div>
              <div className="h-1.5 overflow-hidden rounded-full bg-white/10"><div className={`h-full ${readiness === 100 ? 'bg-emerald-400' : 'bg-amber-400'}`} style={{ width: `${readiness}%` }} /></div>
              <div className="text-xs text-white/50">{verifiedCount}/{models.length} 模型就绪</div>
              <Link href="/production-adapters" className="inline-block text-xs text-violet-300 hover:text-violet-200">查看模型状态 →</Link>
            </>
          )}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-white/10 bg-white/[0.04]" data-testid="studio-model-contracts">
      <CardContent className="space-y-2 p-3">
        <h3 className="text-sm font-semibold text-white">视频模型契约</h3>
        {unavailable ? <div className="text-xs text-amber-100/70">契约目录暂不可用</div> : null}
        {!unavailable && !models.length ? <div className="text-xs text-white/45">暂无可用模型契约</div> : null}
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {models.slice(0, 6).map((model) => {
            const verified = model.verified ?? model.test_status === 'success';
            const status = model.contract_status || model.adapter_status || (model.is_configured ? 'configured' : 'unknown');
            return (
              <div key={model.id || model.name} className="min-w-0 rounded-lg border border-white/10 bg-black/20 px-3 py-2">
                <div className="flex min-w-0 items-center justify-between gap-2">
                  <div className="min-w-0 truncate text-sm text-white">{model.name || model.display_name || model.id}</div>
                  <Badge variant="outline" className="shrink-0 border-white/15 text-white/60">
                    {status} · {verified ? '已验证' : '未验证'}
                  </Badge>
                </div>
                {model.verification_gaps?.length ? (
                  <div className="mt-1 break-words text-xs text-amber-100/65">缺口：{model.verification_gaps.join(' · ')}</div>
                ) : null}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

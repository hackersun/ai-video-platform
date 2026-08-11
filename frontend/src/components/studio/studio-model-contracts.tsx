'use client';

import { useEffect, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import apiClient from '@/lib/api-client';
import { contractSummary, StudioModelContractSummary, type ModelContract } from './studio-model-contract-summary';

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

  if (compact) {
    return <StudioModelContractSummary models={models} unavailable={unavailable} />;
  }

  return (
    <Card className="border-white/10 bg-white/[0.04]" data-testid="studio-model-contracts">
      <CardContent className="space-y-2 p-3">
        <h3 className="text-sm font-semibold text-white">视频模型契约</h3>
        {unavailable ? <div className="text-xs text-amber-100/70">契约目录暂不可用</div> : null}
        {!unavailable && !models.length ? <div className="text-xs text-white/45">暂无可用模型契约</div> : null}
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {models.slice(0, 6).map((model) => {
            const summary = contractSummary(model);
            return (
              <div key={model.id || model.name} className="min-w-0 rounded-lg border border-white/10 bg-black/20 px-3 py-2">
                <div className="flex min-w-0 items-center justify-between gap-2">
                  <div className="min-w-0 truncate text-sm text-white">{summary.name}</div>
                  <Badge variant="outline" className="shrink-0 border-white/15 text-white/60">
                    {summary.status} · {summary.verified ? '已验证' : '未验证'}
                  </Badge>
                </div>
                {summary.gaps.length ? (
                  <div className="mt-1 break-words text-xs text-amber-100/65">缺口：{summary.gaps.join('；')}</div>
                ) : null}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

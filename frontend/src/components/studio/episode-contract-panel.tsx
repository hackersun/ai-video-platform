'use client';

import { FileCheck2, LockKeyhole, RefreshCw } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { EpisodeContract } from '@/lib/studio-types';

function shortHash(value?: string) {
  if (!value) return '未锁定';
  return value.length > 16 ? `${value.slice(0, 12)}...${value.slice(-6)}` : value;
}

export function EpisodeContractPanel({
  contract,
  loading,
  onLock,
}: {
  contract?: EpisodeContract | null;
  loading?: boolean;
  onLock?: () => void;
}) {
  const entityCount = contract?.entity_locks?.length || 0;
  const checks = contract?.required_checks || [];

  return (
    <Card data-testid="episode-contract-panel" className="border-white/10 bg-white/5">
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-white">
              <LockKeyhole className="h-4 w-4 text-cyan-300" />
              剧集合约
            </CardTitle>
            <div className="mt-1 text-sm text-white/55">锁定本集使用的风格、实体、声线和检查项。</div>
          </div>
          <Button onClick={onLock} disabled={loading} size="sm" className="w-fit gap-2">
            {contract?.contract_id ? <RefreshCw className="h-4 w-4" /> : <FileCheck2 className="h-4 w-4" />}
            {contract?.contract_id ? '重新锁定剧集合约' : '锁定剧集合约'}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="min-w-0">
          <div className="text-xs text-white/45">Production Bible Hash</div>
          <div className="mt-1 break-all text-sm font-medium text-white">{shortHash(contract?.production_bible_hash)}</div>
        </div>
        <div className="min-w-0">
          <div className="text-xs text-white/45">锁定时间</div>
          <div className="mt-1 break-words text-sm font-medium text-white">{contract?.locked_at || '未锁定'}</div>
        </div>
        <div className="min-w-0">
          <div className="text-xs text-white/45">实体锁</div>
          <div className="mt-1 text-sm font-medium text-white">{entityCount} 个</div>
        </div>
        <div className="min-w-0">
          <div className="text-xs text-white/45">检查项</div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {checks.length ? checks.map((check) => (
              <Badge key={check} variant="outline" className="border-white/15 text-white/65">{check}</Badge>
            )) : <span className="text-sm text-white/50">暂无</span>}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

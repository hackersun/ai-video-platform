'use client';

import { ShieldCheck, TestTube2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { studioModeDescriptions, studioModeLabels, studioModeTone } from '@/lib/studio-mode';
import type { StudioRunMode } from '@/lib/studio-types';

export function StudioModeBanner({
  mode,
  onModeChange,
}: {
  mode: StudioRunMode;
  onModeChange: (mode: StudioRunMode) => void;
}) {
  const Icon = mode === 'production' ? ShieldCheck : TestTube2;
  return (
    <div className={`rounded-lg border px-3 py-2.5 ${studioModeTone(mode)}`} data-testid="studio-mode-banner">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div className="flex min-w-0 items-center gap-2.5">
          <Icon className="h-4 w-4 shrink-0" />
          <div className="min-w-0">
            <div className="text-sm font-medium text-white">{studioModeLabels[mode]}</div>
            <div className="mt-0.5 text-xs leading-5 text-white/65">{studioModeDescriptions[mode]}</div>
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button
            size="sm"
            variant={mode === 'test' ? 'default' : 'outline'}
            className={mode === 'test' ? 'bg-amber-600 hover:bg-amber-700' : 'border-white/20 text-white'}
            onClick={() => onModeChange('test')}
          >
            测试验证
          </Button>
          <Button
            size="sm"
            variant={mode === 'production' ? 'default' : 'outline'}
            className={mode === 'production' ? 'bg-cyan-600 hover:bg-cyan-700' : 'border-white/20 text-white'}
            onClick={() => onModeChange('production')}
          >
            生产出片
          </Button>
        </div>
      </div>
    </div>
  );
}

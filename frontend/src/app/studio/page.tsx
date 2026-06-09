'use client';

import { Suspense } from 'react';
import { MainLayout } from '@/components/layout/main-layout';
import { StudioShell } from '@/components/studio/studio-shell';

export default function StudioPage() {
  return (
    <MainLayout>
      <Suspense fallback={<div className="p-6 text-white/60">正在加载创作工作台…</div>}>
        <StudioShell />
      </Suspense>
    </MainLayout>
  );
}

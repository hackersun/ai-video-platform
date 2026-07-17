'use client';

import { Suspense } from 'react';
import { MainLayout } from '@/components/layout/main-layout';
import { StudioShell } from '@/components/studio/studio-shell';

export default function StudioPage() {
  return (
    <MainLayout wide>
      <Suspense fallback={<div className="p-6 text-white/60">正在加载系列动漫工作室…</div>}>
        <StudioShell />
      </Suspense>
    </MainLayout>
  );
}

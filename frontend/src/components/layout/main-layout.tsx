'use client';

import { useRouter } from 'next/navigation';
import { ReactNode, Suspense } from 'react';
import { StudioReturnDock, StudioTaskContext } from '@/components/studio/studio-return-dock';
import { TopNavigation } from './top-navigation';

interface MainLayoutProps {
  children: ReactNode;
  wide?: boolean;
}

export function MainLayout({ children, wide = false }: MainLayoutProps) {
  return (
    <div className="min-h-screen">
      <TopNavigation />
      <main className={`mx-auto w-full px-4 py-8 pt-24 ${wide ? 'max-w-[1480px] sm:px-8' : 'max-w-7xl sm:px-6'}`}>
        <Suspense fallback={null}><StudioTaskContext /></Suspense>
        {children}
      </main>
      <Suspense fallback={null}><StudioReturnDock /></Suspense>
    </div>
  );
}

export function ExpertToolBanner() {
  const router = useRouter();

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-cyan-400/20 bg-cyan-500/10 p-4 text-sm text-cyan-50 sm:flex-row sm:items-center sm:justify-between">
      <div>这是专业工作台。日常请用小说页「一键生成视频」；这里只做分步精修。</div>
      <button
        type="button"
        onClick={() => router.push('/novels')}
        className="inline-flex h-9 shrink-0 items-center justify-center rounded-md bg-cyan-600 px-3 text-sm font-medium text-white transition-colors hover:bg-cyan-700"
      >
        去小说页
      </button>
    </div>
  );
}

'use client';

import { usePathname, useRouter } from 'next/navigation';
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
  const pathname = usePathname() || '';
  const showBackToStudio = !pathname.startsWith('/studio');

  return (
    <div className="pointer-events-none fixed inset-x-0 top-16 z-30 flex h-8 items-center justify-center border-b border-cyan-400/20 bg-cyan-950/80 px-4 text-xs text-cyan-50 backdrop-blur-sm">
      <div className="pointer-events-auto flex w-full max-w-[1480px] items-center justify-between gap-3">
        <div className="truncate">这是专业工作台。日常请用小说页「一键生成视频」；这里只做分步精修。</div>
        <div className="flex shrink-0 items-center gap-2">
          {showBackToStudio && (
            <button
              type="button"
              onClick={() => router.push('/studio')}
              className="inline-flex h-6 items-center justify-center rounded-md border border-cyan-400/40 px-2.5 font-medium text-cyan-50 transition-colors hover:bg-cyan-800/80"
            >
              回到工作室
            </button>
          )}
          <button
            type="button"
            onClick={() => router.push('/novels')}
            className="inline-flex h-6 items-center justify-center rounded-md bg-cyan-600 px-2.5 font-medium text-white transition-colors hover:bg-cyan-700"
          >
            去小说页
          </button>
        </div>
      </div>
    </div>
  );
}

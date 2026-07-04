'use client';

import { useRouter } from 'next/navigation';
import { ReactNode } from 'react';
import { TopNavigation } from './top-navigation';

interface MainLayoutProps {
  children: ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
  return (
    <div className="min-h-screen">
      <TopNavigation />
      <main className="mx-auto w-full max-w-7xl px-4 py-8 pt-24 sm:px-6">
        {children}
      </main>
    </div>
  );
}

export function ExpertToolBanner() {
  const router = useRouter();

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-cyan-400/20 bg-cyan-500/10 p-4 text-sm text-cyan-50 sm:flex-row sm:items-center sm:justify-between">
      <div>这是专家工具。连续动漫制作建议从工作室统一管控。</div>
      <button
        type="button"
        onClick={() => router.push('/studio')}
        className="inline-flex h-9 shrink-0 items-center justify-center rounded-md bg-cyan-600 px-3 text-sm font-medium text-white transition-colors hover:bg-cyan-700"
      >
        回到工作室
      </button>
    </div>
  );
}

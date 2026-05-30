'use client';

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

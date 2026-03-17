'use client';

import { ReactNode } from 'react';
import { TopNavigation } from './top-navigation';

interface MainLayoutProps {
  children: ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-violet-900/20 to-gray-900">
      <TopNavigation />
      <main className="container mx-auto px-4 py-8 pt-24">
        {children}
      </main>
    </div>
  );
}
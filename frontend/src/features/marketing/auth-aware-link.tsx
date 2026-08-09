'use client';

import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';

const GUEST_START_PATH = '/login?next=%2Fquick-start';

export function StartCreatingLink({ className }: { className: string }) {
  const { isAuthenticated } = useAuth();
  return (
    <Link className={className} href={isAuthenticated ? '/quick-start' : GUEST_START_PATH}>
      开始创作
      <span aria-hidden="true">→</span>
    </Link>
  );
}

export function AccountEntryLink({ className }: { className: string }) {
  const { isAuthenticated } = useAuth();
  return (
    <Link className={className} href={isAuthenticated ? '/dashboard' : '/login'}>
      {isAuthenticated ? '进入工作台' : '登录'}
    </Link>
  );
}

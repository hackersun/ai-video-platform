'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { CheckCircle, Loader2, XCircle } from 'lucide-react';
import { authApiBase, buildSessionRequest } from '@/lib/auth-session';

function VerifyEmailContent() {
  const router = useRouter();
  const params = useSearchParams();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('正在验证邮箱，请稍候');

  useEffect(() => {
    const token = params.get('token');
    if (!token) {
      setStatus('error');
      setMessage('验证链接缺少必要信息，请重新打开邮件中的链接');
      return;
    }
    void fetch(`${authApiBase}/auth/verify-email`, buildSessionRequest({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    })).then(async response => {
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.success) throw new Error(payload.detail || '邮箱验证失败');
      setStatus('success');
      setMessage('邮箱验证成功，即将进入工作台');
      router.replace('/dashboard');
    }).catch(error => {
      setStatus('error');
      setMessage(error instanceof Error ? error.message : '邮箱验证失败，请重新申请验证邮件');
    });
  }, [params, router]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-950 px-4 text-white">
      <section className="w-full max-w-md rounded-xl border border-white/10 bg-slate-900 p-8 text-center shadow-2xl">
        {status === 'loading' && <Loader2 className="mx-auto h-10 w-10 animate-spin text-cyan-300" />}
        {status === 'success' && <CheckCircle className="mx-auto h-10 w-10 text-emerald-300" />}
        {status === 'error' && <XCircle className="mx-auto h-10 w-10 text-red-300" />}
        <h1 className="mt-5 text-2xl font-semibold">验证邮箱</h1>
        <p className="mt-3 text-sm leading-6 text-slate-300">{message}</p>
        {status === 'error' && (
          <Link className="mt-6 inline-flex text-sm font-medium text-cyan-200 hover:text-cyan-100" href="/login">
            返回登录
          </Link>
        )}
      </section>
    </main>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={
      <main className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-300">
        正在加载邮箱验证页面…
      </main>
    }>
      <VerifyEmailContent />
    </Suspense>
  );
}

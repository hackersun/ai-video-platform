'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { ArrowLeft, CheckCircle, Loader2, Mail, XCircle } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [resetToken, setResetToken] = useState('');

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    setMessage('');
    setResetToken('');

    if (!email.trim()) {
      setError('请输入注册邮箱');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim() }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || data.message || '提交失败');
      }
      setMessage(data.message || '如果邮箱存在，系统已生成密码重置说明');
      if (data.reset_token) {
        setResetToken(data.reset_token);
      }
    } catch (err: any) {
      setError(err?.message || '提交失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-violet-900/20 to-gray-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <Card className="bg-white/5 border-white/10 backdrop-blur">
          <CardHeader>
            <CardTitle className="text-white text-center text-xl">找回密码</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm text-white/80 mb-2">注册邮箱</label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                  <Input
                    type="email"
                    placeholder="请输入注册邮箱"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    className="pl-10 bg-white/5 border-white/10 text-white placeholder:text-white/40"
                  />
                </div>
              </div>

              {error && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                  <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                  <span className="text-red-400 text-sm">{error}</span>
                </div>
              )}

              {message && (
                <div className="space-y-3 rounded-lg bg-green-500/10 border border-green-500/20 p-3">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0" />
                    <span className="text-green-300 text-sm">{message}</span>
                  </div>
                  {resetToken && (
                    <Link href={`/reset-password?token=${encodeURIComponent(resetToken)}`} className="inline-flex text-sm text-violet-300 hover:text-violet-200">
                      使用 DEV_MODE 重置令牌
                    </Link>
                  )}
                </div>
              )}

              <Button type="submit" disabled={loading} className="w-full bg-violet-600 hover:bg-violet-700 h-11">
                {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Mail className="w-4 h-4 mr-2" />}
                发送重置说明
              </Button>
            </form>

            <div className="mt-6 text-center">
              <Link href="/login" className="inline-flex items-center gap-2 text-white/50 hover:text-white text-sm">
                <ArrowLeft className="w-4 h-4" />
                返回登录
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

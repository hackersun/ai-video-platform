'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { 
  Sparkles,
  User,
  Lock,
  Loader2,
  CheckCircle,
  XCircle,
  ArrowRight
} from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    // 验证
    if (!username || !password) {
      setError('请填写用户名和密码');
      return;
    }

    setIsLoading(true);

    try {
      const res = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username,
          password,
        }),
      });

      const data = await res.json();

      if (data.success) {
        setSuccess('登录成功！正在跳转...');
        // 保存token到localStorage
        if (data.access_token) {
          localStorage.setItem('auth_token', data.access_token);
          localStorage.setItem('user', JSON.stringify(data.user));
        }
        // 2秒后跳转到控制台
        setTimeout(() => {
          router.push('/dashboard');
        }, 2000);
      } else {
        setError(data.message || '登录失败');
      }
    } catch (err) {
      setError('网络错误，请稍后重试');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-violet-900/20 to-gray-900 flex items-center justify-center p-4">
      {/* 背景装饰 */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-violet-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl" />
      </div>

      <div className="w-full max-w-md relative z-10">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-4">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center">
              <Sparkles className="w-6 h-6 text-white" />
            </div>
            <span className="text-2xl font-bold text-white">AI视频平台</span>
          </div>
          <p className="text-white/60">欢迎回来，继续创作之旅</p>
        </div>

        <Card className="bg-white/5 border-white/10 backdrop-blur">
          <CardHeader>
            <CardTitle className="text-white text-center text-xl">用户登录</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* 用户名 */}
              <div>
                <label className="block text-sm text-white/80 mb-2">用户名</label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                  <Input
                    type="text"
                    placeholder="请输入用户名"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="pl-10 bg-white/5 border-white/10 text-white placeholder:text-white/40"
                  />
                </div>
              </div>

              {/* 密码 */}
              <div>
                <label className="block text-sm text-white/80 mb-2">密码</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                  <Input
                    type="password"
                    placeholder="请输入密码"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="pl-10 bg-white/5 border-white/10 text-white placeholder:text-white/40"
                  />
                </div>
              </div>

              {/* 错误提示 */}
              {error && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                  <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                  <span className="text-red-400 text-sm">{error}</span>
                </div>
              )}

              {/* 成功提示 */}
              {success && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                  <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0" />
                  <span className="text-green-400 text-sm">{success}</span>
                </div>
              )}

              {/* 提交按钮 */}
              <Button
                type="submit"
                disabled={isLoading}
                className="w-full bg-violet-600 hover:bg-violet-700 h-11"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    登录中...
                  </>
                ) : (
                  <>
                    登录
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </>
                )}
              </Button>
            </form>

            {/* 注册链接 */}
            <div className="mt-6 text-center">
              <p className="text-white/60 text-sm">
                还没有账号？{' '}
                <Link href="/register" className="text-violet-400 hover:text-violet-300">
                  立即注册
                </Link>
              </p>
            </div>
          </CardContent>
        </Card>

        {/* 返回首页 */}
        <div className="mt-4 text-center">
          <Link href="/" className="text-white/40 hover:text-white/60 text-sm">
            ← 返回首页
          </Link>
        </div>
      </div>
    </div>
  );
}

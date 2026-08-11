'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  ArrowRight,
  BadgeCheck,
  CheckCircle,
  Film,
  Loader2,
  Lock,
  ShieldCheck,
  Sparkles,
  User,
  Workflow,
  XCircle,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { safeLoginDestination } from '@/features/auth/navigation';
import { PasswordInput } from '@/features/auth/password-input';

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!username || !password) {
      setError('请填写用户名和密码');
      return;
    }

    setIsLoading(true);

    try {
      const result = await login(username, password);

      if (result.success) {
        setSuccess('登录成功，正在进入工作台');
        router.replace(safeLoginDestination(window.location.search));
      } else {
        setError(result.detail || result.message || '登录失败');
      }
    } catch (err: any) {
      setError(err?.message || '网络错误，请稍后重试');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main
      data-testid="login-page"
      className="relative min-h-screen overflow-hidden bg-background text-foreground"
    >
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(hsl(var(--border)/0.38)_1px,transparent_1px),linear-gradient(90deg,hsl(var(--border)/0.38)_1px,transparent_1px)] bg-[size:42px_42px]" />
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(115deg,hsl(var(--background)/0.56),hsl(var(--background)/0.9)_48%,hsl(var(--background))),radial-gradient(circle_at_20%_12%,rgba(20,184,166,0.15),transparent_30%),radial-gradient(circle_at_82%_18%,rgba(245,158,11,0.08),transparent_24%)]" />

      <div className="relative mx-auto grid min-h-screen w-full max-w-7xl grid-cols-1 lg:grid-cols-[1.05fr_0.95fr]">
        <section className="hidden border-r border-border px-10 py-8 lg:flex lg:flex-col lg:justify-between">
          <Link href="/" className="inline-flex w-fit items-center gap-3" aria-label="AI视频平台">
            <span className="flex h-11 w-11 items-center justify-center rounded-lg border border-border bg-card/80">
              <Sparkles className="h-5 w-5 text-cyan-200" aria-hidden="true" />
            </span>
            <span className="text-xl font-semibold text-foreground">AI视频平台</span>
          </Link>

          <div className="max-w-2xl">
            <div className="mb-4 inline-flex items-center gap-2 rounded-md border border-cyan-300/20 bg-cyan-300/10 px-3 py-2 text-sm font-medium text-cyan-100">
              <ShieldCheck className="h-4 w-4" aria-hidden="true" />
              AI 动漫制作工作台
            </div>
            <h1 className="text-4xl font-semibold leading-tight text-foreground">
              从小说进入角色、分镜与视频生产
            </h1>
            <p className="mt-4 max-w-xl text-base leading-7 text-muted-foreground">
              登录后继续管理小说章节、角色资产、提示词技能与生产任务，让创作流程保持一致、可核对、可追踪。
            </p>

            <div className="mt-8 grid grid-cols-3 gap-3">
              <div className="rounded-lg border border-border bg-card/80 p-4">
                <User className="mb-3 h-5 w-5 text-cyan-200" aria-hidden="true" />
                <div className="text-sm font-semibold text-card-foreground">角色资产</div>
                <div className="mt-1 text-xs leading-5 text-muted-foreground">人物设定与一致性</div>
              </div>
              <div className="rounded-lg border border-border bg-card/80 p-4">
                <Workflow className="mb-3 h-5 w-5 text-amber-200" aria-hidden="true" />
                <div className="text-sm font-semibold text-card-foreground">剧本分镜</div>
                <div className="mt-1 text-xs leading-5 text-muted-foreground">章节改编与镜头拆解</div>
              </div>
              <div className="rounded-lg border border-border bg-card/80 p-4">
                <Film className="mb-3 h-5 w-5 text-violet-200" aria-hidden="true" />
                <div className="text-sm font-semibold text-card-foreground">视频生成</div>
                <div className="mt-1 text-xs leading-5 text-muted-foreground">镜头预览与任务跟踪</div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-2 text-sm text-muted-foreground">
            <BadgeCheck className="mt-0.5 h-4 w-4 text-emerald-300" aria-hidden="true" />
            <span>登录状态会沿用现有工作台权限与任务上下文</span>
            <BadgeCheck className="mt-0.5 h-4 w-4 text-emerald-300" aria-hidden="true" />
            <span>进入后可继续使用 AI 辅助抽取、剧本编写与分镜生产</span>
          </div>
        </section>

        <section className="flex min-h-screen items-center justify-center px-4 py-8 sm:px-6 lg:px-10">
          <div className="w-full max-w-md space-y-5">
            <div className="lg:hidden">
              <Link href="/" className="mb-5 inline-flex items-center gap-3" aria-label="AI视频平台">
                <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-card/80">
                  <Sparkles className="h-5 w-5 text-cyan-200" aria-hidden="true" />
                </span>
                <span className="text-lg font-semibold text-foreground">AI视频平台</span>
              </Link>
              <div className="inline-flex items-center gap-2 rounded-md border border-cyan-300/20 bg-cyan-300/10 px-3 py-2 text-sm font-medium text-cyan-100">
                <ShieldCheck className="h-4 w-4" aria-hidden="true" />
                AI 动漫制作工作台
              </div>
            </div>

            <div
              data-testid="login-form-panel"
              className="bg-card text-card-foreground rounded-lg border border-border p-5 shadow-2xl shadow-black/15 backdrop-blur sm:p-6"
            >
              <div className="mb-6">
                <div className="mb-3 inline-flex items-center gap-2 rounded-md border border-border bg-muted px-3 py-1.5 text-xs font-medium text-muted-foreground">
                  <Lock className="h-3.5 w-3.5 text-emerald-300" aria-hidden="true" />
                  安全登录
                </div>
                <h2 className="text-2xl font-semibold text-card-foreground">用户登录</h2>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  继续处理小说、角色资产与视频生产任务。
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label htmlFor="username" className="mb-2 block text-sm font-medium text-foreground">
                    用户名
                  </label>
                  <div className="relative">
                    <User className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                    <Input
                      id="username"
                      type="text"
                      placeholder="请输入用户名"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      autoComplete="username"
                      className="h-12 border-input bg-background pl-10 text-foreground placeholder:text-muted-foreground focus-visible:ring-cyan-300"
                    />
                  </div>
                </div>

                <PasswordInput value={password} onChange={setPassword} />

                {error && (
                  <div
                    role="alert"
                    className="flex items-start gap-2 rounded-lg border border-red-400/20 bg-red-500/10 p-3"
                  >
                    <XCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-300" />
                    <span className="text-sm leading-5 text-red-200">{error}</span>
                  </div>
                )}

                {success && (
                  <div
                    role="status"
                    className="flex items-start gap-2 rounded-lg border border-emerald-400/20 bg-emerald-500/10 p-3"
                  >
                    <CheckCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-emerald-300" />
                    <span className="text-sm leading-5 text-emerald-100">{success}</span>
                  </div>
                )}

                <Button
                  type="submit"
                  disabled={isLoading}
                  className="h-12 w-full bg-cyan-400 text-slate-950 shadow-lg shadow-cyan-950/30 hover:bg-cyan-300"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      正在登录...
                    </>
                  ) : (
                    <>
                      登录
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </>
                  )}
                </Button>
              </form>

              <div className="mt-6 flex flex-col gap-3 border-t border-border pt-5 text-center text-sm text-muted-foreground">
                <p>
                  还没有账号？{' '}
                  <Link href="/register" className="font-medium text-cyan-200 hover:text-cyan-100">
                    立即注册
                  </Link>
                </p>
                <Link href="/forgot-password" className="font-medium text-slate-300 hover:text-white">
                  忘记密码？
                </Link>
              </div>
            </div>

            <div className="text-center">
              <Link
                href="/"
                className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground"
              >
                <ArrowRight className="h-4 w-4 rotate-180" aria-hidden="true" />
                返回首页
              </Link>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

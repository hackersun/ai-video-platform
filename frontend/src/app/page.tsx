import Link from 'next/link';
import { CheckCircle, Film, Palette, Sparkles, Workflow, Zap } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { AccountEntryLink, StartCreatingLink } from '@/features/marketing/auth-aware-link';

const features = [
  { icon: Sparkles, step: '01', title: '导入小说', description: '粘贴章节或完整小说，先整理故事主线与人物关系。' },
  { icon: Palette, step: '02', title: '锁定世界观', description: '统一角色、场景、道具、画面风格与声线设定。' },
  { icon: Workflow, step: '03', title: '生成剧本分镜', description: '把章节改编为可核对、可修改、可追踪的镜头计划。' },
  { icon: Film, step: '04', title: '完成视频', description: '生成配音、字幕和镜头视频，再进入成片合成。' },
];

const highlights = ['完整小说连续改编', '角色与声线一致性', '先用短片验证风格', '保留高级模型配置'];

const primaryLink = 'inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-violet-500 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-950/30 transition hover:bg-violet-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-300';
const secondaryLink = 'inline-flex min-h-11 items-center justify-center rounded-lg border border-white/15 bg-white/[0.04] px-5 py-3 text-sm font-semibold text-slate-100 transition hover:border-white/25 hover:bg-white/[0.08] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-300';

export default function HomePage() {
  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-white focus:px-4 focus:py-2 focus:text-slate-950">
        跳到主要内容
      </a>
      <header className="relative z-20 border-b border-white/10 bg-slate-950/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link href="/" className="inline-flex items-center gap-3 font-semibold" aria-label="AI视频平台首页">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-500 text-white"><Sparkles className="h-5 w-5" aria-hidden="true" /></span>
            <span>AI视频平台</span>
          </Link>
          <nav className="hidden items-center gap-7 text-sm text-slate-300 md:flex" aria-label="首页导航">
            <a href="#workflow" className="hover:text-white">制作流程</a>
            <a href="#capabilities" className="hover:text-white">核心能力</a>
            <a href="#start" className="hover:text-white">开始使用</a>
          </nav>
          <AccountEntryLink className={secondaryLink} />
        </div>
      </header>

      <section id="main-content" className="relative overflow-hidden px-4 pb-24 pt-20 sm:px-6 sm:pt-28">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(124,58,237,0.24),transparent_38%),radial-gradient(circle_at_85%_35%,rgba(37,99,235,0.14),transparent_28%)]" />
        <div className="relative z-10 mx-auto max-w-5xl text-center">
          <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-violet-300/20 bg-violet-400/10 px-4 py-2 text-sm text-violet-200">
            <Zap className="h-4 w-4" aria-hidden="true" />
            小说到连续动漫的一体化生产工作台
          </div>
          <h1 className="text-4xl font-bold leading-tight tracking-tight sm:text-6xl lg:text-7xl">
            把完整小说，做成
            <span className="block bg-gradient-to-r from-violet-300 via-fuchsia-300 to-blue-300 bg-clip-text text-transparent">人物一致的连续动漫</span>
          </h1>
          <p className="mx-auto mt-7 max-w-2xl text-base leading-8 text-slate-300 sm:text-lg">
            从故事、角色和世界观开始，逐步完成剧本、分镜、参考资产、配音、字幕与视频。每一步都能查看、修改和继续生产。
          </p>
          <div className="mt-9 flex flex-col items-stretch justify-center gap-3 sm:flex-row sm:items-center">
            <StartCreatingLink className={primaryLink} />
            <a href="#workflow" className={secondaryLink}>查看制作流程</a>
          </div>
          <ul className="mt-10 flex flex-wrap justify-center gap-x-6 gap-y-3 text-sm text-slate-400" aria-label="平台能力摘要">
            {highlights.map(item => <li key={item} className="flex items-center gap-2"><CheckCircle className="h-4 w-4 text-emerald-400" aria-hidden="true" />{item}</li>)}
          </ul>
        </div>
      </section>

      <section id="workflow" className="border-y border-white/10 bg-white/[0.025] px-4 py-20 sm:px-6">
        <div className="mx-auto max-w-6xl">
          <div className="mb-12 max-w-2xl">
            <p className="text-sm font-semibold text-violet-300">标准化制作流程</p>
            <h2 className="mt-3 text-3xl font-bold sm:text-4xl">从第一章到第一集，步骤清楚</h2>
            <p className="mt-4 leading-7 text-slate-400">先完成必要信息，再进入下一环节；遇到缺口时会直接说明原因和处理动作。</p>
          </div>
          <div id="capabilities" className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {features.map(feature => (
              <Card key={feature.title} className="group border-white/10 bg-slate-900/75 p-6 transition hover:-translate-y-1 hover:border-violet-400/30">
                <div className="flex items-center justify-between"><span className="text-sm font-semibold text-slate-500">{feature.step}</span><feature.icon className="h-5 w-5 text-violet-300" aria-hidden="true" /></div>
                <h3 className="mt-8 text-lg font-semibold">{feature.title}</h3>
                <p className="mt-3 text-sm leading-6 text-slate-400">{feature.description}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section id="start" className="px-4 py-20 sm:px-6">
        <div className="mx-auto grid max-w-6xl items-center gap-8 rounded-2xl border border-violet-400/20 bg-gradient-to-br from-violet-500/15 to-blue-500/10 p-7 sm:p-10 md:grid-cols-[1fr_auto]">
          <div><p className="text-sm font-semibold text-violet-200">建议从一章开始</p><h2 className="mt-2 text-3xl font-bold">先验证人物、画风和节奏，再扩展连续章节</h2><p className="mt-4 max-w-2xl leading-7 text-slate-300">向导会保留已经确认的角色和视觉参考，后续章节继续沿用，减少重复配置。</p></div>
          <StartCreatingLink className={primaryLink} />
        </div>
      </section>

      <footer className="border-t border-white/10 px-4 py-8 text-sm text-slate-500 sm:px-6">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><span>© {new Date().getFullYear()} AI视频平台</span><span>小说 · 资产 · 剧本 · 分镜 · 视频</span></div>
      </footer>
    </main>
  );
}

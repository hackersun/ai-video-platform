import Link from 'next/link';
import { LEGAL_DRAFT_NOTICE, TERMS_VERSION, type LegalSection } from '@/features/legal/legal-texts';

export function LegalDocument({ title, sections }: { title: string; sections: LegalSection[] }) {
  return (
    <div className="min-h-screen bg-gray-950 px-4 py-10 text-white">
      <article className="mx-auto max-w-3xl space-y-6">
        <header className="space-y-2">
          <h1 className="text-2xl font-bold">{title}</h1>
          <p data-testid="legal-draft-notice" className="inline-block rounded bg-amber-500/15 px-2 py-1 text-sm text-amber-200">
            「{LEGAL_DRAFT_NOTICE}」 · 版本 {TERMS_VERSION}
          </p>
        </header>
        {sections.map((section) => (
          <section key={section.heading} className="space-y-2">
            <h2 className="text-lg font-semibold">{section.heading}</h2>
            {section.body.map((line) => <p key={line} className="text-sm leading-6 text-white/75">{line}</p>)}
          </section>
        ))}
        <footer className="flex gap-4 border-t border-white/10 pt-4 text-sm">
          <Link href="/register" className="text-violet-400 hover:text-violet-300">返回注册</Link>
          <Link href="/settings" className="text-violet-400 hover:text-violet-300">返回设置</Link>
        </footer>
      </article>
    </div>
  );
}

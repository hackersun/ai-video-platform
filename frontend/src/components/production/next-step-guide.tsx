'use client';

import Link from 'next/link';
import { ArrowRight, CheckCircle, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

type NextStepGuideProps = {
  title?: string;
  current: string;
  next: string;
  reason: string;
  href: string;
  actionLabel: string;
  checklist?: string[];
};

export function NextStepGuide({
  title = 'AI 下一步建议',
  current,
  next,
  reason,
  href,
  actionLabel,
  checklist = [],
}: NextStepGuideProps) {
  return (
    <Card className="border-cyan-400/20 bg-cyan-500/10">
      <CardContent className="space-y-4 p-5">
        <div className="flex items-center gap-2 text-sm font-medium text-cyan-100">
          <Sparkles className="h-4 w-4 text-cyan-300" />
          {title}
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-lg border border-white/10 bg-white/5 p-3">
            <div className="text-xs text-white/45">当前状态</div>
            <div className="mt-1 text-sm text-white">{current}</div>
          </div>
          <div className="rounded-lg border border-white/10 bg-white/5 p-3">
            <div className="text-xs text-white/45">推荐下一步</div>
            <div className="mt-1 text-sm text-white">{next}</div>
          </div>
          <div className="rounded-lg border border-white/10 bg-white/5 p-3">
            <div className="text-xs text-white/45">为什么重要</div>
            <div className="mt-1 text-sm text-white">{reason}</div>
          </div>
        </div>
        {checklist.length > 0 && (
          <div className="grid gap-2 sm:grid-cols-2">
            {checklist.map((item) => (
              <div key={item} className="flex items-center gap-2 text-sm text-cyan-50/80">
                <CheckCircle className="h-4 w-4 text-emerald-300" />
                {item}
              </div>
            ))}
          </div>
        )}
        <Button asChild className="bg-cyan-600 hover:bg-cyan-700">
          <Link href={href}>
            {actionLabel}
            <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}

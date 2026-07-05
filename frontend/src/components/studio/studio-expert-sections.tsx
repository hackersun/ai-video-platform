'use client';

import type { ReactNode } from 'react';
import { Boxes, ClipboardCheck, Film, Settings2 } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export function StudioExpertSections({
  setup,
  production,
  review,
  operations,
}: {
  setup: ReactNode;
  production: ReactNode;
  review: ReactNode;
  operations: ReactNode;
}) {
  return (
    <Tabs defaultValue="production" className="space-y-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">高级工作区</h2>
          <p className="mt-1 text-sm leading-6 text-white/50">按设定、生产、复审和操作记录拆分专家工具。</p>
        </div>
        <TabsList className="h-auto w-full flex-wrap justify-start rounded-lg border border-white/10 bg-white/[0.05] sm:w-auto">
          <TabsTrigger value="setup" className="gap-1.5">
            <Boxes className="h-4 w-4" aria-hidden />
            设定
          </TabsTrigger>
          <TabsTrigger value="production" className="gap-1.5">
            <Film className="h-4 w-4" aria-hidden />
            生产
          </TabsTrigger>
          <TabsTrigger value="review" className="gap-1.5">
            <ClipboardCheck className="h-4 w-4" aria-hidden />
            复审
          </TabsTrigger>
          <TabsTrigger value="operations" className="gap-1.5">
            <Settings2 className="h-4 w-4" aria-hidden />
            操作
          </TabsTrigger>
        </TabsList>
      </div>

      <TabsContent value="setup" className="space-y-5">
        {setup}
      </TabsContent>
      <TabsContent value="production" className="space-y-5">
        {production}
      </TabsContent>
      <TabsContent value="review" className="space-y-5">
        {review}
      </TabsContent>
      <TabsContent value="operations" className="space-y-5">
        {operations}
      </TabsContent>
    </Tabs>
  );
}

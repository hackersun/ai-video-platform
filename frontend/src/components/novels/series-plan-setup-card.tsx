'use client';

import { ListChecks, Loader2, Sparkles } from 'lucide-react';

import {
  ImageStyleTemplatePicker,
  type ImageStyleTemplate,
} from '@/components/media/image-style-template-picker';
import { Button } from '@/components/ui/button';

export function SeriesPlanSetupCard({
  templates,
  style,
  onStyleChange,
  onGenerate,
  generating,
  toMediaUrl,
}: {
  templates: ImageStyleTemplate[];
  style: string;
  onStyleChange: (style: string) => void;
  onGenerate: () => void;
  generating: boolean;
  toMediaUrl: (url?: string) => string;
}) {
  return (
    <div className="space-y-4 rounded-lg border border-dashed border-white/15 bg-white/5 p-6">
      <div className="text-center">
        <ListChecks className="mx-auto mb-3 h-10 w-10 text-blue-300" />
        <div className="font-medium text-white">还没有整书生产计划</div>
        <p className="mx-auto mt-2 max-w-2xl text-sm text-white/50">
          先锁定全书画面风格，再生成章节覆盖、剧情钩子、角色场景道具和后续制作计划。
        </p>
      </div>
      <ImageStyleTemplatePicker
        templates={templates}
        value={style}
        onChange={onStyleChange}
        toMediaUrl={toMediaUrl}
        recommendedFor="shot"
        title="整书统一画面风格"
        layout="inline"
      />
      <div className="text-center">
        <Button className="bg-violet-600 hover:bg-violet-700" onClick={onGenerate} disabled={generating}>
          {generating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
          AI 生成多集计划
        </Button>
      </div>
    </div>
  );
}

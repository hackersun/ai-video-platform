'use client';

import { BookOpen, Clapperboard, FileText, ScrollText } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { StudioSnapshot } from '@/lib/studio-types';

function ContextRow({ icon: Icon, label, value, detail }: any) {
  return (
    <div className="rounded-lg border border-white/10 bg-black/20 p-3">
      <div className="flex items-center gap-2 text-xs text-white/45">
        <Icon className="h-4 w-4" />
        {label}
      </div>
      <div className="mt-1 truncate text-sm font-medium text-white">{value || '未绑定'}</div>
      {detail && <div className="mt-1 truncate text-xs text-white/45">{detail}</div>}
    </div>
  );
}

export function StudioContextPanel({ snapshot }: { snapshot: StudioSnapshot | null }) {
  const context = snapshot?.story_context || {};
  const bible = snapshot?.story_bible || {};
  return (
    <Card className="border-white/10 bg-white/5">
      <CardHeader className="pb-3">
        <CardTitle className="text-white">项目上下文</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <ContextRow icon={BookOpen} label="作品" value={context.novel?.title} detail={context.novel?.genre} />
        <ContextRow
          icon={ScrollText}
          label="章节"
          value={context.chapter?.title}
          detail={context.chapter?.chapter_number ? `第 ${context.chapter.chapter_number} 章` : ''}
        />
        <ContextRow icon={FileText} label="剧本" value={context.script?.title} detail={context.script?.status} />
        <ContextRow
          icon={Clapperboard}
          label="Story Bible"
          value={bible.title}
          detail={bible.id ? `角色 ${bible.character_rule_count || 0} · 场景 ${bible.scene_rule_count || 0} · 道具 ${bible.prop_rule_count || 0}` : ''}
        />
      </CardContent>
    </Card>
  );
}

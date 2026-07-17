'use client';

import { BookMarked, CheckCircle2, Mic2, Palette, Sparkles } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { StudioSnapshot } from '@/lib/studio-types';

type EntitySectionKey = 'characters' | 'scenes' | 'props' | 'events';

const ENTITY_SECTIONS: Array<{ key: EntitySectionKey; label: string }> = [
  { key: 'characters', label: '角色' },
  { key: 'scenes', label: '场景' },
  { key: 'props', label: '道具' },
  { key: 'events', label: '事件' },
];

function textValue(value: unknown, fallback = '未设置') {
  if (Array.isArray(value)) return value.filter(Boolean).join(' / ') || fallback;
  if (typeof value === 'string') return value.trim() || fallback;
  if (value && typeof value === 'object') return Object.values(value).filter(Boolean).slice(0, 3).join(' / ') || fallback;
  return fallback;
}

function entityIdOf(item: Record<string, any>) {
  return String(item.entity_id || item.id || '');
}

function EntityRow({
  item,
  onApprove,
}: {
  item: Record<string, any>;
  onApprove?: (entityId: string) => void;
}) {
  const entityId = entityIdOf(item);
  const approved = Boolean(item.approved || item.is_approved);
  return (
    <div className="flex min-w-0 items-start justify-between gap-3 border-t border-white/10 py-3 first:border-t-0 first:pt-0">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <div className="break-words text-sm font-medium text-white">{item.name || item.canonical_name || '未命名实体'}</div>
          <Badge variant="outline" className={approved ? 'border-emerald-300/30 text-emerald-100' : 'border-amber-300/30 text-amber-100'}>
            {approved ? '已确认' : '待确认'}
          </Badge>
        </div>
        <div className="mt-1 line-clamp-2 break-words text-xs leading-5 text-white/50">
          {item.description || textValue(item.visual_dna || item.voice || item.asset_count, '缺少描述')}
        </div>
        {item.evidence ? (
          <div className="mt-1 break-words text-xs leading-5 text-cyan-100/70">证据：{textValue(item.evidence)}</div>
        ) : null}
      </div>
      <Button
        size="sm"
        variant="outline"
        className="h-8 shrink-0 border-white/15 px-3 text-xs text-white"
        disabled={!entityId || approved}
        onClick={() => entityId && onApprove?.(entityId)}
      >
        确认
      </Button>
    </div>
  );
}

export function ProductionBiblePanel({
  snapshot,
  onApproveEntity,
}: {
  snapshot: StudioSnapshot | null;
  onApproveEntity?: (entityId: string) => void;
}) {
  const bible = snapshot?.production_bible_summary;
  const style = bible?.style || {};
  const voices = bible?.voices || [];
  const readiness = bible?.readiness_score ?? 0;

  return (
    <Card data-testid="production-bible-panel" className="border-white/10 bg-white/5">
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-white">
              <BookMarked className="h-4 w-4 text-cyan-300" />
              Production Bible
            </CardTitle>
            <div className="mt-1 text-sm text-white/55">统一管控风格、人物、场景、道具、事件和声线。</div>
          </div>
          <Badge variant="outline" className="w-fit border-cyan-300/30 text-cyan-100">
            连续性准备度 {readiness}%
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
        <section className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-medium text-white">
            <Palette className="h-4 w-4 text-cyan-300" />
            风格
          </div>
          <div className="mt-3 space-y-2 text-sm text-white/60">
            <div className="break-words">视觉：{textValue(style.visual_style || style.style || style.title)}</div>
            <div className="break-words">世界观：{textValue(style.worldview)}</div>
            <div className="break-words">负面约束：{textValue(style.negative_prompt)}</div>
          </div>
        </section>

        {ENTITY_SECTIONS.map((section) => {
          const items = bible?.[section.key] || [];
          return (
            <section key={section.key} className="min-w-0">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-sm font-medium text-white">
                  <Sparkles className="h-4 w-4 text-cyan-300" />
                  {section.label}
                </div>
                <Badge variant="outline" className="border-white/15 text-white/60">{items.length}</Badge>
              </div>
              <div className="mt-3 space-y-2">
                {items.length ? (
                  items.slice(0, 4).map((item) => (
                    <EntityRow key={`${section.key}-${entityIdOf(item) || item.name}`} item={item} onApprove={onApproveEntity} />
                  ))
                ) : (
                  <div className="border-t border-white/10 py-3 text-sm text-white/45">暂无条目</div>
                )}
              </div>
            </section>
          );
        })}

        <section className="min-w-0">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-sm font-medium text-white">
              <Mic2 className="h-4 w-4 text-cyan-300" />
              声线
            </div>
            <Badge variant="outline" className="border-white/15 text-white/60">{voices.length}</Badge>
          </div>
          <div className="mt-3 space-y-2">
            {voices.length ? (
              voices.slice(0, 5).map((voice, index) => (
                <div key={`${voice.entity_id || voice.character_name || index}`} className="border-t border-white/10 py-3 first:border-t-0 first:pt-0">
                  <div className="break-words text-sm font-medium text-white">
                    {voice.character_name || voice.name || voice.entity_id || `声线 ${index + 1}`}
                  </div>
                  <div className="mt-1 break-words text-xs text-white/50">{textValue(voice.voice || voice.profile || voice.source)}</div>
                </div>
              ))
            ) : (
              <div className="border-t border-white/10 py-3 text-sm text-white/45">暂无条目</div>
            )}
          </div>
        </section>
      </CardContent>
    </Card>
  );
}

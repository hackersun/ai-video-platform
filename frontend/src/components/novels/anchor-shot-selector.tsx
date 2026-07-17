'use client';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { AnchorShotRecommendation } from '@/lib/api-client';

const DIMENSION_LABELS: Record<string, string> = {
  narrative_truth: '剧情事件', character_visual: '人物角色', scene_prop_state: '场景道具',
  style_cinematography: '动漫风格', voice_dialogue: '配音对白', delivery_integrity: '成片交付',
};

export function AnchorShotSelector({ recommendations, selected, onChange, onGenerate, busy }: {
  recommendations: AnchorShotRecommendation[];
  selected: string[];
  onChange: (ids: string[]) => void;
  onGenerate: () => void;
  busy?: boolean;
}) {
  const toggle = (shotId: string) => onChange(selected.includes(shotId)
    ? selected.filter((id) => id !== shotId)
    : [...selected, shotId]);
  return (
    <div className="space-y-3" data-testid="anchor-shot-selector">
      <div className="grid gap-2 md:grid-cols-2">
        {recommendations.map((shot) => (
          <label key={shot.shot_id} className="flex cursor-pointer gap-3 rounded-lg border border-white/10 bg-black/15 p-3">
            <input aria-label={`选择第${shot.episode_number}章镜头`} type="checkbox" checked={selected.includes(shot.shot_id)} onChange={() => toggle(shot.shot_id)} />
            <span className="min-w-0">
              <span className="text-sm font-medium text-white">第 {shot.episode_number} 章 · 镜头 {shot.shot_number}</span>
              <span className="mt-2 flex flex-wrap gap-1">
                {shot.dimensions.map((dimension) => <Badge key={dimension} variant="outline" className="border-white/20 text-white/60">{DIMENSION_LABELS[dimension] || dimension}</Badge>)}
              </span>
            </span>
          </label>
        ))}
      </div>
      <Button onClick={onGenerate} disabled={busy || selected.length === 0} className="bg-violet-600 hover:bg-violet-700">
        生成所选 {selected.length} 个关键镜头
      </Button>
    </div>
  );
}

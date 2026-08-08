'use client';

import { useEffect, useState } from 'react';
import { Loader2, Save } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import type { ReviewEntity } from './types';

export function EntityEditForm({ entity, onSave }: { entity: ReviewEntity; onSave: (patch: Partial<ReviewEntity>) => Promise<void> }) {
  const [draft, setDraft] = useState<Partial<ReviewEntity>>({});
  const [saving, setSaving] = useState(false);
  useEffect(() => setDraft({ entity_type: entity.entity_type, name: entity.name, canonical_name: entity.canonical_name,
    aliases: entity.aliases, description: entity.description, appearance: entity.appearance,
    visual_prompt: entity.visual_prompt, evidence: entity.evidence }), [entity]);
  const field = (key: keyof ReviewEntity, value: unknown) => setDraft((current) => ({ ...current, [key]: value }));
  const save = async () => { setSaving(true); try { await onSave(draft); } finally { setSaving(false); } };
  return <div className="space-y-3">
    <div className="grid grid-cols-[120px_1fr] gap-2"><select aria-label="编辑实体类型" value={draft.entity_type || 'character'} onChange={(event) => field('entity_type', event.target.value)} className="h-9 rounded border border-white/15 bg-slate-950 px-2 text-white"><option value="character">角色</option><option value="scene">场景</option><option value="prop">道具</option><option value="event">事件</option></select><Input aria-label="实体名称" value={draft.name || ''} onChange={(event) => field('name', event.target.value)} /></div>
    <Input aria-label="规范名称" placeholder="规范名称" value={draft.canonical_name || ''} onChange={(event) => field('canonical_name', event.target.value)} />
    <Input aria-label="别名" placeholder="别名，用逗号分隔" value={(draft.aliases || []).join('，')} onChange={(event) => field('aliases', event.target.value.split(/[，,]/).map((item) => item.trim()).filter(Boolean))} />
    <Textarea aria-label="实体描述" placeholder="实体描述" value={draft.description || ''} onChange={(event) => field('description', event.target.value)} />
    <Textarea aria-label="外观描述" placeholder="外观描述" value={draft.appearance || ''} onChange={(event) => field('appearance', event.target.value)} />
    <Textarea aria-label="视觉提示词" placeholder="视觉提示词" value={draft.visual_prompt || ''} onChange={(event) => field('visual_prompt', event.target.value)} />
    <Textarea aria-label="原文证据" placeholder="原文证据" value={draft.evidence || ''} onChange={(event) => field('evidence', event.target.value)} />
    <Button className="w-full" onClick={save} disabled={saving || !draft.name?.trim()}>{saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}保存修改</Button>
  </div>;
}

'use client';

import { useState, type ReactNode } from 'react';
import { ChevronDown, ChevronUp, Loader2, RefreshCw, Settings2, Sparkles } from 'lucide-react';
import type { ImageStyleTemplate } from '@/components/media/image-style-template-picker';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';

type Option = { value: string; label: string; disabled?: boolean };

type Props = {
  novels: { id: string; title: string }[];
  entityOptions: Option[];
  selectedNovelId: string;
  selectedEntityType: string;
  selectedEntityId: string;
  selectedStyle: string;
  consistencyMode: 'draft' | 'standard' | 'strict';
  presetTitle: string;
  presetDescription?: string;
  completedCount: number;
  totalCount: number;
  missingCount: number;
  primaryActionLabel?: string;
  generating: boolean;
  rebuilding: boolean;
  entityInvalid: boolean;
  disabledEntityCount: number;
  styleTemplates: ImageStyleTemplate[];
  contextNotice?: ReactNode;
  visualContract?: Record<string, any> | null;
  children: ReactNode;
  onNovelChange: (value: string) => void;
  onEntityTypeChange: (value: string) => void;
  onEntityChange: (value: string) => void;
  onStyleChange: (value: string) => void;
  onConsistencyModeChange: (value: 'draft' | 'standard' | 'strict') => void;
  onGenerate: () => void;
  onRebuild: () => void;
};

const TYPE_LABELS: Record<string, string> = { character: '角色', scene: '场景', prop: '道具' };

export function AssetProductionWizard(props: Props) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const progress = props.totalCount ? Math.round((props.completedCount / props.totalCount) * 100) : 0;
  const typeLabel = TYPE_LABELS[props.selectedEntityType] || props.selectedEntityType;
  const generateLabel = props.primaryActionLabel || (props.missingCount > 0 ? `生成 ${props.missingCount} 个缺失视图` : '必备视图已补齐');

  return (
    <section data-testid="asset-wizard" className="overflow-hidden rounded-2xl border border-white/10 bg-slate-950/55 shadow-2xl shadow-black/20">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-white/10 px-5 py-4">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold text-white"><Sparkles className="h-5 w-5 text-violet-300" />补齐资产</h2>
          <p className="mt-1 text-sm text-white/50">选择制片对象，检查缺失视图，然后一次补齐。</p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <Badge variant="outline" className="border-white/15 text-white/60">{typeLabel}</Badge>
          <Badge variant="outline" className="border-emerald-300/30 text-emerald-100">{props.completedCount}/{props.totalCount} 已完成</Badge>
        </div>
      </div>

      <div className="space-y-4 p-5">
        {props.contextNotice}
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.2fr)_auto] lg:items-end">
          <label className="space-y-1 text-sm text-white/65" htmlFor="asset-wizard-novel"><span>向导小说</span><Select id="asset-wizard-novel" value={props.selectedNovelId} onChange={(event) => props.onNovelChange(event.target.value)} options={[{ value: '', label: '请选择小说' }, ...props.novels.map((novel) => ({ value: novel.id, label: novel.title }))]} /></label>
          <label className="space-y-1 text-sm text-white/65" htmlFor="asset-wizard-entity-type"><span>资产对象类型</span><Select id="asset-wizard-entity-type" value={props.selectedEntityType} onChange={(event) => props.onEntityTypeChange(event.target.value)} options={[{ value: 'character', label: '角色' }, { value: 'scene', label: '场景' }, { value: 'prop', label: '道具' }]} /></label>
          <label className="space-y-1 text-sm text-white/65" htmlFor="asset-wizard-entity"><span>小说对象</span><Select id="asset-wizard-entity" value={props.selectedEntityId} disabled={!props.selectedNovelId || props.entityOptions.length === 0} onChange={(event) => props.onEntityChange(event.target.value)} options={[{ value: '', label: props.selectedNovelId ? (props.entityOptions.length ? `请选择${typeLabel}` : `暂无${typeLabel}，请先创建或定稿对象`) : '请先选择小说' }, ...props.entityOptions]} /></label>
          <Button className="h-10 bg-violet-600 px-5 hover:bg-violet-700" disabled={!props.selectedEntityId || props.generating || props.entityInvalid || props.missingCount === 0} onClick={props.onGenerate}>{props.generating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}{generateLabel}</Button>
        </div>

        {(props.disabledEntityCount > 0 || props.entityInvalid) && <div className="rounded-lg border border-amber-400/20 bg-amber-500/10 px-3 py-2 text-xs leading-5 text-amber-100">角色三视图只能用于单一角色；群体或复合角色请先在实体库拆分。</div>}

        <div className="rounded-xl border border-white/10 bg-black/20">
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
            <div className="min-w-0"><h3 className="font-medium text-white">{props.presetTitle}</h3><div className="mt-1 truncate text-xs text-white/45">{props.presetDescription || '锁定必备参考视图，供后续镜头稳定复用。'}</div></div>
            <div className="flex items-center gap-3"><div className="hidden w-28 overflow-hidden rounded-full bg-white/10 sm:block"><div className="h-1.5 rounded-full bg-violet-400" style={{ width: `${progress}%` }} /></div><Button type="button" variant="ghost" size="sm" className="text-white/65" onClick={() => setSettingsOpen((value) => !value)}><Settings2 className="mr-1 h-4 w-4" />生成设置{settingsOpen ? <ChevronUp className="ml-1 h-4 w-4" /> : <ChevronDown className="ml-1 h-4 w-4" />}</Button></div>
          </div>
          {settingsOpen && <div className="grid gap-4 border-t border-white/10 p-4 lg:grid-cols-[minmax(220px,1fr)_minmax(220px,1fr)_auto] lg:items-end"><label className="space-y-1 text-sm text-white/65" htmlFor="asset-wizard-style"><span>画面风格</span><Select id="asset-wizard-style" value={props.selectedStyle} onChange={(event) => props.onStyleChange(event.target.value)} options={props.styleTemplates.map((template) => ({ value: template.style, label: template.label }))} /></label><label className="space-y-1 text-sm text-white/65" htmlFor="asset-wizard-consistency-mode"><span>一致性模式</span><Select id="asset-wizard-consistency-mode" value={props.consistencyMode} onChange={(event) => props.onConsistencyModeChange(event.target.value as Props['consistencyMode'])} options={[{ value: 'standard', label: '标准：故事契约 + 锚点参考' }, { value: 'strict', label: '严格：必须支持参考图' }, { value: 'draft', label: '草稿：快速生成后复审' }]} /></label><Button type="button" variant="outline" className="border-cyan-300/35 text-cyan-100" disabled={props.rebuilding || props.entityInvalid || (!props.selectedEntityId && !props.selectedNovelId)} onClick={props.onRebuild}>{props.rebuilding ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}重建资产包</Button></div>}
        </div>

        {props.visualContract && <div data-testid="asset-visual-contract-panel" className="rounded-lg border border-cyan-300/20 bg-cyan-400/10 px-3 py-3 text-xs text-cyan-50"><div className="font-medium text-white">视觉契约</div><div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-cyan-100/80">{props.visualContract.continuity_axes?.era && <span>时代：{props.visualContract.continuity_axes.era}</span>}{props.visualContract.continuity_axes?.weather && <span>天气：{props.visualContract.continuity_axes.weather}</span>}{props.visualContract.continuity_axes?.lighting_direction && <span>光源：{props.visualContract.continuity_axes.lighting_direction}</span>}{props.visualContract.continuity_axes?.color_palette && <span>色彩：{props.visualContract.continuity_axes.color_palette}</span>}{Array.isArray(props.visualContract.spatial_layout?.fixed_elements) && props.visualContract.spatial_layout.fixed_elements.length > 0 && <span>固定空间：{props.visualContract.spatial_layout.fixed_elements.join('、')}</span>}</div></div>}
        {props.children}
      </div>
    </section>
  );
}

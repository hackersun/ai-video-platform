import type { StudioRunMode } from './studio-types';

export const studioModeLabels: Record<StudioRunMode, string> = {
  test: '测试验证模式',
  production: '生产出片模式',
};

export const studioModeDescriptions: Record<StudioRunMode, string> = {
  test: '测试验证模式允许临时跳过部分限制，产物不能视为最终出片。',
  production: '生产出片模式会强制执行资产锁、模型验证、公开素材地址和一致性要求。',
};

export function studioModeTone(mode: StudioRunMode) {
  return mode === 'production'
    ? 'border-cyan-500/25 bg-cyan-500/10 text-cyan-50'
    : 'border-amber-500/25 bg-amber-500/10 text-amber-50';
}

export function severityLabel(severity?: string) {
  if (severity === 'blocking' || severity === 'error') return '阻断';
  if (severity === 'confirmable') return '可确认跳过';
  if (severity === 'warning') return '风险';
  return '提示';
}

export function severityTone(severity?: string) {
  if (severity === 'blocking' || severity === 'error') return 'border-red-500/25 bg-red-500/10 text-red-50';
  if (severity === 'confirmable') return 'border-amber-500/25 bg-amber-500/10 text-amber-50';
  if (severity === 'warning') return 'border-yellow-500/25 bg-yellow-500/10 text-yellow-50';
  return 'border-white/10 bg-white/5 text-white/70';
}

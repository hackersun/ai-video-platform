'use client';

import Link from 'next/link';
import { AlertCircle, CheckCircle2, Settings, Sparkles } from 'lucide-react';
import {
  getConfigsByCapability,
  getDefaultConfigForCapability,
  ModelCapability,
  MODEL_CAPABILITY_LABELS,
  modelStatusLabel,
  SavedModelConfig,
} from '@/lib/model-configs';
import { cn } from '@/lib/utils';

type ModelCapabilitySelectorProps = {
  capability: ModelCapability;
  configs: SavedModelConfig[];
  value?: string;
  onChange?: (configId: string) => void;
  disabled?: boolean;
  title?: string;
  description?: string;
  requireVerified?: boolean;
  compact?: boolean;
  className?: string;
};

export function ModelCapabilitySelector({
  capability,
  configs,
  value,
  onChange,
  disabled = false,
  title,
  description,
  requireVerified = false,
  compact = false,
  className,
}: ModelCapabilitySelectorProps) {
  const scopedConfigs = getConfigsByCapability(configs, capability);
  const defaultConfig = getDefaultConfigForCapability(configs, capability);
  const selectedConfig = scopedConfigs.find((config) => config.id === value) || defaultConfig;
  const selectableConfigs = requireVerified
    ? scopedConfigs.filter((config) => config.test_status === 'success' && config.key_available !== false)
    : scopedConfigs;
  const hasConfiguredModel = scopedConfigs.length > 0;
  const verified = selectedConfig?.test_status === 'success' && selectedConfig.key_available !== false;
  const failed = selectedConfig?.test_status === 'failed' || selectedConfig?.key_available === false;
  const configLabel = selectedConfig
    ? `${selectedConfig.name} · ${selectedConfig.provider_name || selectedConfig.provider_id} / ${selectedConfig.model_name}`
    : `未配置${MODEL_CAPABILITY_LABELS[capability]}模型`;

  return (
    <div
      className={cn(
        'rounded-lg border border-white/10 bg-white/[0.03] p-3 text-sm',
        compact && 'p-2',
        className,
      )}
    >
      <div className="flex min-w-0 flex-col gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 text-white">
            <Sparkles className="h-4 w-4 shrink-0 text-violet-300" aria-hidden="true" />
            <span className="min-w-0 break-words font-medium leading-5">
              {title || `${MODEL_CAPABILITY_LABELS[capability]}模型`}
            </span>
            {selectedConfig?.is_default && (
              <span className="shrink-0 rounded border border-violet-400/30 bg-violet-500/15 px-2 py-0.5 text-xs text-violet-100">
                默认
              </span>
            )}
            <span
              className={cn(
                'inline-flex shrink-0 items-center gap-1 rounded border px-2 py-0.5 text-xs',
                verified
                  ? 'border-emerald-400/30 bg-emerald-500/15 text-emerald-100'
                  : failed
                    ? 'border-red-400/30 bg-red-500/15 text-red-100'
                    : 'border-yellow-400/30 bg-yellow-500/15 text-yellow-100',
              )}
            >
              {verified ? (
                <CheckCircle2 className="h-3 w-3 shrink-0" aria-hidden="true" />
              ) : (
                <AlertCircle className="h-3 w-3 shrink-0" aria-hidden="true" />
              )}
              {selectedConfig ? modelStatusLabel(selectedConfig.test_status) : '未配置'}
            </span>
          </div>
          <p className="mt-1 break-words text-xs leading-5 text-white/55">
            {description || '生成时会优先使用该能力的默认模型，也可切换到其他已保存配置。'}
          </p>
          <p className="mt-1 truncate text-xs text-white/40">{configLabel}</p>
          {failed && selectedConfig?.test_message && (
            <p className="mt-1 break-words text-xs leading-5 text-red-100/80">{selectedConfig.test_message}</p>
          )}
        </div>

        <div className="flex min-w-0 flex-col gap-2">
          {hasConfiguredModel ? (
            <select
              value={selectedConfig?.id || ''}
              onChange={(event) => onChange?.(event.target.value)}
              disabled={disabled || selectableConfigs.length === 0}
              aria-label={`${MODEL_CAPABILITY_LABELS[capability]}模型配置`}
              className="min-h-10 w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 text-xs text-white disabled:opacity-50"
              title={`${MODEL_CAPABILITY_LABELS[capability]}模型配置`}
            >
              {selectableConfigs.length === 0 ? (
                <option value="">暂无已验证配置</option>
              ) : (
                selectableConfigs.map((config) => (
                  <option key={config.id} value={config.id}>
                    {config.is_default ? '默认 · ' : ''}
                    {config.name} · {modelStatusLabel(config.test_status)}
                  </option>
                ))
              )}
            </select>
          ) : (
            <Link
              href="/llm-config"
              className="inline-flex items-center justify-center gap-2 rounded-md border border-violet-400/40 px-3 py-2 text-xs text-violet-100 hover:bg-violet-500/10"
            >
              <Settings className="h-3.5 w-3.5" />
              前往配置
            </Link>
          )}
          {requireVerified && hasConfiguredModel && selectableConfigs.length === 0 && (
            <div className="text-xs text-yellow-100/80">当前能力没有已验证通过的配置。</div>
          )}
        </div>
      </div>
    </div>
  );
}

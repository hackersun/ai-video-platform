'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/api-client';

// LLM 配置类型
export interface LLMConfig {
  id: string;
  provider_id: string;
  provider_name?: string;
  model_id: string;
  model_name?: string;
  api_key?: string;
  is_active: boolean;
}

export interface UseActiveLLMConfigReturn {
  configs: LLMConfig[];
  activeVolcanoConfig: LLMConfig | null;
  activeQianlianConfig: LLMConfig | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

/**
 * Hook to get active LLM configurations
 */
export function useActiveLLMConfig(): UseActiveLLMConfigReturn {
  const [configs, setConfigs] = useState<LLMConfig[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadConfigs = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await apiClient.getLLMConfigs();
      setConfigs(data || []);
    } catch (err: any) {
      console.error('加载LLM配置失败:', err);
      setError(err.message || '加载LLM配置失败');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConfigs();
  }, [loadConfigs]);

  // 获取活跃的火山引擎配置
  const activeVolcanoConfig = configs.find(
    (c) => c.provider_id === 'volcano' && c.is_active
  ) || null;

  // 获取活跃的阿里百炼配置
  const activeQianlianConfig = configs.find(
    (c) => c.provider_id === 'qianlian' && c.is_active
  ) || null;

  return {
    configs,
    activeVolcanoConfig,
    activeQianlianConfig,
    isLoading,
    error,
    refresh: loadConfigs,
  };
}

/**
 * Hook to get a specific provider's active config
 */
export function useProviderConfig(providerId: string) {
  const { configs, isLoading, error, refresh } = useActiveLLMConfig();

  const activeConfig = configs.find(
    (c) => c.provider_id === providerId && c.is_active
  ) || null;

  return {
    config: activeConfig,
    isLoading,
    error,
    refresh,
  };
}

'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { jobApi } from '@/lib/api';
import type { Job, JobFilters, JobStats } from '@/types/job';

const POLLING_INTERVAL = 3000;

export function useJobs(filters?: JobFilters) {
  return useQuery({
    queryKey: ['jobs', filters],
    queryFn: async () => {
      const response = await jobApi.getList({
        status: filters?.status,
        type: filters?.type,
        page: filters?.page || 1,
        limit: filters?.limit || 20,
      });
      return response.data;
    },
    refetchInterval: POLLING_INTERVAL,
  });
}

export function useJob(id: string) {
  return useQuery({
    queryKey: ['jobs', id],
    queryFn: async () => {
      const response = await jobApi.getById(id);
      return response.data;
    },
    enabled: !!id,
    refetchInterval: POLLING_INTERVAL,
  });
}

export function useJobStats() {
  return useQuery({
    queryKey: ['jobs', 'stats'],
    queryFn: async () => {
      const response = await jobApi.getStats();
      return response.data as JobStats;
    },
    refetchInterval: POLLING_INTERVAL,
  });
}

export function useCancelJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      const response = await jobApi.cancel(id);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });
}

export function useRetryJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      const response = await jobApi.retry(id);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });
}

export function useDeleteJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      await jobApi.delete(id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });
}

export function useBatchDeleteJobs() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (ids: string[]) => {
      await jobApi.batchDelete(ids);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });
}

export function useCreateJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: { type: string; input_params?: Record<string, unknown> }) => {
      const response = await jobApi.create(data);
      return response.data as Job;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });
}
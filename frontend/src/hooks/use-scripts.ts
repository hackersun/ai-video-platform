// 剧本数据Hook - React Query
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

// 剧本类型
export interface Script {
  id: string;
  title: string;
  novel_id: string;
  novel_title: string;
  description: string;
  status: "completed" | "writing" | "planning";
  scenes: number;
  characters: number;
  content?: string;
  created_at: string;
  updated_at: string;
}

export interface CreateScriptInput {
  title: string;
  novel_id: string;
  description: string;
}

export interface GenerateScriptInput {
  novel_id: string;
  chapter_range?: { start: number; end: number };
  style?: string;
}

// 获取剧本列表
export function useScripts() {
  return useQuery({
    queryKey: ["scripts"],
    queryFn: () => api.get<Script[]>("/api/scripts"),
  });
}

// 获取单个剧本
export function useScript(id: string) {
  return useQuery({
    queryKey: ["scripts", id],
    queryFn: () => api.get<Script>(`/api/scripts/${id}`),
    enabled: !!id,
  });
}

// 创建剧本
export function useCreateScript() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateScriptInput) =>
      api.post<Script>("/api/scripts", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scripts"] });
    },
  });
}

// 更新剧本
export function useUpdateScript() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Script> }) =>
      api.patch<Script>(`/api/scripts/${id}`, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["scripts"] });
      queryClient.invalidateQueries({ queryKey: ["scripts", variables.id] });
    },
  });
}

// 删除剧本
export function useDeleteScript() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/scripts/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scripts"] });
    },
  });
}

// AI生成剧本
export function useGenerateScript() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: GenerateScriptInput) =>
      api.post<Script>("/api/scripts/generate", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scripts"] });
    },
  });
}

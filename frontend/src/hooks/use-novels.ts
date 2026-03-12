// 小说数据Hook - React Query
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

// 小说类型
export interface Novel {
  id: string;
  title: string;
  author: string;
  description: string;
  status: "completed" | "writing" | "planning";
  chapters: number;
  characters: number;
  created_at: string;
  updated_at: string;
}

export interface CreateNovelInput {
  title: string;
  author: string;
  description: string;
}

// 获取小说列表
export function useNovels() {
  return useQuery({
    queryKey: ["novels"],
    queryFn: () => api.get<Novel[]>("/api/novels"),
  });
}

// 获取单个小说
export function useNovel(id: string) {
  return useQuery({
    queryKey: ["novels", id],
    queryFn: () => api.get<Novel>(`/api/novels/${id}`),
    enabled: !!id,
  });
}

// 创建小说
export function useCreateNovel() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateNovelInput) =>
      api.post<Novel>("/api/novels", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["novels"] });
    },
  });
}

// 更新小说
export function useUpdateNovel() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<CreateNovelInput> }) =>
      api.patch<Novel>(`/api/novels/${id}`, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["novels"] });
      queryClient.invalidateQueries({ queryKey: ["novels", variables.id] });
    },
  });
}

// 删除小说
export function useDeleteNovel() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/novels/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["novels"] });
    },
  });
}

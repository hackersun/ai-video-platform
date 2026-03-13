/**
 * 任务队列类型定义
 */

// 任务状态
export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';

// 任务类型
export type JobType = 'video_generation' | 'tts_generation' | 'avatar_generation' | 'script_generation';

// 任务结果
export interface JobResult {
  video_url?: string;
  audio_url?: string;
  avatar_url?: string;
  script_content?: string;
  output_path?: string;
  metadata?: Record<string, unknown>;
}

// 任务接口
export interface Job {
  id: string;
  type: JobType;
  status: JobStatus;
  progress: number; // 0-100
  result?: JobResult;
  error?: string;
  created_at: string;
  updated_at: string;
  // 扩展字段
  title?: string;
  description?: string;
  input_params?: Record<string, unknown>;
}

// 创建任务输入
export interface CreateJobInput {
  type: JobType;
  input_params?: Record<string, unknown>;
}

// 任务筛选参数
export interface JobFilters {
  status?: JobStatus;
  type?: JobType;
  page?: number;
  limit?: number;
}

// 任务列表响应
export interface JobListResponse {
  items: Job[];
  total: number;
  page: number;
  limit: number;
}

// 任务状态统计
export interface JobStats {
  total: number;
  pending: number;
  processing: number;
  completed: number;
  failed: number;
  cancelled: number;
}
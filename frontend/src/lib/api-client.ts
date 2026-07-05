/**
 * API 客户端
 * 统一处理前后端API通信
 */

import type { NovelProductionEntry } from './studio-types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

const TOKEN_KEY = 'auth_token';

// ========== 类型定义 ==========

type ApiError = {
  detail?: any;
  message?: string;
};

type TTSJob = {
  id: string;
  task_id?: string;
  title?: string;
  text?: string;
  model_name?: string;
  voice?: string;
  speed?: number;
  shot_id?: string;
  status: string;
  progress: number;
  audio_url?: string;
  duration_seconds?: number;
  error_message?: string;
  extra_data?: any;
  created_at: string;
  updated_at: string;
};

type WorkflowStatusParams = {
  novel_id?: string;
  chapter_id?: string;
  script_id?: string;
  storyboard_id?: string;
};

type TTSGenerateParams = {
  text_content: string;
  voice_model: string;
  speed: number;
  title?: string;
  api_provider?: string;
  model_config_id?: string;
  model_id?: string;
  novel_id?: string;
  chapter_id?: string;
  script_id?: string;
  storyboard_id?: string;
  shot_id?: string;
  character_id?: string;
};

type TTSGenerateResponse = TTSJob;

type SynthesisJob = {
  id: string;
  job_id?: string;
  task_id?: string;
  title?: string;
  model_name?: string;
  project_id?: string;
  workflow_id?: string;
  novel_id?: string;
  chapter_id?: string;
  script_id?: string;
  storyboard_id?: string;
  shot_id?: string;
  video_job_id?: string;
  tts_job_id?: string;
  video_url?: string;
  audio_url?: string;
  status: string;
  progress: number;
  output_url?: string;
  cover_url?: string;
  duration_seconds?: number;
  manifest_url?: string;
  preview_url?: string;
  srt_url?: string;
  timeline_url?: string;
  render_manifest_url?: string;
  render_status?: string;
  render_backend?: string;
  is_publishable?: boolean;
  output_kind?: string;
  publication_blockers?: Array<{ code?: string; message?: string }>;
  segment_count?: number;
  error_message?: string;
  extra_data?: any;
  created_at: string;
  updated_at: string;
};

type SynthesisGenerateParams = {
  video_job_id?: string;
  tts_job_id?: string;
  video_url?: string;
  audio_url?: string;
  title?: string;
  project_id?: string;
  workflow_id?: string;
};

type SynthesisGenerateResponse = SynthesisJob;

type SynthesisExecuteParams = {
  video_urls: string[];
  audio_urls?: string[];
  subtitles?: Array<{ text: string; start_time: number; end_time: number; style?: any }>;
  title?: string;
  output_format?: string;
  quality?: string;
  project_id?: string;
  workflow_id?: string;
};

type SynthesisExecuteResponse = {
  job_id: string;
  status: string;
  video_url?: string;
  cover_url?: string;
  duration_seconds?: number;
  error?: string;
};

type StoryboardMergeVideosParams = {
  shot_ids?: string[];
  title?: string;
  transition_style?: string;
  transition_duration_seconds?: number;
  include_subtitles?: boolean;
  subtitle_mode?: string;
  audio_mix_strategy?: string;
  quality_profile?: string;
  render_strategy?: 'auto' | 'ffmpeg' | 'manifest_only';
  parent_job_id?: string;
};

type StoryboardMergeVideosResponse = {
  job_id: string;
  storyboard_id: string;
  message: string;
  output_url?: string;
  manifest_url: string;
  srt_url?: string;
  segment_count: number;
  duration_seconds: number;
  segments: any[];
  selected_shot_ids: string[];
  selected_shot_numbers: number[];
  skipped_shot_numbers: number[];
  version_number: number;
  parent_job_id?: string;
  render_backend: string;
  is_real_merged: boolean;
  render_message?: string;
};

export type WorkflowRenderBackend = 'local_artifact_package' | 'ffmpeg_cloud' | 'ffmpeg_local';

type WorkflowRenderResponse = {
  status: string;
  render_status?: string;
  render_backend?: WorkflowRenderBackend | string;
  output_url?: string;
  manifest_url?: string;
  preview_url?: string;
  srt_url?: string;
  timeline_url?: string;
  render_manifest_url?: string;
  segment_count?: number;
  duration_seconds?: number;
  render_source?: string;
  timeline_id?: string;
  is_publishable?: boolean;
  output_kind?: string;
  publication_blockers?: Array<{ code?: string; message?: string }>;
  publish_block_reason?: string;
  [key: string]: any;
};

export type ProductionCardEntityType = 'character' | 'scene' | 'prop';

export type ProductionCardGap = {
  code?: string;
  message: string;
  fix_url?: string;
};

export type ProductionCardView = {
  view_key: string;
  view_label?: string;
  asset_id?: string;
  url?: string;
  is_locked?: boolean;
  is_final?: boolean;
  version?: number;
};

export type ProductionCard = {
  entity_id: string;
  entity_type: ProductionCardEntityType;
  name: string;
  novel_id: string;
  visual?: {
    views?: ProductionCardView[];
    required_views?: string[];
    missing_views?: string[];
    locked_count?: number;
  };
  voice?: {
    voice?: string | null;
    voice_speed?: number | null;
    story_bible_id?: string | null;
    locked?: boolean;
  } | null;
  profile?: {
    description?: string;
    visual_dna?: any;
    personality?: string;
    relationships?: any;
    forbidden_changes?: any;
  };
  state?: any;
  usage?: {
    shot_count?: number;
    last_used_at?: string | null;
  };
  readiness?: {
    score?: number;
    final_ready?: boolean;
    gaps?: ProductionCardGap[];
  };
};

export type ProductionCardsResponse = {
  novel_id: string;
  cards: ProductionCard[];
  summary?: {
    ready?: number;
    incomplete?: number;
  };
};

export type ContinuityReviewTask = {
  shot_id: string;
  shot_number: number;
  storyboard_id?: string | null;
  storyboard_title?: string | null;
  storyboard_url?: string | null;
  novel_id?: string | null;
  novel_title?: string | null;
  workflow_id?: string | null;
  workflow_title?: string | null;
  shot_review_url?: string | null;
  shot_url?: string | null;
  status?: string | null;
  shot_summary?: string | null;
  entity_id?: string | null;
  entity_name?: string | null;
  entity_type?: string | null;
  episode_index?: number | null;
  review_reason?: string | null;
  review_at?: string | null;
  review_state?: string | null;
  review_notes?: string | null;
  change_note?: string | null;
  marked_at?: string | null;
};

export type ContinuityReviewTasksResponse = {
  tasks: ContinuityReviewTask[];
  total: number;
  workflow_id?: string | null;
  filters?: {
    workflow_id?: string | null;
    novel_id?: string | null;
    entity_id?: string | null;
    episode_index?: number | null;
    review_state?: string | null;
    status?: string | null;
  };
  sort?: string;
};

export type ContinuityReviewResolveResponse = {
  status: string;
  shot_id: string;
  review_state: string;
  resolved_at: string;
  resolution_note?: string | null;
};

export type ContinuityReviewBatchResolveResponse = {
  status: string;
  resolved_count: number;
  shot_ids: string[];
  tasks?: ContinuityReviewResolveResponse[];
};

export type BatchFinalizeSupportingRequest = {
  min_occurrences?: number;
  image_model_config_id?: string | null;
  voice_pool?: string[] | null;
};

export type BatchFinalizeSupportingResponse = {
  novel_id: string;
  finalized: Array<{
    entity_id: string;
    name: string;
    asset_id: string;
    voice: string;
  }>;
  skipped: Array<{
    entity_id: string;
    name?: string;
    reason: string;
    occurrences?: number;
  }>;
};

export type WorkflowShotReviewItem = {
  shot_id: string;
  shot_number: number;
  latest_video_job_id?: string | null;
  latest_tts_job_id?: string | null;
  video_url?: string | null;
  status?: string;
  duration?: number;
  subtitle_text?: string;
  character_names?: string[];
  evidence?: {
    strategy_routing?: any;
    reference_package_mode?: any;
    reference_package?: any;
    generation_preflight?: any;
    visual_consistency?: {
      score?: number;
      status?: string;
      model?: string;
      method?: string;
      reference_asset_id?: string;
      frame_count?: number;
      blocking?: boolean;
      issues?: string[];
      notes?: string;
      checked_at?: string;
      [key: string]: any;
    } | null;
  };
  quality_report?: Record<string, any>;
  visual_consistency_score?: number | null;
  regeneration_count?: number;
};

export type WorkflowRenderArtifacts = {
  output_url?: string | null;
  manifest_url?: string | null;
  source_manifest_url?: string | null;
  preview_url?: string | null;
  srt_url?: string | null;
  timeline_url?: string | null;
  render_manifest_url?: string | null;
};

export type WorkflowShotReviewResponse = {
  workflow_id: string;
  shots: WorkflowShotReviewItem[];
  latest_render_artifacts?: WorkflowRenderArtifacts | null;
};

export type WorkflowShotRegenerateRequest = {
  shot_ids?: string[] | null;
  filter?: 'failed' | 'all_selected' | null;
  character_name?: string | null;
  production_strategy?: string | null;
  model_config_id?: string | null;
  audio_model_config_id?: string | null;
  audio_mode?: 'model_audio' | 'none';
};

export type WorkflowShotRegenerateResponse = {
  workflow_id?: string;
  regenerated_shot_ids: string[];
  created_count?: number;
  video_job_ids: string[];
  tts_job_ids?: string[];
  media_job_ids?: string[];
  concatenate_video_job_ids?: string[];
  concatenate_tts_job_ids?: string[];
  concatenate_media_job_ids?: string[];
  subtitle_track_ids?: string[];
  skipped?: Array<{ shot_id?: string; reason?: string }>;
  ready_for_concatenate?: boolean;
};

type NovelImportChapter = {
  title: string;
  chapter_number?: number;
  word_count?: number;
  preview?: string;
};

type NovelImportConfirmParams = {
  job_id: string;
  title?: string;
  description?: string;
  genre?: string;
  tags?: string[];
};

type UsageLogParams = {
  limit?: number;
  offset?: number;
  model?: string;
  status?: string;
};


class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  // ========== Token 管理 ==========

  private getToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(TOKEN_KEY);
  }

  setToken(token: string | null): void {
    if (typeof window === 'undefined') return;
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  }

  clearToken(): void {
    this.setToken(null);
  }

  // ========== 请求核心 ==========

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;

    const token = this.getToken();
    const headers: Record<string, string> = {
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(options.headers as Record<string, string> || {}),
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const config: RequestInit = {
      ...options,
      headers,
    };

    try {
      const response = await fetch(url, config);

      if (!response.ok) {
        const error = await response.json().catch(() => ({})) as ApiError;
        const detail = error?.detail;
        const message = typeof detail === 'string'
          ? detail
          : detail?.message || error?.message || `HTTP ${response.status}`;
        const apiError = new Error(message) as Error & { detail?: any; status?: number };
        apiError.detail = detail;
        apiError.status = response.status;
        throw apiError;
      }

      // 204 No Content
      if (response.status === 204) {
        return {} as T;
      }

      return response.json();
    } catch (error: any) {
      console.error(`API Error [${endpoint}]:`, error);
      throw error;
    }
  }
  
  // ========== LLM 配置相关 ==========
  
  async getLLMProviders() {
    return this.request<any[]>('/llm/providers');
  }
  
  async getLLMModels(provider?: string) {
    const params = provider ? `?provider=${provider}` : '';
    return this.request<any[]>(`/llm/models${params}`);
  }
  
  async getLLMConfigs() {
    return this.request<any[]>('/llm/configs');
  }
  
  async createLLMConfig(config: any) {
    return this.request<any>('/llm/configs', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }
  
  async updateLLMConfig(configId: string, config: any) {
    return this.request<any>(`/llm/configs/${configId}`, {
      method: 'PUT',
      body: JSON.stringify(config),
    });
  }
  
  async deleteLLMConfig(configId: string) {
    return this.request<any>(`/llm/configs/${configId}`, {
      method: 'DELETE',
    });
  }
  
  async testLLMConfig(configId: string, message: string = '你好') {
    return this.request<any>(`/llm/configs/${configId}/test`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
  }
  
  // ========== Coding Plan 相关 ==========
  
  async generateCodingPlan(requirement: string, apiKey?: string, model?: string, modelConfigId?: string) {
    return this.request<any>('/coding-plan/generate', {
      method: 'POST',
      body: JSON.stringify({ requirement, api_key: apiKey || undefined, model, model_config_id: modelConfigId || undefined }),
    });
  }
  
  async generateNovelWithPlan(prompt: string, apiKey?: string, model?: string, modelConfigId?: string) {
    return this.request<any>('/coding-plan/novel', {
      method: 'POST',
      body: JSON.stringify({ prompt, api_key: apiKey || undefined, model, model_config_id: modelConfigId || undefined }),
    });
  }
  
  async autoGenerate(userInput: string, generateType: string, apiKey?: string, modelConfigId?: string) {
    return this.request<any>('/coding-plan/auto-generate', {
      method: 'POST',
      body: JSON.stringify({ 
        user_input: userInput, 
        generate_type: generateType,
        api_key: apiKey || undefined,
        model_config_id: modelConfigId || undefined,
      }),
    });
  }
  
  // ========== 角色管理相关 ==========
  
  async getCharacters(params: {
    novel_id?: string;
    chapter_id?: string;
    include_global?: boolean;
  } = {}) {
    const search = new URLSearchParams();
    if (params.novel_id) search.set('novel_id', params.novel_id);
    if (params.chapter_id) search.set('chapter_id', params.chapter_id);
    if (params.include_global !== undefined) search.set('include_global', String(params.include_global));
    return this.request<any[]>(`/characters${search.toString() ? `?${search}` : ''}`);
  }
  
  async createCharacter(character: any) {
    return this.request<any>('/characters', {
      method: 'POST',
      body: JSON.stringify(character),
    });
  }
  
  async updateCharacter(id: string, character: any) {
    return this.request<any>(`/characters/${id}`, {
      method: 'PUT',
      body: JSON.stringify(character),
    });
  }
  
  async deleteCharacter(id: string) {
    return this.request<any>(`/characters/${id}`, {
      method: 'DELETE',
    });
  }
  
  // ========== 小说管理相关 ==========

  async getNovels() {
    return this.request<any[]>('/novels');
  }

  async getNovel(novelId: string) {
    return this.request<any>(`/novels/${novelId}`);
  }

  async getNovelProductionEntries(novelIds: string[]) {
    const uniqueNovelIds = Array.from(new Set(novelIds.map((id) => id.trim()).filter(Boolean)));
    const entries: Record<string, NovelProductionEntry> = {};
    const batchSize = 100;

    for (let index = 0; index < uniqueNovelIds.length; index += batchSize) {
      const searchParams = new URLSearchParams();
      searchParams.set('novel_ids', uniqueNovelIds.slice(index, index + batchSize).join(','));
      const batch = await this.request<{ entries: Record<string, NovelProductionEntry>; count: number }>(
        `/novels/production-entries?${searchParams.toString()}`
      );
      Object.assign(entries, batch.entries);
    }

    return { entries, count: Object.keys(entries).length };
  }

  async getNovelProductionEntry(novelId: string) {
    return this.request<NovelProductionEntry>(`/novels/${novelId}/production-entry`);
  }

  async createNovel(novel: any) {
    return this.request<any>('/novels', {
      method: 'POST',
      body: JSON.stringify(novel),
    });
  }

  async updateNovel(novelId: string, data: any) {
    return this.request<any>(`/novels/${novelId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteNovel(novelId: string) {
    return this.request<any>(`/novels/${novelId}`, {
      method: 'DELETE',
    });
  }

  async getNovelSeriesPlan(novelId: string) {
    return this.request<any>(`/novels/${novelId}/series-plan`);
  }

  async generateNovelSeriesPlan(novelId: string, params: {
    target_episode_count?: number;
    chapters_per_episode?: number;
    target_duration_seconds?: number;
    aspect_ratio?: string;
    style?: string;
    persist?: boolean;
  } = {}) {
    return this.request<any>(`/novels/${novelId}/series-plan`, {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async createSeriesPlan(novelId: string, targetEpisodeCount?: number) {
    return this.request<any>(`/novels/${novelId}/series-plan`, {
      method: 'POST',
      body: JSON.stringify({ target_episode_count: targetEpisodeCount }),
    });
  }

  async previewNovelImport(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    return this.request<any>('/novels/import/preview', {
      method: 'POST',
      body: formData,
      headers: {},
    });
  }

  async confirmNovelImport(data: NovelImportConfirmParams) {
    return this.request<any>('/novels/import/confirm', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getNovelImportJobs() {
    return this.request<any[]>('/novels/import/jobs');
  }

  async getNovelImportJob(jobId: string) {
    return this.request<any>(`/novels/import/jobs/${jobId}`);
  }

  async createChapter(data: {
    novel_id: string;
    title: string;
    content?: string;
    chapter_number?: number;
  }) {
    return this.request<any>('/chapters', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getChapter(chapterId: string) {
    return this.request<any>(`/chapters/${chapterId}`);
  }

  async getChapters(novelId: string) {
    return this.request<any[]>(`/chapters/novel/${novelId}`);
  }

  async updateChapter(chapterId: string, data: any) {
    return this.request<any>(`/chapters/${chapterId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteChapter(chapterId: string) {
    return this.request<any>(`/chapters/${chapterId}`, {
      method: 'DELETE',
    });
  }

  // ========== 一键生产链路相关 ==========

  async getChapterProductionStatus(chapterId: string) {
    return this.request<any>(`/chapters/${chapterId}/production-status`);
  }

  async generateChapterScript(chapterId: string, data: {
    style?: string;
    genre?: string;
    model_config_id?: string;
  } = {}) {
    return this.request<any>(`/chapters/${chapterId}/generate-script`, {
      method: 'POST',
      body: JSON.stringify({
        style: 'anime',
        ...data,
      }),
    });
  }

  async generateChapterStoryboard(chapterId: string, data: {
    style?: string;
    genre?: string;
    model_config_id?: string;
    shot_count?: number;
  } = {}) {
    return this.request<any>(`/chapters/${chapterId}/generate-storyboard`, {
      method: 'POST',
      body: JSON.stringify({
        style: 'anime',
        ...data,
      }),
    });
  }

  async generateChapterAll(chapterId: string, data: {
    style?: string;
    genre?: string;
    model_config_id?: string;
    shot_count?: number;
  } = {}) {
    return this.request<any>(`/chapters/${chapterId}/generate-all`, {
      method: 'POST',
      body: JSON.stringify({
        style: 'anime',
        ...data,
      }),
    });
  }

  async getScript(scriptId: string) {
    return this.request<any>(`/scripts/${scriptId}`);
  }

  async createScript(script: any) {
    return this.request<any>('/scripts', {
      method: 'POST',
      body: JSON.stringify(script),
    });
  }

  async updateScript(scriptId: string, data: any) {
    return this.request<any>(`/scripts/${scriptId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteScript(scriptId: string) {
    return this.request<any>(`/scripts/${scriptId}`, {
      method: 'DELETE',
    });
  }

  async getScriptGenerateContext(chapterId: string, params: { style?: string; genre?: string } = {}) {
    const searchParams = new URLSearchParams();
    if (params.style) searchParams.set('style', params.style);
    if (params.genre) searchParams.set('genre', params.genre);
    const qs = searchParams.toString();
    return this.request<any>(`/scripts/generate-context/${chapterId}${qs ? `?${qs}` : ''}`);
  }

  async checkScriptConsistency(scriptId: string) {
    return this.request<any>(`/scripts/${scriptId}/check-consistency`);
  }

  async assistScriptEdit(data: {
    title: string;
    description?: string;
    content?: string;
    genre?: string;
    style?: string;
    mode: 'polish_description' | 'polish_content' | 'short_drama';
    model_config_id?: string;
  }) {
    return this.request<any>('/scripts/ai-assist', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getScriptVersions(scriptId: string) {
    return this.request<any[]>(`/scripts/${scriptId}/versions`);
  }

  async createScriptVersion(scriptId: string, note?: string) {
    return this.request<any>(`/scripts/${scriptId}/versions`, {
      method: 'POST',
      body: JSON.stringify({ note }),
    });
  }

  async restoreScriptVersion(scriptId: string, snapshotId: string) {
    return this.request<any>(`/scripts/${scriptId}/versions/restore`, {
      method: 'POST',
      body: JSON.stringify({ snapshot_id: snapshotId }),
    });
  }
  
  // ========== 分镜管理相关 ==========

  async getScripts(params: { novel_id?: string; chapter_id?: string; page?: number; page_size?: number } = {}) {
    const searchParams = new URLSearchParams();
    if (params.novel_id) searchParams.set('novel_id', params.novel_id);
    if (params.chapter_id) searchParams.set('chapter_id', params.chapter_id);
    if (params.page) searchParams.set('page', String(params.page));
    if (params.page_size) searchParams.set('page_size', String(params.page_size));
    const qs = searchParams.toString();
    return this.request<any[]>(`/scripts${qs ? `?${qs}` : ''}`);
  }

  async generateScript(data: {
    chapter_id: string;
    style?: string;
    genre?: string;
    model_config_id?: string;
  }) {
    return this.request<any>('/scripts/generate', {
      method: 'POST',
      body: JSON.stringify({
        style: 'anime',
        ...data,
      }),
    });
  }

  async getStoryboards(params?: string | { script_id?: string; novel_id?: string; chapter_id?: string }) {
    if (typeof params === 'string') {
      return this.request<any[]>(`/storyboards/script/${params}`);
    }
    const searchParams = new URLSearchParams();
    if (params?.script_id) searchParams.set('script_id', params.script_id);
    if (params?.novel_id) searchParams.set('novel_id', params.novel_id);
    if (params?.chapter_id) searchParams.set('chapter_id', params.chapter_id);
    const qs = searchParams.toString();
    return this.request<any[]>(`/storyboards${qs ? `?${qs}` : ''}`);
  }

  async getStoryboard(storyboardId: string) {
    return this.request<any>(`/storyboards/${storyboardId}`);
  }

  async createStoryboard(data: any) {
    return this.request<any>('/storyboards', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateStoryboard(storyboardId: string, data: any) {
    return this.request<any>(`/storyboards/${storyboardId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteStoryboard(storyboardId: string) {
    return this.request<any>(`/storyboards/${storyboardId}`, {
      method: 'DELETE',
    });
  }

  // ========== 镜头管理相关 ==========

  async getShots(storyboardId: string) {
    return this.request<any[]>(`/shots/storyboard/${storyboardId}`);
  }

  async getShot(shotId: string) {
    return this.request<any>(`/shots/${shotId}`);
  }

  async createShot(data: any) {
    return this.request<any>('/shots', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateShot(shotId: string, data: any) {
    return this.request<any>(`/shots/${shotId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteShot(shotId: string) {
    return this.request<any>(`/shots/${shotId}`, {
      method: 'DELETE',
    });
  }

  async batchCreateShots(storyboardId: string, shots: any[]) {
    return this.request<any[]>(`/shots/batch?storyboard_id=${storyboardId}`, {
      method: 'POST',
      body: JSON.stringify(shots),
    });
  }

  // ========== 图像生成相关 ==========

  async generateCharacterAvatar(characterId: string, params: { style?: string; model_config_id?: string } = {}) {
    return this.request<any>(`/characters/${characterId}/generate-avatar`, {
      method: 'POST',
      body: JSON.stringify({
        style: params.style || 'anime',
        model_config_id: params.model_config_id,
      }),
    });
  }

  async getImageJobStatus(taskId: string) {
    return this.request<any>(`/images/status/${taskId}`);
  }

  async getImageJobs(params: { limit?: number; status?: string } = {}) {
    const searchParams = new URLSearchParams();
    if (params.limit) searchParams.set('limit', String(params.limit));
    if (params.status) searchParams.set('status', params.status);
    const qs = searchParams.toString();
    return this.request<any[]>(`/images/jobs${qs ? `?${qs}` : ''}`);
  }

  async deleteImageJob(jobId: string) {
    return this.request<any>(`/images/jobs/${jobId}`, {
      method: 'DELETE',
    });
  }

  async generateShotImage(shotId: string, params: { style?: string; model_config_id?: string } = {}) {
    return this.request<any>(`/shots/${shotId}/generate-image`, {
      method: 'POST',
      body: JSON.stringify({
        style: params.style || 'anime',
        model_config_id: params.model_config_id,
      }),
    });
  }

  async generateShotsImages(storyboardId: string, shotIds: string[], params: { style?: string; model_config_id?: string } = {}) {
    return this.request<any>(`/storyboards/${storyboardId}/shots/generate-images`, {
      method: 'POST',
      body: JSON.stringify({
        shot_ids: shotIds,
        style: params.style || 'anime',
        model_config_id: params.model_config_id,
      }),
    });
  }

  async generateVideo(params: any) {
    return this.request<any>('/video/generate', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }
  
  async getVideoJobs(params: {
    project_id?: string;
    workflow_id?: string;
    novel_id?: string;
    chapter_id?: string;
    script_id?: string;
    storyboard_id?: string;
    shot_id?: string;
  } = {}) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value) searchParams.set(key, String(value));
    });
    const qs = searchParams.toString();
    return this.request<any[]>(`/video/jobs${qs ? `?${qs}` : ''}`);
  }
  
  async getVideoJobStatus(jobId: string) {
    return this.request<any>(`/video/jobs/${jobId}`);
  }

  async cancelVideoJob(jobId: string) {
    return this.request<any>(`/video/jobs/${jobId}/cancel`, {
      method: 'POST',
    });
  }

  async deleteVideoJob(jobId: string) {
    return this.request<any>(`/video/jobs/${jobId}`, {
      method: 'DELETE',
    });
  }
  
  // ========== TTS 相关 ==========

  async getTTSJobs() {
    return this.request<TTSJob[]>('/tts/jobs');
  }

  async generateTTS(params: TTSGenerateParams) {
    return this.request<TTSGenerateResponse>('/tts/generate', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async deleteTTSJob(jobId: string) {
    return this.request<any>(`/tts/jobs/${jobId}`, {
      method: 'DELETE',
    });
  }

  // ========== 音视频合成相关 ==========

  async getSynthesisJobs(params: {
    project_id?: string;
    workflow_id?: string;
    novel_id?: string;
    chapter_id?: string;
    script_id?: string;
    storyboard_id?: string;
    shot_id?: string;
    status?: string;
    render_status?: string;
    limit?: number;
  } = {}) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value) searchParams.set(key, String(value));
    });
    const qs = searchParams.toString();
    return this.request<SynthesisJob[]>(`/synthesis/jobs${qs ? `?${qs}` : ''}`);
  }

  async generateSynthesis(params: SynthesisGenerateParams) {
    return this.request<SynthesisGenerateResponse>('/synthesis/create', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async executeSynthesis(params: SynthesisExecuteParams): Promise<SynthesisExecuteResponse> {
    return this.request<SynthesisExecuteResponse>('/synthesis/execute', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async synthesizeVideos(params: SynthesisExecuteParams) {
    return this.request<SynthesisJob>('/synthesis/synthesize', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async publishSynthesis(jobId: string, data: { title?: string; visibility?: string; metadata?: Record<string, any> } = {}) {
    return this.request<any>('/synthesis/publish', {
      method: 'POST',
      body: JSON.stringify({
        synthesis_job_id: jobId,
        title: data.title,
        metadata: { ...(data.metadata || {}), visibility: data.visibility || 'private' },
      }),
    });
  }

  async exportSynthesis(jobId: string, data: { format?: string } = {}) {
    return this.request<any>('/synthesis/publish', {
      method: 'POST',
      body: JSON.stringify({
        synthesis_job_id: jobId,
        title: data.format ? `导出 ${data.format.toUpperCase()}` : undefined,
        metadata: { format: data.format || 'json' },
      }),
    });
  }

  async getPublications(params: { status?: string; include_archived?: boolean } = {}) {
    const searchParams = new URLSearchParams();
    if (params.status) searchParams.set('status', params.status);
    if (params.include_archived) searchParams.set('include_archived', 'true');
    const qs = searchParams.toString();
    return this.request<any[]>(`/synthesis/publications${qs ? `?${qs}` : ''}`);
  }

  async updatePublication(publicationId: string, data: { title?: string; status?: string; metadata?: Record<string, any> }) {
    return this.request<any>(`/synthesis/publications/${publicationId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async revokePublication(publicationId: string) {
    return this.request<any>(`/synthesis/publications/${publicationId}/revoke`, {
      method: 'POST',
    });
  }

  async deletePublication(publicationId: string) {
    return this.request<any>(`/synthesis/publications/${publicationId}`, {
      method: 'DELETE',
    });
  }

  async publishVideo(publicationId: string) {
    return this.request<any>(`/synthesis/publications/${publicationId}/publish`, {
      method: 'POST',
    });
  }

  async getPublicationDownload(publicationId: string) {
    return this.request<any>(`/synthesis/publications/${publicationId}/download`);
  }

  async deleteSynthesisJob(jobId: string) {
    return this.request<any>(`/synthesis/jobs/${jobId}`, {
      method: 'DELETE',
    });
  }

  // ========== Dashboard 统计 ==========

  async getDashboardStats() {
    return this.request<any>('/dashboard/stats');
  }

  async getAnalyticsDashboard(days: number = 14) {
    return this.request<any>(`/dashboard/analytics?days=${days}`);
  }

  // ========== 使用统计 ==========

  async getUsageStats(period: string = 'day') {
    if (period === 'day' || period === 'daily') {
      return this.getDailyUsage(30);
    }
    return this.getUsageSummary();
  }

  async getUsageSummary() {
    return this.request<any>('/usage-stats/summary');
  }

  async getUsageByModel() {
    return this.request<any[]>('/usage-stats/by-model');
  }

  async getDailyUsage(days: number = 30) {
    return this.request<any[]>(`/usage-stats/daily?days=${days}`);
  }

  async getUsageLogs(params: UsageLogParams = {}) {
    const searchParams = new URLSearchParams();
    if (params.limit !== undefined) searchParams.set('limit', String(params.limit));
    if (params.offset !== undefined) searchParams.set('offset', String(params.offset));
    if (params.model) searchParams.set('model', params.model);
    if (params.status) searchParams.set('status', params.status);
    const qs = searchParams.toString();
    return this.request<any[]>(`/usage-stats/logs${qs ? `?${qs}` : ''}`);
  }

  // ========== Workflow 工作流相关 ==========

  async getWorkflowSteps() {
    return this.request<any>('/workflow/steps');
  }

  async getWorkflows(params: {
    limit?: number;
    offset?: number;
  } = {}) {
    const searchParams = new URLSearchParams();
    if (params.limit !== undefined) searchParams.set('limit', String(params.limit));
    if (params.offset !== undefined) searchParams.set('offset', String(params.offset));
    const qs = searchParams.toString();
    return this.request<any[]>(`/workflow${qs ? `?${qs}` : ''}`);
  }

  async startWorkflow(params: { title?: string; novel_id?: string; chapter_id?: string; script_id?: string; storyboard_id?: string }) {
    return this.request<any>('/workflow/start', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async updateWorkflowStep(
    workflowId: string,
    params: {
      current_step: number;
      completed_steps?: number[];
      status?: string;
      novel_id?: string;
      chapter_id?: string;
      script_id?: string;
      storyboard_id?: string;
      video_job_ids?: string[];
      tts_job_ids?: string[];
      synthesis_job_ids?: string[];
    }
  ) {
    return this.request<any>(`/workflow/${workflowId}/step`, {
      method: 'PUT',
      body: JSON.stringify(params),
    });
  }

  async getWorkflowStatus(
    workflowId: string,
    params?: WorkflowStatusParams
  ) {
    const searchParams = new URLSearchParams();
    if (params?.novel_id) searchParams.set('novel_id', params.novel_id);
    if (params?.chapter_id) searchParams.set('chapter_id', params.chapter_id);
    if (params?.script_id) searchParams.set('script_id', params.script_id);
    if (params?.storyboard_id) searchParams.set('storyboard_id', params.storyboard_id);
    const qs = searchParams.toString();
    return this.request<any>(`/workflow/status/${workflowId}${qs ? `?${qs}` : ''}`);
  }

  async preflightGeneration(params: {
    task_type: string;
    model_config_id?: string;
    external_config_id?: string;
    image_url?: string;
    production_mode?: boolean;
    require_public_reference_image?: boolean;
    novel_id?: string;
    chapter_id?: string;
    script_id?: string;
    storyboard_id?: string;
    shot_id?: string;
  }) {
    return this.request<any>('/consistency/preflight', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async concatenateVideos(
    workflowId: string,
    params: {
      video_job_ids: string[];
      tts_job_ids?: string[];
      media_job_ids?: string[];
      title?: string;
      transition_style?: string;
      transition_duration_seconds?: number;
      include_subtitles?: boolean;
      subtitle_mode?: string;
      audio_mix_strategy?: string;
      quality_profile?: string;
    }
  ) {
    return this.request<any>(`/workflow/concatenate/${workflowId}`, {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async mergeStoryboardVideos(
    storyboardId: string,
    params: StoryboardMergeVideosParams = {}
  ) {
    return this.request<StoryboardMergeVideosResponse>(`/storyboards/${storyboardId}/merge-videos`, {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async preflightWorkflowRender(workflowId: string, synthesisJobId?: string, params: {
    use_editable_timeline?: boolean;
    timeline_id?: string;
  } = {}) {
    const searchParams = new URLSearchParams();
    if (synthesisJobId) searchParams.set('synthesis_job_id', synthesisJobId);
    if (params.use_editable_timeline !== undefined) {
      searchParams.set('use_editable_timeline', params.use_editable_timeline ? 'true' : 'false');
    }
    if (params.timeline_id) searchParams.set('timeline_id', params.timeline_id);
    const qs = searchParams.toString();
    return this.request<any>(`/workflow/${workflowId}/render/preflight${qs ? `?${qs}` : ''}`);
  }

  async renderWorkflowPackage(workflowId: string, params: {
    synthesis_job_id?: string;
    force?: boolean;
    quality_profile?: string;
    render_backend?: WorkflowRenderBackend;
    external_config_id?: string;
    burn_subtitles?: boolean;
    use_editable_timeline?: boolean;
    timeline_id?: string;
  } = {}) {
    return this.request<WorkflowRenderResponse>(`/workflow/${workflowId}/render`, {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async syncWorkflowTimeline(workflowId: string, params: {
    synthesis_job_id?: string;
    name?: string;
    force?: boolean;
  } = {}) {
    return this.request<any>(`/workflow/${workflowId}/timeline/sync`, {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async getTimelineTracks(timelineId: string) {
    return this.request<any[]>(`/timelines/${timelineId}/tracks`);
  }

  async getTimelineClips(timelineId: string) {
    return this.request<any[]>(`/timelines/${timelineId}/clips`);
  }

  async getProjectTimelines(projectId: string) {
    return this.request<any[]>(`/timelines/project/${projectId}`);
  }

  async getTimeline(timelineId: string) {
    return this.request<any>(`/timelines/${timelineId}`);
  }

  async updateTimeline(timelineId: string, data: Record<string, any>) {
    return this.request<any>(`/timelines/${timelineId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async updateTimelineTrack(timelineId: string, trackId: string, data: Record<string, any>) {
    return this.request<any>(`/timelines/${timelineId}/tracks/${trackId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async createTimelineClip(timelineId: string, data: Record<string, any>) {
    return this.request<any>(`/timelines/${timelineId}/clips`, {
      method: 'POST',
      body: JSON.stringify({ ...data, timeline_id: timelineId }),
    });
  }

  async updateTimelineClip(timelineId: string, clipId: string, data: Record<string, any>) {
    return this.request<any>(`/timelines/${timelineId}/clips/${clipId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteTimelineClip(timelineId: string, clipId: string) {
    return this.request<any>(`/timelines/${timelineId}/clips/${clipId}`, {
      method: 'DELETE',
    });
  }

  async reorderTimelineClips(timelineId: string, clipOrders: Array<{ clip_id: string; position: number; track_id?: string }>) {
    return this.request<any>(`/timelines/${timelineId}/clips/reorder`, {
      method: 'POST',
      body: JSON.stringify(clipOrders),
    });
  }

  async generateTimelinePreview(timelineId: string) {
    return this.request<any>(`/timelines/${timelineId}/preview`, {
      method: 'POST',
    });
  }

  async syncTimelineFromSynthesis(timelineId: string, params: { synthesis_job_id: string; name?: string }) {
    return this.request<any>(`/timelines/${timelineId}/sync`, {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async exportTimeline(timelineId: string) {
    return this.request<any>(`/timelines/${timelineId}/export`);
  }

  async generateWorkflowMediaBatch(workflowId: string, params: {
    production_strategy?: string;
    strategy?: string;
    shot_ids?: string[];
    duration_seconds?: number;
    resolution?: string;
    subtitle_mode?: string;
    audio_mode?: string;
    model_config_id?: string;
    audio_model_config_id?: string;
    voice_model?: string;
    speed?: number;
    story_bible_id?: string;
    use_story_bible_voice?: boolean;
  } = {}) {
    return this.request<any>(`/workflow/${workflowId}/generate-media-batch`, {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async getWorkflowShotReview(workflowId: string) {
    return this.request<WorkflowShotReviewResponse>(`/workflow/${workflowId}/shot-review`);
  }

  async regenerateWorkflowShots(workflowId: string, payload: WorkflowShotRegenerateRequest) {
    return this.request<WorkflowShotRegenerateResponse>(`/workflow/${workflowId}/regenerate-shots`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async lockEpisodeContract(workflowId: string) {
    return this.request<any>(`/workflow/${workflowId}/episode-contract/lock`, { method: 'POST' });
  }

  // ========== Short Video Production 相关 ==========

  async generateShortEpisodePlan(params: {
    novel_id: string;
    chapter_id?: string;
    target_duration_seconds?: number;
    aspect_ratio?: string;
    style?: string;
  }) {
    return this.request<any>('/short-video/episode-plan', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async refreshShotProductionContract(shotId: string, persist: boolean = true) {
    const searchParams = new URLSearchParams();
    searchParams.set('persist', persist ? 'true' : 'false');
    return this.request<any>(`/short-video/shots/${shotId}/production-contract?${searchParams}`);
  }

  async getWorkflowShortVideoReadiness(workflowId: string, params: {
    target_duration_seconds?: number;
    aspect_ratio?: string;
    style_asset_id?: string;
  } = {}) {
    const searchParams = new URLSearchParams();
    if (params.target_duration_seconds) {
      searchParams.set('target_duration_seconds', String(params.target_duration_seconds));
    }
    if (params.aspect_ratio) searchParams.set('aspect_ratio', params.aspect_ratio);
    if (params.style_asset_id) searchParams.set('style_asset_id', params.style_asset_id);
    const qs = searchParams.toString();
    return this.request<any>(`/short-video/workflow/${workflowId}/readiness${qs ? `?${qs}` : ''}`);
  }

  async getWorkflowProductionStatus(workflowId: string, params: {
    target_duration_seconds?: number;
    aspect_ratio?: string;
    style_asset_id?: string;
  } = {}) {
    return this.getWorkflowShortVideoReadiness(workflowId, params);
  }

  async refreshWorkflowShortVideoContracts(workflowId: string, params: {
    shot_ids?: string[];
  } = {}) {
    return this.request<any>(`/short-video/workflow/${workflowId}/refresh-contracts`, {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async getProductionCards(novelId: string) {
    return this.request<ProductionCardsResponse>(`/production-cards/novel/${novelId}`);
  }

  async getProductionCard(entityId: string) {
    return this.request<ProductionCard>(`/production-cards/entity/${entityId}`);
  }

  async batchFinalizeSupportingCharacters(novelId: string, payload: BatchFinalizeSupportingRequest = {}) {
    return this.request<BatchFinalizeSupportingResponse>(`/production-cards/novel/${novelId}/batch-finalize-supporting`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  // ========== Unified Media / Subtitle 相关 ==========

  async generateMedia(params: any) {
    return this.request<any>('/media/generate', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async getMediaJobs(params: {
    task_type?: string;
    media_type?: string;
    workflow_id?: string;
    novel_id?: string;
    chapter_id?: string;
    script_id?: string;
    storyboard_id?: string;
    shot_id?: string;
    status?: string;
  } = {}) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value) searchParams.set(key, String(value));
    });
    const qs = searchParams.toString();
    return this.request<any[]>(`/media/jobs${qs ? `?${qs}` : ''}`);
  }

  async getSubtitleTrack(trackId: string) {
    return this.request<any>(`/subtitles/tracks/${trackId}`);
  }

  async getSubtitleTracks(params: {
    workflow_id?: string;
    media_job_id?: string;
    shot_id?: string;
    novel_id?: string;
    chapter_id?: string;
    storyboard_id?: string;
    include_segments?: boolean;
  } = {}) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== '') searchParams.set(key, String(value));
    });
    const qs = searchParams.toString();
    return this.request<any[]>(`/subtitles/tracks${qs ? `?${qs}` : ''}`);
  }

  async createSubtitleTrackFromShot(data: { shot_id: string; duration_seconds?: number; language?: string; kind?: string; title?: string }) {
    return this.request<any>('/subtitles/from-shot', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateSubtitleSegment(trackId: string, segmentId: string, data: any) {
    return this.request<any>(`/subtitles/tracks/${trackId}/segments/${segmentId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async createSubtitleSegment(trackId: string, data: any) {
    return this.request<any>(`/subtitles/tracks/${trackId}/segments`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async deleteSubtitleSegment(trackId: string, segmentId: string) {
    return this.request<any>(`/subtitles/tracks/${trackId}/segments/${segmentId}`, {
      method: 'DELETE',
    });
  }

  async exportSubtitleTrack(trackId: string, format: 'srt' | 'vtt' | 'ass' = 'srt') {
    return this.request<any>(`/subtitles/tracks/${trackId}/export`, {
      method: 'POST',
      body: JSON.stringify({ format }),
    });
  }

  // ========== Production Adapter / External Capability 相关 ==========

  async getExternalProviders() {
    return this.request<any[]>('/external/providers');
  }

  async getExternalConfigs() {
    return this.request<any[]>('/external/configs');
  }

  async getExternalCapabilityStatus() {
    return this.request<any>('/external/capability-status');
  }

  async createExternalConfig(data: any) {
    return this.request<any>('/external/configs', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateExternalConfig(configId: string, data: any) {
    return this.request<any>(`/external/configs/${configId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async testExternalConfig(configId: string) {
    return this.request<any>(`/external/configs/${configId}/test`, {
      method: 'POST',
    });
  }

  async deleteExternalConfig(configId: string) {
    return this.request<any>(`/external/configs/${configId}`, {
      method: 'DELETE',
    });
  }

  async getShotProductionContext(shotId: string) {
    return this.request<any>(`/shots/${shotId}/production-context`);
  }

  async updateShotProductionContext(shotId: string, data: any) {
    return this.request<any>(`/shots/${shotId}/production-context`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async getShotQuality(shotId: string) {
    return this.request<any>(`/shots/${shotId}/quality`);
  }

  async refreshShotQuality(shotId: string) {
    return this.request<any>(`/shots/${shotId}/quality`, {
      method: 'POST',
    });
  }

  async refreshShotsQuality(shotIds: string[]) {
    return this.request<any>('/shots/quality/batch', {
      method: 'POST',
      body: JSON.stringify({ shot_ids: shotIds }),
    });
  }

  async getShotQualityReport(shotId: string) {
    return this.request<any>(`/shots/${shotId}/quality-report`);
  }

  async retryShotVideo(shotId: string, maxAttempts?: number) {
    const params = maxAttempts ? `?max_attempts=${maxAttempts}` : '';
    return this.request<any>(`/shots/${shotId}/retry${params}`, {
      method: 'POST',
    });
  }

  async getStoryboardQualitySummary(storyboardId: string) {
    return this.request<any>(`/shots/storyboard/${storyboardId}/quality-summary`);
  }

  // ========== Production Control 相关 ==========

  async getNovelProductionPack(novelId: string, params: {
    create_missing_assets?: boolean;
    persist?: boolean;
  } = {}) {
    const searchParams = new URLSearchParams();
    if (params.create_missing_assets !== undefined) {
      searchParams.set('create_missing_assets', String(params.create_missing_assets));
    }
    if (params.persist !== undefined) {
      searchParams.set('persist', String(params.persist));
    }
    const qs = searchParams.toString();
    return this.request<any>(`/production-control/novels/${novelId}/production-pack${qs ? `?${qs}` : ''}`);
  }

  async createNovelProductionPack(novelId: string, data: {
    create_missing_assets?: boolean;
    persist?: boolean;
  } = {}) {
    return this.request<any>(`/production-control/novels/${novelId}/production-pack`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async applyWorkflowAssetLocks(workflowId: string, data: {
    create_missing_assets?: boolean;
    persist?: boolean;
  } = {}) {
    return this.request<any>(`/production-control/workflow/${workflowId}/asset-locks`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async auditWorkflowMedia(workflowId: string, data: {
    persist_remote?: boolean;
    dry_run?: boolean;
  } = {}) {
    return this.request<any>(`/production-control/workflow/${workflowId}/media-audit`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async checkWorkflowProductionQuality(workflowId: string, data: {
    persist?: boolean;
  } = {}) {
    return this.request<any>(`/production-control/workflow/${workflowId}/quality-check`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async runProducerAssistant(workflowId: string, data: {
    auto_fix?: boolean;
    action_code?: string;
  } = {}) {
    return this.request<any>(`/production-control/workflow/${workflowId}/producer-assistant`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // ========== Project / Team 相关 ==========

  async getProjects() {
    return this.request<any[]>('/projects');
  }

  async getProject(projectId: string) {
    return this.request<any>(`/projects/${projectId}`);
  }

  async getProjectMembers(projectId: string) {
    return this.request<any[]>(`/projects/${projectId}/members`);
  }

  async createProjectMember(projectId: string, data: { user_id?: string; email?: string; role: string }) {
    return this.request<any>(`/projects/${projectId}/members`, {
      method: 'POST',
      body: JSON.stringify({
        user_id: data.user_id || data.email,
        role: data.role,
      }),
    });
  }

  async updateProjectMember(projectId: string, memberUserId: string, data: { role?: string; is_active?: boolean }) {
    return this.request<any>(`/projects/${projectId}/members/${memberUserId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteProjectMember(projectId: string, memberUserId: string) {
    return this.request<any>(`/projects/${projectId}/members/${memberUserId}`, {
      method: 'DELETE',
    });
  }

  // ========== Asset / Template 相关 ==========

  async getAssetCategories() {
    return this.request<any[]>('/assets/categories');
  }

  async getAssets(params: {
    category?: string;
    project_id?: string;
    novel_id?: string;
    chapter_id?: string;
    script_id?: string;
    entity_id?: string;
    scope?: string;
    search?: string;
    include_public?: boolean;
    limit?: number;
  } = {}) {
    const searchParams = new URLSearchParams();
    if (params.category) searchParams.set('category', params.category);
    if (params.project_id) searchParams.set('project_id', params.project_id);
    if (params.novel_id) searchParams.set('novel_id', params.novel_id);
    if (params.chapter_id) searchParams.set('chapter_id', params.chapter_id);
    if (params.script_id) searchParams.set('script_id', params.script_id);
    if (params.entity_id) searchParams.set('entity_id', params.entity_id);
    if (params.scope) searchParams.set('scope', params.scope);
    if (params.search) searchParams.set('search', params.search);
    if (params.include_public !== undefined) searchParams.set('include_public', String(params.include_public));
    if (params.limit) searchParams.set('limit', String(params.limit));
    const qs = searchParams.toString();
    return this.request<any[]>(`/assets${qs ? `?${qs}` : ''}`);
  }

  async createAsset(data: any) {
    return this.request<any>('/assets', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateAsset(assetId: string, data: any) {
    return this.request<any>(`/assets/${assetId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async uploadAssetFile(file: File, params: { asset_type?: string; kind?: 'resource' | 'thumbnail' } = {}) {
    const searchParams = new URLSearchParams();
    searchParams.set('asset_type', params.asset_type || 'image');
    searchParams.set('kind', params.kind || 'resource');
    const formData = new FormData();
    formData.append('file', file);
    return this.request<any>(`/assets/upload?${searchParams.toString()}`, {
      method: 'POST',
      body: formData,
      headers: {},
    });
  }

  async getAssetViewPresets() {
    return this.request<any>('/assets/view-presets');
  }

  async getAssetStyleTemplates() {
    return this.request<any>('/assets/style-templates');
  }

  async generateEntityViewAssets(data: {
    entity_id: string;
    novel_id?: string;
    chapter_id?: string;
    script_id?: string;
    view_keys?: string[];
    style?: string;
    model_config_id?: string;
    consistency_mode?: 'draft' | 'standard' | 'strict';
    force_contract_refresh?: boolean;
    anchor_view_key?: string;
  }) {
    return this.request<any>('/assets/generate-entity-views', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async reviewAssetContract(assetId: string) {
    return this.request<any>(`/assets/${assetId}/review-contract`, {
      method: 'POST',
    });
  }

  async retryAssetGeneration(assetId: string) {
    return this.request<any>(`/assets/${assetId}/retry-generation`, {
      method: 'POST',
    });
  }

  async regenerateAsset(assetId: string, data: { style?: string; model_config_id?: string } = {}) {
    return this.request<any>(`/assets/${assetId}/regenerate`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async recordAssetVisualConsistency(assetId: string, data: {
    score: number;
    model?: string;
    reference_asset_ids?: string[];
    issues?: string[];
    notes?: string;
  }) {
    return this.request<any>(`/assets/${assetId}/visual-consistency`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async deleteAsset(assetId: string) {
    return this.request<any>(`/assets/${assetId}`, {
      method: 'DELETE',
    });
  }

  async bulkActionAssets(data: {
    asset_ids: string[];
    action: 'archive' | 'lock' | 'unlock' | 'set_scope' | 'set_tags';
    scope?: 'global' | 'project' | 'novel' | 'chapter' | 'script' | 'entity';
    project_id?: string;
    novel_id?: string;
    chapter_id?: string;
    script_id?: string;
    entity_id?: string;
    tags?: string[];
    allow_test_override?: boolean;
  }) {
    return this.request<any>('/assets/bulk-action', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async reextractAssets(data: {
    entity_ids?: string[];
    novel_id?: string;
    chapter_id?: string;
    script_id?: string;
    entity_types?: string[];
    mode?: 'append' | 'overwrite' | 'delete_then_extract';
    style?: string;
    view_keys?: string[];
    model_config_id?: string;
    allow_test_override?: boolean;
  }) {
    return this.request<any>('/assets/reextract', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateAssetScope(assetId: string, data: {
    scope: 'global' | 'project' | 'novel' | 'chapter' | 'script' | 'entity';
    project_id?: string;
    novel_id?: string;
    chapter_id?: string;
    script_id?: string;
    entity_id?: string;
  }) {
    return this.request<any>(`/assets/${assetId}/scope`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // ========== 模板市场 ==========

  async getTemplateCategories() {
    return this.request<any[]>('/templates/categories');
  }

  async getTemplates(params: {
    category?: string;
    is_public?: boolean;
    search?: string;
    include_presets?: boolean;
  } = {}) {
    const searchParams = new URLSearchParams();
    if (params.category) searchParams.set('category', params.category);
    if (params.is_public !== undefined) searchParams.set('is_public', String(params.is_public));
    if (params.search) searchParams.set('search', params.search);
    if (params.include_presets !== undefined) searchParams.set('include_presets', String(params.include_presets));
    const qs = searchParams.toString();
    return this.request<any[]>(`/templates${qs ? `?${qs}` : ''}`);
  }

  async getPresetTemplates(category?: string) {
    const qs = category ? `?category=${category}` : '';
    return this.request<any[]>(`/templates/presets${qs}`);
  }

  async getTemplate(templateId: string) {
    return this.request<any>(`/templates/${templateId}`);
  }

  async createTemplate(data: {
    name: string;
    description?: string;
    category?: string;
    tags?: string[];
    content: any;
    is_public?: boolean;
  }) {
    return this.request<any>('/templates', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateTemplate(templateId: string, data: any) {
    return this.request<any>(`/templates/${templateId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteTemplate(templateId: string) {
    return this.request<any>(`/templates/${templateId}`, {
      method: 'DELETE',
    });
  }

  async useTemplate(templateId: string) {
    return this.request<any>(`/templates/${templateId}/use`, {
      method: 'POST',
    });
  }

  async cloneTemplate(templateId: string) {
    return this.request<any>(`/templates/${templateId}/clone`, {
      method: 'POST',
    });
  }

  async bulkActionTemplates(data: {
    template_ids: string[];
    action: 'delete' | 'clone' | 'set_category' | 'set_tags' | 'set_public';
    category?: string;
    tags?: string[];
    is_public?: boolean;
  }) {
    return this.request<any>('/templates/bulk-action', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // ========== 资产生成和版本锁定 ==========

  async generateCharacterAssets(data: {
    character_id: string;
    style?: string;
    model_config_id?: string;
  }) {
    return this.request<any>('/assets/generate-character', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async generateSceneAssets(data: {
    scene_id: string;
    scene_name: string;
    scene_description: string;
    style?: string;
    model_config_id?: string;
  }) {
    return this.request<any>('/assets/generate-scene', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async generatePropAssets(data: {
    prop_id: string;
    prop_name: string;
    prop_description: string;
    style?: string;
    model_config_id?: string;
  }) {
    return this.request<any>('/assets/generate-prop', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async lockAsset(assetId: string) {
    return this.request<any>(`/assets/${assetId}/lock`, {
      method: 'POST',
    });
  }

  async unlockAsset(assetId: string) {
    return this.request<any>(`/assets/${assetId}/unlock`, {
      method: 'POST',
    });
  }

  async getEntityAssets(entityId: string, params?: {
    entity_type?: string;
    include_locked_only?: boolean;
  }) {
    const searchParams = new URLSearchParams();
    if (params?.entity_type) searchParams.set('entity_type', params.entity_type);
    if (params?.include_locked_only) searchParams.set('include_locked_only', 'true');
    const qs = searchParams.toString();
    return this.request<any>(`/assets/entity/${entityId}${qs ? `?${qs}` : ''}`);
  }

  async getEntityAssetVersions(entityId: string, entityType: string) {
    return this.request<any[]>(`/assets/entity/${entityId}/versions?entity_type=${entityType}`);
  }

  async batchLockAssets(assetIds: string[]) {
    const result = await this.bulkActionAssets({ asset_ids: assetIds, action: 'lock' });
    return { ...result, locked_count: result?.updated_count || 0 };
  }

  // ========== AI 生成相关 ==========

  /**
   * 生成小说
   */
  async generateNovel(data: {
    prompt: string;
    genre?: string;
    chapter_count?: number;
    style?: string;
  }) {
    return this.request<any>('/novels/generate', {
      method: 'POST',
      body: JSON.stringify({
        prompt: data.prompt,
        genre: data.genre || '通用',
        chapter_count: data.chapter_count || 3,
        style: data.style,
      }),
    });
  }

  /**
   * 生成章节
   */
  async generateChapter(novelId: string, data: {
    chapter_title?: string;
    prev_chapter_content?: string;
    target_word_count?: number;
    instruction?: string;
    model_config_id?: string;
  }) {
    return this.request<any>('/chapters/generate', {
      method: 'POST',
      body: JSON.stringify({ novel_id: novelId, ...data }),
    });
  }

  async aiAssistChapter(chapterId: string, data: {
    mode: 'rewrite' | 'extend' | 'polish';
    instruction?: string;
    target_word_count?: number;
    sync_story_bible?: boolean;
    model_config_id?: string;
  }) {
    return this.request<any>(`/chapters/${chapterId}/ai-assist`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /**
   * 提取角色
   */
  async extractCharacters(data: {
    text?: string;
    novel_id?: string;
    chapter_id?: string;
    character_count?: number;
    auto_generate_avatar?: boolean;
    model_config_id?: string;
    image_model_config_id?: string;
  }) {
    return this.request<any>('/characters/extract', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async extractNovelEntities(data: {
    novel_id?: string;
    chapter_id?: string;
    script_id?: string;
    text?: string;
    entity_types?: string[];
    persist?: boolean;
    model_config_id?: string;
  }) {
    return this.request<any>('/story-bibles/entities/extract', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async extractEntitiesAndAssets(data: {
    novel_id?: string;
    chapter_id?: string;
    script_id?: string;
    text?: string;
    entity_types?: string[];
    persist_entities?: boolean;
    create_assets?: boolean;
    asset_scope?: 'global' | 'novel' | 'chapter' | 'script' | 'entity';
    model_config_id?: string;
  }) {
    return this.request<any>('/story-bibles/entities/extract-assets', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async reextractStoryEntities(data: {
    novel_id?: string;
    chapter_id?: string;
    script_id?: string;
    text?: string;
    entity_types?: string[];
    mode?: 'append' | 'overwrite' | 'delete_then_extract';
    create_assets?: boolean;
    asset_scope?: 'global' | 'novel' | 'chapter' | 'script' | 'entity';
    model_config_id?: string;
    allow_test_override?: boolean;
  }) {
    return this.request<any>('/story-bibles/entities/reextract', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getStoryEntities(params: {
    novel_id?: string;
    chapter_id?: string;
    script_id?: string;
    entity_type?: string;
    scope?: string;
    limit?: number;
  } = {}) {
    const searchParams = new URLSearchParams();
    if (params.novel_id) searchParams.set('novel_id', params.novel_id);
    if (params.chapter_id) searchParams.set('chapter_id', params.chapter_id);
    if (params.script_id) searchParams.set('script_id', params.script_id);
    if (params.entity_type) searchParams.set('entity_type', params.entity_type);
    if (params.scope) searchParams.set('scope', params.scope);
    if (params.limit) searchParams.set('limit', String(params.limit));
    const qs = searchParams.toString();
    return this.request<any[]>(`/story-bibles/entities${qs ? `?${qs}` : ''}`);
  }

  async getStoryEntityStats(params: {
    novel_id?: string;
    chapter_id?: string;
    script_id?: string;
    scope?: string;
  } = {}) {
    const searchParams = new URLSearchParams();
    if (params.novel_id) searchParams.set('novel_id', params.novel_id);
    if (params.chapter_id) searchParams.set('chapter_id', params.chapter_id);
    if (params.script_id) searchParams.set('script_id', params.script_id);
    if (params.scope) searchParams.set('scope', params.scope);
    const qs = searchParams.toString();
    return this.request<any>(`/story-bibles/entities/stats${qs ? `?${qs}` : ''}`);
  }

  async getStoryProductionPack(novelId: string) {
    return this.request<any>(`/story-bibles/entities/production-pack/${novelId}`);
  }

  async checkStoryEntityConsistency(data: { novel_id: string; chapter_id?: string }) {
    return this.request<any>('/story-bibles/entities/check-consistency', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async createStoryEntity(data: any) {
    return this.request<any>('/story-bibles/entities', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateStoryEntity(entityId: string, data: any) {
    return this.request<any>(`/story-bibles/entities/${entityId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async getStoryEntityImpact(entityId: string) {
    return this.request<any>(`/story-bibles/entities/${entityId}/impact`);
  }

  async getContinuityReviewTasks(params: {
    workflow_id?: string;
    novel_id?: string;
    entity_id?: string;
    episode_index?: number;
    review_state?: string;
    status?: string;
    sort?: string;
    limit?: number;
  } = {}) {
    const searchParams = new URLSearchParams();
    if (params.workflow_id) searchParams.set('workflow_id', params.workflow_id);
    if (params.novel_id) searchParams.set('novel_id', params.novel_id);
    if (params.entity_id) searchParams.set('entity_id', params.entity_id);
    if (params.episode_index) searchParams.set('episode_index', String(params.episode_index));
    if (params.review_state) searchParams.set('review_state', params.review_state);
    if (params.status) searchParams.set('status', params.status);
    if (params.sort) searchParams.set('sort', params.sort);
    if (params.limit) searchParams.set('limit', String(params.limit));
    const qs = searchParams.toString();
    return this.request<ContinuityReviewTasksResponse>(`/story-bibles/continuity-review-tasks${qs ? `?${qs}` : ''}`);
  }

  async resolveContinuityReviewTask(shotId: string, data: {
    resolution_note?: string;
  } = {}) {
    return this.request<ContinuityReviewResolveResponse>(`/story-bibles/continuity-review-tasks/${shotId}/resolve`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async resolveContinuityReviewTasks(shotIds: string[], data: {
    resolution_note?: string;
  } = {}) {
    return this.request<ContinuityReviewBatchResolveResponse>('/story-bibles/continuity-review-tasks/resolve-batch', {
      method: 'POST',
      body: JSON.stringify({
        shot_ids: shotIds,
        ...data,
      }),
    });
  }

  async createStoryEntityImpactReviewPlan(entityId: string, data: {
    episode_index: number;
    change_note?: string;
  }) {
    return this.request<any>(`/story-bibles/entities/${entityId}/impact/review-plan`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateStoryEntityScope(entityId: string, data: {
    scope: 'global' | 'novel' | 'chapter' | 'script';
    novel_id?: string;
    chapter_id?: string;
    script_id?: string;
  }) {
    return this.request<any>(`/story-bibles/entities/${entityId}/scope`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async createStoryEntityVersion(entityId: string, note?: string) {
    return this.request<any>(`/story-bibles/entities/${entityId}/versions`, {
      method: 'POST',
      body: JSON.stringify({ note }),
    });
  }

  async restoreStoryEntityVersion(entityId: string, snapshotId: string) {
    return this.request<any>(`/story-bibles/entities/${entityId}/versions/restore`, {
      method: 'POST',
      body: JSON.stringify({ snapshot_id: snapshotId }),
    });
  }

  async deleteStoryEntity(entityId: string) {
    return this.request<any>(`/story-bibles/entities/${entityId}`, {
      method: 'DELETE',
    });
  }

  async bulkActionStoryEntities(data: {
    entity_ids: string[];
    action: 'delete' | 'approve' | 'set_scope' | 'set_tags';
    approved?: boolean;
    scope?: 'global' | 'novel' | 'chapter' | 'script';
    novel_id?: string;
    chapter_id?: string;
    script_id?: string;
    tags?: string[];
    allow_test_override?: boolean;
  }) {
    return this.request<any>('/story-bibles/entities/bulk-action', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async mergeStoryEntities(data: {
    source_entity_ids: string[];
    target_entity_id: string;
    keep_source_as_alias?: boolean;
  }) {
    return this.request<any>('/story-bibles/entities/merge', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async bulkApproveStoryEntities(data: {
    entity_ids: string[];
    approved?: boolean;
  }) {
    return this.request<any>('/story-bibles/entities/bulk-approve', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getProductionBibleReview(novelId: string) {
    return this.request<any>(`/story-bibles/novel/${novelId}/production-bible/review`);
  }

  async approveProductionEntity(entityId: string, approved: boolean, approvalNote?: string) {
    return this.request<any>(`/story-bibles/entities/${entityId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approved, approval_note: approvalNote }),
    });
  }

  // ========== Graph / Character Relations 相关 ==========

  async getNovelGraph(novelId: string) {
    return this.request<any>(`/graph/novel/${novelId}`);
  }

  async getCharacterRelations(characterId: string) {
    return this.request<any>(`/graph/character/${characterId}`);
  }

  async createRelation(data: {
    from_entity_id: string;
    from_entity_type?: string;
    to_entity_id: string;
    to_entity_type?: string;
    relation_type: string;
    description?: string;
  }) {
    return this.request<any>('/graph/relation', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async deleteRelation(fromEntityId: string, toEntityId: string, relationType: string) {
    return this.request<any>(`/graph/relation?from_entity_id=${fromEntityId}&to_entity_id=${toEntityId}&relation_type=${relationType}`, {
      method: 'DELETE',
    });
  }

  async getPropTrajectory(propId: string) {
    return this.request<any[]>(`/graph/prop/${propId}/trajectory`);
  }

  async getNovelTimeline(novelId: string) {
    return this.request<any[]>(`/graph/novel/${novelId}/timeline`);
  }

  async getRelationTypes() {
    return this.request<any>('/graph/relation-types');
  }

  async getGraphStatus() {
    return this.request<any>('/graph/status');
  }

  async syncCharacterToGraph(characterId: string) {
    return this.request<any>(`/graph/character/${characterId}/sync`, {
      method: 'POST',
    });
  }

  async buildNovelGraph(novelId: string) {
    return this.request<any>(`/graph/novel/${novelId}/build-graph`, {
      method: 'POST',
    });
  }

  // ========== Story Bible 相关 ==========

  async getStoryBibles(params?: { novel_id?: string; project_id?: string }) {
    const searchParams = new URLSearchParams();
    if (params?.novel_id) searchParams.set('novel_id', params.novel_id);
    if (params?.project_id) searchParams.set('project_id', params.project_id);
    const qs = searchParams.toString();
    return this.request<any[]>(`/story-bibles${qs ? `?${qs}` : ''}`);
  }

  async createStoryBible(data: {
    novel_id?: string;
    project_id?: string;
    title: string;
    style?: string;
    worldview?: string;
    character_rules?: any[];
    scene_rules?: any[];
    prop_rules?: any[];
    event_timeline?: any[];
    negative_prompt?: string;
    extra_data?: Record<string, any>;
  }) {
    return this.request<any>('/story-bibles', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async generateStoryBible(data: {
    novel_id: string;
    project_id?: string;
    title?: string;
    style?: string;
    negative_prompt?: string;
    model_config_id?: string;
  }) {
    return this.request<any>('/story-bibles/generate-from-novel', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async syncStoryBible(storyBibleId: string, data: any) {
    return this.request<any>(`/story-bibles/${storyBibleId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async syncStoryBibleFromChapter(data: { story_bible_id: string; chapter_id: string }) {
    return this.request<any>('/story-bibles/sync-from-chapter', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async checkStoryBible(data: {
    story_bible_id: string;
    novel_id?: string;
    chapter_id?: string;
    text?: string;
  }) {
    return this.request<any>('/story-bibles/check-consistency', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getStoryBibleStateMachine(storyBibleId: string) {
    return this.request<any>(`/story-bibles/${storyBibleId}/state-machine`);
  }

  async generateStoryBibleStateMachine(storyBibleId: string, data: {
    novel_id?: string;
    persist?: boolean;
  } = {}) {
    return this.request<any>(`/story-bibles/${storyBibleId}/state-machine`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async checkStoryBibleStateMachine(storyBibleId: string, data: {
    novel_id?: string;
    persist?: boolean;
  } = {}) {
    return this.request<any>(`/story-bibles/${storyBibleId}/state-machine/check`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async resolveStoryBibleConflict(data: {
    story_bible_id: string;
    issue_code: string;
    resolution: string;
    resolved_data?: Record<string, any>;
    entity_id?: string;
  }) {
    return this.request<any>('/story-bibles/resolve-conflict', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getStoryBible(storyBibleId: string) {
    return this.request<any>(`/story-bibles/${storyBibleId}`);
  }

  async updateStoryBible(storyBibleId: string, data: any) {
    return this.request<any>(`/story-bibles/${storyBibleId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteStoryBible(storyBibleId: string) {
    return this.request<any>(`/story-bibles/${storyBibleId}`, {
      method: 'DELETE',
    });
  }

  /**
   * 生成分镜
   */
  async generateStoryboard(scriptId: string, data: {
    shot_count?: number;
    style?: string;
    model_config_id?: string;
  }) {
    return this.request<any>('/storyboards/generate', {
      method: 'POST',
      body: JSON.stringify({
        script_id: scriptId,
        shot_count: data.shot_count || 5,
        style: data.style || 'anime',
        model_config_id: data.model_config_id,
      }),
    });
  }

  async getStoryboardTemplates() {
    return this.request<any[]>('/storyboards/templates');
  }

  async generateSmartStoryboard(data: {
    novel_id: string;
    chapter_id?: string;
    script_id?: string;
    template_id?: string;
    shot_count?: number;
    style?: string;
    title?: string;
    story_bible_id?: string;
    project_id?: string;
    use_ai_refine?: boolean;
    use_consistency_context?: boolean;
    model_config_id?: string;
  }) {
    return this.request<any>('/storyboards/generate-smart', {
      method: 'POST',
      body: JSON.stringify({
        style: 'anime',
        use_ai_refine: false,
        use_consistency_context: true,
        ...data,
      }),
    });
  }

  /**
   * AI 辅助：生成台词和镜头建议
   */
  async generateDialogue(data: {
    scene_description: string;
    chapter_content?: string;
    script_content?: string;
    current_dialogue?: string;
    speaker_name?: string;
    dialogue_mode?: 'extract' | 'polish' | 'rewrite' | 'suggest';
    characters?: any[];
    style?: string;
    novel_id?: string;
    chapter_id?: string;
    script_id?: string;
    storyboard_id?: string;
    shot_id?: string;
  }) {
    return this.request<any>('/storyboard-ai/generate-dialogue', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /**
   * AI 批量生成分镜镜头
   */
  async generateShotsAI(data: {
    storyboard_id: string;
    scene_description: string;
    shot_count?: number;
    style?: string;
    chapter_content?: string;
    script_content?: string;
    characters?: any[];
  }) {
    return this.request<any>('/storyboard-ai/generate-shots', {
      method: 'POST',
      body: JSON.stringify({
        storyboard_id: data.storyboard_id,
        scene_description: data.scene_description,
        shot_count: data.shot_count || 5,
        style: data.style || 'anime',
        chapter_content: data.chapter_content,
        script_content: data.script_content,
        characters: data.characters,
      }),
    });
  }

  // ========== OpenAI 相关 ==========

  /**
   * OpenAI 聊天补全
   */
  async openAIChat(data: {
    model?: string;
    messages: Array<{ role: string; content: string }>;
    temperature?: number;
    max_tokens?: number;
  }) {
    return this.request<any>('/openai/chat', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /**
   * OpenAI DALL-E 图像生成
   */
  async generateOpenAIImage(data: {
    prompt: string;
    model?: string;
    size?: string;
    quality?: string;
    n?: number;
  }) {
    return this.request<any>('/openai/image', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /**
   * OpenAI 提取角色
   */
  async extractCharactersOpenAI(data: {
    text: string;
    model?: string;
    character_count?: number;
  }) {
    return this.request<any>('/openai/extract', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /**
   * 获取 OpenAI 模型列表
   */
  async getOpenAIModels() {
    return this.request<any[]>('/openai/models');
  }

  // ========== 认证相关 ==========

  /**
   * 用户登录
   */
  async login(username: string, password: string) {
    const response = await this.request<{
      success: boolean;
      message: string;
      user?: any;
      access_token?: string;
    }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });

    if (response.access_token) {
      this.setToken(response.access_token);
    }

    return response;
  }

  /**
   * 用户注册
   */
  async register(username: string, email: string, password: string) {
    const response = await this.request<{
      success: boolean;
      message: string;
      user?: any;
      access_token?: string;
    }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, email, password }),
    });

    if (response.access_token) {
      this.setToken(response.access_token);
    }

    return response;
  }

  /**
   * 获取当前用户信息
   */
  async getCurrentUser() {
    return this.request<any>('/auth/me');
  }

  // ========== 批量任务相关 ==========

  async createBatchJob(params: {
    job_type: 'image' | 'tts' | 'video';
    title?: string;
    shot_ids: string[];
    storyboard_id?: string;
    workflow_id?: string;
    extra_data?: Record<string, any>;
  }) {
    return this.request<any>('/batch/create', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async getBatchJobs(params?: {
    job_type?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }) {
    const searchParams = new URLSearchParams();
    if (params?.job_type) searchParams.set('job_type', params.job_type);
    if (params?.status) searchParams.set('status', params.status);
    if (params?.limit !== undefined) searchParams.set('limit', String(params.limit));
    if (params?.offset !== undefined) searchParams.set('offset', String(params.offset));
    const qs = searchParams.toString();
    return this.request<any>(`/batch/list${qs ? `?${qs}` : ''}`);
  }

  async getBatchJob(jobId: string) {
    return this.request<any>(`/batch/${jobId}`);
  }

  async getBatchJobProgress(jobId: string) {
    return this.request<any>(`/batch/${jobId}/progress`);
  }

  async getBatchJobItems(jobId: string, status?: string) {
    const searchParams = new URLSearchParams();
    if (status) searchParams.set('status', status);
    const qs = searchParams.toString();
    return this.request<any>(`/batch/${jobId}/items${qs ? `?${qs}` : ''}`);
  }

  async startBatchJob(jobId: string) {
    return this.request<any>(`/batch/${jobId}/start`, {
      method: 'POST',
    });
  }

  async pauseBatchJob(jobId: string) {
    return this.request<any>(`/batch/${jobId}/pause`, {
      method: 'POST',
    });
  }

  async resumeBatchJob(jobId: string) {
    return this.request<any>(`/batch/${jobId}/resume`, {
      method: 'POST',
    });
  }

  async retryFailedBatchJob(jobId: string) {
    return this.request<any>(`/batch/${jobId}/retry-failed`, {
      method: 'POST',
    });
  }

  async skipBatchItem(jobId: string, itemId: string) {
    return this.request<any>(`/batch/${jobId}/skip/${itemId}`, {
      method: 'POST',
    });
  }

  async updateBatchItem(jobId: string, itemId: string, data: {
    status?: string;
    image_url?: string;
    video_url?: string;
    audio_url?: string;
    image_job_id?: string;
    video_job_id?: string;
    tts_job_id?: string;
    error_message?: string;
  }) {
    return this.request<any>(`/batch/${jobId}/items/${itemId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteBatchJob(jobId: string) {
    return this.request<void>(`/batch/${jobId}`, {
      method: 'DELETE',
    });
  }

  // ========== 版本管理相关 ==========

  /**
   * 获取资源的所有版本历史
   */
  async getVersions(resourceType: string, resourceId: string, limit: number = 50) {
    return this.request<any[]>(`/versions/${resourceType}/${resourceId}?limit=${limit}`);
  }

  /**
   * 获取版本数量
   */
  async getVersionCount(resourceType: string, resourceId: string) {
    return this.request<{ count: number }>(`/versions/count/${resourceType}/${resourceId}`);
  }

  /**
   * 获取版本详情
   */
  async getVersionDetail(versionId: string) {
    return this.request<any>(`/versions/detail/${versionId}`);
  }

  /**
   * 创建新版本
   */
  async createVersion(resourceType: string, resourceId: string, data: {
    version_label?: string;
    change_summary?: string;
  }) {
    return this.request<any>(`/versions/${resourceType}/${resourceId}`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /**
   * 回滚到指定版本
   */
  async rollbackVersion(versionId: string, confirm: boolean = true) {
    return this.request<any>(`/versions/${versionId}/rollback`, {
      method: 'POST',
      body: JSON.stringify({ confirm }),
    });
  }

  /**
   * 获取版本差异
   */
  async getVersionDiff(versionId: string, compareWithCurrent: boolean = false) {
    const qs = compareWithCurrent ? '?compare_with_current=true' : '';
    return this.request<any>(`/versions/${versionId}/diff${qs}`);
  }

  /**
   * 删除版本
   */
  async deleteVersion(versionId: string) {
    return this.request<any>(`/versions/${versionId}`, {
      method: 'DELETE',
    });
  }

  /**
   * 获取版本规则
   */
  async getVersionRule(resourceType: string) {
    return this.request<any>(`/versions/rules/${resourceType}`);
  }
}

// 导出单例
export const apiClient = new ApiClient(API_BASE_URL);
export default apiClient;

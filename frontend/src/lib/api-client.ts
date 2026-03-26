/**
 * API 客户端
 * 统一处理前后端API通信
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

const TOKEN_KEY = 'auth_token';

// ========== 类型定义 ==========

type ApiError = {
  detail?: string;
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
  created_at: string;
  updated_at: string;
};

type TTSGenerateParams = {
  text: string;
  model?: string;
  voice: string;
  speed: number;
  title?: string;
  api_key: string;
  shot_id?: string;
};

type TTSGenerateResponse = {
  task_id: string;
  job_id: string;
  status: string;
  message: string;
};

type SynthesisJob = {
  id: string;
  task_id?: string;
  title?: string;
  model_name?: string;
  video_url?: string;
  audio_url?: string;
  status: string;
  progress: number;
  output_url?: string;
  cover_url?: string;
  duration_seconds?: number;
  error_message?: string;
  created_at: string;
  updated_at: string;
};

type SynthesisGenerateParams = {
  video_url: string;
  audio_url: string;
  title?: string;
  api_key: string;
};

type SynthesisGenerateResponse = {
  task_id: string;
  job_id: string;
  status: string;
  message: string;
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
      'Content-Type': 'application/json',
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
        const message = error?.detail || error?.message || `HTTP ${response.status}`;
        throw new Error(message);
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
  
  async generateCodingPlan(requirement: string, apiKey: string, model: string = 'qwen-coder-plus') {
    return this.request<any>('/coding-plan/generate', {
      method: 'POST',
      body: JSON.stringify({ requirement, api_key: apiKey, model }),
    });
  }
  
  async generateNovelWithPlan(prompt: string, apiKey: string, model: string = 'qwen-coder-plus') {
    return this.request<any>('/coding-plan/novel', {
      method: 'POST',
      body: JSON.stringify({ prompt, api_key: apiKey, model }),
    });
  }
  
  async autoGenerate(userInput: string, generateType: string, apiKey: string) {
    return this.request<any>('/coding-plan/auto-generate', {
      method: 'POST',
      body: JSON.stringify({ 
        user_input: userInput, 
        generate_type: generateType,
        api_key: apiKey,
      }),
    });
  }
  
  // ========== 角色管理相关 ==========
  
  async getCharacters() {
    return this.request<any[]>('/characters');
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
  
  // ========== 分镜管理相关 ==========

  async getStoryboards(scriptId?: string) {
    if (scriptId) {
      return this.request<any[]>(`/storyboards/script/${scriptId}`);
    }
    return this.request<any[]>('/storyboards');
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

  async generateCharacterAvatar(characterId: string, params: { prompt: string }) {
    return this.request<any>('/images/generate', {
      method: 'POST',
      body: JSON.stringify({
        prompt: params.prompt,
        model: 'doubao-seedream-3-0',
        extra_data: { character_id: characterId },
      }),
    });
  }

  async getImageJobStatus(taskId: string) {
    return this.request<any>(`/images/status/${taskId}`);
  }

  async generateShotImage(shotId: string) {
    return this.request<any>(`/shots/${shotId}/generate-image`, {
      method: 'POST',
    });
  }

  async generateShotsImages(storyboardId: string, shotIds: string[]) {
    return this.request<any>(`/storyboards/${storyboardId}/shots/generate-images`, {
      method: 'POST',
      body: JSON.stringify(shotIds),
    });
  }

  async generateVideo(params: any) {
    return this.request<any>('/video/generate', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }
  
  async getVideoJobs() {
    return this.request<any[]>('/video/jobs');
  }
  
  async getVideoJobStatus(jobId: string) {
    return this.request<any>(`/video/jobs/${jobId}`);
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

  // ========== 音视频合成相关 ==========

  async getSynthesisJobs() {
    return this.request<SynthesisJob[]>('/synthesis/jobs');
  }

  async generateSynthesis(params: SynthesisGenerateParams) {
    return this.request<SynthesisGenerateResponse>('/synthesis/generate', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  // ========== Dashboard 统计 ==========

  async getDashboardStats() {
    return this.request<any>('/dashboard/stats');
  }

  // ========== 使用统计 ==========

  async getUsageStats(period: string = 'day') {
    return this.request<any>(`/usage-stats?period=${period}`);
  }

  // ========== Workflow 工作流相关 ==========

  async getWorkflowSteps() {
    return this.request<any>('/workflow/steps');
  }

  async startWorkflow(params: { title?: string; novel_id?: string }) {
    return this.request<any>('/workflow/start', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async getWorkflowStatus(
    workflowId: string,
    params?: { novel_id?: string; chapter_id?: string; script_id?: string }
  ) {
    const searchParams = new URLSearchParams();
    if (params?.novel_id) searchParams.set('novel_id', params.novel_id);
    if (params?.chapter_id) searchParams.set('chapter_id', params.chapter_id);
    if (params?.script_id) searchParams.set('script_id', params.script_id);
    const qs = searchParams.toString();
    return this.request<any>(`/workflow/status/${workflowId}${qs ? `?${qs}` : ''}`);
  }

  async concatenateVideos(
    workflowId: string,
    params: {
      video_job_ids: string[];
      tts_job_ids?: string[];
      title?: string;
    }
  ) {
    return this.request<any>(`/workflow/concatenate/${workflowId}`, {
      method: 'POST',
      body: JSON.stringify(params),
    });
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
        model: 'qwen-long',
        max_tokens: 8000,
        temperature: 0.8,
      }),
    });
  }

  /**
   * 生成章节
   */
  async generateChapter(novelId: string, data: {
    chapter_title: string;
    prev_chapter_content?: string;
  }) {
    return this.request<any>('/chapters/generate', {
      method: 'POST',
      body: JSON.stringify({ novel_id: novelId, ...data }),
    });
  }

  /**
   * 提取角色
   */
  async extractCharacters(data: {
    text: string;
    novel_id?: string;
    character_count?: number;
  }) {
    return this.request<any>('/characters/extract', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /**
   * 生成分镜
   */
  async generateStoryboard(scriptId: string, data: {
    shot_count?: number;
    style?: string;
  }) {
    return this.request<any>('/storyboards/generate', {
      method: 'POST',
      body: JSON.stringify({
        script_id: scriptId,
        shot_count: data.shot_count || 5,
        style: data.style || 'anime',
      }),
    });
  }

  /**
   * AI 辅助：生成台词和镜头建议
   */
  async generateDialogue(data: {
    scene_description: string;
    chapter_content?: string;
    characters?: any[];
    style?: string;
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
}

// 导出单例
export const apiClient = new ApiClient(API_BASE_URL);
export default apiClient;
/**
 * API 客户端
 * 统一处理前后端API通信
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

class ApiClient {
  private baseUrl: string;
  
  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }
  
  private async request<T>(
    endpoint: string, 
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    
    const config: RequestInit = {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    };
    
    try {
      const response = await fetch(url, config);
      
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || `HTTP ${response.status}`);
      }
      
      return response.json();
    } catch (error) {
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
  
  async generateStoryboard(sceneDescription: string, apiKey: string, model: string = 'qwen-coder-plus') {
    return this.request<any>('/coding-plan/storyboard', {
      method: 'POST',
      body: JSON.stringify({ 
        scene_description: sceneDescription, 
        api_key: apiKey, 
        model 
      }),
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
  
  // ========== 小说/剧本相关 ==========
  
  async getNovels() {
    return this.request<any[]>('/novels');
  }
  
  async createNovel(novel: any) {
    return this.request<any>('/novels', {
      method: 'POST',
      body: JSON.stringify(novel),
    });
  }
  
  async getScripts() {
    return this.request<any[]>('/scripts');
  }
  
  async createScript(script: any) {
    return this.request<any>('/scripts', {
      method: 'POST',
      body: JSON.stringify(script),
    });
  }
  
  // ========== 视频生成相关 ==========
  
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
  
  // ========== Dashboard 统计 ==========
  
  async getDashboardStats() {
    return this.request<any>('/dashboard/stats');
  }
  
  // ========== 使用统计 ==========
  
  async getUsageStats(period: string = 'day') {
    return this.request<any>(`/usage-stats?period=${period}`);
  }
}

// 导出单例
export const apiClient = new ApiClient(API_BASE_URL);
export default apiClient;
/**
 * API客户端配置
 * 基于axios的HTTP客户端，用于与后端API通信
 */

import axios from 'axios';

// API基础URL - 开发环境使用本地后端
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

// 创建axios实例
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器 - 自动添加JWT令牌
apiClient.interceptors.request.use(
  (config) => {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('access_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器 - 统一错误处理
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token过期，清除本地存储
      if (typeof window !== 'undefined') {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        // 可以在这里添加跳转登录页的逻辑
      }
    }
    return Promise.reject(error);
  }
);

// 认证API
export const authApi = {
  login: (data: { username: string; password: string }) =>
    apiClient.post('/v1/auth/login', 
      new URLSearchParams({
        username: data.username,
        password: data.password,
      }).toString(),
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      }
    ),
  
  register: (data: { username: string; email: string; password: string; nickname?: string }) =>
    apiClient.post('/v1/auth/register/', data),
  
  logout: () =>
    apiClient.post('/v1/auth/logout/'),
  
  refresh: (refreshToken: string) =>
    apiClient.post('/v1/auth/refresh/', { refresh_token: refreshToken }),
  
  me: () =>
    apiClient.get('/v1/users/me/'),
};

// 用户API
export const userApi = {
  getProfile: () =>
    apiClient.get('/v1/users/me/'),
  
  updateProfile: (data: { username?: string; email?: string; avatar?: string }) =>
    apiClient.patch('/v1/users/me/', data),
  
  changePassword: (data: { old_password: string; new_password: string }) =>
    apiClient.post('/v1/users/change-password/', data),
};

// 小说API
export const novelApi = {
  getList: () =>
    apiClient.get('/v1/novels/'),
  
  getMyList: (params?: { page?: number; limit?: number; status?: string }) =>
    apiClient.get('/v1/novels/', { params }),
  
  getById: (id: string) =>
    apiClient.get(`/v1/novels/${id}`),
  
  create: (data: { title: string; description?: string; cover_image?: string; genre?: string }) =>
    apiClient.post('/v1/novels/', data),
  
  update: (id: string, data: { title: string; description?: string; cover_image?: string; genre?: string; status?: string }) =>
    apiClient.put(`/v1/novels/${id}`, data),
  
  delete: (id: string) =>
    apiClient.delete(`/v1/novels/${id}`),
  
  publish: (id: string) =>
    apiClient.post(`/v1/novels/${id}/publish`),
  
  getChapters: (id: string) =>
    apiClient.get(`/v1/novels/${id}/chapters`),
  
  createChapter: (novelId: string, data: { title: string; content?: string; chapter_number?: number }) =>
    apiClient.post(`/v1/novels/${novelId}/chapters`, data),
  
  getChapter: (novelId: string, chapterId: string) =>
    apiClient.get(`/v1/novels/${novelId}/chapters/${chapterId}`),
  
  updateChapter: (novelId: string, chapterId: string, data: { title?: string; content?: string; chapter_number?: number }) =>
    apiClient.put(`/v1/novels/${novelId}/chapters/${chapterId}`, data),
  
  deleteChapter: (novelId: string, chapterId: string) =>
    apiClient.delete(`/v1/novels/${novelId}/chapters/${chapterId}`),
  
  generateCover: (data: { title: string; description?: string; genre?: string }) =>
    apiClient.post('/v1/novels/generate-cover/', data),
};

// 剧本API
export const scriptApi = {
  getList: (params?: { novel_id?: string; chapter_id?: string; status?: string; skip?: number; limit?: number }) =>
    apiClient.get('/v1/scripts/', { params }),
  
  getById: (id: string) =>
    apiClient.get(`/v1/scripts/${id}`),
  
  create: (data: { title: string; novel_id: string; content?: string }) =>
    apiClient.post('/v1/scripts/', data),
  
  update: (id: string, data: Partial<{ title: string; content: string }>) =>
    apiClient.patch(`/v1/scripts/${id}`),
  
  delete: (id: string) =>
    apiClient.delete(`/v1/scripts/${id}`),
  
  generate: (data: { novel_id: string; prompt?: string }) =>
    apiClient.post('/v1/scripts/generate/', data),
  
  // 场景相关
  getScenes: (scriptId: string) =>
    apiClient.get(`/v1/scripts/${scriptId}/scenes/`),
  
  createScene: (scriptId: string, data: { 
    title: string; 
    content?: string; 
    scene_number?: number;
    description?: string;
    location?: string;
    time_of_day?: string;
    characters?: string[];
    dialogue?: Record<string, unknown>;
    action_description?: string;
    camera_direction?: string;
  }) =>
    apiClient.post(`/v1/scripts/${scriptId}/scenes/`, data),
  
  updateScene: (scriptId: string, sceneId: string, data: Partial<{ 
    title: string; 
    content: string;
    scene_number?: number;
    description?: string;
    location?: string;
    time_of_day?: string;
    characters?: string[];
    dialogue?: Record<string, unknown>;
    action_description?: string;
    camera_direction?: string;
  }>) =>
    apiClient.patch(`/v1/scripts/${scriptId}/scenes/${sceneId}`),
  
  deleteScene: (scriptId: string, sceneId: string) =>
    apiClient.delete(`/v1/scripts/${scriptId}/scenes/${sceneId}`),
  
  // 场景视频生成
  generateSceneVideo: (sceneId: string, data: { style?: string; duration?: number }) =>
    apiClient.post(`/v1/scripts/scenes/${sceneId}/generate-video`, data),
};

// 角色API
export const characterApi = {
  getList: (novelId?: string) =>
    apiClient.get('/v1/characters/', { params: { novel_id: novelId } }),
  
  getById: (id: string) =>
    apiClient.get(`/v1/characters/${id}`),
  
  create: (data: { name: string; novel_id: string; description?: string; avatar?: string }) =>
    apiClient.post('/v1/characters/', data),
  
  update: (id: string, data: Partial<{ name: string; description: string; avatar: string }>) =>
    apiClient.put(`/v1/characters/${id}`, data),
  
  delete: (id: string) =>
    apiClient.delete(`/v1/characters/${id}`),
  
  generateAvatar: (id: string) =>
    apiClient.post(`/v1/characters/${id}/generate-avatar`),
};

// 视频API
export const videoApi = {
  getList: () =>
    apiClient.get('/v1/videos/'),
  
  getById: (id: string) =>
    apiClient.get(`/v1/videos/${id}`),
  
  create: (data: { title: string; script_id: string; settings?: object }) =>
    apiClient.post('/v1/videos/', data),
  
  delete: (id: string) =>
    apiClient.delete(`/v1/videos/${id}`),
  
  generate: (id: string) =>
    apiClient.post(`/v1/videos/${id}/generate`),
  
  getStatus: (id: string) =>
    apiClient.get(`/v1/videos/${id}/status`),
};

// 默认导出
export default apiClient;

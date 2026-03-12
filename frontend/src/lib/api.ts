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

// 响应拦截器 - 处理令牌刷新和错误
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // 如果是401且没有重试过，尝试刷新令牌
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          const response = await axios.post(`${API_BASE_URL}/v1/auth/refresh`, null, {
            headers: { Authorization: `Bearer ${refreshToken}` },
          });

          const { access_token, refresh_token: new_refresh_token } = response.data;
          localStorage.setItem('access_token', access_token);
          localStorage.setItem('refresh_token', new_refresh_token);

          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return apiClient(originalRequest);
        }
      } catch (refreshError) {
        // 刷新失败，清除令牌并跳转登录
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

// 导出API客户端
export default apiClient;

// 认证相关API
export const authApi = {
  login: (data: { username: string; password: string }) =>
    apiClient.post('/v1/auth/login', data),
  register: (data: { email: string; username: string; password: string; nickname?: string }) =>
    apiClient.post('/v1/auth/register', data),
  logout: () => apiClient.post('/v1/auth/logout'),
  getCurrentUser: () => apiClient.get('/v1/auth/me'),
  changePassword: (data: { old_password: string; new_password: string }) =>
    apiClient.post('/v1/auth/password/change', data),
};

// 用户相关API
export const userApi = {
  getProfile: () => apiClient.get('/v1/users/me'),
  getMyProfile: () => apiClient.get('/v1/users/me/profile'),
  getQuota: () => apiClient.get('/v1/users/me/quota'),
  updateProfile: (data: { nickname?: string; avatar?: string; phone?: string }) =>
    apiClient.put('/v1/users/me', data),
};

// 小说相关API
export const novelApi = {
  list: (params?: { page?: number; limit?: number; genre?: string; search?: string }) =>
    apiClient.get('/v1/novels', { params }),
  getMyList: (params?: { page?: number; limit?: number; status?: string }) =>
    apiClient.get('/v1/novels/my', { params }),
  get: (id: string) => apiClient.get(`/v1/novels/${id}`),
  create: (data: { title: string; description?: string; genre?: string; cover_image?: string }) =>
    apiClient.post('/v1/novels', data),
  update: (id: string, data: { title?: string; description?: string; genre?: string; status?: string }) =>
    apiClient.put(`/v1/novels/${id}`, data),
  delete: (id: string) => apiClient.delete(`/v1/novels/${id}`),
  publish: (id: string) => apiClient.post(`/v1/novels/${id}/publish`),
  getChapters: (novelId: string) => apiClient.get(`/v1/novels/${novelId}/chapters`),
  createChapter: (novelId: string, data: { title: string; content?: string; chapter_number: number }) =>
    apiClient.post(`/v1/novels/${novelId}/chapters`, data),
  updateChapter: (novelId: string, chapterId: string, data: { title?: string; content?: string }) =>
    apiClient.put(`/v1/novels/${novelId}/chapters/${chapterId}`, data),
  deleteChapter: (novelId: string, chapterId: string) =>
    apiClient.delete(`/v1/novels/${novelId}/chapters/${chapterId}`),
};

// 剧本相关API
export const scriptApi = {
  list: (params?: { novel_id?: string; page?: number; limit?: number }) =>
    apiClient.get('/v1/scripts', { params }),
  get: (id: string) => apiClient.get(`/v1/scripts/${id}`),
  create: (data: { title: string; novel_id?: string; chapter_id?: string }) =>
    apiClient.post('/v1/scripts', data),
  update: (id: string, data: { title?: string; content?: object; status?: string }) =>
    apiClient.put(`/v1/scripts/${id}`, data),
  delete: (id: string) => apiClient.delete(`/v1/scripts/${id}`),
  getScenes: (scriptId: string) => apiClient.get(`/v1/scripts/${scriptId}/scenes`),
  createScene: (scriptId: string, data: object) =>
    apiClient.post(`/v1/scripts/${scriptId}/scenes`, data),
  updateScene: (scriptId: string, sceneId: string, data: object) =>
    apiClient.put(`/v1/scripts/${scriptId}/scenes/${sceneId}`, data),
  deleteScene: (scriptId: string, sceneId: string) =>
    apiClient.delete(`/v1/scripts/${scriptId}/scenes/${sceneId}`),
};
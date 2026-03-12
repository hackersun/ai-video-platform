// API客户端配置
import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from "axios";

// API基础配置
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// 创建axios实例
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

// 请求拦截器 - 添加Token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器 - 错误处理
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // 401错误 - Token过期
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        // 尝试刷新Token
        const refreshToken = localStorage.getItem("refresh_token");
        if (refreshToken) {
          const response = await axios.post(`${API_BASE_URL}/api/auth/refresh`, {
            refresh_token: refreshToken,
          });

          const { access_token } = response.data;
          localStorage.setItem("access_token", access_token);

          // 重试原请求
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return apiClient(originalRequest);
        }
      } catch (refreshError) {
        // 刷新失败，清除Token并跳转登录
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        window.location.href = "/login";
        return Promise.reject(refreshError);
      }
    }

    // 统一错误处理
    const errorMessage = handleApiError(error);
    console.error("API Error:", errorMessage);
    
    return Promise.reject({
      ...error,
      message: errorMessage,
    });
  }
);

// 错误处理函数
function handleApiError(error: AxiosError): string {
  if (error.response) {
    const { status, data } = error.response;
    
    switch (status) {
      case 400:
        return (data as any)?.detail || "请求参数错误";
      case 401:
        return "登录已过期，请重新登录";
      case 403:
        return "没有权限执行此操作";
      case 404:
        return "请求的资源不存在";
      case 422:
        return (data as any)?.detail || "数据验证失败";
      case 500:
        return "服务器内部错误";
      default:
        return (data as any)?.detail || `请求失败 (${status})`;
    }
  } else if (error.request) {
    return "网络连接失败，请检查网络";
  } else {
    return error.message || "未知错误";
  }
}

// API方法封装
export const api = {
  get: <T>(url: string, params?: object) => 
    apiClient.get<T>(url, { params }).then((res) => res.data),
  
  post: <T>(url: string, data?: object) => 
    apiClient.post<T>(url, data).then((res) => res.data),
  
  put: <T>(url: string, data?: object) => 
    apiClient.put<T>(url, data).then((res) => res.data),
  
  patch: <T>(url: string, data?: object) => 
    apiClient.patch<T>(url, data).then((res) => res.data),
  
  delete: <T>(url: string) => 
    apiClient.delete<T>(url).then((res) => res.data),
};

export default apiClient;

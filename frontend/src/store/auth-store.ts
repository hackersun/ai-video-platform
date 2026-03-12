// 认证状态管理 - Zustand
import { create } from "zustand";
import { persist } from "zustand/middleware";
import { api } from "@/lib/api";

// 用户类型
export interface User {
  id: string;
  email: string;
  username: string;
  avatar?: string;
  created_at: string;
}

// 认证状态
interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  
  // Actions
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, username: string) => Promise<void>;
  logout: () => void;
  fetchUser: () => Promise<void>;
  updateUser: (data: Partial<User>) => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      isLoading: false,

      // 登录
      login: async (email: string, password: string) => {
        set({ isLoading: true });
        try {
          const response = await api.post<{
            access_token: string;
            refresh_token: string;
            user: User;
          }>("/api/auth/login", {
            email,
            password,
          });

          // 存储Token
          localStorage.setItem("access_token", response.access_token);
          localStorage.setItem("refresh_token", response.refresh_token);

          set({
            user: response.user,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      // 注册
      register: async (email: string, password: string, username: string) => {
        set({ isLoading: true });
        try {
          const response = await api.post<{
            access_token: string;
            refresh_token: string;
            user: User;
          }>("/api/auth/register", {
            email,
            password,
            username,
          });

          // 存储Token
          localStorage.setItem("access_token", response.access_token);
          localStorage.setItem("refresh_token", response.refresh_token);

          set({
            user: response.user,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      // 登出
      logout: () => {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        set({
          user: null,
          isAuthenticated: false,
        });
      },

      // 获取用户信息
      fetchUser: async () => {
        try {
          const response = await api.get<User>("/api/users/me");
          set({
            user: response,
            isAuthenticated: true,
          });
        } catch (error) {
          // Token无效，清除状态
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          set({
            user: null,
            isAuthenticated: false,
          });
        }
      },

      // 更新用户信息
      updateUser: async (data: Partial<User>) => {
        const response = await api.patch<User>("/api/users/me", data);
        set({ user: response });
      },
    }),
    {
      name: "auth-storage",
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
);

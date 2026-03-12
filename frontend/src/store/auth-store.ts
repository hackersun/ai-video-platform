// 认证状态管理 - Zustand
import { create } from "zustand";
import { persist } from "zustand/middleware";
import { authApi } from "@/lib/api";

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
    (set) => ({
      user: null,
      isAuthenticated: false,
      isLoading: false,

      // 登录
      login: async (email: string, password: string) => {
        set({ isLoading: true });
        try {
          const response = await authApi.login({ username: email, password });

          // 存储Token
          localStorage.setItem("access_token", response.data.access_token);
          localStorage.setItem("refresh_token", response.data.refresh_token);

          set({
            user: response.data.user,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (err) {
          set({ isLoading: false });
          throw err;
        }
      },

      // 注册
      register: async (email: string, password: string, username: string) => {
        set({ isLoading: true });
        try {
          const response = await authApi.register({
            email,
            password,
            username,
          });

          // 存储Token
          localStorage.setItem("access_token", response.data.access_token);
          localStorage.setItem("refresh_token", response.data.refresh_token);

          set({
            user: response.data.user,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (err) {
          set({ isLoading: false });
          throw err;
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
          const response = await authApi.me();
          set({
            user: response.data,
            isAuthenticated: true,
          });
        } catch (err) {
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
        const response = await authApi.me();
        set({ user: response.data });
      },
    }),
    {
      name: "auth-storage",
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
);

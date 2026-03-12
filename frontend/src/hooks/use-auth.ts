// 认证Hook
import { useEffect } from "react";
import { useAuthStore } from "@/store/auth-store";

export function useAuth() {
  const { user, isAuthenticated, isLoading, fetchUser, logout } = useAuthStore();

  // 初始化时检查登录状态
  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token && !isAuthenticated) {
      fetchUser();
    }
  }, [fetchUser, isAuthenticated]);

  return {
    user,
    isAuthenticated,
    isLoading,
    logout,
  };
}

// 检查是否登录
export function useRequireAuth() {
  const { isAuthenticated, isLoading } = useAuth();

  return {
    isAuthenticated,
    isLoading,
    shouldRedirect: !isLoading && !isAuthenticated,
  };
}

/**
 * 认证状态与重定向管理
 * 提供全局认证状态、自动过期检测和 401 自动跳转登录页功能
 */
'use client';

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';

// ========== 类型定义 ==========

type User = {
  id: string;
  username: string;
  email: string;
  is_active?: boolean;
  created_at?: string;
};

type AuthResponse = {
  success: boolean;
  message: string;
  detail?: string;
  user?: User;
  access_token?: string;
};

type AuthContextValue = {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<AuthResponse>;
  logout: (redirect?: boolean) => void;
  register: (username: string, email: string, password: string) => Promise<AuthResponse>;
  getToken: () => string | null;
  refreshUser: () => Promise<void>;
};

async function readAuthResponse(response: Response, fallbackMessage: string): Promise<AuthResponse> {
  const contentType = response.headers.get('content-type')?.toLowerCase() || '';
  if (!contentType.includes('application/json')) {
    return { success: false, message: fallbackMessage };
  }
  try {
    return await response.json();
  } catch {
    return { success: false, message: fallbackMessage };
  }
}

const TOKEN_KEY = 'auth_token';
const USER_KEY = 'user';
const PUBLIC_PATHS = ['/', '/login', '/register', '/forgot-password', '/reset-password'];

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.some(path => pathname === path || pathname.startsWith(`${path}/`));
}

// ========== JWT 工具函数 ==========

/** 解析 JWT payload（不验证签名） */
function parseJwtPayload(token: string): { sub?: string; exp?: number } | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = parts[1];
    // atob for browser, Buffer for Node
    const decoded = typeof window !== 'undefined'
      ? atob(payload.replace(/-/g, '+').replace(/_/g, '/'))
      : Buffer.from(payload.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString();
    return JSON.parse(decoded);
  } catch {
    return null;
  }
}

/** 检查 token 是否已过期 */
export function isTokenExpired(token: string | null): boolean {
  if (!token) return true;
  const payload = parseJwtPayload(token);
  if (!payload || !payload.exp) return false; // 无 exp 字段，不过期
  return Date.now() / 1000 >= payload.exp;
}

// ========== Context ==========

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// ========== Provider ==========

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // 初始化：从 localStorage 恢复认证状态，并检查 token 有效性
  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    const userStr = localStorage.getItem(USER_KEY);

    if (token && userStr) {
      if (isTokenExpired(token)) {
        // Token 已过期，清除并跳转登录
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
        const pathname = window.location.pathname;
        if (!isPublicPath(pathname)) {
          window.location.href = '/login';
        }
        setIsAuthenticated(false);
      } else {
        try {
          const parsedUser = JSON.parse(userStr);
          setUser(parsedUser);
          setIsAuthenticated(true);
        } catch {
          localStorage.removeItem(TOKEN_KEY);
          localStorage.removeItem(USER_KEY);
          setIsAuthenticated(false);
        }
      }
    } else {
      // 无 token，跳转登录
      const pathname = window.location.pathname;
      if (!isPublicPath(pathname)) {
        window.location.href = '/login';
      }
      setIsAuthenticated(false);
    }
    setIsLoading(false);
  }, []);

  const getToken = useCallback((): string | null => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token && isTokenExpired(token)) {
      // 已过期，触发登出
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      setUser(null);
      setIsAuthenticated(false);
      const pathname = window.location.pathname;
      if (!isPublicPath(pathname)) {
        window.location.href = '/login';
      }
      return null;
    }
    return token;
  }, []);

  const refreshUser = useCallback(async () => {
    const token = getToken();
    if (!token) {
      setUser(null);
      setIsAuthenticated(false);
      return;
    }

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const userData = await res.json();
        setUser(userData);
        setIsAuthenticated(true);
        localStorage.setItem(USER_KEY, JSON.stringify(userData));
      } else {
        // /auth/me 返回非200，token 可能无效
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
        setUser(null);
        setIsAuthenticated(false);
        if (!isPublicPath(window.location.pathname)) {
          window.location.href = '/login';
        }
      }
    } catch {
      // 网络错误，保持当前状态
    }
  }, [getToken]);

  const login = useCallback(async (username: string, password: string): Promise<AuthResponse> => {
    const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const data = await readAuthResponse(response, '登录服务暂时不可用，请稍后重试');

    if (data.success && data.access_token && data.user) {
      localStorage.setItem(TOKEN_KEY, data.access_token);
      localStorage.setItem(USER_KEY, JSON.stringify(data.user));
      setUser(data.user);
      setIsAuthenticated(true);
    }
    return data;
  }, []);

  const logout = useCallback((redirect = true) => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setUser(null);
    setIsAuthenticated(false);
    if (redirect) {
      window.location.href = '/login';
    }
  }, []);

  const register = useCallback(
    async (username: string, email: string, password: string): Promise<AuthResponse> => {
      const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
      const response = await fetch(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password }),
      });
      const data = await readAuthResponse(response, '注册服务暂时不可用，请稍后重试');

      if (data.success && data.access_token && data.user) {
        localStorage.setItem(TOKEN_KEY, data.access_token);
        localStorage.setItem(USER_KEY, JSON.stringify(data.user));
        setUser(data.user);
        setIsAuthenticated(true);
      }
      return data;
    },
    []
  );

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
        isLoading,
        login,
        logout,
        register,
        getToken,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// ========== Hook ==========

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  ReactNode,
} from 'react';
import { apiClient } from '@/lib/api-client';

// ========== 类型定义 ==========

type User = {
  id: string;
  username: string;
  email: string;
  is_active: boolean;
  created_at: string;
};

type AuthResponse = {
  success: boolean;
  message: string;
  user?: User;
  access_token?: string;
};

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<AuthResponse>;
  logout: () => void;
  register: (username: string, email: string, password: string) => Promise<AuthResponse>;
};

// ========== Context ==========

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// ========== Provider ==========

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchUser = useCallback(async () => {
    try {
      const userData = await apiClient.getCurrentUser();
      setUser(userData);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  const login = useCallback(async (username: string, password: string): Promise<AuthResponse> => {
    const response = await apiClient.login(username, password);
    if (response.success && response.user) {
      setUser(response.user);
    }
    return response;
  }, []);

  const logout = useCallback(() => {
    apiClient.clearToken();
    setUser(null);
  }, []);

  const register = useCallback(
    async (username: string, email: string, password: string): Promise<AuthResponse> => {
      const response = await apiClient.register(username, email, password);
      if (response.success && response.user) {
        setUser(response.user);
      }
      return response;
    },
    []
  );

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, register }}>
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

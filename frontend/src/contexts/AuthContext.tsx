'use client';

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import {
  authApiBase,
  buildSessionRequest,
  clearLegacySession,
  fetchWithSession,
  getLegacyAccessToken,
} from '@/lib/auth-session';

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
  verification_token?: string;
};

type AuthContextValue = {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<AuthResponse>;
  logout: (redirect?: boolean) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<AuthResponse>;
  getToken: () => string | null;
  refreshUser: () => Promise<void>;
};

const PUBLIC_PATHS = ['/', '/login', '/register', '/forgot-password', '/reset-password', '/verify-email'];
const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.some(path => pathname === path || pathname.startsWith(`${path}/`));
}

function redirectToLoginIfNeeded(): void {
  if (!isPublicPath(window.location.pathname)) window.location.href = '/login';
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const applySignedOutState = useCallback((redirect = true) => {
    clearLegacySession();
    setUser(null);
    setIsAuthenticated(false);
    if (redirect) redirectToLoginIfNeeded();
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const response = await fetchWithSession(`${authApiBase}/auth/me`);
      if (!response.ok) {
        applySignedOutState(true);
        return;
      }
      const currentUser = await response.json() as User;
      setUser(currentUser);
      setIsAuthenticated(true);
    } catch {
      applySignedOutState(false);
    }
  }, [applySignedOutState]);

  useEffect(() => {
    void refreshUser().finally(() => setIsLoading(false));
  }, [refreshUser]);

  const login = useCallback(async (username: string, password: string): Promise<AuthResponse> => {
    const response = await fetch(`${authApiBase}/auth/login`, buildSessionRequest({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    }));
    const data = await response.json() as AuthResponse;
    if (data.success && data.user) {
      clearLegacySession();
      setUser(data.user);
      setIsAuthenticated(true);
    }
    return data;
  }, []);

  const register = useCallback(async (
    username: string,
    email: string,
    password: string,
  ): Promise<AuthResponse> => {
    const response = await fetch(`${authApiBase}/auth/register`, buildSessionRequest({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, email, password }),
    }));
    return response.json();
  }, []);

  const logout = useCallback(async (redirect = true) => {
    try {
      await fetch(`${authApiBase}/auth/logout`, buildSessionRequest({ method: 'POST' }));
    } finally {
      applySignedOutState(false);
      if (redirect) window.location.href = '/login';
    }
  }, [applySignedOutState]);

  return (
    <AuthContext.Provider value={{
      user,
      isAuthenticated,
      isLoading,
      login,
      logout,
      register,
      getToken: getLegacyAccessToken,
      refreshUser,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
}

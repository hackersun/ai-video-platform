/**
 * 带认证的 fetch 封装
 * 自动从 localStorage 获取 token 并添加到 Authorization header
 * 自动处理 401 响应和 token 过期
 */

const TOKEN_KEY = 'auth_token';
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const PUBLIC_PATHS = ['/', '/login', '/register', '/forgot-password', '/reset-password'];

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.some(path => pathname === path || pathname.startsWith(`${path}/`));
}

/** 解析 JWT payload（不验证签名） */
function parseJwtPayload(token: string): { sub?: string; exp?: number } | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = payload + '='.repeat((4 - (payload.length % 4)) % 4);
    const decoded = atob(padded);
    return JSON.parse(decoded);
  } catch {
    return null;
  }
}

/** 检查 token 是否已过期 */
function isTokenExpired(token: string | null): boolean {
  if (!token) return true;
  const payload = parseJwtPayload(token);
  if (!payload || !payload.exp) return false;
  return Date.now() / 1000 >= payload.exp;
}

/** 检查 token 是否有效，无效则清除并跳转 */
function validateAndRedirect(): boolean {
  if (typeof window === 'undefined') return true;

  const token = localStorage.getItem(TOKEN_KEY);
  const pathname = window.location.pathname;

  // 公共路径不需要认证
  const isPublic = isPublicPath(pathname) || pathname.startsWith('/api/');
  if (isPublic) return true;

  if (isTokenExpired(token)) {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem('user');
    window.location.href = '/login';
    return false;
  }
  return true;
}

/**
 * 获取当前有效 token
 * 如果 token 无效或过期，返回 null 并触发跳转
 */
function getValidToken(): string | null {
  const token = localStorage.getItem(TOKEN_KEY);
  if (isTokenExpired(token)) {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem('user');
    const pathname = window.location.pathname;
    if (!isPublicPath(pathname)) {
      window.location.href = '/login';
    }
    return null;
  }
  return token;
}

/** 判断响应是否为 401（未认证） */
async function isUnauthorized(response: Response): Promise<boolean> {
  if (response.status !== 401) return false;
  try {
    const data = await response.clone().json();
    // 某些端点返回 success: false 但 HTTP 状态码不是 401
    if (data.success === false && (data.detail === 'Not authenticated' || data.message?.includes('认证'))) {
      return true;
    }
  } catch {
    // JSON 解析失败，忽略
  }
  return response.status === 401;
}

export async function fetchWithAuth(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  // SSR 阶段直接返回
  if (typeof window === 'undefined') {
    return fetch(url, options);
  }

  const token = getValidToken();
  if (token === null) {
    // token 过期或无效，等待跳转
    return new Response(JSON.stringify({ detail: 'Token expired, redirecting...' }), { status: 401 });
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };
  headers['Authorization'] = `Bearer ${token}`;

  const response = await fetch(url, {
    ...options,
    headers,
  });

  // 处理 401：清除 token 并跳转登录页
  if (await isUnauthorized(response)) {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem('user');
    const pathname = window.location.pathname;
    if (!isPublicPath(pathname)) {
      window.location.href = '/login';
    }
  }

  return response;
}

/**
 * 带认证的 fetch，返回解析后的 JSON
 * 401 时自动抛出错误（调用方可用 try/catch 捕获）
 */
export async function fetchJsonWithAuth<T = any>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetchWithAuth(url, options);

  if (!response.ok) {
    try {
      const error = await response.json();
      throw new Error(error.detail || error.message || `HTTP ${response.status}`);
    } catch (e) {
      if (e instanceof Error && (e.message.includes('expired') || e.message.includes('redirecting'))) {
        throw e; // token 过期，等跳转
      }
      throw new Error(`HTTP ${response.status}`);
    }
  }
  return response.json();
}

/** 导出工具函数供其他模块使用 */
export { getValidToken, isTokenExpired, parseJwtPayload };

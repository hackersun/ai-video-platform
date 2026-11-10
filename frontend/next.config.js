/** @type {import('next').NextConfig} */
const apiProxyTarget = (process.env.API_PROXY_TARGET || 'http://127.0.0.1:8000').replace(/\/+$/, '')

const nextConfig = {
  ...(process.env.NEXT_DIST_DIR ? { distDir: process.env.NEXT_DIST_DIR } : {}),
  async redirects() {
    // 旧入口统一收敛：保留可访问（永不 404），跳转到唯一的规范入口。
    return [
      { source: '/teams', destination: '/settings/team', permanent: false },
      { source: '/model-settings', destination: '/llm-config', permanent: false },
    ]
  },
  async rewrites() {
    return [
      {
        source: '/api/v1/workflow',
        destination: `${apiProxyTarget}/api/v1/workflow/`,
      },
      {
        source: '/api/v1/:path*',
        destination: `${apiProxyTarget}/api/v1/:path*`,
      },
    ]
  },
}

module.exports = nextConfig

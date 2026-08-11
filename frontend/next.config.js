/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  ...(process.env.NEXT_DIST_DIR ? { distDir: process.env.NEXT_DIST_DIR } : {}),
  turbopack: {
    root: __dirname,
  },
}

module.exports = nextConfig

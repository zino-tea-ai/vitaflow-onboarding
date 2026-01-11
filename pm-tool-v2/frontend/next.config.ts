import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  // 跳过 TypeScript 构建检查（部署用）
  typescript: {
    ignoreBuildErrors: true,
  },

  // API 代理配置 - 将 /api 请求转发到 FastAPI 后端
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8004/api/:path*',
      },
    ]
  },

  // 图片域名配置
  images: {
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
        port: '8004',
      },
    ],
  },
}

export default nextConfig

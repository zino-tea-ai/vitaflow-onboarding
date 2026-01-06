import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Turbopack - Next.js 16 已稳定为顶级配置
  turbopack: {},

  // 图片优化
  images: {
    formats: ["image/avif", "image/webp"],
    deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048, 3840],
  },

  // 启用严格模式，帮助发现潜在问题
  reactStrictMode: true,

  // 优化生产构建
  poweredByHeader: false,
};

export default nextConfig;

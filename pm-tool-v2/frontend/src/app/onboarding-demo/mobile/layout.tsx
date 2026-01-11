import type { Metadata, Viewport } from "next";

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: 'cover', // 支持 iPhone 刘海屏
}

export const metadata: Metadata = {
  title: "VitaFlow",
  description: "Your AI Nutrition Companion",
  appleWebApp: {
    capable: true,
    statusBarStyle: 'default',
    title: 'VitaFlow',
  },
  formatDetection: {
    telephone: false,
  },
  other: {
    'mobile-web-app-capable': 'yes',
  }
};

export default function MobileLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="h-[100dvh] w-full overflow-hidden bg-[#F8F8FA]">
      {children}
    </div>
  );
}

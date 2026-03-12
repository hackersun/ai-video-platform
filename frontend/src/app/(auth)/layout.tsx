import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: '登录 - AI视频平台',
  description: '登录您的AI视频平台账号',
};

export default function LoginLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
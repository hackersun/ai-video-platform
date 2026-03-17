import './globals.css'

export const metadata = {
  title: 'AI视频平台',
  description: '智能视频创作平台',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-gray-900 text-white antialiased">{children}</body>
    </html>
  )
}

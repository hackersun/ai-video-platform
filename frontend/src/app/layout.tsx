import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { QueryProvider } from "@/components/providers/query-provider";
import { Toaster } from "@/components/ui/toaster";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AI视频平台 - 智能创作",
  description: "AI驱动的视频创作平台，让创意无限可能",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className={`${inter.className} antialiased bg-[#0a0a0f] text-white min-h-screen`}>
        <QueryProvider>
          <div className="bg-gradient-mesh min-h-screen">
            {children}
          </div>
          <Toaster />
        </QueryProvider>
      </body>
    </html>
  );
}

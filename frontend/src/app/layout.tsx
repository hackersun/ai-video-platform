import './globals.css';
import { AuthProvider } from '@/contexts/AuthContext';
import { ToastProvider } from '@/components/ui/toast';
import { UserPreferencesHydrator } from '@/components/user-preferences-hydrator';

export const metadata = {
  title: 'AI视频平台',
  description: '智能视频创作平台',
};

const themeBootstrapScript = `
(() => {
  try {
    const user = JSON.parse(localStorage.getItem('user') || 'null');
    const scopedKey = user?.id ? 'settings.appearance:' + user.id : 'settings.appearance';
    const raw = localStorage.getItem(scopedKey) || localStorage.getItem('settings.appearance');
    const saved = raw ? JSON.parse(raw) : {};
    const preference = ['dark', 'light', 'system'].includes(saved.theme) ? saved.theme : 'dark';
    const resolved = preference === 'system'
      ? (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark')
      : preference;
    document.documentElement.dataset.themePreference = preference;
    document.documentElement.dataset.theme = resolved;
    document.documentElement.style.colorScheme = resolved;
  } catch {
    document.documentElement.dataset.themePreference = 'dark';
    document.documentElement.dataset.theme = 'dark';
  }
})();
`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootstrapScript }} />
      </head>
      <body className="min-h-screen bg-background text-foreground antialiased">
        <ToastProvider>
          <AuthProvider>
            <UserPreferencesHydrator />
            {children}
          </AuthProvider>
        </ToastProvider>
      </body>
    </html>
  );
}

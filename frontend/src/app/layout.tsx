import type { Metadata } from 'next';
import './globals.css';
import ThemeRegistry from '@/components/layout/ThemeRegistry';
import AppLayout from '@/components/layout/AppLayout';
import { I18nProvider } from '@/i18n/I18nProvider';
import { AppRouterCacheProvider } from '@mui/material-nextjs/v15-appRouter';

export const metadata: Metadata = {
  title: 'VinUni HR - AI CV Screening Workspace',
  description: 'AI-Native CV Matching & Ranking Platform for VinUniversity HR',
  icons: {
    icon: '/vinuni-logo.png',
    shortcut: '/vinuni-logo.png',
    apple: '/vinuni-logo.png',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <body suppressHydrationWarning={true}>
        <AppRouterCacheProvider>
          <I18nProvider><ThemeRegistry>
            <AppLayout>{children}</AppLayout>
          </ThemeRegistry></I18nProvider>
        </AppRouterCacheProvider>
      </body>
    </html>
  );
}

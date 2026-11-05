import type { Metadata } from 'next';
import './globals.css';
import ThemeRegistry from '@/components/layout/ThemeRegistry';
import AppLayout from '@/components/layout/AppLayout';

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
        <ThemeRegistry>
          <AppLayout>{children}</AppLayout>
        </ThemeRegistry>
      </body>
    </html>
  );
}

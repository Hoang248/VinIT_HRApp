import type { Metadata } from 'next';
import './globals.css';
import ThemeRegistry from '@/components/layout/ThemeRegistry';
import AppLayout from '@/components/layout/AppLayout';

export const metadata: Metadata = {
  title: 'VinUni HR - AI CV Screening Workspace',
  description: 'AI-Native CV Matching & Ranking Platform for VinUniversity HR',
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

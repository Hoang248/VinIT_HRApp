import type { Metadata } from 'next';
import './globals.css';

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
      <body suppressHydrationWarning={true}>{children}</body>
    </html>
  );
}

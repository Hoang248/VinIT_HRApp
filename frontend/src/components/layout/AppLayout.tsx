'use client';

import * as React from 'react';
import { Box, CircularProgress } from '@mui/material';
import { useRouter, usePathname } from 'next/navigation';
import { useState, useEffect } from 'react';
import Sidebar, { DRAWER_WIDTH } from './Sidebar';
import Header, { APPBAR_HEIGHT } from './Header';
import { authApi } from '@/lib/api';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [isLoading, setIsLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    // Skip auth check on login page
    if (pathname === '/') {
      setIsLoading(false);
      return;
    }

    const checkAuth = async () => {
      const token = localStorage.getItem('hra_access_token');
      if (!token) {
        router.push('/');
        return;
      }

      try {
        await authApi.me();
        setAuthenticated(true);
      } catch (e) {
        localStorage.removeItem('hra_access_token');
        router.push('/');
      } finally {
        setIsLoading(false);
      }
    };

    checkAuth();
  }, [pathname, router]);

  if (isLoading) {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
          backgroundColor: '#F8FAFC',
        }}
      >
        <CircularProgress color="secondary" />
      </Box>
    );
  }

  if (pathname === '/') {
    return <>{children}</>;
  }

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <Sidebar />
      <Header />
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          ml: `${DRAWER_WIDTH}px`,
          backgroundColor: '#F8FAFC',
          minHeight: '100vh',
        }}
      >
        <Box sx={{ mt: `${APPBAR_HEIGHT}px`, p: 3 }}>
          {children}
        </Box>
      </Box>
    </Box>
  );
}

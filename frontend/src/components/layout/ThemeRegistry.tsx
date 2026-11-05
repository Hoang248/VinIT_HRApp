'use client';

import * as React from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { enUS, viVN } from '@mui/material/locale';
import { useI18n } from '@/i18n/I18nProvider';
import CssBaseline from '@mui/material/CssBaseline';
import theme from '@/lib/theme';

export default function ThemeRegistry({ children }: { children: React.ReactNode }) {
  const { locale } = useI18n();
  const localizedTheme = React.useMemo(() => createTheme(theme, locale === 'vi' ? viVN : enUS), [locale]);
  return (
    <ThemeProvider theme={localizedTheme}>
      <CssBaseline />
      {children}
    </ThemeProvider>
  );
}

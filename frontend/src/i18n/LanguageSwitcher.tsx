'use client';

import * as React from 'react';
import { Box, Button } from '@mui/material';
import { useI18n } from './I18nProvider';

export default function LanguageSwitcher({ light = false }: { light?: boolean }) {
  const { locale, setLocale, t } = useI18n();
  return <Box role="group" aria-label={t('Chọn ngôn ngữ')} sx={{ display: 'flex', gap: 0.25, flexShrink: 0 }}>
    <Button size="small" aria-label="Tiếng Việt" aria-pressed={locale === 'vi'} onClick={() => setLocale('vi')}
      sx={{ minWidth: 32, px: 0.5, color: light ? '#fff' : 'primary.main', fontWeight: locale === 'vi' ? 800 : 400 }}>VI</Button>
    <Button size="small" aria-label="English" aria-pressed={locale === 'en'} onClick={() => setLocale('en')}
      sx={{ minWidth: 32, px: 0.5, color: light ? '#fff' : 'primary.main', fontWeight: locale === 'en' ? 800 : 400 }}>EN</Button>
  </Box>;
}

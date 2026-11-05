'use client';

import * as React from 'react';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

import { translate, type Locale, type Arguments } from './translate';
export type { Locale } from './translate';

type I18nContextValue = { locale: Locale; setLocale: (locale: Locale) => void; t: (key: string, ...args: Arguments) => string; dateLocale: string };
const I18nContext = createContext<I18nContextValue | null>(null);
let activeLocale: Locale | undefined;

export function getStoredLocale(): Locale {
  if (typeof window === 'undefined') return 'vi';
  if (activeLocale) return activeLocale;
  try { return window.localStorage.getItem('hra_locale') === 'en' ? 'en' : 'vi'; }
  catch { return 'vi'; }
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  // Vietnamese is also the server-rendered default, avoiding hydration drift.
  const [locale, setLocaleState] = useState<Locale>('vi');
  const localeRef = useRef<Locale>('vi');
  localeRef.current = locale;
  useEffect(() => { const saved = getStoredLocale(); activeLocale = saved; setLocaleState(saved); }, []);
  useEffect(() => { document.documentElement.lang = locale; }, [locale]);
  const setLocale = useCallback((next: Locale) => {
    localeRef.current = next;
    activeLocale = next;
    setLocaleState(next);
    try { window.localStorage.setItem('hra_locale', next); } catch { /* preferences remain in memory */ }
  }, []);
  // Stable function identity prevents effects and data requests from restarting
  // unnecessarily; context changes still re-render all translated components.
  const t = useCallback((key: string, ...args: Arguments) => translate(key, localeRef.current, ...args), []);
  const value = useMemo(() => ({ locale, setLocale, t, dateLocale: locale === 'vi' ? 'vi-VN' : 'en-US' }), [locale, setLocale, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const value = useContext(I18nContext);
  if (!value) throw new Error('I18nProvider is missing');
  return value;
}

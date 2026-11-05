'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Alert, Box, Button, Card, CardContent, CircularProgress, TextField, Typography } from '@mui/material';
import LanguageSwitcher from '@/i18n/LanguageSwitcher';
import { useI18n } from '@/i18n/I18nProvider';
import { authApi } from '@/lib/api';

export default function ChangePasswordPage() {
  const { t } = useI18n();
  const router = useRouter();
  const [current, setCurrent] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => { if (!localStorage.getItem('hra_access_token')) router.replace('/'); }, [router]);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setError(null);
    if (password !== confirm) { setError(t("Mật khẩu xác nhận không khớp.")); return; }
    if ([...password].length < 12 || new TextEncoder().encode(password).length > 72) {
      setError(t("Mật khẩu cần ít nhất 12 ký tự và tối đa 72 byte UTF-8.")); return;
    }
    try {
      setLoading(true);
      await authApi.changePassword(current, password);
      localStorage.removeItem('hra_access_token');
      setCurrent(''); setPassword(''); setConfirm(''); setSuccess(true);
    } catch (err: any) { setError(err.response?.data?.detail || t("Không thể đổi mật khẩu.")); }
    finally { setLoading(false); }
  };

  return <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: '#F8FAFC', p: 2 }}>
    <Card sx={{ width: '100%', maxWidth: 500 }}><CardContent sx={{ p: { xs: 3, sm: 4 } }}>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}><LanguageSwitcher /></Box>
      <Typography variant="h1" sx={{ fontSize: 24, color: '#0A2B57', mb: 1 }}>{t("Đổi mật khẩu tạm thời")}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>{t("Bạn cần đổi mật khẩu do Admin cấp trước khi sử dụng hệ thống.")}</Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{t(error)}</Alert>}
      {success ? <Alert severity="success">{t("Đã đổi mật khẩu. Vui lòng chờ vài giây rồi đăng nhập lại.")}</Alert> : <Box component="form" onSubmit={submit}>
        <TextField label={t("Mật khẩu tạm thời")} type="password" value={current} onChange={e => setCurrent(e.target.value)} fullWidth required margin="normal" autoComplete="current-password" />
        <TextField label={t("Mật khẩu mới")} type="password" value={password} onChange={e => setPassword(e.target.value)} fullWidth required margin="normal" autoComplete="new-password" helperText={t("Ít nhất 12 ký tự, tối đa 72 byte UTF-8.")} />
        <TextField label={t("Xác nhận mật khẩu")} type="password" value={confirm} onChange={e => setConfirm(e.target.value)} fullWidth required margin="normal" autoComplete="new-password" />
        <Button type="submit" variant="contained" color="secondary" fullWidth disabled={loading} sx={{ mt: 2 }}>
          {loading ? <CircularProgress size={22} color="inherit" /> : t("Đổi mật khẩu")}
        </Button>
      </Box>}
      <Button fullWidth sx={{ mt: 2 }} onClick={() => { localStorage.removeItem('hra_access_token'); router.push('/'); }}>{t("Quay lại đăng nhập")}</Button>
    </CardContent></Card>
  </Box>;
}

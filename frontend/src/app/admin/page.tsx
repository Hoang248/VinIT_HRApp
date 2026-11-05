'use client';

import * as React from 'react';
import { useCallback, useEffect, useState } from 'react';
import { Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Grid, Typography } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import { adminApi } from '@/lib/api';

type RuntimeConfig = { provider: string; model_name: string; api_base?: string; temperature_default: number; external_api_allowed: boolean };

export default function AdminPage() {
  const [config, setConfig] = useState<RuntimeConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try {
      setLoading(true); setError(null);
      const response = await adminApi.getActiveAiConfig();
      setConfig(response.data.config);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Không thể tải cấu hình AI.');
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 2, mb: 3 }}>
        <Box><Typography variant="h1" sx={{ fontSize: 26, color: '#0A2B57' }}>Quản trị AI</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>Cấu hình thực tế của dịch vụ xử lý</Typography></Box>
        <Button startIcon={<RefreshIcon />} variant="outlined" onClick={load} disabled={loading}>Làm mới</Button>
      </Box>
      {loading ? <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress color="secondary" /></Box> : error ? (
        <Alert severity="error" action={<Button color="inherit" onClick={load}>Thử lại</Button>}>{error}</Alert>
      ) : config && (
        <>
          <Alert severity="info" sx={{ mb: 3 }}>Cấu hình hiện được quản lý bằng biến môi trường của backend. Chức năng thay đổi và kích hoạt model trên giao diện chưa khả dụng; cần khởi động lại dịch vụ sau khi thay đổi.</Alert>
          <Card variant="outlined"><CardContent sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}><Typography variant="h4">Cấu hình đang sử dụng</Typography><Chip size="small" label="Môi trường" /></Box>
            <Grid container spacing={3}>
              {[
                ['Nhà cung cấp', config.provider], ['Model', config.model_name], ['API endpoint', config.api_base || 'Chưa cấu hình'],
                ['Temperature', String(config.temperature_default)], ['API bên ngoài', config.external_api_allowed ? 'Được cho phép trong cấu hình' : 'Không cho phép'],
              ].map(([label, value]) => <Grid item xs={12} sm={6} key={label}>
                <Typography variant="caption" color="text.secondary">{label}</Typography>
                <Typography variant="body1" sx={{ mt: 0.5, wordBreak: 'break-word', fontWeight: 600 }}>{value}</Typography>
              </Grid>)}
            </Grid>
          </CardContent></Card>
          <Alert severity="warning" sx={{ mt: 3 }}>Chỉ sử dụng dịch vụ AI đã được phê duyệt để xử lý dữ liệu ứng viên. Kiểm tra chính sách và kết nối trước khi vận hành.</Alert>
        </>
      )}
    </Box>
  );
}

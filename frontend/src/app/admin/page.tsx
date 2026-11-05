'use client';

import { useI18n } from '@/i18n/I18nProvider';

import * as React from 'react';
import { useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, FormControl, Grid,
  InputLabel, MenuItem, Select, TextField, Typography,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import { adminApi } from '@/lib/api';

type WorkerHealth = { pending: number; processing: number; stale_heartbeat: number; long_running: number; failed_24h: number; recoveries_24h: number; oldest_pending_seconds: number };
type RuntimeConfig = { config_id?: string | null; provider: string; model_name: string; api_base?: string | null; temperature_default: number; external_api_allowed: boolean };
type AIOptions = { models: string[]; endpoints: string[]; external_api_allowed: boolean };
type ConfigVersion = RuntimeConfig & { config_id: string; status: string; created_at: string };

export default function AdminPage() {
  const { t, dateLocale } = useI18n();
  const [config, setConfig] = useState<RuntimeConfig | null>(null);
  const [source, setSource] = useState('environment');
  const [allowed, setAllowed] = useState(false);
  const [options, setOptions] = useState<AIOptions | null>(null);
  const [versions, setVersions] = useState<ConfigVersion[]>([]);
  const [health, setHealth] = useState<WorkerHealth | null>(null);
  const [provider, setProvider] = useState('local');
  const [model, setModel] = useState('');
  const [endpoint, setEndpoint] = useState('');
  const [temperature, setTemperature] = useState('0.1');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true); setError(null);
      const [active, worker, permitted, history] = await Promise.all([
        adminApi.getActiveAiConfig(), adminApi.getWorkerHealth(), adminApi.getAiOptions(), adminApi.listAiConfigs(),
      ]);
      const current: RuntimeConfig = active.data.config;
      setConfig(current); setSource(active.data.source); setAllowed(active.data.allowed_by_this_process);
      setHealth(worker.data); setOptions(permitted.data); setVersions(history.data);
      setProvider(current.provider); setModel(current.model_name); setEndpoint(current.api_base || '');
      setTemperature(String(current.temperature_default));
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể tải cấu hình AI và trạng thái hàng đợi."));
    } finally { setLoading(false); }
  }, [t]);
  useEffect(() => { load(); }, [load]);

  const save = async () => {
    const value = Number(temperature);
    if (!model || !endpoint || !Number.isFinite(value) || value < 0 || value > 1) {
      setError(t("Vui lòng chọn model, endpoint và temperature trong khoảng 0–1.")); return;
    }
    try {
      setSaving(true); setError(null); setSuccess(null);
      const created = await adminApi.createAiConfig({ provider, model_name: model, api_base: endpoint, temperature_default: value });
      await adminApi.enableAiConfig(created.data.config_id);
      await load();
      setSuccess(t("Đã kích hoạt phiên bản cấu hình. Tác vụ đang chạy tiếp tục dùng cấu hình đã ghim."));
    } catch (err: any) { setError(err.response?.data?.detail || t("Không thể kích hoạt cấu hình AI.")); }
    finally { setSaving(false); }
  };
  const activate = async (id: string) => {
    try {
      setSaving(true); setError(null); setSuccess(null);
      await adminApi.enableAiConfig(id); await load(); setSuccess(t("Đã kích hoạt phiên bản cấu hình."));
    } catch (err: any) { setError(err.response?.data?.detail || t("Không thể kích hoạt cấu hình AI.")); }
    finally { setSaving(false); }
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 2, mb: 3 }}>
        <Box><Typography variant="h1" sx={{ fontSize: 26, color: '#0A2B57' }}>{t("Quản trị AI")}</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{t("Cấu hình và giám sát dịch vụ xử lý")}</Typography></Box>
        <Button startIcon={<RefreshIcon />} variant="outlined" onClick={load} disabled={loading || saving}>{t("Làm mới")}</Button>
      </Box>
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{t(error)}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>{t(success)}</Alert>}
      {loading ? <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress color="secondary" /></Box> : config && options && (
        <>
          <Alert severity="info" sx={{ mb: 3 }}>{t("Chỉ chọn được model và endpoint do người vận hành cho phép. Không nhập API key trên giao diện: khóa chỉ được cung cấp qua môi trường/secret manager. Chính sách mạng và ALLOW_EXTERNAL_API không thể thay đổi tại đây.")}</Alert>
          {!allowed && <Alert severity="warning" sx={{ mb: 3 }}>{t("Cấu hình hiện tại chưa hợp lệ theo chính sách của tiến trình này. Kiểm tra danh sách cho phép và kết nối trước khi dùng AI.")}</Alert>}
          <Alert severity="info" sx={{ mb: 3 }}>{t("Mọi lựa chọn nhà cung cấp chỉ dùng giao thức OpenAI-compatible /chat/completions với Bearer. Không hỗ trợ trực tiếp API Azure riêng (api-key/api-version); cần gateway tương thích đã được phê duyệt.")}</Alert>
          <Card variant="outlined"><CardContent sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}><Typography variant="h4">{t("Cấu hình đang sử dụng")}</Typography><Chip size="small" label={source === 'database' ? t("Phiên bản đã kích hoạt") : t("Mặc định môi trường")} /></Box>
            <Grid container spacing={3}>
              {[
                [t("Nhà cung cấp"), config.provider], ['Model', config.model_name], ['API endpoint', config.api_base || t("Chưa cấu hình")],
                [t("Temperature tạo tiêu chí"), String(config.temperature_default)], [t("API bên ngoài"), config.external_api_allowed ? t("Môi trường cho phép") : t("Không cho phép")],
              ].map(([label, value]) => <Grid item xs={12} sm={6} key={label}>
                <Typography variant="caption" color="text.secondary">{label}</Typography>
                <Typography variant="body1" sx={{ mt: 0.5, wordBreak: 'break-word', fontWeight: 600 }}>{value}</Typography>
              </Grid>)}
            </Grid>
          </CardContent></Card>
          <Card variant="outlined" sx={{ mt: 3 }}><CardContent sx={{ p: 3 }}>
            <Typography variant="h4" sx={{ mb: 2 }}>{t("Tạo và kích hoạt phiên bản mới")}</Typography>
            {options.endpoints.length === 0 && <Alert severity="warning" sx={{ mb: 2 }}>{t("Chưa có endpoint được phép. Quản trị viên hệ thống cần cấu hình môi trường trước.")}</Alert>}
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}><FormControl fullWidth size="small"><InputLabel id="ai-provider-label">{t("Nhà cung cấp")}</InputLabel>
                <Select labelId="ai-provider-label" label={t("Nhà cung cấp")} value={provider} onChange={e => setProvider(e.target.value)}>
                  <MenuItem value="local">Local</MenuItem><MenuItem value="compatible">OpenAI-compatible</MenuItem><MenuItem value="openai">OpenAI-compatible (OpenAI)</MenuItem><MenuItem value="azure">OpenAI-compatible (Azure gateway)</MenuItem>
                </Select></FormControl></Grid>
              <Grid item xs={12} sm={6}><FormControl fullWidth size="small"><InputLabel id="ai-model-label">{t("Model được phép")}</InputLabel>
                <Select labelId="ai-model-label" label={t("Model được phép")} value={options.models.includes(model) ? model : ''} onChange={e => setModel(e.target.value)}>
                  {options.models.map(item => <MenuItem key={item} value={item}>{item}</MenuItem>)}
                </Select></FormControl></Grid>
              <Grid item xs={12} sm={8}><FormControl fullWidth size="small"><InputLabel id="ai-endpoint-label">{t("Endpoint được phép")}</InputLabel>
                <Select labelId="ai-endpoint-label" label={t("Endpoint được phép")} value={options.endpoints.includes(endpoint) ? endpoint : ''} onChange={e => setEndpoint(e.target.value)}>
                  {options.endpoints.map(item => <MenuItem key={item} value={item}>{item}</MenuItem>)}
                </Select></FormControl></Grid>
              <Grid item xs={12} sm={4}><TextField fullWidth size="small" type="number" label="Temperature" value={temperature} onChange={e => setTemperature(e.target.value)} inputProps={{ min: 0, max: 1, step: 0.05 }} /></Grid>
            </Grid>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>{t("Temperature áp dụng khi tạo tiêu chí; trích xuất và đối chiếu CV luôn dùng 0. Các tác vụ đã bắt đầu giữ cấu hình của lần chạy đầu tiên, kể cả khi phục hồi.")}</Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>{t("Kết quả đã có không tự đánh giá lại khi đổi cấu hình; pipeline chỉ đánh giá profile và tiêu chí chưa có kết quả hiện hành.")}</Typography>
            <Button variant="contained" sx={{ mt: 2 }} onClick={save} disabled={saving || !options.endpoints.length}>{t("Tạo và kích hoạt")}</Button>
          </CardContent></Card>
          {versions.length > 0 && <Card variant="outlined" sx={{ mt: 3 }}><CardContent sx={{ p: 3 }}>
            <Typography variant="h4" sx={{ mb: 2 }}>{t("Lịch sử phiên bản")}</Typography>
            {versions.map(version => <Box key={version.config_id} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap', py: 1 }}>
              <Box><Typography variant="body2" fontWeight={600}>{version.model_name} · {t(version.status === "ACTIVE" ? "Đang hoạt động cấu hình" : version.status === "DRAFT" ? "Bản nháp cấu hình" : "Đã tắt cấu hình")}</Typography><Typography variant="caption" color="text.secondary" sx={{ wordBreak: 'break-all' }}>{version.api_base || t("Không có endpoint")} · {new Date(version.created_at).toLocaleString(dateLocale)}</Typography></Box>
              {version.status !== 'ACTIVE' && <Button size="small" disabled={saving} onClick={() => activate(version.config_id)}>{t("Kích hoạt")}</Button>}
            </Box>)}
          </CardContent></Card>}
          {health && <Card variant="outlined" sx={{ mt: 3 }}><CardContent sx={{ p: 3 }}>
            <Typography variant="h4" sx={{ mb: 2 }}>{t("Giám sát hàng đợi xử lý")}</Typography>
            <Grid container spacing={2}>
              {[
                [t("Đang chờ"), health.pending], [t("Đang xử lý"), health.processing],
                [t("Mất heartbeat trên 2 phút"), health.stale_heartbeat], [t("Chạy trên 30 phút"), health.long_running],
                [t("Thất bại trong 24 giờ"), health.failed_24h], [t("Phục hồi trong 24 giờ"), health.recoveries_24h],
                [t("Tác vụ chờ lâu nhất (giây)"), health.oldest_pending_seconds],
              ].map(([label, value]) => <Grid item xs={6} sm={4} key={label}>
                <Typography variant="caption" color="text.secondary">{label}</Typography>
                <Typography variant="body1" sx={{ fontWeight: 600 }}>{value}</Typography>
              </Grid>)}
            </Grid>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>{t("Đây là chỉ số hàng đợi, không chứng minh worker còn sống. Không tự đặt lại tác vụ chỉ vì heartbeat cũ; xem runbook vận hành.")}</Typography>
          </CardContent></Card>}
          <Alert severity="warning" sx={{ mt: 3 }}>{t("Chỉ sử dụng dịch vụ AI đã được phê duyệt để xử lý dữ liệu ứng viên. Che dữ liệu nhạy cảm chỉ là biện pháp giảm thiểu, không bảo đảm ẩn danh hoàn toàn.")}</Alert>
        </>
      )}
    </Box>
  );
}

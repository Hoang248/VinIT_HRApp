'use client';

import * as React from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  CircularProgress,
  Alert,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Switch,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import { useEffect, useState } from 'react';
import { adminApi } from '@/lib/api';
import StatusBadge from '@/components/common/StatusBadge';

export default function AdminPage() {
  const [configs, setConfigs] = useState<any[]>([]);
  const [activeConfig, setActiveConfig] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({
    provider: 'local',
    model_name: '',
    api_base: '',
    api_key: '',
    deployment_mode: 'local',
    temperature_default: 0.1,
    external_api_allowed: false,
  });

  const loadData = async () => {
    try {
      setLoading(true);
      const [allRes, activeRes] = await Promise.all([
        adminApi.listAiConfigs(),
        adminApi.getActiveAiConfig(),
      ]);
      setConfigs(allRes.data);
      setActiveConfig(activeRes.data.config);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Không thể tải cấu hình quản trị');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateConfig = async () => {
    try {
      setSaving(true);
      await adminApi.createAiConfig(formData);
      setDialogOpen(false);
      setFormData({
        provider: 'local',
        model_name: '',
        api_base: '',
        api_key: '',
        deployment_mode: 'local',
        temperature_default: 0.1,
        external_api_allowed: false,
      });
      await loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Không thể tạo cấu hình mới');
    } finally {
      setSaving(false);
    }
  };

  const handleEnableConfig = async (configId: string) => {
    try {
      await adminApi.enableAiConfig(configId);
      await loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Không thể kích hoạt cấu hình');
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 10 }}>
        <CircularProgress color="secondary" />
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
        <Box>
          <Typography variant="h1" sx={{ fontSize: 28, color: '#0A2B57', mb: 0.5 }}>
            Quản trị cấu hình AI
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Quản lý các cấu hình mô hình AI được phê duyệt để sử dụng trong hệ thống
          </Typography>
        </Box>
        <Button
          variant="contained"
          color="secondary"
          startIcon={<AddIcon />}
          onClick={() => setDialogOpen(true)}
        >
          Thêm cấu hình AI mới
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Active Config */}
      {activeConfig && (
        <Card sx={{ mb: 4, borderLeft: '4px solid #067647' }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <CheckCircleIcon sx={{ color: '#067647', mr: 2, fontSize: 32 }} />
              <Box sx={{ flexGrow: 1 }}>
                <Typography variant="h4" sx={{ fontSize: 16, fontWeight: 600, color: '#067647', mb: 0.5 }}>
                  Cấu hình đang hoạt động
                </Typography>
                <Grid container spacing={2} sx={{ mt: 0.5 }}>
                  <Grid item xs={12} sm={3}>
                    <Typography variant="caption" color="text.secondary">Nhà cung cấp</Typography>
                    <Typography variant="body2" fontWeight={600}>{activeConfig.provider}</Typography>
                  </Grid>
                  <Grid item xs={12} sm={3}>
                    <Typography variant="caption" color="text.secondary">Tên model</Typography>
                    <Typography variant="body2" fontWeight={600}>{activeConfig.model_name}</Typography>
                  </Grid>
                  <Grid item xs={12} sm={3}>
                    <Typography variant="caption" color="text.secondary">Chế độ triển khai</Typography>
                    <Typography variant="body2" fontWeight={600}>{activeConfig.deployment_mode}</Typography>
                  </Grid>
                  <Grid item xs={12} sm={3}>
                    <Typography variant="caption" color="text.secondary">Kích hoạt lúc</Typography>
                    <Typography variant="body2" fontWeight={600}>
                      {activeConfig.enabled_at ? new Date(activeConfig.enabled_at).toLocaleString('vi-VN') : '-'}
                    </Typography>
                  </Grid>
                </Grid>
              </Box>
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Configs Table */}
      <Typography variant="h4" sx={{ fontSize: 16, fontWeight: 600, mb: 2 }}>
        Tất cả cấu hình AI
      </Typography>
      <TableContainer component={Paper} sx={{ borderRadius: 2, boxShadow: '0 1px 3px rgba(0,0,0,0.05)', mb: 4 }}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Nhà cung cấp</TableCell>
              <TableCell>Tên model</TableCell>
              <TableCell>API Base</TableCell>
              <TableCell>Chế độ triển khai</TableCell>
              <TableCell>Trạng thái</TableCell>
              <TableCell align="right">Thao tác</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {configs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center" sx={{ py: 6, color: 'text.secondary' }}>
                  Chưa có cấu hình AI nào được tạo
                </TableCell>
              </TableRow>
            ) : (
              configs.map((config) => (
                <TableRow key={config.config_id} hover>
                  <TableCell>
                    <Typography variant="body2" fontWeight={500} sx={{ textTransform: 'capitalize' }}>
                      {config.provider}
                    </Typography>
                  </TableCell>
                  <TableCell>{config.model_name}</TableCell>
                  <TableCell>
                    <Typography variant="caption" fontFamily="monospace" color="text.secondary">
                      {config.api_base || '(cục bộ)'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={config.deployment_mode}
                      size="small"
                      color={config.deployment_mode === 'local' ? 'primary' : 'warning'}
                      sx={{ textTransform: 'capitalize' }}
                    />
                  </TableCell>
                  <TableCell>
                    {config.status === 'ACTIVE' ? (
                      <StatusBadge type="criteria-approved" label="Đang hoạt động" />
                    ) : (
                      <StatusBadge type="criteria-draft" label={config.status} />
                    )}
                  </TableCell>
                  <TableCell align="right">
                    {config.status !== 'ACTIVE' && (
                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() => handleEnableConfig(config.config_id)}
                        sx={{ borderColor: '#067647', color: '#067647' }}
                      >
                        Kích hoạt
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <Alert severity="info" sx={{ mb: 3 }}>
        <Typography variant="body2" fontWeight={600} sx={{ mb: 0.5 }}>Lưu ý quan trọng:</Typography>
        <Typography variant="body2">
          • Chỉ các mô hình đã được IT/Security và Legal/Privacy phê duyệt mới được thêm vào và kích hoạt.<br />
          • Mô hình chạy cục bộ (on-premise) được ưu tiên để bảo vệ dữ liệu ứng viên.<br />
          • Tuyệt đối không gửi CV production đến API bên thứ ba khi chưa có phê duyệt chính thức.<br />
          • Nhà cung cấp không được phép sử dụng dữ liệu CV để huấn luyện mô hình.
        </Typography>
      </Alert>

      {/* Create Config Dialog */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ color: '#0A2B57' }}>Thêm cấu hình AI mới</DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={2} sx={{ pt: 1 }}>
            <Grid item xs={12}>
              <FormControl fullWidth required>
                <InputLabel>Loại nhà cung cấp</InputLabel>
                <Select
                  value={formData.provider}
                  label="Loại nhà cung cấp"
                  onChange={(e) => setFormData({ ...formData, provider: e.target.value })}
                >
                  <MenuItem value="local">Mô hình chạy cục bộ (vLLM / Local)</MenuItem>
                  <MenuItem value="openai_compatible">API chuẩn OpenAI Compatible</MenuItem>
                  <MenuItem value="openai">OpenAI API (chỉ cho kiểm thử)</MenuItem>
                  <MenuItem value="azure">Azure OpenAI</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12}>
              <TextField
                label="Tên model"
                fullWidth
                required
                value={formData.model_name}
                onChange={(e) => setFormData({ ...formData, model_name: e.target.value })}
                placeholder="vinuni/hra-llm-7b, qwen2.5:7b, gpt-4o-mini, ..."
                helperText="Tên định danh của mô hình"
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                label="API Base URL"
                fullWidth
                value={formData.api_base}
                onChange={(e) => setFormData({ ...formData, api_base: e.target.value })}
                placeholder="http://localhost:8001/v1 (cho local) hoặc https://api.openai.com/v1"
                helperText="Bỏ trống nếu chạy mô hình cục bộ cùng mạng"
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                label="API Key"
                fullWidth
                type="password"
                value={formData.api_key}
                onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                helperText="Sẽ được mã hóa trong cơ sở dữ liệu"
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                label="Temperature mặc định"
                type="number"
                fullWidth
                inputProps={{ min: 0, max: 1, step: 0.1 }}
                value={formData.temperature_default}
                onChange={(e) => setFormData({ ...formData, temperature_default: parseFloat(e.target.value) })}
                helperText="Nhiệt độ tạo sinh của LLM. Giá trị thấp hơn cho kết quả nhất quán hơn."
              />
            </Grid>
            <Grid item xs={12}>
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.external_api_allowed}
                    onChange={(e) => setFormData({ ...formData, external_api_allowed: e.target.checked })}
                    color="warning"
                  />
                }
                label="Cho phép gọi API bên ngoài (cần phê duyệt)"
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setDialogOpen(false)}>Hủy</Button>
          <Button
            variant="contained"
            color="secondary"
            onClick={handleCreateConfig}
            disabled={saving || !formData.model_name}
          >
            {saving ? <CircularProgress size={20} color="inherit" /> : 'Thêm cấu hình'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

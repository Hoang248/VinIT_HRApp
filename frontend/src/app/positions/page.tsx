'use client';

import * as React from 'react';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Chip,
  CircularProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Autocomplete,
  Tooltip,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { positionsApi, usersApi, dashboardApi, authApi } from '@/lib/api';
import StatusBadge from '@/components/common/StatusBadge';
import { Position, UserSummary } from '@/types';

export default function PositionsPage() {
  const router = useRouter();
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [applicationTotal, setApplicationTotal] = useState<number | null>(null);
  const [canCreate, setCanCreate] = useState(false);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [formData, setFormData] = useState({
    position_code: '',
    title: '',
    org_unit: '',
    jd_content: '',
    hiring_manager_user_id: '',
  });
  const [hmSearchQuery, setHmSearchQuery] = useState('');
  const [hmOptions, setHmOptions] = useState<UserSummary[]>([]);
  const [hmLoading, setHmLoading] = useState(false);
  const [hmSelectedName, setHmSelectedName] = useState('');

  useEffect(() => {
    loadPositions();
  }, []);

  const loadPositions = async () => {
    try {
      setLoading(true);
      const [positions, stats, me] = await Promise.all([
        positionsApi.listAll(), dashboardApi.getSummary().catch(() => null), authApi.me(),
      ]);
      setCanCreate(me.data.system_roles?.some((role: string) => ['ADMIN', 'HR_LEAD', 'HR_RECRUITER'].includes(role)) ||
        me.data.position_assignments?.some((a: any) => ['HR_RECRUITER', 'HR_LEAD'].includes(a.position_role)) || false);
      setPositions(positions);
      setError(null);
      setApplicationTotal(stats?.data?.total_applications ?? null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Không thể tải danh sách vị trí');
    } finally {
      setLoading(false);
    }
  };

  const handleCreatePosition = async () => {
    try {
      setCreateLoading(true); setCreateError(null);
      const payload = { ...formData };
      await positionsApi.create(payload);
      setCreateDialogOpen(false);
      setFormData({ position_code: '', title: '', org_unit: '', jd_content: '', hiring_manager_user_id: '' });
      setHmSelectedName('');
      setHmSearchQuery('');
      setHmOptions([]);
      await loadPositions();
    } catch (err: any) {
      setCreateError(err.response?.data?.detail || 'Không thể tạo vị trí mới');
    } finally {
      setCreateLoading(false);
    }
  };

  // HM search
  useEffect(() => {
    if (!createDialogOpen) return;
    const q = hmSearchQuery.trim();
    if (q.length < 1) {
      setHmOptions([]);
      return;
    }
    setHmLoading(true);
    const t = setTimeout(async () => {
      try {
        const res = await usersApi.list({ search: q });
        setHmOptions(res.data || []);
      } catch {
        setHmOptions([]);
      } finally {
        setHmLoading(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [hmSearchQuery, createDialogOpen]);

  const getPositionStatusBadge = (status: string) => {
    switch (status) {
      case 'OPEN':
        return <StatusBadge type="position-open" label="Đang mở" />;
      case 'PAUSED':
        return <StatusBadge type="position-paused" label="Tạm dừng" />;
      case 'CLOSED':
        return <StatusBadge type="position-closed" label="Đã đóng" />;
      default:
        return null;
    }
  };

  const getCriteriaBadge = (pos: Position) => {
    const labels: Record<string, string> = {
      DRAFT: 'Bản nháp', PENDING_HR_REVIEW: 'Chờ HR duyệt',
      PENDING_HM_APPROVAL: 'Chờ HM duyệt', APPROVED: 'Đã duyệt', REJECTED: 'Từ chối',
    };
    const label = pos.criteria_status ? (labels[pos.criteria_status] || 'Chưa rõ') : 'Chưa có';
    const description = pos.criteria_approved && pos.criteria_status !== 'APPROVED'
      ? 'Phiên bản mới nhất chưa hoàn tất; vẫn có phiên bản trước đã duyệt.'
      : 'Trạng thái của phiên bản tiêu chí mới nhất';
    return (
      <Tooltip title={description}>
        <span><StatusBadge type={pos.criteria_status === 'APPROVED' ? 'criteria-approved' : 'criteria-draft'} label={label} /></span>
      </Tooltip>
    );
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
      {/* Page Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2, mb: 4 }}>
        <Box>
          <Typography variant="h1" sx={{ fontSize: 28, color: '#0A2B57', mb: 0.5 }}>
            Danh sách vị trí tuyển dụng
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Quản lý các vị trí đang tuyển, tiêu chí đánh giá và hồ sơ ứng viên
          </Typography>
        </Box>
        {canCreate && <Button
          variant="contained"
          color="secondary"
          startIcon={<AddIcon />}
          onClick={() => { setCreateError(null); setCreateDialogOpen(true); }}
          size="large"
        >
          Tạo vị trí mới
        </Button>}
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} action={<Button color="inherit" onClick={loadPositions}>Thử lại</Button>}>
          {error}
        </Alert>
      )}

      {!error && <>
      {/* Summary Cards */}
      <Grid container spacing={{ xs: 2, sm: 3 }} sx={{ mb: 4 }}>
        <Grid item xs={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="caption" color="text.secondary">Vị trí đang mở</Typography>
              <Typography variant="h3" sx={{ fontSize: 24, fontWeight: 'bold', color: '#0A2B57', mt: 1 }}>
                {positions.filter(p => p.status === 'OPEN').length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="caption" color="text.secondary">Tạm dừng</Typography>
              <Typography variant="h3" sx={{ fontSize: 24, fontWeight: 'bold', color: '#B54708', mt: 1 }}>
                {positions.filter(p => p.status === 'PAUSED').length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="caption" color="text.secondary">Đã đóng</Typography>
              <Typography variant="h3" sx={{ fontSize: 24, fontWeight: 'bold', color: '#475569', mt: 1 }}>
                {positions.filter(p => p.status === 'CLOSED').length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="caption" color="text.secondary">Tổng hồ sơ</Typography>
              <Typography variant="h3" sx={{ fontSize: 24, fontWeight: 'bold', color: '#0A2B57', mt: 1 }}>
                {applicationTotal ?? '—'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* On small screens cards keep the actions and status visible without horizontal scrolling. */}
      <Box sx={{ display: { xs: 'grid', md: 'none' }, gap: 2 }}>
        {positions.length === 0 ? (
          <Paper sx={{ p: 4, textAlign: 'center', color: 'text.secondary' }}>Chưa có vị trí trong phạm vi của bạn</Paper>
        ) : positions.map(pos => (
          <Card key={pos.position_id} sx={{ border: '1px solid #E9EEF4' }}>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 1 }}>
                <Box sx={{ minWidth: 0 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 700, color: '#0A2B57', overflowWrap: 'anywhere' }}>{pos.title}</Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ overflowWrap: 'anywhere' }}>{pos.position_code} · {pos.org_unit || 'Chưa có đơn vị'}</Typography>
                </Box>
                {getPositionStatusBadge(pos.status)}
              </Box>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 1, mt: 2 }}>
                <Box><Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>Tiêu chí mới nhất</Typography>{getCriteriaBadge(pos)}</Box>
                <Button variant="outlined" size="small" onClick={() => router.push(`/positions/${pos.position_id}`)} aria-label={`Xem vị trí ${pos.title}`}>Xem vị trí</Button>
              </Box>
            </CardContent>
          </Card>
        ))}
      </Box>

      {/* Wider screens retain the compact table. */}
      <TableContainer component={Paper} sx={{ display: { xs: 'none', md: 'block' }, borderRadius: 2, boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <Table aria-label="Danh sách vị trí tuyển dụng">
          <TableHead>
            <TableRow>
              <TableCell>Mã vị trí</TableCell>
              <TableCell>Tên vị trí</TableCell>
              <TableCell>Đơn vị</TableCell>
              <TableCell>Trạng thái</TableCell>
              <TableCell>Tiêu chí mới nhất</TableCell>
              <TableCell align="right">Thao tác</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {positions.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center" sx={{ py: 8, color: 'text.secondary' }}>
                  Chưa có vị trí nào được tạo
                </TableCell>
              </TableRow>
            ) : (
              positions.map((pos) => (
                <TableRow key={pos.position_id} hover>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 600, fontFamily: 'monospace' }}>
                      {pos.position_code}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>{pos.title}</Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">{pos.org_unit || '-'}</Typography>
                  </TableCell>
                  <TableCell>{getPositionStatusBadge(pos.status)}</TableCell>
                  <TableCell>
                    {getCriteriaBadge(pos)}
                  </TableCell>
                  <TableCell align="right">
                    <IconButton
                      color="primary"
                      onClick={() => router.push(`/positions/${pos.position_id}`)}
                      sx={{ color: '#0A2B57' }}
                      aria-label={`Xem vị trí ${pos.title}`}
                    >
                      <VisibilityIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
      </>}

      {/* Create Position Dialog */}
      <Dialog
        open={createDialogOpen}
        onClose={() => { if (!createLoading) setCreateDialogOpen(false); }}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ color: '#0A2B57', fontWeight: 'bold' }}>
          Tạo vị trí tuyển dụng mới
        </DialogTitle>
        <DialogContent dividers>
          {createError && <Alert severity="error" sx={{ mb: 2 }}>{createError}</Alert>}
          <Grid container spacing={3} sx={{ pt: 1 }}>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Mã vị trí"
                fullWidth
                required
                value={formData.position_code}
                onChange={(e) => setFormData({ ...formData, position_code: e.target.value })}
                placeholder="REQ-IT-001"
                helperText="Mã định danh duy nhất cho vị trí"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Tên vị trí"
                fullWidth
                required
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="Senior Software Engineer"
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                label="Đơn vị / Phòng ban"
                fullWidth
                value={formData.org_unit}
                onChange={(e) => setFormData({ ...formData, org_unit: e.target.value })}
                placeholder="Phòng Công nghệ thông tin"
              />
            </Grid>
            <Grid item xs={12}>
              <Autocomplete
                options={hmOptions}
                loading={hmLoading}
                getOptionLabel={(opt: any) => typeof opt === 'string' ? opt : opt.display_name || ''}
                isOptionEqualToValue={(opt: any, val: any) => opt.user_id === val?.user_id}
                inputValue={hmSearchQuery}
                onInputChange={(_, val) => setHmSearchQuery(val)}
                value={formData.hiring_manager_user_id ? { user_id: formData.hiring_manager_user_id, display_name: hmSelectedName } : null}
                onChange={(_, val: any) => {
                  if (val && typeof val === 'object') {
                    setFormData({ ...formData, hiring_manager_user_id: val.user_id });
                    setHmSelectedName(val.display_name);
                  } else {
                    setFormData({ ...formData, hiring_manager_user_id: '' });
                    setHmSelectedName('');
                  }
                }}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Hiring Manager" required
                    placeholder="Tìm theo tên người dùng..."
                    helperText="Người này sẽ duyệt chuyên môn cho vị trí"
                    InputProps={{
                      ...params.InputProps,
                      endAdornment: (
                        <>
                          {hmLoading ? <CircularProgress size={16} /> : null}
                          {params.InputProps.endAdornment}
                        </>
                      ),
                    }}
                  />
                )}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                label="Nội dung Job Description (tiếng Anh)"
                fullWidth
                required
                multiline
                rows={10}
                value={formData.jd_content}
                onChange={(e) => setFormData({ ...formData, jd_content: e.target.value })}
                placeholder="Paste full JD content here..."
                helperText="Sau khi tạo, bạn có thể yêu cầu AI đề xuất bản nháp tiêu chí từ JD"
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ p: 3 }}>
          <Button onClick={() => setCreateDialogOpen(false)} color="inherit">
            Hủy
          </Button>
          <Button
            onClick={handleCreatePosition}
            variant="contained"
            color="secondary"
            disabled={createLoading || !formData.position_code.trim() || !formData.title.trim() || !formData.jd_content.trim() || !formData.hiring_manager_user_id}
          >
            {createLoading ? <CircularProgress size={20} color="inherit" /> : 'Tạo vị trí'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

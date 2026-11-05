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
  DialogContentText,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { positionsApi } from '@/lib/api';
import StatusBadge from '@/components/common/StatusBadge';
import { Position } from '@/types';

export default function PositionsPage() {
  const router = useRouter();
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [formData, setFormData] = useState({
    position_code: '',
    title: '',
    org_unit: '',
    jd_content: '',
  });

  useEffect(() => {
    loadPositions();
  }, []);

  const loadPositions = async () => {
    try {
      setLoading(true);
      const res = await positionsApi.list();
      setPositions(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Không thể tải danh sách vị trí');
    } finally {
      setLoading(false);
    }
  };

  const handleCreatePosition = async () => {
    try {
      setCreateLoading(true);
      await positionsApi.create(formData);
      setCreateDialogOpen(false);
      setFormData({ position_code: '', title: '', org_unit: '', jd_content: '' });
      await loadPositions();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Không thể tạo vị trí mới');
    } finally {
      setCreateLoading(false);
    }
  };

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
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
        <Box>
          <Typography variant="h1" sx={{ fontSize: 28, color: '#0A2B57', mb: 0.5 }}>
            Danh sách vị trí tuyển dụng
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Quản lý các vị trí đang tuyển, tiêu chí đánh giá và hồ sơ ứng viên
          </Typography>
        </Box>
        <Button
          variant="contained"
          color="secondary"
          startIcon={<AddIcon />}
          onClick={() => setCreateDialogOpen(true)}
          size="large"
        >
          Tạo vị trí mới
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Summary Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="caption" color="text.secondary">Vị trí đang mở</Typography>
              <Typography variant="h3" sx={{ fontSize: 24, fontWeight: 'bold', color: '#0A2B57', mt: 1 }}>
                {positions.filter(p => p.status === 'OPEN').length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="caption" color="text.secondary">Tạm dừng</Typography>
              <Typography variant="h3" sx={{ fontSize: 24, fontWeight: 'bold', color: '#B54708', mt: 1 }}>
                {positions.filter(p => p.status === 'PAUSED').length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="caption" color="text.secondary">Đã đóng</Typography>
              <Typography variant="h3" sx={{ fontSize: 24, fontWeight: 'bold', color: '#475569', mt: 1 }}>
                {positions.filter(p => p.status === 'CLOSED').length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="caption" color="text.secondary">Tổng hồ sơ</Typography>
              <Typography variant="h3" sx={{ fontSize: 24, fontWeight: 'bold', color: '#0A2B57', mt: 1 }}>
                -
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Positions Table */}
      <TableContainer component={Paper} sx={{ borderRadius: 2, boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Mã vị trí</TableCell>
              <TableCell>Tên vị trí</TableCell>
              <TableCell>Đơn vị</TableCell>
              <TableCell>Trạng thái</TableCell>
              <TableCell>Tiêu chí</TableCell>
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
                    <StatusBadge type="criteria-draft" label="Chưa duyệt" />
                  </TableCell>
                  <TableCell align="right">
                    <IconButton
                      color="primary"
                      onClick={() => router.push(`/positions/${pos.position_id}`)}
                      sx={{ color: '#0A2B57' }}
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

      {/* Create Position Dialog */}
      <Dialog
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ color: '#0A2B57', fontWeight: 'bold' }}>
          Tạo vị trí tuyển dụng mới
        </DialogTitle>
        <DialogContent dividers>
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
              <TextField
                label="Nội dung Job Description (tiếng Anh)"
                fullWidth
                required
                multiline
                rows={10}
                value={formData.jd_content}
                onChange={(e) => setFormData({ ...formData, jd_content: e.target.value })}
                placeholder="Paste full JD content here..."
                helperText="Sau khi tạo, AI sẽ tự động đề xuất bản nháp tiêu chí đánh giá từ JD này"
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
            disabled={createLoading || !formData.position_code || !formData.title || !formData.jd_content}
          >
            {createLoading ? <CircularProgress size={20} color="inherit" /> : 'Tạo vị trí'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

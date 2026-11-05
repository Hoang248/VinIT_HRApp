'use client';

import * as React from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  CircularProgress,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from '@mui/material';
import WorkIcon from '@mui/icons-material/Work';
import PeopleIcon from '@mui/icons-material/People';
import WarningIcon from '@mui/icons-material/Warning';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import { useEffect, useState } from 'react';
import { dashboardApi } from '@/lib/api';
import StatusBadge from '@/components/common/StatusBadge';

export default function DashboardPage() {
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const res = await dashboardApi.getSummary();
      setSummary(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Không thể tải dữ liệu tổng hợp');
    } finally {
      setLoading(false);
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
      <Box sx={{ mb: 4 }}>
        <Typography variant="h1" sx={{ fontSize: 28, color: '#0A2B57', mb: 0.5 }}>
          Bảng điều khiển tổng hợp
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Theo dõi tiến độ tuyển dụng, chất lượng xử lý và hiệu quả pilot
        </Typography>
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
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="caption" color="text.secondary">Vị trí đang mở</Typography>
                  <Typography variant="h3" sx={{ fontSize: 28, fontWeight: 'bold', color: '#0A2B57', mt: 1 }}>
                    {summary?.open_positions || 0}
                  </Typography>
                </Box>
                <WorkIcon sx={{ fontSize: 40, color: '#E8F1FC' }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="caption" color="text.secondary">Tổng hồ sơ nhận</Typography>
                  <Typography variant="h3" sx={{ fontSize: 28, fontWeight: 'bold', color: '#0A2B57', mt: 1 }}>
                    {summary?.total_applications || 0}
                  </Typography>
                </Box>
                <PeopleIcon sx={{ fontSize: 40, color: '#E8F1FC' }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="caption" color="text.secondary">Hồ sơ cần kiểm tra</Typography>
                  <Typography variant="h3" sx={{ fontSize: 28, fontWeight: 'bold', color: '#B54708', mt: 1 }}>
                    {summary?.files_needing_hr_review || 0}
                  </Typography>
                </Box>
                <WarningIcon sx={{ fontSize: 40, color: '#FFFAEB' }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="caption" color="text.secondary">Đã shortlist</Typography>
                  <Typography variant="h3" sx={{ fontSize: 28, fontWeight: 'bold', color: '#067647', mt: 1 }}>
                    {summary?.applications_by_status?.SHORTLIST || 0}
                  </Typography>
                </Box>
                <CheckCircleIcon sx={{ fontSize: 40, color: '#ECFDF3' }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Status Breakdown */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h4" sx={{ fontSize: 16, fontWeight: 600, mb: 2 }}>
                Phân bố trạng thái hồ sơ
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Trạng thái</TableCell>
                      <TableCell align="right">Số lượng</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    <TableRow>
                      <TableCell><StatusBadge type="app-new" label="Mới" /></TableCell>
                      <TableCell align="right">{summary?.applications_by_status?.NEW || 0}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell><StatusBadge type="app-review" label="Đang xem" /></TableCell>
                      <TableCell align="right">{summary?.applications_by_status?.IN_REVIEW || 0}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell><StatusBadge type="app-shortlist" label="Shortlist" /></TableCell>
                      <TableCell align="right">{summary?.applications_by_status?.SHORTLIST || 0}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell><StatusBadge type="app-rejected" label="Bị loại" /></TableCell>
                      <TableCell align="right">{summary?.applications_by_status?.REJECTED_SCREENING || 0}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell><StatusBadge type="app-review" label="Đang phỏng vấn" /></TableCell>
                      <TableCell align="right">{summary?.applications_by_status?.INTERVIEW || 0}</TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h4" sx={{ fontSize: 16, fontWeight: 600, mb: 2 }}>
                Chỉ số chất lượng Pilot
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Dữ liệu sẽ được thu thập trong quá trình chạy pilot để đánh giá hiệu quả.
              </Typography>
              <Box sx={{ '& > *': { mb: 1.5 } }}>
                <Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="body2">Tỷ lệ hồ sơ cần HR kiểm tra thủ công</Typography>
                    <Typography variant="body2" fontWeight={600}>-</Typography>
                  </Box>
                </Box>
                <Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="body2">Tỷ lệ HR điều chỉnh gợi ý AI (Override rate)</Typography>
                    <Typography variant="body2" fontWeight={600}>-</Typography>
                  </Box>
                </Box>
                <Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="body2">Thời gian rà soát trung bình/hồ sơ</Typography>
                    <Typography variant="body2" fontWeight={600}>Đang đo baseline</Typography>
                  </Box>
                </Box>
                <Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="body2">Độ phủ bằng chứng trung bình</Typography>
                    <Typography variant="body2" fontWeight={600}>-</Typography>
                  </Box>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}

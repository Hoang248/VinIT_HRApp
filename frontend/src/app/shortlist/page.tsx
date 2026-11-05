'use client';

import * as React from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
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
  IconButton,
  Tooltip,
} from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import ShareIcon from '@mui/icons-material/Share';
import { useEffect, useState } from 'react';
import { shortlistApi } from '@/lib/api';
import StatusBadge from '@/components/common/StatusBadge';
import { useRouter } from 'next/navigation';

export default function ShortlistPage() {
  const router = useRouter();
  const [shares, setShares] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const res = await shortlistApi.getSharedWithMe();
      // Also fetch shares I created (for Recruiter view) - placeholder for now
      setShares(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Không thể tải danh sách shortlist');
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
          Shortlist được chia sẻ
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Xem các shortlist đã được HR chia sẻ để bạn phản hồi
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <TableContainer component={Paper} sx={{ borderRadius: 2, boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Vị trí</TableCell>
              <TableCell>Chia sẻ bởi</TableCell>
              <TableCell>Số ứng viên</TableCell>
              <TableCell>Quyền xem CV</TableCell>
              <TableCell>Trạng thái</TableCell>
              <TableCell>Ngày chia sẻ</TableCell>
              <TableCell align="right">Thao tác</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {shares.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 8, color: 'text.secondary' }}>
                  Chưa có shortlist nào được chia sẻ với bạn
                </TableCell>
              </TableRow>
            ) : (
              shares.map((share) => (
                <TableRow key={share.share_id} hover>
                  <TableCell>
                    <Typography variant="body2" fontWeight={500}>
                      {share.position?.title}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" fontFamily="monospace">
                      {share.position?.position_code}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {share.created_by_profile?.display_name || 'HR Recruiter'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip label={`${share.application_count} ứng viên`} size="small" />
                  </TableCell>
                  <TableCell>
                    {share.allow_cv_view ? (
                      <StatusBadge type="file-completed" label="Được phép" />
                    ) : (
                      <StatusBadge type="file-review" label="Chỉ xem tóm tắt" />
                    )}
                  </TableCell>
                  <TableCell>
                    <StatusBadge
                      type={share.status === 'ACTIVE' ? 'app-shortlist' : 'app-rejected'}
                      label={share.status === 'ACTIVE' ? 'Đang hoạt động' : 'Đã thu hồi'}
                    />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {new Date(share.created_at).toLocaleDateString('vi-VN')}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="Xem chi tiết & phản hồi">
                      <IconButton sx={{ color: '#0A2B57' }}>
                        <VisibilityIcon />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}

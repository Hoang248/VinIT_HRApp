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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Divider,
  Avatar,
} from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import SendIcon from '@mui/icons-material/Send';
import PersonIcon from '@mui/icons-material/Person';
import { useEffect, useState } from 'react';
import { shortlistApi } from '@/lib/api';
import StatusBadge from '@/components/common/StatusBadge';
import { useRouter } from 'next/navigation';

interface FeedbackItem {
  feedback_id: string;
  author_user_id: string;
  author_profile?: { display_name?: string };
  content: string;
  created_at: string;
}

interface ShortlistShare {
  share_id: string;
  position?: { title?: string; position_code?: string };
  created_by_profile?: { display_name?: string };
  application_count?: number;
  allow_cv_view?: boolean;
  status?: string;
  created_at?: string;
  note?: string;
  feedback?: FeedbackItem[];
  applications?: Array<{
    application_id: string;
    candidate_name?: string;
    display_name?: string;
    matching_score?: number;
    matching_status?: string;
  }>;
}

export default function ShortlistPage() {
  const router = useRouter();
  const [shares, setShares] = useState<ShortlistShare[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedShare, setSelectedShare] = useState<ShortlistShare | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [feedbackText, setFeedbackText] = useState('');
  const [submittingFeedback, setSubmittingFeedback] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const res = await shortlistApi.getSharedWithMe();
      setShares(res.data || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Không thể tải danh sách shortlist');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenDetail = async (share: ShortlistShare) => {
    setSelectedShare(share);
    setFeedbackText('');
    try {
      setDetailLoading(true);
      const res = await shortlistApi.getDetail(share.share_id);
      setSelectedShare(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Không thể tải chi tiết shortlist');
    } finally {
      setDetailLoading(false);
    }
  };

  const handleCloseDetail = () => {
    setSelectedShare(null);
    setFeedbackText('');
  };

  const handleSubmitFeedback = async () => {
    if (!selectedShare || !feedbackText.trim()) return;
    try {
      setSubmittingFeedback(true);
      await shortlistApi.addFeedback(selectedShare.share_id, feedbackText.trim());
      // Reload detail
      const res = await shortlistApi.getDetail(selectedShare.share_id);
      setSelectedShare(res.data);
      setFeedbackText('');
      // Refresh list to update counts
      await loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Không thể gửi phản hồi');
    } finally {
      setSubmittingFeedback(false);
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
                    <Chip label={`${share.application_count || 0} ứng viên`} size="small" />
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
                      {share.created_at ? new Date(share.created_at).toLocaleDateString('vi-VN') : '—'}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="Xem chi tiết & phản hồi">
                      <IconButton
                        sx={{ color: '#0A2B57' }}
                        onClick={() => handleOpenDetail(share)}
                      >
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

      {/* Detail + Feedback Dialog */}
      <Dialog open={!!selectedShare} onClose={handleCloseDetail} maxWidth="md" fullWidth>
        {selectedShare && (
          <>
            <DialogTitle>
              <Typography variant="h6" color="#0A2B57">
                Shortlist — {selectedShare.position?.title}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Chia sẻ bởi {selectedShare.created_by_profile?.display_name || 'HR'} ·{' '}
                {selectedShare.created_at ? new Date(selectedShare.created_at).toLocaleDateString('vi-VN') : ''}
              </Typography>
            </DialogTitle>
            <DialogContent dividers>
              {detailLoading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                  <CircularProgress size={28} />
                </Box>
              ) : (
                <>
                  {selectedShare.note && (
                    <Alert severity="info" sx={{ mb: 2 }}>
                      <strong>Ghi chú từ HR:</strong> {selectedShare.note}
                    </Alert>
                  )}

                  <Typography variant="subtitle2" sx={{ mb: 1 }}>
                    Danh sách ứng viên ({selectedShare.applications?.length || 0})
                  </Typography>
                  <Box sx={{ mb: 3, border: '1px solid #F2F4F7', borderRadius: 1, maxHeight: 200, overflowY: 'auto' }}>
                    {(selectedShare.applications || []).map((a, idx) => (
                      <Box key={a.application_id} sx={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        py: 1,
                        px: 2,
                        borderBottom: idx < (selectedShare.applications?.length || 0) - 1 ? '1px solid #F2F4F7' : 'none'
                      }}>
                        <Typography variant="body2">{a.candidate_name || a.display_name || 'Ứng viên'}</Typography>
                        <Chip
                          size="small"
                          label={a.matching_status === 'MEETS_MANDATORY' ? 'Đáp ứng bắt buộc' : (a.matching_status || 'Chưa đánh giá')}
                          color={a.matching_status === 'MEETS_MANDATORY' ? 'success' : 'default'}
                        />
                      </Box>
                    ))}
                    {(!selectedShare.applications || selectedShare.applications.length === 0) && (
                      <Typography variant="body2" color="text.secondary" sx={{ py: 2, px: 2 }}>
                        Không có dữ liệu ứng viên.
                      </Typography>
                    )}
                  </Box>

                  <Divider sx={{ mb: 2 }} />

                  <Typography variant="subtitle2" sx={{ mb: 1 }}>
                    Phản hồi ({(selectedShare.feedback || []).length})
                  </Typography>
                  <Box sx={{ mb: 2, maxHeight: 180, overflowY: 'auto' }}>
                    {(selectedShare.feedback || []).length === 0 ? (
                      <Typography variant="body2" color="text.secondary">
                        Chưa có phản hồi nào.
                      </Typography>
                    ) : (
                      selectedShare.feedback!.map((f) => (
                        <Box key={f.feedback_id} sx={{ display: 'flex', gap: 1.5, mb: 2 }}>
                          <Avatar sx={{ width: 32, height: 32, bgcolor: '#0A2B57' }}>
                            <PersonIcon fontSize="small" />
                          </Avatar>
                          <Box sx={{ flex: 1 }}>
                            <Box sx={{ display: 'flex', gap: 1, alignItems: 'baseline' }}>
                              <Typography variant="body2" fontWeight={600}>
                                {f.author_profile?.display_name || 'Người dùng'}
                              </Typography>
                              <Typography variant="caption" color="text.secondary">
                                {new Date(f.created_at).toLocaleString('vi-VN')}
                              </Typography>
                            </Box>
                            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                              {f.content}
                            </Typography>
                          </Box>
                        </Box>
                      ))
                    )}
                  </Box>

                  {selectedShare.status === 'ACTIVE' && (
                    <Box sx={{ mt: 2 }}>
                      <TextField
                        label="Phản hồi của bạn"
                        multiline
                        rows={3}
                        fullWidth
                        value={feedbackText}
                        onChange={(e) => setFeedbackText(e.target.value)}
                        placeholder="Đánh giá tổng quan shortlist, đề xuất ứng viên nên mời phỏng vấn, lý do, câu hỏi thêm cho HR..."
                      />
                    </Box>
                  )}
                </>
              )}
            </DialogContent>
            <DialogActions>
              <Button onClick={handleCloseDetail}>Đóng</Button>
              {selectedShare.status === 'ACTIVE' && (
                <Button
                  variant="contained"
                  color="secondary"
                  endIcon={<SendIcon />}
                  onClick={handleSubmitFeedback}
                  disabled={!feedbackText.trim() || submittingFeedback}
                >
                  {submittingFeedback ? 'Đang gửi...' : 'Gửi phản hồi'}
                </Button>
              )}
            </DialogActions>
          </>
        )}
      </Dialog>
    </Box>
  );
}

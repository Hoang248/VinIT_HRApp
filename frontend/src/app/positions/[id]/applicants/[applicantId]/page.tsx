'use client';

import * as React from 'react';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  Grid,
  CircularProgress,
  Alert,
  Divider,
  Paper,
  Chip,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import GetAppIcon from '@mui/icons-material/GetApp';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore';
import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { applicationsApi } from '@/lib/api';
import StatusBadge from '@/components/common/StatusBadge';
import type { ApplicationWithAssessment } from '@/types';

// Outcome styling for evidence cards
const outcomeStyles: Record<string, { borderColor: string; label: string; color: string }> = {
  STRONG_MATCH: {
    borderColor: '#067647',
    label: 'Đáp ứng tốt',
    color: '#067647',
  },
  MATCH: {
    borderColor: '#0A2B57',
    label: 'Đáp ứng',
    color: '#0A2B57',
  },
  UNCLEAR: {
    borderColor: '#B54708',
    label: 'Chưa rõ',
    color: '#B54708',
  },
  NO_MATCH: {
    borderColor: '#C72127',
    label: 'Chưa đáp ứng',
    color: '#C72127',
  },
};

export default function ApplicantDetailPage() {
  const params = useParams();
  const router = useRouter();
  const positionId = params.id as string;
  const applicantId = params.applicantId as string;

  const [application, setApplication] = useState<ApplicationWithAssessment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusDialogOpen, setStatusDialogOpen] = useState(false);
  const [newStatus, setNewStatus] = useState('');
  const [statusNote, setStatusNote] = useState('');
  const [selectedPage, setSelectedPage] = useState(1);
  const [cvUrl, setCvUrl] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, [applicantId]);

  const loadData = async () => {
    try {
      setLoading(true);
      const res = await applicationsApi.getById(applicantId);
      setApplication(res.data);

      // Get CV URL/PDF
      const cvRes = await applicationsApi.getCvUrl(applicantId);
      if (cvRes.data.signed_url) {
        setCvUrl(cvRes.data.signed_url);
      } else if (cvRes.config?.url) {
        // Local file response will be handled as blob
        setCvUrl(cvRes.config.url);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Không thể tải thông tin hồ sơ');
    } finally {
      setLoading(false);
    }
  };

  const handleStatusUpdate = async () => {
    try {
      await applicationsApi.updateStatus(applicantId, newStatus, '', statusNote);
      setStatusDialogOpen(false);
      await loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Cập nhật trạng thái không thành công');
    }
  };

  const jumpToPage = (page: number) => {
    setSelectedPage(page);
    // Try to navigate native PDF viewer iframe via #page=N anchor (Chrome/Edge/FF support)
    if (cvUrl) {
      const iframe = document.getElementById('cv-pdf-viewer') as HTMLIFrameElement | null;
      if (iframe) {
        try {
          const sep = cvUrl.includes('#') ? '&' : '#';
          iframe.src = `${cvUrl}${sep}page=${page}`;
        } catch (_) { /* ignore */ }
      }
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 10 }}>
        <CircularProgress color="secondary" />
      </Box>
    );
  }

  if (!application) {
    return <Alert severity="error">Không tìm thấy hồ sơ ứng viên</Alert>;
  }

  const assessment = application.latest_assessment;
  const criteriaResults = assessment?.criterion_results || [];

  return (
    <Box>
      {/* Back button */}
      <Button
        component={Link}
        href={`/positions/${positionId}/applicants`}
        startIcon={<ArrowBackIcon />}
        sx={{ color: '#0A2B57', mb: 2 }}
      >
        Quay lại danh sách xếp hạng
      </Button>

      {/* Warnings */}
      {(application.file_processing_status === 'NEEDS_HR_REVIEW' || application.has_duplicate_warning) && (
        <Alert
          severity="warning"
          sx={{ mb: 2, border: '1px solid #FEDF89' }}
        >
          {application.file_processing_status === 'NEEDS_HR_REVIEW' && (
            <Typography variant="body2">
              <strong>CV cần được HR xem lại:</strong> {application.file_error || 'File CV có vấn đề (lỗi xử lý, định dạng quét/OCR cần thiết, hoặc bị mã hóa).'}
            </Typography>
          )}
          {application.has_duplicate_warning && (
            <Typography variant="body2" sx={{ mt: application.file_processing_status === 'NEEDS_HR_REVIEW' ? 0.5 : 0 }}>
              <strong>Cảnh báo trùng lặp:</strong> Phát hiện hồ sơ có thể đã tồn tại trong hệ thống. Vui lòng kiểm tra lại trước khi đưa ra quyết định.
            </Typography>
          )}
        </Alert>
      )}

      {/* Applicant Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
        <Box>
          <Typography variant="h1" sx={{ fontSize: 24, color: '#0A2B57', mb: 0.5 }}>
            {application.identity?.display_name || 'Hồ sơ ứng viên'}
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mt: 1, flexWrap: 'wrap' }}>
            <Typography variant="body2" color="text.secondary" fontFamily="monospace">
              ID: {application.application_id.slice(0, 8)}...
            </Typography>
            {application.file_processing_status === 'PROCESSING' && (
              <Chip label="Đang xử lý CV" size="small" />
            )}
            {application.has_duplicate_warning && (
              <Chip label="Hồ sơ trùng lặp" size="small" sx={{ backgroundColor: '#FEF0C7', color: '#B54708' }} />
            )}
            {assessment && (
              <>
                {assessment.matching_status === 'MEETS_MANDATORY' && (
                  <StatusBadge type="match-meets" label="Đáp ứng bắt buộc" />
                )}
                {assessment.matching_status === 'NEEDS_HR_VERIFICATION' && (
                  <StatusBadge type="match-verify" label="Cần HR xác minh" />
                )}
                {assessment.matching_status === 'POSSIBLE_MISMATCH' && (
                  <StatusBadge type="match-mismatch" label="Có dấu hiệu miss-match" />
                )}
              </>
            )}
            <StatusBadge
              type={
                application.application_status === 'NEW' ? 'app-new' :
                application.application_status === 'IN_REVIEW' ? 'app-review' :
                application.application_status === 'SHORTLIST' ? 'app-shortlist' : 'app-rejected'
              }
              label={
                application.application_status === 'NEW' ? 'Mới' :
                application.application_status === 'IN_REVIEW' ? 'Đang xem' :
                application.application_status === 'SHORTLIST' ? 'Shortlist' : 'Bị loại'
              }
            />
          </Box>
        </Box>

        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<GetAppIcon />}
            href={cvUrl || '#'}
            target="_blank"
            sx={{ borderColor: '#0A2B57', color: '#0A2B57' }}
          >
            Tải CV gốc
          </Button>
          <Button
            variant="outlined"
            color="error"
            startIcon={<CancelIcon />}
            onClick={() => { setNewStatus('REJECTED_SCREENING'); setStatusDialogOpen(true); }}
          >
            Loại vòng sàng lọc
          </Button>
          <Button
            variant="contained"
            color="secondary"
            startIcon={<CheckCircleIcon />}
            onClick={() => { setNewStatus('SHORTLIST'); setStatusDialogOpen(true); }}
          >
            Đưa vào Shortlist
          </Button>
        </Box>
      </Box>

      {/* Score summary */}
      {assessment && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={12} sm={4}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">Điểm matching tổng hợp</Typography>
                <Typography
                  variant="h3"
                  sx={{
                    fontSize: 32,
                    fontWeight: 'bold',
                    color: assessment.matching_score && assessment.matching_score >= 80 ? '#067647' :
                            assessment.matching_score && assessment.matching_score >= 60 ? '#0A2B57' : '#B54708',
                    mt: 1,
                  }}
                >
                  {assessment.matching_score !== null ? `${assessment.matching_score}%` : '-'}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">Độ phủ bằng chứng</Typography>
                <Typography
                  variant="h3"
                  sx={{
                    fontSize: 32,
                    fontWeight: 'bold',
                    color: (assessment.evidence_coverage || 0) >= 0.7 ? '#067647' : '#B54708',
                    mt: 1,
                  }}
                >
                  {assessment.evidence_coverage !== null ? `${Math.round(assessment.evidence_coverage * 100)}%` : '-'}
                </Typography>
                {(assessment.evidence_coverage || 0) < 0.7 && (
                  <Typography variant="caption" color="#B54708">
                    Cần xem xét kỹ
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">Số tiêu chí đánh giá</Typography>
                <Typography variant="h3" sx={{ fontSize: 32, fontWeight: 'bold', color: '#0A2B57', mt: 1 }}>
                  {criteriaResults.length}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {criteriaResults.filter(r => r.outcome === 'MATCH' || r.outcome === 'STRONG_MATCH').length} đáp ứng,{' '}
                  {criteriaResults.filter(r => r.outcome === 'UNCLEAR').length} chưa rõ
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Side-by-side layout: Evidence on left, CV on right */}
      <Grid container spacing={3}>
        {/* Left Column: Criteria Assessment & Evidence */}
        <Grid item xs={12} md={6}>
          <Typography variant="h4" sx={{ fontSize: 16, fontWeight: 600, color: '#0A2B57', mb: 2 }}>
            Kết quả đánh giá theo tiêu chí
          </Typography>

          {criteriaResults.length === 0 ? (
            <Card>
              <CardContent sx={{ textAlign: 'center', py: 6, color: 'text.secondary' }}>
                Chưa có kết quả đánh giá cho hồ sơ này
              </CardContent>
            </Card>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {criteriaResults.map((result) => {
                const style = outcomeStyles[result.outcome];
                return (
                  <Card
                    key={result.criterion_id}
                    className={`evidence-card ${result.outcome.toLowerCase().replace('_', '-')}`}
                    sx={{
                      borderLeft: `4px solid ${style.borderColor}`,
                      borderRadius: '0 8px 8px 0',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                    }}
                  >
                    <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                        <Box>
                          <Chip
                            label={style.label}
                            size="small"
                            sx={{
                              backgroundColor: `${style.borderColor}15`,
                              color: style.color,
                              fontWeight: 700,
                              fontSize: 11,
                              height: 22,
                              mr: 1,
                              mb: 0.5,
                            }}
                          />
                          <Chip
                            label={result.category === 'MUST_HAVE' ? 'Bắt buộc' : 'Ưu tiên'}
                            size="small"
                            sx={{
                              backgroundColor: result.category === 'MUST_HAVE' ? '#FDF2F2' : '#E8F1FC',
                              color: result.category === 'MUST_HAVE' ? '#941616' : '#0A2B57',
                              fontWeight: 600,
                              fontSize: 10,
                              height: 22,
                            }}
                          />
                        </Box>
                        {result.score !== null && (
                          <Typography variant="h6" sx={{ fontSize: 16, fontWeight: 'bold', color: style.color }}>
                            {result.score}%
                          </Typography>
                        )}
                      </Box>

                      <Typography variant="body1" sx={{ fontWeight: 600, fontSize: 14, mb: 0.5 }}>
                        {result.criterion_name}
                      </Typography>

                      {result.reasoning && (
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                          {result.reasoning}
                        </Typography>
                      )}

                      {/* Evidence Quote */}
                      {(result.verbatim_quote || (result.evidence && result.evidence.length > 0)) && (
                        <Paper
                          elevation={0}
                          sx={{
                            backgroundColor: '#F8FAFC',
                            borderLeft: '2px solid #E2E8F0',
                            p: 1.5,
                            borderRadius: 1,
                            mt: 1,
                            cursor: 'pointer',
                            '&:hover': { backgroundColor: '#F1F5F9' }
                          }}
                          onClick={() => jumpToPage(result.page_number || 1)}
                        >
                          <Typography
                            variant="body2"
                            sx={{
                              fontStyle: 'italic',
                              color: '#112434',
                              fontSize: 13,
                              lineHeight: 1.6,
                            }}
                          >
                            "{result.verbatim_quote || result.evidence?.[0]?.verbatim_quote}"
                          </Typography>
                          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 1 }}>
                            <Chip
                              label={`Trang ${result.page_number || result.evidence?.[0]?.page_number || '?'}`}
                              size="small"
                              sx={{
                                backgroundColor: '#0A2B57',
                                color: 'white',
                                fontWeight: 700,
                                fontSize: 10,
                                height: 20,
                              }}
                            />
                          </Box>
                        </Paper>
                      )}

                      {result.outcome === 'UNCLEAR' && (
                        <Alert severity="warning" icon={false} sx={{ mt: 2, py: 0, fontSize: 12 }}>
                          Không tìm thấy bằng chứng rõ ràng. Vui lòng kiểm tra CV để xác minh.
                        </Alert>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </Box>
          )}
        </Grid>

        {/* Right Column: CV Viewer */}
        <Grid item xs={12} md={6}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h4" sx={{ fontSize: 16, fontWeight: 600, color: '#0A2B57' }}>
              CV gốc
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Tooltip title="Trang trước">
                <IconButton size="small" disabled={selectedPage <= 1}>
                  <NavigateBeforeIcon />
                </IconButton>
              </Tooltip>
              <Typography variant="body2">Trang {selectedPage}</Typography>
              <Tooltip title="Trang sau">
                <IconButton size="small">
                  <NavigateNextIcon />
                </IconButton>
              </Tooltip>
            </Box>
          </Box>

          <Card sx={{ height: 'calc(100vh - 250px)', overflow: 'auto' }}>
            <CardContent sx={{ p: 0, height: '100%' }}>
              {cvUrl ? (
                <Box sx={{ height: '100%', backgroundColor: '#525659', padding: 2 }}>
                  <iframe
                    id="cv-pdf-viewer"
                    src={`${cvUrl}#page=${selectedPage}`}
                    width="100%"
                    height="100%"
                    style={{ border: 'none', backgroundColor: 'white' }}
                    title="CV Original"
                  />
                </Box>
              ) : (
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'text.secondary' }}>
                  <Typography variant="body2">Không thể tải CV. Vui lòng tải xuống để xem.</Typography>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Status Update Dialog */}
      <Dialog open={statusDialogOpen} onClose={() => setStatusDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ color: newStatus === 'SHORTLIST' ? '#067647' : '#B42318' }}>
          {newStatus === 'SHORTLIST' ? 'Xác nhận đưa vào Shortlist' : 'Xác nhận loại hồ sơ'}
        </DialogTitle>
        <DialogContent dividers>
          <Typography variant="body2" sx={{ mb: 2 }}>
            {newStatus === 'SHORTLIST'
              ? 'Hồ sơ sẽ được chuyển vào danh sách Shortlist để chia sẻ với Hiring Manager xem xét.'
              : 'Hồ sơ sẽ được đánh dấu loại ở vòng sàng lọc. Lý do của bạn sẽ được lưu vào lịch sử trạng thái.'}
          </Typography>
          <TextField
            label={newStatus === 'SHORTLIST' ? 'Ghi chú (tùy chọn)' : 'Lý do loại'}
            fullWidth
            multiline
            rows={3}
            value={statusNote}
            onChange={(e) => setStatusNote(e.target.value)}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setStatusDialogOpen(false)}>Hủy</Button>
          <Button
            variant="contained"
            color={newStatus === 'SHORTLIST' ? 'success' : 'error'}
            onClick={handleStatusUpdate}
          >
            Xác nhận
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

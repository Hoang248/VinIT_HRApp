'use client';

import { useI18n } from '@/i18n/I18nProvider';
import { localizeServerMessage } from '@/i18n/serverMessages';

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
  Select,
  InputLabel,
  FormControl,
  Snackbar,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import GetAppIcon from '@mui/icons-material/GetApp';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { applicationsApi } from '@/lib/api';
import StatusBadge from '@/components/common/StatusBadge';
import CandidateProfilePanel from '@/components/candidates/CandidateProfilePanel';
import HRNotesPanel from '@/components/candidates/HRNotesPanel';
import type { ApplicationWithAssessment } from '@/types';
import { APPLICATION_STATUSES, APPLICATION_TRANSITIONS, isApplicationStatus } from '@/lib/applicationStatus';

interface StatusEvent {
  event_id: string;
  previous_status: string | null;
  new_status: string;
  reason: string | null;
  note: string | null;
  changed_at: string;
  changed_by_name: string | null;
}

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
  const { t, dateLocale, locale } = useI18n();
  const params = useParams();
  const positionId = params.id as string;
  const applicantId = params.applicantId as string;

  const [application, setApplication] = useState<ApplicationWithAssessment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusDialogOpen, setStatusDialogOpen] = useState(false);
  const [newStatus, setNewStatus] = useState('');
  const [statusReason, setStatusReason] = useState('');
  const [statusNote, setStatusNote] = useState('');
  const [statusError, setStatusError] = useState<string | null>(null);
  const [statusSubmitting, setStatusSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [history, setHistory] = useState<StatusEvent[]>([]);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [selectedPage, setSelectedPage] = useState(1);
  const [cvUrl, setCvUrl] = useState<string | null>(null);
  const [cvError, setCvError] = useState<string | null>(null);
  const blobUrl = useRef<string | null>(null);
  const requestId = useRef(0);

  const loadData = useCallback(async (initial = false) => {
    const currentRequest = ++requestId.current;
    try {
      if (initial) setLoading(true);
      const res = await applicationsApi.getById(applicantId);
      if (currentRequest !== requestId.current) return;
      if (res.data.position_id !== positionId) throw new Error(t("Hồ sơ không thuộc vị trí này"));
      setApplication(res.data);
      setError(null);
      if (res.data.can_update_status) {
        applicationsApi.getStatusEvents(applicantId).then(events => {
          if (currentRequest === requestId.current) { setHistory(events.data || []); setHistoryError(null); }
        }).catch(() => { if (currentRequest === requestId.current) setHistoryError(t("Không thể tải lịch sử trạng thái.")); });
      } else { setHistory([]); setHistoryError(null); }
      if (res.data.can_view_cv) {
        try {
          const cvRes = await applicationsApi.getCvUrl(applicantId);
          if (currentRequest !== requestId.current) return;
          if (blobUrl.current) { URL.revokeObjectURL(blobUrl.current); blobUrl.current = null; }
          setCvError(null);
          if (typeof cvRes.data.signed_url === 'string') {
            setCvUrl(cvRes.data.signed_url);
          } else if (cvRes.data.source === 'local') {
            const file = await applicationsApi.getCvBlob(applicantId);
            if (currentRequest !== requestId.current) return;
            blobUrl.current = URL.createObjectURL(file.data);
            setCvUrl(blobUrl.current);
          } else {
            setCvUrl(null);
            setCvError(t("Không thể lấy đường dẫn CV."));
          }
        } catch {
          if (currentRequest === requestId.current) { setCvUrl(null); setCvError(t("Không thể tải CV gốc. Vui lòng thử lại sau.")); }
        }
      } else {
        if (blobUrl.current) { URL.revokeObjectURL(blobUrl.current); blobUrl.current = null; }
        setCvUrl(null); setCvError(null);
      }
    } catch (err: any) {
      if (currentRequest === requestId.current) {
        if (err.response?.status === 403 || err.response?.status === 404) setApplication(null);
        setError(err.response?.data?.detail || t("Không thể tải thông tin hồ sơ"));
      }
    } finally { if (currentRequest === requestId.current) setLoading(false); }
  }, [applicantId, positionId, t]);

  useEffect(() => {
    loadData(true);
    return () => { requestId.current += 1; if (blobUrl.current) { URL.revokeObjectURL(blobUrl.current); blobUrl.current = null; } };
  }, [loadData]);

  const handleStatusUpdate = async () => {
    if (!newStatus || statusSubmitting) return;
    const rejected = newStatus.startsWith('REJECTED');
    if (rejected && !statusReason.trim()) { setStatusError(t("Vui lòng nhập lý do loại hồ sơ.")); return; }
    try {
      setStatusSubmitting(true); setStatusError(null);
      await applicationsApi.updateStatus(applicantId, newStatus, statusReason.trim() || undefined, statusNote.trim() || undefined);
      setStatusDialogOpen(false); setSuccess(true);
      await loadData();
    } catch (err: any) {
      setStatusError(err.response?.data?.detail || t("Cập nhật trạng thái không thành công"));
    } finally { setStatusSubmitting(false); }
  };

  const jumpToPage = (page: number) => { if (page >= 1) setSelectedPage(page); };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 10 }}>
        <CircularProgress color="secondary" />
      </Box>
    );
  }

  if (!application) {
    return <Alert severity="error" action={<Button onClick={() => loadData(true)}>{t("Thử lại")}</Button>}>{t(error || "Không tìm thấy hồ sơ ứng viên")}</Alert>;
  }

  const assessment = application.latest_assessment;
  const criteriaResults = assessment?.criterion_results || [];
  const canViewEvidence = Boolean(application.can_view_assessment_evidence);
  const currentStatus = isApplicationStatus(application.application_status) ? application.application_status : null;
  const nextStatuses = currentStatus ? APPLICATION_TRANSITIONS[currentStatus] : [];
  const statusLabel = currentStatus ? APPLICATION_STATUSES[currentStatus] : null;
  const selectedLabel = isApplicationStatus(newStatus) ? t(APPLICATION_STATUSES[newStatus].label) : newStatus;
  const isPdf = application.documents?.[0]?.mime_type === 'application/pdf' || /\.pdf$/i.test(application.documents?.[0]?.original_filename || '');

  return (
    <Box>
      {/* Back button */}
      <Button
        component={Link}
        href={application.can_update_status ? `/positions/${positionId}/applicants` : '/shortlist'}
        startIcon={<ArrowBackIcon />}
        sx={{ color: '#0A2B57', mb: 2 }}
      >
        {application.can_update_status ? t("Quay lại danh sách xếp hạng") : t("Quay lại shortlist")}
      </Button>

      {/* Warnings */}
      {(application.file_processing_status === 'NEEDS_HR_REVIEW' || application.has_duplicate_warning) && (
        <Alert
          severity="warning"
          sx={{ mb: 2, border: '1px solid #FEDF89' }}
        >
          {application.file_processing_status === 'NEEDS_HR_REVIEW' && (
            <Typography variant="body2">
              <strong>{t("CV cần được HR xem lại:")}</strong> {application.file_error ? localizeServerMessage(application.file_error, locale) : t("File CV có vấn đề (lỗi xử lý, định dạng quét/OCR cần thiết, hoặc bị mã hóa).")}
            </Typography>
          )}
          {application.has_duplicate_warning && (
            <Typography variant="body2" sx={{ mt: application.file_processing_status === 'NEEDS_HR_REVIEW' ? 0.5 : 0 }}>
              <strong>{t("Cảnh báo trùng lặp:")}</strong> {t("Phát hiện hồ sơ có thể đã tồn tại trong hệ thống. Vui lòng kiểm tra lại trước khi đưa ra quyết định.")}</Typography>
          )}
        </Alert>
      )}

      {/* Applicant Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 2, flexWrap: 'wrap', mb: 2 }}>
        <Box>
          <Typography variant="h1" sx={{ fontSize: 24, color: '#0A2B57', mb: 0.5 }}>
            {application.identity?.display_name || t("Hồ sơ ứng viên")}
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mt: 1, flexWrap: 'wrap' }}>
            <Typography variant="body2" color="text.secondary" fontFamily="monospace">
              ID: {application.application_id.slice(0, 8)}...
            </Typography>
            {application.file_processing_status === 'PROCESSING' && (
              <Chip label={t("Đang xử lý CV")} size="small" />
            )}
            {application.has_duplicate_warning && (
              <Chip label={t("Hồ sơ trùng lặp")} size="small" sx={{ backgroundColor: '#FEF0C7', color: '#B54708' }} />
            )}
            {assessment && (
              <>
                {assessment.matching_status === 'MEETS_MANDATORY' && (
                  <StatusBadge type="match-meets" label={t("Đáp ứng bắt buộc")} />
                )}
                {assessment.matching_status === 'NEEDS_HR_VERIFICATION' && (
                  <StatusBadge type="match-verify" label={t("Cần HR xác minh")} />
                )}
                {assessment.matching_status === 'POSSIBLE_MISMATCH' && (
                  <StatusBadge type="match-mismatch" label={t("Có dấu hiệu miss-match")} />
                )}
              </>
            )}
            {statusLabel && <StatusBadge type={statusLabel.badge} label={t(statusLabel.label)} />}
          </Box>
        </Box>

        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          <Button
            variant="outlined"
            startIcon={<GetAppIcon />}
            href={cvUrl || '#'}
            target="_blank"
            rel="noreferrer"
            disabled={!cvUrl}
            sx={{ borderColor: '#0A2B57', color: '#0A2B57' }}
          >{t("Tải CV gốc")}</Button>
          {application.can_update_status && nextStatuses.length > 0 && (
            <FormControl size="small" sx={{ minWidth: 220 }}>
              <InputLabel id="application-status-label">{t("Cập nhật trạng thái")}</InputLabel>
              <Select
                labelId="application-status-label"
                value=""
                label={t("Cập nhật trạng thái")}
                onChange={(e) => {
                  if (e.target.value) {
                    setNewStatus(e.target.value);
                    setStatusReason(''); setStatusNote(''); setStatusError(null);
                    setStatusDialogOpen(true);
                  }
                }}
              >
                {nextStatuses.map(code => (
                  <MenuItem key={code} value={code}>{t(APPLICATION_STATUSES[code].label)}</MenuItem>
                ))}
              </Select>
            </FormControl>
          )}
          {application.can_update_status && currentStatus && nextStatuses.length === 0 && (
            <Chip label={t("Hồ sơ đã kết thúc")} size="small" color="default" />
          )}
        </Box>
      </Box>

      {application.can_view_cv && <CandidateProfilePanel key={applicantId} applicationId={applicantId} canEdit={!!application.can_update_status} onSaved={() => { loadData(); }} />}
      {application.can_manage_hr_notes && <HRNotesPanel key={applicantId} applicationId={applicantId} />}

      {application.can_update_status && (
        <Accordion disableGutters elevation={0} sx={{ mb: 3, border: '1px solid #E4E7EC', borderRadius: '8px !important', '&:before': { display: 'none' } }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />} aria-controls="status-history-content" id="status-history-header">
            <Typography fontWeight={600}>{t("Lịch sử trạng thái ")}{history.length > 0 && `(${history.length})`}</Typography>
          </AccordionSummary>
          <AccordionDetails id="status-history-content">
            {historyError ? <Alert severity="error">{t(historyError)}</Alert> : history.length === 0 ? (
              <Typography variant="body2" color="text.secondary">{t("Chưa có thay đổi trạng thái.")}</Typography>
            ) : history.map(event => (
              <Box key={event.event_id} sx={{ py: 1.5, borderTop: '1px solid #EDF1F5' }}>
                <Typography variant="body2" fontWeight={600}>
                  {event.previous_status && isApplicationStatus(event.previous_status) ? t(APPLICATION_STATUSES[event.previous_status].label) : event.previous_status || '—'} →{' '}
                  {isApplicationStatus(event.new_status) ? t(APPLICATION_STATUSES[event.new_status].label) : event.new_status}
                </Typography>
                <Typography variant="caption" color="text.secondary">{event.changed_by_name || 'HR'} · {new Date(event.changed_at).toLocaleString(dateLocale)}</Typography>
                {event.reason && <Typography variant="body2" sx={{ mt: 0.5, whiteSpace: 'pre-wrap' }}>{t("Lý do: ")}{event.reason}</Typography>}
                {event.note && <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap' }}>{t("Ghi chú: ")}{event.note}</Typography>}
              </Box>
            ))}
          </AccordionDetails>
        </Accordion>
      )}

      {assessment?.evidence_coverage != null && assessment.evidence_coverage < 0.7 && (
        <Alert severity="warning" sx={{ mb: 2 }}>{t("Chưa đủ dữ liệu để xếp hạng ổn định. Điểm chỉ mang tính tham khảo; HR cần kiểm tra bằng chứng trước khi quyết định.")}</Alert>
      )}

      {/* Score summary */}
      {assessment && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={12} sm={4}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">{t("Điểm matching tổng hợp")}</Typography>
                <Typography
                  variant="h3"
                  sx={{
                    fontSize: 32,
                    fontWeight: 'bold',
                    color: assessment.evidence_coverage != null && assessment.evidence_coverage < 0.7 ? '#B54708' :
                            assessment.matching_score != null && assessment.matching_score >= 80 ? '#067647' :
                            assessment.matching_score != null && assessment.matching_score >= 60 ? '#0A2B57' : '#B54708',
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
                <Typography variant="caption" color="text.secondary">{t("Độ phủ bằng chứng")}</Typography>
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
                {assessment.evidence_coverage !== null && assessment.evidence_coverage < 0.7 && (
                  <Typography variant="caption" color="#B54708">{t("Chưa đủ dữ liệu để xếp hạng ổn định")}</Typography>
                )}
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">{t("Số tiêu chí đánh giá")}</Typography>
                <Typography variant="h3" sx={{ fontSize: 32, fontWeight: 'bold', color: '#0A2B57', mt: 1 }}>
                  {canViewEvidence ? criteriaResults.length : '—'}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {canViewEvidence ? t("{0} đáp ứng, {1} chưa rõ", criteriaResults.filter(r => r.outcome === 'MATCH' || r.outcome === 'STRONG_MATCH').length, criteriaResults.filter(r => r.outcome === 'UNCLEAR').length) : t("Chỉ được phép xem tóm tắt")}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {t(error)}
        </Alert>
      )}

      {/* Side-by-side layout: Evidence on left, CV on right */}
      <Grid container spacing={3}>
        {/* Left Column: Criteria Assessment & Evidence */}
        <Grid item xs={12} md={6}>
          <Typography variant="h4" sx={{ fontSize: 16, fontWeight: 600, color: '#0A2B57', mb: 2 }}>{t("Kết quả đánh giá theo tiêu chí")}</Typography>

          {criteriaResults.length === 0 ? (
            <Card>
              <CardContent sx={{ textAlign: 'center', py: 6, color: 'text.secondary' }}>{assessment && !canViewEvidence ? t("Bản đánh giá này chỉ được chia sẻ ở chế độ tóm tắt.") : t("Chưa có kết quả đánh giá cho hồ sơ này")}</CardContent>
            </Card>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {criteriaResults.map((result) => {
                const style = outcomeStyles[result.outcome] || outcomeStyles.UNCLEAR;
                const citation = result.evidence?.[0];
                const verified = citation?.verification_status === 'VERIFIED' || citation?.verification_status === 'MANUAL_FIX';
                const page = citation?.page_number || result.page_number;
                const canJump = !!(verified && page && isPdf && cvUrl);
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
                            label={t(style.label)}
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
                            label={result.category === 'MUST_HAVE' ? t("Bắt buộc") : t("Ưu tiên")}
                            size="small"
                            sx={{
                              backgroundColor: result.category === 'MUST_HAVE' ? '#FDF2F2' : '#E8F1FC',
                              color: result.category === 'MUST_HAVE' ? '#941616' : '#0A2B57',
                              fontWeight: 600,
                              fontSize: 10,
                              height: 22,
                              mr: 1,
                            }}
                          />
                          {result.decision_source && (
                            <Chip
                              label={`${t(result.decision_source === 'RULE' ? "Theo quy tắc xác định" : result.decision_source === 'HYBRID' ? "Quy tắc + AI" : "AI đối chiếu")}${result.evidence_strength != null ? ` · ${Math.round(result.evidence_strength * 100)}%` : ''}`}
                              size="small"
                              sx={{
                                backgroundColor: result.decision_source === 'RULE' ? '#ECFDF3' : result.decision_source === 'HYBRID' ? '#F4EBFF' : '#F2F4F7',
                                color: result.decision_source === 'RULE' ? '#067647' : result.decision_source === 'HYBRID' ? '#6941C6' : '#344054',
                                fontWeight: 600,
                                fontSize: 10,
                                height: 22,
                              }}
                            />
                          )}
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
                            cursor: canJump ? 'pointer' : 'default',
                            '&:hover': canJump ? { backgroundColor: '#F1F5F9' } : undefined,
                          }}
                          role={canJump ? 'button' : undefined}
                          tabIndex={canJump ? 0 : undefined}
                          onClick={() => { if (canJump && page) jumpToPage(page); }}
                          onKeyDown={event => { if (canJump && page && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); jumpToPage(page); } }}
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
                            &ldquo;{result.verbatim_quote || result.evidence?.[0]?.verbatim_quote}&rdquo;
                          </Typography>
                          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 1 }}>
                            <Chip
                              label={!verified ? t("Trích dẫn chưa xác minh") : (isPdf && page ? t("Trang {0} · Đã xác minh", page) : t("Đoạn trích đã xác minh"))}
                              size="small"
                              sx={{
                                backgroundColor: verified ? '#0A2B57' : '#B54708',
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
                        <Alert severity="warning" icon={false} sx={{ mt: 2, py: 0, fontSize: 12 }}>{t("Không tìm thấy bằng chứng rõ ràng. Vui lòng kiểm tra CV để xác minh.")}</Alert>
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
            <Typography variant="h4" sx={{ fontSize: 16, fontWeight: 600, color: '#0A2B57' }}>{t("CV gốc")}</Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Tooltip title={t("Trang trước")}>
                <IconButton aria-label={t("Trang trước")} size="small" disabled={!cvUrl || !isPdf || selectedPage <= 1} onClick={() => jumpToPage(selectedPage - 1)}>
                  <NavigateBeforeIcon />
                </IconButton>
              </Tooltip>
              <Typography variant="body2">{t("Trang")} {selectedPage}</Typography>
              <Tooltip title={t("Trang sau")}>
                <IconButton aria-label={t("Trang sau")} size="small" disabled={!cvUrl || !isPdf} onClick={() => jumpToPage(selectedPage + 1)}>
                  <NavigateNextIcon />
                </IconButton>
              </Tooltip>
            </Box>
          </Box>

          <Card sx={{ height: 'calc(100vh - 250px)', overflow: 'auto' }}>
            <CardContent sx={{ p: 0, height: '100%' }}>
              {cvUrl && isPdf ? (
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
                  <Typography variant="body2">{!application.can_view_cv ? t("Shortlist này không cho phép xem CV gốc.") : cvError ? t(cvError) : (cvUrl && !isPdf ? t("Tệp DOCX cần được tải xuống để xem.") : t("Không thể tải CV. Vui lòng thử lại."))}</Typography>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Status changes follow the server transition matrix. */}
      <Dialog open={statusDialogOpen} onClose={() => !statusSubmitting && setStatusDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{t("Xác nhận chuyển sang: ")}{selectedLabel}</DialogTitle>
        <DialogContent dividers>
          <Typography variant="body2" sx={{ mb: 2 }}>{t("            Trạng thái hiện tại:")} <strong>{statusLabel ? t(statusLabel.label) : ""}</strong>{t(". Quyết định và lý do sẽ được lưu vào lịch sử hồ sơ.")}</Typography>
          {statusError && <Alert severity="error" sx={{ mb: 2 }}>{t(statusError)}</Alert>}
          {newStatus.startsWith('REJECTED') && (
            <TextField label={t("Lý do loại hồ sơ")} required fullWidth multiline minRows={2} value={statusReason}
              onChange={e => setStatusReason(e.target.value)} inputProps={{ maxLength: 1000 }} sx={{ mb: 2 }} />
          )}
          <TextField label={t("Ghi chú (tùy chọn)")} fullWidth multiline minRows={2} value={statusNote}
            onChange={e => setStatusNote(e.target.value)} inputProps={{ maxLength: 2000 }} />
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setStatusDialogOpen(false)} disabled={statusSubmitting}>{t("Hủy")}</Button>
          <Button variant="contained" color={newStatus.startsWith('REJECTED') ? 'error' : 'secondary'}
            disabled={statusSubmitting || (newStatus.startsWith('REJECTED') && !statusReason.trim())} onClick={handleStatusUpdate}>
            {statusSubmitting ? t("Đang lưu…") : t("Xác nhận")}
          </Button>
        </DialogActions>
      </Dialog>
      <Snackbar open={success} autoHideDuration={4000} onClose={() => setSuccess(false)}
        message={t("Đã cập nhật trạng thái hồ sơ")} />
    </Box>
  );
}

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
  LinearProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  OutlinedInput,
  InputAdornment,
  IconButton,
  Tooltip,
  Stack,
  Link as MuiLink,
  TextField,
  Snackbar,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import RefreshIcon from '@mui/icons-material/Refresh';
import VisibilityIcon from '@mui/icons-material/Visibility';
import SortIcon from '@mui/icons-material/Sort';
import BookmarkAddOutlinedIcon from '@mui/icons-material/BookmarkAddOutlined';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import PlaylistAddCheckIcon from '@mui/icons-material/PlaylistAddCheck';
import ShareIcon from '@mui/icons-material/Share';
import Checkbox from '@mui/material/Checkbox';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import DialogContentText from '@mui/material/DialogContentText';
import FormControlLabel from '@mui/material/FormControlLabel';
import Switch from '@mui/material/Switch';
import Autocomplete from '@mui/material/Autocomplete';
import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { assessmentsApi, operationsApi, applicationsApi, shortlistApi } from '@/lib/api';
import StatusBadge from '@/components/common/StatusBadge';
import type { RankingItem, UserSummary } from '@/types';
import { APPLICATION_STATUSES, isApplicationStatus } from '@/lib/applicationStatus';

const inScreening = (status?: string) => ['NEW', 'IN_REVIEW', 'SHORTLIST'].includes(status || '');

export default function ApplicantsRankingPage() {
  const { t } = useI18n();
  const params = useParams();
  const positionId = params.id as string;

  const [rankingItems, setRankingItems] = useState<RankingItem[]>([]);
  const [appsNeedingReview, setAppsNeedingReview] = useState<number>(0);
  const [duplicateCount, setDuplicateCount] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [assessing, setAssessing] = useState(false);
  const [operationStatus, setOperationStatus] = useState<{
    operation_id?: string;
    status?: string;
    progress?: { total: number; processed: number; failed: number; percent_complete: number };
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rankingError, setRankingError] = useState<string | null>(null);
  const [shareError, setShareError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Shortlist share dialog state
  const [shareDialogOpen, setShareDialogOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [shareRecipient, setShareRecipient] = useState<UserSummary | null>(null);
  const [shareRecipientQuery, setShareRecipientQuery] = useState('');
  const [shareRecipientOptions, setShareRecipientOptions] = useState<UserSummary[]>([]);
  const [shareAllowCv, setShareAllowCv] = useState(false);
  // F2.02: optional scorecard deadline (YYYY-MM-DD); empty = 3 working days.
  const [shareDueDate, setShareDueDate] = useState('');
  const [shareSubmitting, setShareSubmitting] = useState(false);

  const loadRanking = useCallback(async () => {
    try {
      const [rankRes, appsRes] = await Promise.all([
        assessmentsApi.getLatestRanking(positionId),
        applicationsApi.listAll(positionId),
      ]);
      const ranks: RankingItem[] = rankRes.data || [];
      const apps: any[] = appsRes;

      // Merge ranking with application flags
      const appMap = new Map<string, any>();
      apps.forEach((a: any) => appMap.set(a.application_id, a));
      const merged = ranks.filter((r: RankingItem) => inScreening(appMap.get(r.application_id)?.application_status)).map((r: RankingItem) => {
        const a = appMap.get(r.application_id) || {};
        return {
          ...r,
          file_processing_status: a.file_processing_status,
          file_error: a.file_error,
          has_duplicate_warning: a.has_duplicate_warning,
          application_status: a.application_status,
          is_shortlisted: a.application_status === 'SHORTLIST',
        };
      });

      // Add unassessed applications to list (if they exist in apps response but not ranks)
      const rankedIds = new Set(merged.map(r => r.application_id));
      apps.forEach((a: any) => {
        if (!rankedIds.has(a.application_id)) {
          const identity = a.identity;
          let name = t("Chưa trích xuất tên");
          if (Array.isArray(identity) && identity[0]) name = identity[0].display_name || name;
          else if (identity && typeof identity === 'object') name = identity.display_name || name;
          merged.push({
            application_id: a.application_id,
            candidate_name: name,
            rank_number: null,
            matching_status: 'NOT_ASSESSED' as const,
            matching_score: null,
            evidence_coverage: null,
            needs_verification: false,
            has_mismatch: false,
            file_processing_status: a.file_processing_status,
            file_error: a.file_error,
            has_duplicate_warning: a.has_duplicate_warning,
            application_status: a.application_status,
            is_shortlisted: a.application_status === 'SHORTLIST',
          });
        }
      });

      setRankingError(null);
      setRankingItems(merged);
      setAppsNeedingReview(merged.filter((i) =>
        i.needs_verification || i.file_processing_status === 'NEEDS_HR_REVIEW'
      ).length);
      setDuplicateCount(merged.filter((i) => i.has_duplicate_warning).length);
    } catch (err: any) {
      setRankingError(err.response?.data?.detail || t("Không thể tải bảng xếp hạng"));
    } finally {
      setLoading(false);
    }
  }, [positionId, t]);

  // Stop polling helper
  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  // Poll operation status
  const pollOperation = useCallback((operationId: string) => {
    stopPolling();
    pollTimerRef.current = setInterval(async () => {
      try {
        const res = await operationsApi.getStatus(operationId);
        const data = res.data;
        setOperationStatus(data);
        if (data.status === 'COMPLETED' || data.status === 'FAILED') {
          stopPolling();
          setAssessing(false);
          if (data.status === 'COMPLETED') {
            await loadRanking();
            setNotice(data.progress?.failed ? t("Hoàn tất với {0} tệp cần kiểm tra.", data.progress.failed) : t("Đã cập nhật kết quả xếp hạng."));
          } else {
            setError(t("Đánh giá thất bại: {0}", data.error_message ? localizeServerMessage(data.error_message) : t("Lỗi không xác định")));
          }
        }
      } catch (e) {
        setError(t("Không thể cập nhật tiến trình. Hệ thống sẽ thử lại."));
      }
    }, 2000);
  }, [loadRanking, stopPolling, t]);

  useEffect(() => {
    let mounted = true;
    loadRanking();
    operationsApi.getActiveForPosition(positionId).then(res => {
      if (mounted && res.data) { setAssessing(true); setOperationStatus(res.data); pollOperation(res.data.operation_id); }
    }).catch(() => { if (mounted) setError(t("Không thể tải tiến trình đang xử lý.")); });
    return () => { mounted = false; stopPolling(); };
  }, [loadRanking, stopPolling, pollOperation, positionId, t]);

  const handleRunAssessment = async () => {
    try {
      setAssessing(true);
      setError(null);
      const res = await assessmentsApi.runForPosition(positionId);
      if (String(res.data.status).toUpperCase() === 'COMPLETED') {
        setAssessing(false); setNotice(res.data.message || t("Không có hồ sơ cần đánh giá."));
        await loadRanking();
      } else {
        const opId = res.data.operation_id;
        setOperationStatus({ operation_id: opId, status: 'PENDING', progress: undefined });
        pollOperation(opId);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể chạy đánh giá"));
      setAssessing(false);
    }
  };

  // Only assigned, active Hiring Managers can be recipients.
  useEffect(() => {
    if (!shareDialogOpen) return;
    shortlistApi.getPotentialRecipients(positionId).then(res => setShareRecipientOptions(res.data || []))
      .catch(() => setShareError(t("Không thể tải danh sách Hiring Manager.")));
  }, [shareDialogOpen, positionId, t]);

  const handleToggleSelect = (appId: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(appId)) next.delete(appId);
      else next.add(appId);
      return next;
    });
  };

  const handleSelectAllVisible = () => {
    const visibleIds = filteredItems.filter(i => i.is_shortlisted).map(i => i.application_id);
    const allSelected = visibleIds.every(id => selectedIds.has(id));
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (allSelected) visibleIds.forEach(id => next.delete(id));
      else visibleIds.forEach(id => next.add(id));
      return next;
    });
  };

  const handleOpenShare = () => {
    // Pre-select shortlisted items
    const shortlisted = rankingItems.filter(i => i.is_shortlisted).map(i => i.application_id);
    setSelectedIds(previous => {
      const selected = shortlisted.filter(id => previous.has(id));
      return new Set(selected.length ? selected : shortlisted);
    });
    setShareError(null);
    setShareDueDate('');
    setShareDialogOpen(true);
  };

  const handleShareSubmit = async () => {
    if (!shareRecipient || selectedIds.size === 0) return;
    try {
      setShareSubmitting(true); setShareError(null);
      await shortlistApi.create({
        position_id: positionId,
        shared_with_user_id: shareRecipient.user_id,
        application_ids: Array.from(selectedIds),
        note: '',
        allow_cv_view: shareAllowCv,
        // End of the chosen day in the reviewer's local time.
        ...(shareDueDate ? { due_at: new Date(`${shareDueDate}T17:00:00`).toISOString() } : {}),
      });
      setShareDialogOpen(false);
      setShareRecipient(null);
      setShareRecipientQuery('');
      setSelectedIds(new Set());
      setShareAllowCv(false);
      setNotice(t("Đã chia sẻ shortlist. Hiring Manager có thể xem trong mục Shortlist."));
    } catch (err: any) {
      setShareError(err.response?.data?.detail || t("Không thể chia sẻ shortlist"));
    } finally {
      setShareSubmitting(false);
    }
  };

  const handleToggleShortlist = async (appId: string, currentlyShortlisted: boolean) => {
    const newStatus = currentlyShortlisted ? 'IN_REVIEW' : 'SHORTLIST';
    try {
      await applicationsApi.updateStatus(appId, newStatus);
      await loadRanking();
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể cập nhật trạng thái"));
    }
  };

  const displayCategory = (item: RankingItem) => {
    if (!inScreening(item.application_status)) return 'OUT_OF_SCREENING';
    if (!item.matching_status || item.matching_status === 'NOT_ASSESSED') return 'NOT_ASSESSED';
    if (item.has_mismatch) return 'POSSIBLE_MISMATCH';
    if (item.needs_verification) return 'NEEDS_HR_VERIFICATION';
    return 'MEETS_MANDATORY';
  };
  const filteredItems = rankingItems.filter(item => {
    if (filterStatus !== 'ALL' && displayCategory(item) !== filterStatus) return false;
    if (searchQuery && !item.candidate_name?.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const getMatchingStatusBadge = (item: RankingItem) => {
    if (!inScreening(item.application_status)) return <StatusBadge type="app-new" label={t("Ngoài sàng lọc")} />;
    if (item.matching_status === 'NOT_ASSESSED') return <StatusBadge type="app-new" label={t("Chưa có trong xếp hạng")} />;
    if (item.has_mismatch) {
      return <StatusBadge type="match-mismatch" label={t("Có dấu hiệu miss-match")} />;
    }
    if (item.needs_verification) {
      return <StatusBadge type="match-verify" label={t("Cần HR xác minh")} />;
    }
    return <StatusBadge type="match-meets" label={t("Đáp ứng bắt buộc")} />;
  };

  const getScoreColor = (score: number | null) => {
    if (score === null || score === undefined) return 'text.disabled';
    if (score >= 80) return '#067647';
    if (score >= 60) return '#0A2B57';
    return '#B54708';
  };

  const assessedCount = rankingItems.filter(i => i.matching_status && i.matching_status !== 'NOT_ASSESSED').length;
  const totalApplications = rankingItems.length;

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 10 }}>
        <CircularProgress color="secondary" />
      </Box>
    );
  }

  return (
    <Box>
      <Button component={Link} href={`/positions/${positionId}`} startIcon={<ArrowBackIcon />} sx={{ mb: 1 }}>{t("Quay lại vị trí")}</Button>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 2, mb: 3 }}>
        <Box>
          <Typography variant="h2" sx={{ fontSize: 22, color: '#0A2B57', mb: 0.5 }}>{t("Danh sách ưu tiên rà soát ứng viên")}</Typography>
          <Typography variant="body2" color="text.secondary">{t("Xếp hạng sàng lọc theo phiên bản tiêu chí mới nhất đã duyệt; số thứ hạng là tại lần chạy gần nhất.")}</Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={loadRanking}
            sx={{ borderColor: '#0A2B57', color: '#0A2B57' }}
          >{t("Làm mới")}</Button>
          <Button
            variant="outlined"
            startIcon={<ShareIcon />}
            onClick={handleOpenShare}
            sx={{ borderColor: '#0A2B57', color: '#0A2B57' }}
          >{t("Chia sẻ Shortlist")}</Button>
          <Button
            variant="contained"
            color="secondary"
            startIcon={assessing ? <CircularProgress size={18} color="inherit" /> : <PlaylistAddCheckIcon />}
            onClick={handleRunAssessment}
            disabled={assessing}
          >
            {assessing ? t("Đang đánh giá...") : t("Chạy đánh giá & xếp hạng")}
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {t(error)}
        </Alert>
      )}

      {/* Operation progress */}
      {operationStatus && operationStatus.status && operationStatus.status !== 'COMPLETED' && operationStatus.status !== 'FAILED' && (
        <Card sx={{ mb: 3, border: '1px solid #B2DDFF', backgroundColor: '#EFF8FF' }}>
          <CardContent sx={{ py: 2, '&:last-child': { pb: 2 } }}>
            <Stack direction="row" alignItems="center" spacing={2}>
              <CircularProgress size={20} sx={{ color: '#134D8B' }} />
              <Box sx={{ flex: 1 }}>
                <Typography variant="body2" fontWeight={600} color="#134D8B">
                  {assessing ? t("Đang xử lý đánh giá ứng viên...") : t("Đang xử lý...")}
                </Typography>
                {operationStatus.progress && (
                  <>
                    <LinearProgress
                      variant="determinate"
                      value={operationStatus.progress.percent_complete || 0}
                      sx={{ mt: 1, height: 6, borderRadius: 3, backgroundColor: '#D1E9FF' }}
                    />
                    <Typography variant="caption" color="#134D8B" sx={{ mt: 0.5, display: 'block' }}>{t("                      Đã xử lý")} {operationStatus.progress.processed}/{operationStatus.progress.total} {t("hồ sơ")}{operationStatus.progress.failed > 0 && t(" ({0} lỗi)", operationStatus.progress.failed)}
                    </Typography>
                  </>
                )}
              </Box>
            </Stack>
          </CardContent>
        </Card>
      )}

      {rankingError && <Alert severity="error" sx={{ mb: 3 }} action={<Button color="inherit" onClick={loadRanking}>{t("Thử lại")}</Button>}>{t(rankingError)}</Alert>}
      {!rankingError && <>
      {/* Summary cards */}
      <Stack direction="row" spacing={2} useFlexGap sx={{ mb: 3, flexWrap: 'wrap' }}>
        <Card sx={{ minWidth: 140, flex: '1 1 140px' }}>
          <CardContent sx={{ py: 2, '&:last-child': { pb: 2 } }}>
            <Typography variant="caption" color="text.secondary">{t("Tổng hồ sơ")}</Typography>
            <Typography variant="h4" sx={{ fontSize: 24, fontWeight: 'bold', color: '#0A2B57' }}>{totalApplications}</Typography>
          </CardContent>
        </Card>
        <Card sx={{ minWidth: 140, flex: '1 1 140px' }}>
          <CardContent sx={{ py: 2, '&:last-child': { pb: 2 } }}>
            <Typography variant="caption" color="text.secondary">{t("Có trong xếp hạng")}</Typography>
            <Typography variant="h4" sx={{ fontSize: 24, fontWeight: 'bold', color: '#067647' }}>{assessedCount}</Typography>
          </CardContent>
        </Card>
        <Card sx={{ minWidth: 140, flex: '1 1 140px', border: appsNeedingReview > 0 ? '1px solid #FEDF89' : undefined }}>
          <CardContent sx={{ py: 2, '&:last-child': { pb: 2 } }}>
            <Typography variant="caption" color="text.secondary">{t("Cần HR xác minh")}</Typography>
            <Typography variant="h4" sx={{ fontSize: 24, fontWeight: 'bold', color: appsNeedingReview > 0 ? '#B54708' : '#667085' }}>
              {appsNeedingReview}
            </Typography>
          </CardContent>
        </Card>
        {duplicateCount > 0 && (
          <Card sx={{ minWidth: 140, flex: '1 1 140px', border: '1px solid #FECDCA' }}>
            <CardContent sx={{ py: 2, '&:last-child': { pb: 2 } }}>
              <Typography variant="caption" color="text.secondary">{t("Cảnh báo trùng lặp")}</Typography>
              <Typography variant="h4" sx={{ fontSize: 24, fontWeight: 'bold', color: '#C72127' }}>
                {duplicateCount}
              </Typography>
            </CardContent>
          </Card>
        )}
      </Stack>

      {/* Filters */}
      <Box sx={{ display: 'flex', gap: 2, mb: 3, alignItems: 'center', flexWrap: 'wrap' }}>
        <OutlinedInput
          placeholder={t("Tìm kiếm theo tên ứng viên...")}
          startAdornment={
            <InputAdornment position="start">
              <SearchIcon sx={{ color: '#A09F9C' }} />
            </InputAdornment>
          }
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          sx={{
            maxWidth: 350,
            borderRadius: '30px',
            backgroundColor: '#F3EEEE',
            '&.Mui-focused': { backgroundColor: '#FFFFFF' }
          }}
          size="small"
        />
        <FormControl size="small" sx={{ minWidth: 220 }}>
          <InputLabel id="status-filter-label">{t("Lọc theo nhóm matching")}</InputLabel>
          <Select
            labelId="status-filter-label"
            value={filterStatus}
            label={t("Lọc theo nhóm matching")}
            onChange={(e) => setFilterStatus(e.target.value)}
          >
            <MenuItem value="ALL">{t("Tất cả (")}{totalApplications})</MenuItem>
            <MenuItem value="MEETS_MANDATORY">{t("              Đáp ứng bắt buộc (")}{rankingItems.filter(i => displayCategory(i) === 'MEETS_MANDATORY').length})
            </MenuItem>
            <MenuItem value="NEEDS_HR_VERIFICATION">{t("              Cần xác minh (")}{rankingItems.filter(i => displayCategory(i) === 'NEEDS_HR_VERIFICATION').length})
            </MenuItem>
            <MenuItem value="POSSIBLE_MISMATCH">{t("              Có dấu hiệu miss-match (")}{rankingItems.filter(i => displayCategory(i) === 'POSSIBLE_MISMATCH').length})
            </MenuItem>
            <MenuItem value="NOT_ASSESSED">{t("Chưa có trong xếp hạng (")}{rankingItems.filter(i => displayCategory(i) === 'NOT_ASSESSED').length})</MenuItem>
            <MenuItem value="OUT_OF_SCREENING">{t("Ngoài sàng lọc (")}{rankingItems.filter(i => displayCategory(i) === 'OUT_OF_SCREENING').length})</MenuItem>
          </Select>
        </FormControl>
      </Box>

      {/* Cards keep the primary actions visible on narrow screens. */}
      <Box sx={{ display: { xs: 'grid', md: 'none' }, gap: 2 }}>
        {filteredItems.length === 0 ? (
          <Paper sx={{ p: 4, textAlign: 'center', color: 'text.secondary' }}>
            {rankingItems.length === 0 ? t("Chưa có hồ sơ nào. Tải CV lên để bắt đầu.") : t("Không có hồ sơ nào phù hợp bộ lọc.")}
          </Paper>
        ) : filteredItems.map(item => (
          <Card key={item.application_id} sx={{ border: '1px solid #E9EEF4' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 1 }}>
                <Box><Typography variant="subtitle1" fontWeight={700} color="#0A2B57">{item.candidate_name || t("Chưa trích xuất tên")}</Typography>
                  <Typography variant="caption" color="text.secondary">{t("Thứ hạng: ")}{item.rank_number ?? '—'} · {item.application_status && isApplicationStatus(item.application_status) ? t(APPLICATION_STATUSES[item.application_status].label) : t("Chưa rõ trạng thái")}</Typography></Box>
                {getMatchingStatusBadge(item)}
              </Box>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1.5 }}>
                {item.file_processing_status === 'NEEDS_HR_REVIEW' && <Chip size="small" color="error" variant="outlined" label={t("Cần HR xử lý CV")} />}
                {item.has_duplicate_warning && <Chip size="small" color="warning" variant="outlined" label={t("Hồ sơ trùng lặp")} />}
                {item.evidence_coverage != null && item.evidence_coverage < 0.7 && <Chip size="small" color="warning" variant="outlined" label={t("Độ phủ thấp — cần xác minh")} />}
              </Box>
              <Typography variant="body2" sx={{ mt: 1.5 }}>{t("Điểm: ")}<strong>{item.matching_score == null ? '—' : `${item.matching_score}%`}</strong>{t("· Độ phủ: ")}<strong>{item.evidence_coverage == null ? '—' : `${Math.round(item.evidence_coverage * 100)}%`}</strong></Typography>
              {item.is_shortlisted && <FormControlLabel sx={{ display: 'flex', mt: 0.5 }} control={<Checkbox checked={selectedIds.has(item.application_id)} onChange={() => handleToggleSelect(item.application_id)} />} label={t("Chọn để chia sẻ")} />}
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1.5 }}>
                <Button component={Link} href={`/positions/${positionId}/applicants/${item.application_id}`} variant="outlined" size="small">{t("Xem chi tiết")}</Button>
                {(item.is_shortlisted || item.application_status === 'IN_REVIEW') && <Button size="small" onClick={() => handleToggleShortlist(item.application_id, !!item.is_shortlisted)}>{item.is_shortlisted ? t("Bỏ shortlist") : t("Thêm vào shortlist")}</Button>}
              </Box>
            </CardContent>
          </Card>
        ))}
      </Box>
      {/* Ranking Table */}
      <TableContainer component={Paper} sx={{ display: { xs: 'none', md: 'block' }, borderRadius: 2, boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <Table aria-label={t("Danh sách ưu tiên ứng viên")}>
          <TableHead>
            <TableRow>
              <TableCell padding="checkbox" width="40">
                <Checkbox
                  inputProps={{ 'aria-label': t("Chọn tất cả hồ sơ shortlist đang hiển thị") }}
                  checked={filteredItems.filter(i => i.is_shortlisted).length > 0 && filteredItems.filter(i => i.is_shortlisted).every(i => selectedIds.has(i.application_id))}
                  indeterminate={selectedIds.size > 0 && !filteredItems.filter(i => i.is_shortlisted).every(i => selectedIds.has(i.application_id))}
                  onChange={handleSelectAllVisible}
                  disabled={filteredItems.filter(i => i.is_shortlisted).length === 0}
                />
              </TableCell>
              <TableCell width="70">{t("Thứ hạng")}</TableCell>
              <TableCell>{t("Ứng viên")}</TableCell>
              <TableCell width="170">{t("Nhóm matching")}</TableCell>
              <TableCell width="110" align="center">{t("Điểm")}</TableCell>
              <TableCell width="160">{t("Độ phủ")}</TableCell>
              <TableCell width="100" align="center">Shortlist</TableCell>
              <TableCell width="100" align="right">Xem</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredItems.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} align="center" sx={{ py: 8, color: 'text.secondary' }}>
                  {rankingItems.length === 0
                    ? t("Chưa có hồ sơ nào được đánh giá. Tải CV lên và nhấn \"Chạy đánh giá & xếp hạng\" để xem danh sách.")
                    : t("Không có hồ sơ nào phù hợp bộ lọc.")}
                </TableCell>
              </TableRow>
            ) : (
              filteredItems.map((item) => (
                <TableRow key={item.application_id} hover selected={selectedIds.has(item.application_id)}>
                  <TableCell padding="checkbox">
                    <Checkbox
                      inputProps={{ 'aria-label': t("Chọn hồ sơ {0} để chia sẻ", item.candidate_name || t("ứng viên")) }}
                      checked={selectedIds.has(item.application_id)}
                      disabled={!item.is_shortlisted}
                      onChange={() => handleToggleSelect(item.application_id)}
                    />
                  </TableCell>
                  <TableCell>
                    <Typography
                      variant="h4"
                      sx={{
                        fontSize: 20,
                        fontWeight: 'bold',
                        color: item.rank_number ? '#0A2B57' : 'text.disabled',
                      }}
                    >
                      {item.rank_number ?? '—'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontWeight={500}>
                      {item.candidate_name || t("Chưa trích xuất tên")}
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5, flexWrap: 'wrap' }}>
                      {item.application_status && isApplicationStatus(item.application_status) && <Chip label={t(APPLICATION_STATUSES[item.application_status].label)} size="small" sx={{ height: 20, fontSize: 10 }} />}
                      {item.file_processing_status === 'NEEDS_HR_REVIEW' && (
                        <Chip
                          label={t("Cần HR xử lý CV")}
                          size="small"
                          icon={<ErrorOutlineIcon fontSize="small" />}
                          sx={{ height: 20, fontSize: 10, backgroundColor: '#FECDCA', color: '#B42318' }}
                        />
                      )}
                      {item.has_duplicate_warning && (
                        <Chip
                          label={t("Hồ sơ trùng lặp")}
                          size="small"
                          icon={<ErrorOutlineIcon fontSize="small" />}
                          sx={{ height: 20, fontSize: 10, backgroundColor: '#FEF0C7', color: '#B54708' }}
                        />
                      )}
                      {item.evidence_coverage != null && item.evidence_coverage < 0.7 && (
                        <Chip
                          label={t("Chưa đủ dữ liệu để xếp hạng ổn định")}
                          size="small"
                          icon={<ErrorOutlineIcon fontSize="small" />}
                          sx={{ height: 20, fontSize: 10, backgroundColor: '#FFFAEB', color: '#B54708' }}
                        />
                      )}
                      {item.file_processing_status === 'PROCESSING' && (
                        <Chip label={t("Đang xử lý")} size="small" sx={{ height: 20, fontSize: 10 }} />
                      )}
                    </Box>
                  </TableCell>
                  <TableCell>{getMatchingStatusBadge(item)}</TableCell>
                  <TableCell align="center">
                    <Typography
                      variant="h4"
                      sx={{
                        fontSize: 20,
                        fontWeight: 'bold',
                        color: item.evidence_coverage != null && item.evidence_coverage < 0.7 ? '#B54708' : getScoreColor(item.matching_score),
                      }}
                    >
                      {item.matching_score !== null && item.matching_score !== undefined
                        ? `${item.matching_score}%`
                        : '—'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Box sx={{ flex: 1 }}>
                        <LinearProgress
                          variant="determinate"
                          value={Math.round((item.evidence_coverage ?? 0) * 100)}
                          sx={{
                            height: 8,
                            borderRadius: 4,
                            backgroundColor: '#F2F4F7',
                            '& .MuiLinearProgress-bar': {
                              backgroundColor:
                                (item.evidence_coverage ?? 0) >= 0.7 ? '#067647'
                                : (item.evidence_coverage ?? 0) >= 0.5 ? '#B54708'
                                : '#C72127',
                              borderRadius: 4,
                            },
                          }}
                        />
                      </Box>
                      <Typography variant="caption" sx={{ minWidth: 36, textAlign: 'right' }}>
                        {item.evidence_coverage !== null && item.evidence_coverage !== undefined
                          ? `${Math.round(item.evidence_coverage * 100)}%`
                          : '—'}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell align="center">
                    <Tooltip title={item.is_shortlisted ? t("Bỏ shortlist") : item.application_status === 'IN_REVIEW' ? t("Thêm vào Shortlist") : t("Chuyển hồ sơ sang Đang xem trước khi shortlist")}>
                      <span><IconButton
                        color={item.is_shortlisted ? "secondary" : "default"}
                        onClick={(e) => {
                          e.preventDefault();
                          handleToggleShortlist(item.application_id, !!item.is_shortlisted);
                        }}
                        size="small"
                        aria-label={item.is_shortlisted ? t("Bỏ shortlist") : t("Thêm vào shortlist")}
                        disabled={!item.is_shortlisted && item.application_status !== 'IN_REVIEW'}
                      >
                        <BookmarkAddOutlinedIcon fontSize="small" />
                      </IconButton></span>
                    </Tooltip>
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title={t("Xem chi tiết & đối chiếu bằng chứng")}>
                      <IconButton
                        component={Link}
                        href={`/positions/${positionId}/applicants/${item.application_id}`}
                        aria-label={t("Xem chi tiết hồ sơ {0}", item.candidate_name || t("ứng viên"))}
                        sx={{ color: '#0A2B57' }}
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
      </>}

      {/* Shortlist Share Dialog */}
      <Dialog open={shareDialogOpen} onClose={() => !shareSubmitting && setShareDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{t("Chia sẻ Shortlist cho Hiring Manager")}</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ mb: 2 }}>{t("Chọn Hiring Manager phụ trách và hồ sơ đang ở trạng thái Shortlist. Người nhận có thể xem trong mục Shortlist.")}</DialogContentText>
          {shareError && <Alert severity="error" sx={{ mb: 2 }}>{t(shareError)}</Alert>}
          <Autocomplete
            noOptionsText={t("Chưa có Hiring Manager được phân công")}
            options={shareRecipientOptions}
            getOptionLabel={(opt: any) => opt.display_name || ''}
            isOptionEqualToValue={(opt: any, val: any) => opt.user_id === val?.user_id}
            inputValue={shareRecipientQuery}
            onInputChange={(_, val) => setShareRecipientQuery(val)}
            value={shareRecipient}
            onChange={(_, val) => setShareRecipient(val as UserSummary | null)}
            renderInput={(params) => (
              <TextField
                {...params}
                label={t("Chọn người nhận (gõ tên để tìm)")}
                margin="normal"
                fullWidth
                required
              />
            )}
          />
          <Box sx={{ mt: 2 }}>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>{t("              Ứng viên được chia sẻ (")}{selectedIds.size})
            </Typography>
            <Box sx={{ maxHeight: 220, overflowY: 'auto', border: '1px solid #F2F4F7', borderRadius: 1, p: 1 }}>
              {rankingItems.filter(i => selectedIds.has(i.application_id)).map(i => (
                <Box key={i.application_id} sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  py: 0.75,
                  px: 1,
                  borderRadius: 1,
                  '&:hover': { backgroundColor: '#F9FAFB' }
                }}>
                  <Typography variant="body2">{i.candidate_name}</Typography>
                  <Chip
                    size="small"
                    label={i.matching_status === 'MEETS_MANDATORY' ? t("Đáp ứng") : t("Cần xem xét")}
                    color={i.matching_status === 'MEETS_MANDATORY' ? 'success' : 'warning'}
                  />
                </Box>
              ))}
              {selectedIds.size === 0 && (
                <Typography variant="caption" color="text.secondary">{t("Chưa chọn ứng viên nào. Hãy đánh dấu vào ô chọn ứng viên shortlist.")}</Typography>
              )}
            </Box>
            <FormControlLabel
              control={
                <Switch
                  checked={shareAllowCv}
                  onChange={(e) => setShareAllowCv(e.target.checked)}
                />
              }
              label={t("Cho phép người nhận xem và tải CV gốc")}
              sx={{ mt: 2 }}
            />
            <TextField type="date" fullWidth size="small" sx={{ mt: 2 }} label={t("Hạn hoàn thành scorecard")}
              value={shareDueDate} onChange={e => setShareDueDate(e.target.value)} InputLabelProps={{ shrink: true }}
              inputProps={{ min: new Date().toISOString().slice(0, 10) }}
              helperText={t("Để trống để dùng mặc định 3 ngày làm việc (không tính thứ Bảy, Chủ Nhật; chưa tính ngày lễ). Mỗi ứng viên có một scorecard cho Hiring Manager.")} />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShareDialogOpen(false)} disabled={shareSubmitting}>{t("Hủy")}</Button>
          <Button
            variant="contained"
            color="secondary"
            onClick={handleShareSubmit}
            disabled={!shareRecipient || selectedIds.size === 0 || shareSubmitting}
          >
            {shareSubmitting ? t("Đang gửi...") : t("Chia sẻ")}
          </Button>
        </DialogActions>
      </Dialog>
      <Snackbar open={!!notice} autoHideDuration={5000} onClose={() => setNotice(null)} message={notice ? t(notice) : ""} />
    </Box>
  );
}

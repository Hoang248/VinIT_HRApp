'use client';

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
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import RefreshIcon from '@mui/icons-material/Refresh';
import VisibilityIcon from '@mui/icons-material/Visibility';
import SortIcon from '@mui/icons-material/Sort';
import ContentCutIcon from '@mui/icons-material/ContentCut';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import PlaylistAddCheckIcon from '@mui/icons-material/PlaylistAddCheck';
import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { assessmentsApi, operationsApi, applicationsApi } from '@/lib/api';
import StatusBadge from '@/components/common/StatusBadge';
import type { RankingItem } from '@/types';

export default function ApplicantsRankingPage() {
  const params = useParams();
  const router = useRouter();
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
  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadRanking = useCallback(async () => {
    try {
      const res = await assessmentsApi.getLatestRanking(positionId);
      setRankingItems(res.data || []);
      // Counts
      setAppsNeedingReview((res.data || []).filter((i: RankingItem) =>
        i.needs_verification && (i.evidence_coverage ?? 0) < 0.7
      ).length);
      setDuplicateCount((res.data || []).filter((i: RankingItem) => i.has_mismatch).length);
    } catch (err: any) {
      if (err.response?.status !== 404) {
        setError(err.response?.data?.detail || 'Không thể tải bảng xếp hạng');
      }
    } finally {
      setLoading(false);
    }
  }, [positionId]);

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
            // Small delay to ensure ranking is written
            setTimeout(() => loadRanking(), 1500);
          } else {
            setError(`Đánh giá thất bại: ${data.error_message || 'Lỗi không xác định'}`);
          }
        }
      } catch (e) {
        stopPolling();
        setAssessing(false);
      }
    }, 2000);
  }, [loadRanking, stopPolling]);

  useEffect(() => {
    loadRanking();
    return () => stopPolling();
  }, [loadRanking, stopPolling]);

  const handleRunAssessment = async () => {
    try {
      setAssessing(true);
      setError(null);
      const res = await assessmentsApi.runForPosition(positionId);
      const opId = res.data.operation_id;
      setOperationStatus({ operation_id: opId, status: 'PENDING', progress: undefined });
      pollOperation(opId);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Không thể chạy đánh giá');
      setAssessing(false);
    }
  };

  const filteredItems = rankingItems.filter(item => {
    if (filterStatus !== 'ALL' && item.matching_status !== filterStatus) return false;
    if (searchQuery && !item.candidate_name?.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const getMatchingStatusBadge = (item: RankingItem) => {
    if (item.has_mismatch) {
      return <StatusBadge type="match-mismatch" label="Có dấu hiệu miss-match" />;
    }
    if (item.needs_verification) {
      return <StatusBadge type="match-verify" label="Cần HR xác minh" />;
    }
    return <StatusBadge type="match-meets" label="Đáp ứng bắt buộc" />;
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
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
        <Box>
          <Typography variant="h2" sx={{ fontSize: 22, color: '#0A2B57', mb: 0.5 }}>
            Danh sách ưu tiên rà soát ứng viên
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Xếp hạng trong cùng vị trí theo tiêu chí đã duyệt: ưu tiên đáp ứng tiêu chí bắt buộc trước, sau đó đến điểm số
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={loadRanking}
            sx={{ borderColor: '#0A2B57', color: '#0A2B57' }}
          >
            Làm mới
          </Button>
          <Button
            variant="contained"
            color="secondary"
            startIcon={assessing ? <CircularProgress size={18} color="inherit" /> : <PlaylistAddCheckIcon />}
            onClick={handleRunAssessment}
            disabled={assessing}
          >
            {assessing ? 'Đang đánh giá...' : 'Chạy đánh giá & xếp hạng'}
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
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
                  {assessing ? 'Đang xử lý đánh giá ứng viên...' : 'Đang xử lý...'}
                </Typography>
                {operationStatus.progress && (
                  <>
                    <LinearProgress
                      variant="determinate"
                      value={operationStatus.progress.percent_complete || 0}
                      sx={{ mt: 1, height: 6, borderRadius: 3, backgroundColor: '#D1E9FF' }}
                    />
                    <Typography variant="caption" color="#134D8B" sx={{ mt: 0.5, display: 'block' }}>
                      Đã xử lý {operationStatus.progress.processed}/{operationStatus.progress.total} hồ sơ
                      {operationStatus.progress.failed > 0 && ` (${operationStatus.progress.failed} lỗi)`}
                    </Typography>
                  </>
                )}
              </Box>
            </Stack>
          </CardContent>
        </Card>
      )}

      {/* Summary cards */}
      <Stack direction="row" spacing={2} sx={{ mb: 3, flexWrap: 'wrap' }}>
        <Card sx={{ minWidth: 180, flex: '1 1 180px' }}>
          <CardContent sx={{ py: 2, '&:last-child': { pb: 2 } }}>
            <Typography variant="caption" color="text.secondary">Tổng hồ sơ</Typography>
            <Typography variant="h4" sx={{ fontSize: 24, fontWeight: 'bold', color: '#0A2B57' }}>{totalApplications}</Typography>
          </CardContent>
        </Card>
        <Card sx={{ minWidth: 180, flex: '1 1 180px' }}>
          <CardContent sx={{ py: 2, '&:last-child': { pb: 2 } }}>
            <Typography variant="caption" color="text.secondary">Đã đánh giá</Typography>
            <Typography variant="h4" sx={{ fontSize: 24, fontWeight: 'bold', color: '#067647' }}>{assessedCount}</Typography>
          </CardContent>
        </Card>
        <Card sx={{ minWidth: 180, flex: '1 1 180px', border: appsNeedingReview > 0 ? '1px solid #FEDF89' : undefined }}>
          <CardContent sx={{ py: 2, '&:last-child': { pb: 2 } }}>
            <Typography variant="caption" color="text.secondary">Cần HR xác minh</Typography>
            <Typography variant="h4" sx={{ fontSize: 24, fontWeight: 'bold', color: appsNeedingReview > 0 ? '#B54708' : '#667085' }}>
              {appsNeedingReview}
            </Typography>
          </CardContent>
        </Card>
        {duplicateCount > 0 && (
          <Card sx={{ minWidth: 180, flex: '1 1 180px', border: '1px solid #FECDCA' }}>
            <CardContent sx={{ py: 2, '&:last-child': { pb: 2 } }}>
              <Typography variant="caption" color="text.secondary">Cảnh báo trùng lặp</Typography>
              <Typography variant="h4" sx={{ fontSize: 24, fontWeight: 'bold', color: '#C72127' }}>
                {duplicateCount}
              </Typography>
            </CardContent>
          </Card>
        )}
      </Stack>

      {/* Filters */}
      <Box sx={{ display: 'flex', gap: 2, mb: 3, alignItems: 'center' }}>
        <OutlinedInput
          placeholder="Tìm kiếm theo tên ứng viên..."
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
          <InputLabel id="status-filter-label">Lọc theo nhóm matching</InputLabel>
          <Select
            labelId="status-filter-label"
            value={filterStatus}
            label="Lọc theo nhóm matching"
            onChange={(e) => setFilterStatus(e.target.value)}
          >
            <MenuItem value="ALL">Tất cả ({totalApplications})</MenuItem>
            <MenuItem value="MEETS_MANDATORY">
              Đáp ứng bắt buộc ({rankingItems.filter(i => !i.has_mismatch && !i.needs_verification).length})
            </MenuItem>
            <MenuItem value="NEEDS_HR_VERIFICATION">
              Cần xác minh ({rankingItems.filter(i => i.needs_verification).length})
            </MenuItem>
            <MenuItem value="POSSIBLE_MISMATCH">
              Có dấu hiệu miss-match ({rankingItems.filter(i => i.has_mismatch).length})
            </MenuItem>
            <MenuItem value="NOT_ASSESSED">Chưa đánh giá ({rankingItems.filter(i => !i.matching_status || i.matching_status === 'NOT_ASSESSED').length})</MenuItem>
          </Select>
        </FormControl>
      </Box>

      {/* Ranking Table */}
      <TableContainer component={Paper} sx={{ borderRadius: 2, boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell width="80">Thứ hạng</TableCell>
              <TableCell>Ứng viên</TableCell>
              <TableCell width="160">Nhóm matching</TableCell>
              <TableCell width="120" align="center">Điểm matching</TableCell>
              <TableCell width="170">Độ phủ bằng chứng</TableCell>
              <TableCell width="120" align="right">Thao tác</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredItems.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center" sx={{ py: 8, color: 'text.secondary' }}>
                  {rankingItems.length === 0
                    ? 'Chưa có hồ sơ nào được đánh giá. Tải CV lên và nhấn "Chạy đánh giá & xếp hạng" để xem danh sách.'
                    : 'Không có hồ sơ nào phù hợp bộ lọc.'}
                </TableCell>
              </TableRow>
            ) : (
              filteredItems.map((item) => (
                <TableRow key={item.application_id} hover>
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
                      {item.candidate_name || 'Chưa trích xuất tên'}
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5, flexWrap: 'wrap' }}>
                      {item.needs_verification && (item.evidence_coverage ?? 0) < 0.7 && (
                        <Chip
                          label="Độ phủ bằng chứng thấp"
                          size="small"
                          icon={<ErrorOutlineIcon fontSize="small" />}
                          sx={{
                            height: 20,
                            fontSize: 10,
                            backgroundColor: '#FFFAEB',
                            color: '#B54708',
                          }}
                        />
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
                        color: getScoreColor(item.matching_score),
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
                  <TableCell align="right">
                    <Tooltip title="Xem chi tiết & đối chiếu bằng chứng">
                      <IconButton
                        component={Link}
                        href={`/positions/${positionId}/applicants/${item.application_id}`}
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
    </Box>
  );
}

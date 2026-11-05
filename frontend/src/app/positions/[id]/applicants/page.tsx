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
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import RefreshIcon from '@mui/icons-material/Refresh';
import VisibilityIcon from '@mui/icons-material/Visibility';
import SortIcon from '@mui/icons-material/Sort';
import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { assessmentsApi } from '@/lib/api';
import StatusBadge from '@/components/common/StatusBadge';
import type { RankingItem } from '@/types';

export default function ApplicantsRankingPage() {
  const params = useParams();
  const router = useRouter();
  const positionId = params.id as string;

  const [rankingItems, setRankingItems] = useState<RankingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  const loadRanking = useCallback(async () => {
    try {
      setLoading(true);
      const res = await assessmentsApi.getLatestRanking(positionId);
      setRankingItems(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Không thể tải bảng xếp hạng');
    } finally {
      setLoading(false);
    }
  }, [positionId]);

  useEffect(() => {
    loadRanking();
  }, [loadRanking]);

  const handleGenerateRanking = async () => {
    try {
      setGenerating(true);
      await assessmentsApi.generateRanking(positionId);
      await loadRanking();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Không thể tạo xếp hạng');
    } finally {
      setGenerating(false);
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

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 10 }}>
        <CircularProgress color="secondary" />
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
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
            startIcon={<SortIcon />}
            onClick={handleGenerateRanking}
            disabled={generating}
          >
            {generating ? <CircularProgress size={20} color="inherit" sx={{ mr: 1 }} /> : null}
            Tạo/cập nhật xếp hạng
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

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
            '&.Mui-focused': {
              backgroundColor: '#FFFFFF',
            }
          }}
          size="small"
        />
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel id="status-filter-label">Lọc theo nhóm matching</InputLabel>
          <Select
            labelId="status-filter-label"
            value={filterStatus}
            label="Lọc theo nhóm matching"
            onChange={(e) => setFilterStatus(e.target.value)}
          >
            <MenuItem value="ALL">Tất cả</MenuItem>
            <MenuItem value="MEETS_MANDATORY">Đáp ứng bắt buộc</MenuItem>
            <MenuItem value="NEEDS_HR_VERIFICATION">Cần xác minh</MenuItem>
            <MenuItem value="POSSIBLE_MISMATCH">Có dấu hiệu miss-match</MenuItem>
            <MenuItem value="NOT_ASSESSED">Chưa đánh giá</MenuItem>
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
              <TableCell width="150">Nhóm matching</TableCell>
              <TableCell width="120" align="center">Điểm matching</TableCell>
              <TableCell width="150">Độ phủ bằng chứng</TableCell>
              <TableCell width="120" align="right">Thao tác</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredItems.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center" sx={{ py: 8, color: 'text.secondary' }}>
                  Chưa có dữ liệu xếp hạng. Vui lòng tải lên CV và tạo xếp hạng để xem danh sách.
                </TableCell>
              </TableRow>
            ) : (
              filteredItems.map((item) => (
                <TableRow
                  key={item.application_id}
                  hover
                  sx={{ cursor: 'pointer' }}
                  onClick={() => router.push(`/positions/${positionId}/applicants/${item.application_id}`)}
                >
                  <TableCell>
                    {item.rank_number ? (
                      <Typography
                        variant="h4"
                        sx={{
                          fontSize: 20,
                          fontWeight: 'bold',
                          color: item.rank_number <= 3 ? '#C72127' : '#0A2B57',
                          textAlign: 'center',
                        }}
                      >
                        #{item.rank_number}
                      </Typography>
                    ) : (
                      <Typography variant="caption" color="text.disabled" sx={{ display: 'block', textAlign: 'center' }}>
                        Chưa xếp hạng
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontWeight={500}>
                      {item.candidate_name || 'Chưa trích xuất tên'}
                    </Typography>
                    {item.needs_verification && item.evidence_coverage < 0.7 && (
                      <Chip
                        label="Độ phủ bằng chứng thấp"
                        size="small"
                        sx={{
                          mt: 0.5,
                          height: 20,
                          fontSize: 10,
                          backgroundColor: '#FFFAEB',
                          color: '#B54708',
                        }}
                      />
                    )}
                  </TableCell>
                  <TableCell>{getMatchingStatusBadge(item)}</TableCell>
                  <TableCell align="center">
                    <Typography
                      variant="h6"
                      sx={{
                        fontSize: 18,
                        fontWeight: 'bold',
                        color: getScoreColor(item.matching_score),
                      }}
                    >
                      {item.matching_score !== null && item.matching_score !== undefined
                        ? `${item.matching_score}%`
                        : '-'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Box sx={{ flexGrow: 1 }}>
                        <LinearProgress
                          variant="determinate"
                          value={Math.round((item.evidence_coverage || 0) * 100)}
                          sx={{
                            height: 6,
                            borderRadius: 3,
                            backgroundColor: '#E2E8F0',
                            '& .MuiLinearProgress-bar': {
                              backgroundColor:
                                (item.evidence_coverage || 0) >= 0.7 ? '#067647' : '#B54708',
                              borderRadius: 3,
                            }
                          }}
                        />
                      </Box>
                      <Typography variant="caption" fontWeight={600}>
                        {Math.round((item.evidence_coverage || 0) * 100)}%
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="Xem chi tiết & bằng chứng">
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

      {/* Legend */}
      <Card sx={{ mt: 3, backgroundColor: '#F8FAFC' }}>
        <CardContent>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
            <strong>Ghi chú:</strong>
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
            • Thứ tự xếp hạng chỉ áp dụng trong cùng vị trí, không so sánh giữa các vị trí khác nhau.
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
            • Hồ sơ "Cần HR xác minh" hoặc độ phủ dưới 70% cần được rà soát thủ công trước khi đưa ra quyết định.
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
            • "Có dấu hiệu miss-match" là cảnh báo về tiêu chí bắt buộc không được đáp ứng, <strong>không phải trạng thái tự động loại</strong>.
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
            • AI chỉ hỗ trợ ưu tiên thứ tự rà soát, mọi quyết định shortlist/loại đều do HR thực hiện.
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
}

'use client';

import * as React from 'react';
import {
  Box,
  Typography,
  Button,
  Tabs,
  Tab,
  Card,
  CardContent,
  Grid,
  CircularProgress,
  Alert,
  Breadcrumbs,
  Link as MuiLink,
  Divider,
  List,
  ListItem,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  LinearProgress,
} from '@mui/material';
import HomeIcon from '@mui/icons-material/Home';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import WarningIcon from '@mui/icons-material/Warning';
import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { positionsApi, criteriaApi, applicationsApi, assessmentsApi, operationsApi } from '@/lib/api';
import StatusBadge from '@/components/common/StatusBadge';
import type { Position, CriteriaVersion } from '@/types';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`position-tabpanel-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
}

export default function PositionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const positionId = params.id as string;

  const [position, setPosition] = useState<Position | null>(null);
  const [criteriaVersions, setCriteriaVersions] = useState<CriteriaVersion[]>([]);
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [operationStatus, setOperationStatus] = useState<any>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

  const approvedCriteria = criteriaVersions.find(c => c.status === 'APPROVED');
  const draftCriteria = criteriaVersions.find(c => c.status === 'DRAFT' || c.status === 'PENDING_HR_REVIEW' || c.status === 'PENDING_HM_APPROVAL');
  const currentCriteria = approvedCriteria || draftCriteria;

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [posRes, criteriaRes] = await Promise.all([
        positionsApi.getById(positionId),
        criteriaApi.listVersions(positionId),
      ]);
      setPosition(posRes.data);
      setCriteriaVersions(criteriaRes.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Không thể tải thông tin vị trí');
    } finally {
      setLoading(false);
    }
  }, [positionId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Poll operation status when processing
  useEffect(() => {
    if (!operationStatus || operationStatus.status === 'COMPLETED' || operationStatus.status === 'FAILED') {
      return;
    }

    const pollInterval = setInterval(async () => {
      try {
        const res = await operationsApi.getStatus(operationStatus.operation_id);
        setOperationStatus(res.data);
        if (res.data.status === 'COMPLETED' || res.data.status === 'FAILED') {
          clearInterval(pollInterval);
          await loadData();
        }
      } catch (e) {
        clearInterval(pollInterval);
      }
    }, 2000);

    return () => clearInterval(pollInterval);
  }, [operationStatus, loadData]);

  const handleGenerateCriteria = async () => {
    if (!position) return;
    try {
      setGenerating(true);
      await criteriaApi.generateDraft(positionId);
      await loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Không thể tạo đề xuất tiêu chí');
    } finally {
      setGenerating(false);
    }
  };

  const handleApprove = async (action: 'APPROVE' | 'REJECT' | 'REQUEST_CHANGES') => {
    if (!currentCriteria) return;
    try {
      await criteriaApi.approve(currentCriteria.criteria_version_id, action);
      await loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Thao tác không thành công');
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setSelectedFiles(Array.from(e.target.files));
    }
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) return;
    try {
      setUploading(true);
      setUploadProgress(0);
      const res = await applicationsApi.uploadBatch(positionId, selectedFiles, setUploadProgress);
      setOperationStatus({
        operation_id: res.data.operation_id,
        status: 'PROCESSING'
      });
      setUploadOpen(false);
      setSelectedFiles([]);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload không thành công');
    } finally {
      setUploading(false);
    }
  };

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 10 }}>
        <CircularProgress color="secondary" />
      </Box>
    );
  }

  if (!position) {
    return <Alert severity="error">Không tìm thấy vị trí</Alert>;
  }

  return (
    <Box>
      {/* Breadcrumbs */}
      <Breadcrumbs sx={{ mb: 2 }}>
        <MuiLink component={Link} href="/positions" color="inherit" sx={{ display: 'flex', alignItems: 'center' }}>
          <HomeIcon sx={{ mr: 0.5, fontSize: 16 }} />
          Danh sách vị trí
        </MuiLink>
        <Typography color="text.primary">{position.title}</Typography>
      </Breadcrumbs>

      {/* Position Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
        <Box>
          <Typography variant="h1" sx={{ fontSize: 28, color: '#0A2B57', mb: 0.5 }}>
            {position.title}
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mt: 1 }}>
            <Typography variant="body2" color="text.secondary" fontFamily="monospace">
              {position.position_code}
            </Typography>
            <StatusBadge
              type={position.status === 'OPEN' ? 'position-open' : position.status === 'PAUSED' ? 'position-paused' : 'position-closed'}
              label={position.status === 'OPEN' ? 'Đang mở' : position.status === 'PAUSED' ? 'Tạm dừng' : 'Đã đóng'}
            />
            {approvedCriteria ? (
              <StatusBadge type="criteria-approved" label="Tiêu chí đã duyệt" />
            ) : currentCriteria ? (
              <StatusBadge type="criteria-draft" label={currentCriteria.status.replace('_', ' ')} />
            ) : null}
          </Box>
        </Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="outlined"
            startIcon={<AutoAwesomeIcon />}
            onClick={handleGenerateCriteria}
            disabled={generating || !!approvedCriteria}
            sx={{ borderColor: '#0A2B57', color: '#0A2B57' }}
          >
            {generating ? <CircularProgress size={20} sx={{ mr: 1 }} /> : null}
            Đề xuất tiêu chí AI
          </Button>
          <Button
            variant="contained"
            color="secondary"
            startIcon={<UploadFileIcon />}
            onClick={() => setUploadOpen(true)}
            disabled={!approvedCriteria}
          >
            Tải lên CV
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Processing status */}
      {operationStatus && operationStatus.status !== 'COMPLETED' && (
        <Card sx={{ mb: 3, borderLeft: '4px solid #2599DC' }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <CircularProgress size={18} sx={{ mr: 2 }} />
              <Typography variant="body2" fontWeight={500}>
                Đang xử lý hồ sơ...
              </Typography>
            </Box>
            {operationStatus.progress && (
              <Box sx={{ mt: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  Đã xử lý {operationStatus.progress.processed}/{operationStatus.progress.total} hồ sơ
                  {operationStatus.progress.failed > 0 && ` (${operationStatus.progress.failed} lỗi)`}
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={operationStatus.progress.percent_complete}
                  sx={{ mt: 1, height: 6, borderRadius: 3 }}
                />
              </Box>
            )}
          </CardContent>
        </Card>
      )}

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={activeTab} onChange={handleTabChange}>
          <Tab label="Tiêu chí đánh giá" />
          <Tab label="Danh sách ứng viên" />
          <Tab label="Shortlist đã chia sẻ" />
        </Tabs>
      </Box>

      {/* Tab 1: Criteria & Approval */}
      <TabPanel value={activeTab} index={0}>
        {!currentCriteria ? (
          <Card>
            <CardContent sx={{ textAlign: 'center', py: 8 }}>
              <WarningIcon sx={{ fontSize: 64, color: '#B54708', mb: 2 }} />
              <Typography variant="h4" sx={{ fontSize: 18, mb: 1 }}>
                Chưa có bộ tiêu chí nào
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Nhấn nút "Đề xuất tiêu chí AI" để AI tự động phân tích JD và tạo bộ tiêu chí nháp
              </Typography>
              <Button
                variant="contained"
                color="secondary"
                startIcon={<AutoAwesomeIcon />}
                onClick={handleGenerateCriteria}
                disabled={generating}
              >
                Tạo đề xuất tiêu chí ngay
              </Button>
            </CardContent>
          </Card>
        ) : (
          <Grid container spacing={3}>
            {/* Mandatory Criteria */}
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                    <Chip
                      label="BẮT BUỘC"
                      size="small"
                      sx={{
                        backgroundColor: '#FDF2F2',
                        color: '#941616',
                        fontWeight: 700,
                        fontSize: 11,
                        mr: 2,
                      }}
                    />
                    <Typography variant="h4" sx={{ fontSize: 16, fontWeight: 600 }}>
                      Tiêu chí bắt buộc ({currentCriteria.mandatory_weight_total}% tổng điểm)
                    </Typography>
                  </Box>
                  <Divider sx={{ mb: 2 }} />
                  <List disablePadding>
                    {currentCriteria.criteria
                      .filter(c => c.category === 'MUST_HAVE')
                      .map((crit, idx) => (
                        <ListItem key={crit.criterion_id} sx={{ px: 0, py: 1, flexDirection: 'column', alignItems: 'flex-start' }}>
                          <Box sx={{ width: '100%', display: 'flex', justifyContent: 'space-between' }}>
                            <Typography variant="body2" fontWeight={600}>
                              {idx + 1}. {crit.name}
                            </Typography>
                            <Chip
                              label={`${crit.weight_in_group}%`}
                              size="small"
                              sx={{ height: 20, fontSize: 11, backgroundColor: '#F3EEEE' }}
                            />
                          </Box>
                          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                            {crit.description}
                          </Typography>
                        </ListItem>
                      ))}
                  </List>
                </CardContent>
              </Card>
            </Grid>

            {/* Nice to have Criteria */}
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                    <Chip
                      label="ƯU TIÊN"
                      size="small"
                      sx={{
                        backgroundColor: '#E8F1FC',
                        color: '#0A2B57',
                        fontWeight: 700,
                        fontSize: 11,
                        mr: 2,
                      }}
                    />
                    <Typography variant="h4" sx={{ fontSize: 16, fontWeight: 600 }}>
                      Tiêu chí ưu tiên ({currentCriteria.nice_to_have_weight_total}% tổng điểm)
                    </Typography>
                  </Box>
                  <Divider sx={{ mb: 2 }} />
                  <List disablePadding>
                    {currentCriteria.criteria
                      .filter(c => c.category === 'NICE_TO_HAVE')
                      .map((crit, idx) => (
                        <ListItem key={crit.criterion_id} sx={{ px: 0, py: 1, flexDirection: 'column', alignItems: 'flex-start' }}>
                          <Box sx={{ width: '100%', display: 'flex', justifyContent: 'space-between' }}>
                            <Typography variant="body2" fontWeight={600}>
                              {idx + 1}. {crit.name}
                            </Typography>
                            <Chip
                              label={`${crit.weight_in_group}%`}
                              size="small"
                              sx={{ height: 20, fontSize: 11, backgroundColor: '#F3EEEE' }}
                            />
                          </Box>
                          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                            {crit.description}
                          </Typography>
                        </ListItem>
                      ))}
                  </List>
                </CardContent>
              </Card>
            </Grid>

            {/* Approval Actions */}
            {currentCriteria.status !== 'APPROVED' && (
              <Grid item xs={12}>
                <Card sx={{ backgroundColor: '#FFFAEB', border: '1px solid #FEF0C7' }}>
                  <CardContent sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <WarningIcon sx={{ color: '#B54708', mr: 2 }} />
                      <Box>
                        <Typography variant="body1" fontWeight={600} color="#B54708">
                          Bộ tiêu chí đang ở trạng thái: {currentCriteria.status.replace('_', ' ')}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Vui lòng rà soát và phê duyệt trước khi tải lên CV và chạy đánh giá ứng viên
                        </Typography>
                      </Box>
                    </Box>
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      <Button
                        variant="outlined"
                        color="error"
                        onClick={() => handleApprove('REJECT')}
                      >
                        Từ chối
                      </Button>
                      <Button
                        variant="contained"
                        color="secondary"
                        startIcon={<CheckCircleIcon />}
                        onClick={() => handleApprove('APPROVE')}
                      >
                        Phê duyệt
                      </Button>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            )}
          </Grid>
        )}
      </TabPanel>

      {/* Tab 2: Applications (placeholder) */}
      <TabPanel value={activeTab} index={1}>
        <Card>
          <CardContent sx={{ textAlign: 'center', py: 8 }}>
            <Typography variant="body1" color="text.secondary">
              Danh sách ứng viên và bảng xếp hạng sẽ được hiển thị tại đây sau khi bạn tải CV lên.
            </Typography>
            <Button
              variant="contained"
              color="secondary"
              startIcon={<UploadFileIcon />}
              onClick={() => setUploadOpen(true)}
              disabled={!approvedCriteria}
              sx={{ mt: 2 }}
            >
              Tải lên CV ứng viên
            </Button>
          </CardContent>
        </Card>
      </TabPanel>

      {/* Tab 3: Shortlist (placeholder) */}
      <TabPanel value={activeTab} index={2}>
        <Card>
          <CardContent sx={{ textAlign: 'center', py: 8 }}>
            <Typography variant="body1" color="text.secondary">
              Các shortlist đã chia sẻ với Hiring Manager sẽ được liệt kê tại đây.
            </Typography>
          </CardContent>
        </Card>
      </TabPanel>

      {/* Upload CV Dialog */}
      <Dialog open={uploadOpen} onClose={() => setUploadOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ color: '#0A2B57' }}>Tải lên hồ sơ CV</DialogTitle>
        <DialogContent dividers>
          <Box
            sx={{
              border: '2px dashed #E2E8F0',
              borderRadius: 2,
              p: 4,
              textAlign: 'center',
              backgroundColor: '#F8FAFC',
            }}
          >
            <input
              type="file"
              multiple
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={handleFileSelect}
              style={{ display: 'none' }}
              id="cv-file-input"
            />
            <label htmlFor="cv-file-input">
              <Button component="span" variant="outlined" sx={{ mb: 2 }}>
                Chọn tệp CV
              </Button>
            </label>
            <Typography variant="body2" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
              Hỗ trợ PDF, DOCX (tiếng Anh)
            </Typography>
            <Typography variant="caption" color="text.disabled">
              Tối đa 50 file, mỗi file ≤ 10MB, tổng lô ≤ 250MB
            </Typography>

            {selectedFiles.length > 0 && (
              <Box sx={{ mt: 3, textAlign: 'left' }}>
                <Typography variant="body2" fontWeight={600} sx={{ mb: 1 }}>
                  Đã chọn {selectedFiles.length} tệp:
                </Typography>
                {selectedFiles.slice(0, 5).map((file, i) => (
                  <Typography key={i} variant="caption" display="block" color="text.secondary">
                    • {file.name} ({(file.size / 1_000_000).toFixed(2)} MB)
                  </Typography>
                ))}
                {selectedFiles.length > 5 && (
                  <Typography variant="caption" color="text.disabled">
                    ...và {selectedFiles.length - 5} tệp khác
                  </Typography>
                )}
              </Box>
            )}

            {uploading && (
              <Box sx={{ mt: 3, width: '100%' }}>
                <LinearProgress variant="determinate" value={uploadProgress} />
                <Typography variant="caption" sx={{ mt: 1, display: 'block' }}>
                  Đang tải lên: {uploadProgress}%
                </Typography>
              </Box>
            )}
          </Box>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setUploadOpen(false)} disabled={uploading}>Hủy</Button>
          <Button
            onClick={handleUpload}
            variant="contained"
            color="secondary"
            disabled={selectedFiles.length === 0 || uploading}
          >
            {uploading ? 'Đang tải...' : 'Bắt đầu xử lý'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

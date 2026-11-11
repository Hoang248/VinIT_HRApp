'use client';

import { useI18n } from '@/i18n/I18nProvider';
import { localizeServerMessage } from '@/i18n/serverMessages';

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
  FormControl,
  InputLabel,
  MenuItem,
  Select,
} from '@mui/material';
import HomeIcon from '@mui/icons-material/Home';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import WarningIcon from '@mui/icons-material/Warning';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import AddIcon from '@mui/icons-material/Add';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { positionsApi, criteriaApi, applicationsApi, operationsApi, authApi, dashboardApi } from '@/lib/api';
import StatusBadge from '@/components/common/StatusBadge';
import type { Position, CriteriaVersion, Criterion, CriterionInput, JDVersion, PositionStatusEvent } from '@/types';

// Draft criterion in the add/edit dialog; keywords are edited as one comma-separated field.
type CriterionForm = CriterionInput & { criterion_id?: string; keywordsText: string };

const EMPTY_CRITERION = (category: Criterion['category']): CriterionForm => ({
  name: '', description: '', category, weight_in_group: 0, expected_evidence_keywords: [],
  evidence_guidance: '', jd_reference_text: '', keywordsText: '',
});

// Protected attributes reported by the backend fairness screen (F1.02).
const FAIRNESS_ATTRIBUTE_LABELS: Record<string, string> = {
  AGE: 'Tuổi', GENDER: 'Giới tính', APPEARANCE: 'Ngoại hình', MARITAL_STATUS: 'Hôn nhân/gia đình',
  PERSONALITY: 'Tính cách', CULTURE_FIT: 'Phù hợp văn hóa', NATIONALITY_ETHNICITY: 'Quốc tịch/dân tộc', RELIGION: 'Tôn giáo',
};

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
  const { t, dateLocale, locale } = useI18n();
  const params = useParams();
  const positionId = params.id as string;

  const [position, setPosition] = useState<Position | null>(null);
  const [criteriaVersions, setCriteriaVersions] = useState<CriteriaVersion[]>([]);
  const [jdVersions, setJdVersions] = useState<JDVersion[]>([]);
  const [selectedJdId, setSelectedJdId] = useState('');
  const [jdDialogOpen, setJdDialogOpen] = useState(false);
  const [jdContent, setJdContent] = useState('');
  const [jdLanguage, setJdLanguage] = useState<'vi' | 'en'>('en');
  const [jdExpected, setJdExpected] = useState('');
  const [jdError, setJdError] = useState<string | null>(null);
  const [savingJd, setSavingJd] = useState(false);
  const [me, setMe] = useState<any>(null);
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [operationStatus, setOperationStatus] = useState<any>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [approvalAction, setApprovalAction] = useState<'REJECT' | 'REQUEST_CHANGES' | null>(null);
  const [approvalComment, setApprovalComment] = useState('');
  const [approving, setApproving] = useState(false);
  const [editingCriterion, setEditingCriterion] = useState<CriterionForm | null>(null);
  const [savingCriterion, setSavingCriterion] = useState(false);
  const [criterionError, setCriterionError] = useState<string | null>(null);
  const [deletingCriterion, setDeletingCriterion] = useState<Criterion | null>(null);
  const [deletingBusy, setDeletingBusy] = useState(false);
  const [creatingVersion, setCreatingVersion] = useState(false);
  const [positionStatusReason, setPositionStatusReason] = useState('');
  const [statusEvents, setStatusEvents] = useState<PositionStatusEvent[]>([]);
  const [weightDialogOpen, setWeightDialogOpen] = useState(false);
  const [mandatoryWeight, setMandatoryWeight] = useState('70');
  const [savingWeights, setSavingWeights] = useState(false);
  const [weightError, setWeightError] = useState<string | null>(null);
  const [positionDialogOpen, setPositionDialogOpen] = useState(false);
  const [positionTitle, setPositionTitle] = useState('');
  const [positionStatus, setPositionStatus] = useState<Position['status']>('OPEN');
  const [savingPosition, setSavingPosition] = useState(false);
  const [positionEditError, setPositionEditError] = useState<string | null>(null);
  const [approvalHistory, setApprovalHistory] = useState<any[]>([]);
  const [appCounts, setAppCounts] = useState<{total: number; processing: number; needs_review: number; shortlisted: number} | null>(null);

  const latestJd = jdVersions[0];
  const approvedCriteria = criteriaVersions.find(c => c.status === 'APPROVED' && c.jd_version_id === latestJd?.jd_version_id);
  // Versions are returned newest-first. A newer draft/rejected version must not
  // disappear behind a previously approved version.
  const currentCriteria = criteriaVersions[0];
  const criteriaStale = !!currentCriteria && !!latestJd && currentCriteria.jd_version_id !== latestJd.jd_version_id;
  const selectedJd = jdVersions.find(jd => jd.jd_version_id === selectedJdId) || latestJd;

  const updateCounts = useCallback(async () => {
    const res = await dashboardApi.getPosition(positionId);
    const stats = res.data;
    setAppCounts({ total: stats.total_applications, processing: stats.applications_processing,
      needs_review: stats.files_needing_hr_review, shortlisted: stats.applications_by_status.SHORTLIST });
  }, [positionId]);

  const loadData = useCallback(async (initial = false) => {
    try {
      if (initial) setLoading(true);
      const [posRes, criteriaRes, meRes, jdRes] = await Promise.all([
        positionsApi.getById(positionId), criteriaApi.listVersions(positionId), authApi.me(), positionsApi.getJdVersions(positionId),
      ]);
      setPosition(posRes.data);
      setCriteriaVersions(criteriaRes.data);
      setJdVersions(jdRes.data);
      setSelectedJdId(previous => jdRes.data.some((item: JDVersion) => item.jd_version_id === previous) ? previous : (jdRes.data[0]?.jd_version_id || ''));
      setMe(meRes.data);
      try { setStatusEvents((await positionsApi.getStatusEvents(positionId)).data || []); }
      catch { setStatusEvents([]); }
      const latestVersion = criteriaRes.data[0];
      if (latestVersion) {
        try { setApprovalHistory((await criteriaApi.getApprovalEvents(latestVersion.criteria_version_id)).data || []); }
        catch { setApprovalHistory([]); }
      } else setApprovalHistory([]);
      setError(null);
      const myRoles = meRes.data.position_assignments?.filter((p: any) => p.position_id === positionId).map((p: any) => p.position_role) || [];
      const hr = myRoles.includes('HR_RECRUITER') || myRoles.includes('HR_LEAD') || meRes.data.system_roles?.some((r: string) => r === 'ADMIN' || r === 'HR_LEAD');
      // Show workflow statistics only to HR; an HM uses the shared shortlist.
      if (hr) {
        try { await updateCounts(); }
        catch { setAppCounts(null); setError(t("Không thể tải thống kê hồ sơ. Vui lòng làm mới trang.")); }
      } else setAppCounts(null);
      if (initial && hr) {
        try {
          const active = await operationsApi.getActiveForPosition(positionId);
          if (active.data) setOperationStatus(active.data);
        } catch { setError(t("Không thể tải tiến trình xử lý. Vui lòng làm mới trang.")); }
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể tải thông tin vị trí"));
    } finally {
      setLoading(false);
    }
  }, [positionId, updateCounts, t]);

  useEffect(() => { loadData(true); }, [loadData]);

  const isOperationRunning = !!operationStatus && !['COMPLETED', 'FAILED'].includes(operationStatus.status);
  const operationId = isOperationRunning ? operationStatus.operation_id : null;

  // Refresh counts throughout extraction and assessment, even after navigation.
  useEffect(() => {
    if (!isOperationRunning && !(appCounts?.processing)) return;
    const timer = setInterval(() => {
      updateCounts().catch(() => setError(t("Không thể cập nhật tiến trình CV. Vui lòng thử làm mới.")));
    }, 5000);
    return () => clearInterval(timer);
  }, [isOperationRunning, appCounts?.processing, updateCounts, t]);

  useEffect(() => {
    if (!operationId) return;
    let cancelled = false;
    const timer = setInterval(async () => {
      try {
        const res = await operationsApi.getStatus(operationId);
        if (cancelled) return;
        setOperationStatus(res.data);
        if (res.data.status === 'COMPLETED' || res.data.status === 'FAILED') {
          clearInterval(timer);
          await loadData();
        }
      } catch {
        // Keep polling on transient errors; do not silently report completion.
        if (!cancelled) setError(t("Không thể cập nhật tiến trình. Hệ thống sẽ thử lại."));
      }
    }, 2000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [operationId, loadData, t]);

  const handleGenerateCriteria = async () => {
    try {
      setGenerating(true); setError(null);
      await criteriaApi.generateDraft(positionId);
      await loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể tạo đề xuất tiêu chí"));
    } finally { setGenerating(false); }
  };

  const handleApprove = async (action: 'APPROVE' | 'REJECT' | 'REQUEST_CHANGES', comment?: string) => {
    if (!currentCriteria || approving) return;
    try {
      setApproving(true); setError(null);
      await criteriaApi.approve(currentCriteria.criteria_version_id, action, comment);
      setApprovalAction(null); setApprovalComment('');
      await loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Thao tác không thành công"));
      setApprovalAction(null);
    } finally { setApproving(false); }
  };

  const openEditCriterion = (crit: Criterion) => {
    setCriterionError(null);
    setEditingCriterion({
      criterion_id: crit.criterion_id, name: crit.name, description: crit.description, category: crit.category,
      weight_in_group: Number(crit.weight_in_group), expected_evidence_keywords: crit.expected_evidence_keywords || [],
      evidence_guidance: crit.evidence_guidance || '', jd_reference_text: crit.jd_reference_text || '',
      keywordsText: (crit.expected_evidence_keywords || []).join(', '),
    });
  };

  const openAddCriterion = (category: Criterion['category']) => {
    setCriterionError(null);
    setEditingCriterion(EMPTY_CRITERION(category));
  };

  const saveCriterion = async () => {
    if (!editingCriterion || !currentCriteria) return;
    const payload: CriterionInput = {
      name: editingCriterion.name.trim(), description: editingCriterion.description.trim(),
      category: editingCriterion.category, weight_in_group: Number(editingCriterion.weight_in_group),
      expected_evidence_keywords: editingCriterion.keywordsText.split(',').map(k => k.trim()).filter(Boolean),
      evidence_guidance: editingCriterion.evidence_guidance?.trim() || null,
      jd_reference_text: editingCriterion.jd_reference_text?.trim() || null,
    };
    try {
      setSavingCriterion(true); setCriterionError(null);
      if (editingCriterion.criterion_id) {
        await criteriaApi.updateItem(currentCriteria.criteria_version_id, editingCriterion.criterion_id, payload);
      } else {
        await criteriaApi.addItem(currentCriteria.criteria_version_id, payload);
      }
      setEditingCriterion(null);
      await loadData();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setCriterionError(typeof detail === 'string' ? detail : t("Không thể lưu tiêu chí"));
    } finally { setSavingCriterion(false); }
  };

  const confirmDeleteCriterion = async () => {
    if (!deletingCriterion || !currentCriteria || deletingBusy) return;
    try {
      setDeletingBusy(true); setError(null);
      await criteriaApi.deleteItem(currentCriteria.criteria_version_id, deletingCriterion.criterion_id);
      setDeletingCriterion(null);
      await loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể xóa tiêu chí"));
      setDeletingCriterion(null);
    } finally { setDeletingBusy(false); }
  };

  const handleCreateNewVersion = async () => {
    if (!currentCriteria || creatingVersion) return;
    try {
      setCreatingVersion(true); setError(null);
      await criteriaApi.createNewVersion(currentCriteria.criteria_version_id);
      await loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể tạo phiên bản tiêu chí mới"));
    } finally { setCreatingVersion(false); }
  };

  const weightValue = Number(mandatoryWeight);
  const validWeights = /^\d{1,3}(?:\.\d{0,2})?$/.test(mandatoryWeight) &&
    Number.isFinite(weightValue) && weightValue > 0 && weightValue <= 100;
  const niceWeight = validWeights ? Math.round((100 - weightValue) * 100) / 100 : null;

  const saveWeights = async () => {
    if (!currentCriteria || !validWeights || niceWeight === null || savingWeights) return;
    try {
      setSavingWeights(true); setWeightError(null);
      await criteriaApi.updateWeights(currentCriteria.criteria_version_id, weightValue, niceWeight);
      setWeightDialogOpen(false);
      await loadData();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setWeightError(typeof detail === 'string' ? detail : t("Trọng số không hợp lệ. Vui lòng kiểm tra và thử lại."));
    } finally { setSavingWeights(false); }
  };

  const saveJd = async () => {
    if (!jdContent.trim() || !jdExpected || savingJd) return;
    try {
      setSavingJd(true); setJdError(null);
      const response = await positionsApi.createJdVersion(positionId, { content_text: jdContent.trim(), language_code: jdLanguage, expected_jd_version_id: jdExpected });
      setJdDialogOpen(false); setSelectedJdId(response.data.jd_version_id);
      await loadData();
    } catch (err: any) { setJdError(err.response?.data?.detail || t("Không thể lưu phiên bản JD.")); }
    finally { setSavingJd(false); }
  };

  const savePosition = async () => {
    if (!positionTitle.trim() || savingPosition) return;
    try {
      setSavingPosition(true); setPositionEditError(null);
      const statusChanged = position?.status !== positionStatus;
      await positionsApi.update(positionId, {
        title: positionTitle.trim(), status: positionStatus,
        ...(statusChanged && positionStatusReason.trim() ? { status_reason: positionStatusReason.trim() } : {}),
      });
      setPositionDialogOpen(false);
      await loadData();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setPositionEditError(typeof detail === 'string' ? detail : t("Không thể cập nhật vị trí. Vui lòng thử lại."));
    } finally { setSavingPosition(false); }
  };

  const myPosAssignments = me?.position_assignments?.filter((p: any) => p.position_id === positionId) || [];
  const myPositionRoles = new Set(myPosAssignments.map((p: any) => p.position_role));
  const mySystemRoles = new Set(me?.system_roles || []);
  const isHR = myPositionRoles.has('HR_RECRUITER') || myPositionRoles.has('HR_LEAD') || mySystemRoles.has('ADMIN') || mySystemRoles.has('HR_LEAD');
  const isHM = myPositionRoles.has('HIRING_MANAGER');
  const isSameApprover = !!currentCriteria?.approved_by_hr && currentCriteria.approved_by_hr === me?.user_id;
  const canEditCriteria = isHR && !!currentCriteria && ['DRAFT', 'PENDING_HR_REVIEW'].includes(currentCriteria.status);
  const fairnessIssues = currentCriteria?.fairness_warnings || [];
  const flaggedIds = new Set(fairnessIssues.map(w => w.criterion_id).filter(Boolean));
  const hasOpenCriteria = criteriaVersions.some(c => ['DRAFT', 'PENDING_HR_REVIEW', 'PENDING_HM_APPROVAL'].includes(c.status));
  const canCreateNewVersion = isHR && !!currentCriteria && ['APPROVED', 'REJECTED'].includes(currentCriteria.status) && !hasOpenCriteria;

  const renderCriterion = (crit: Criterion, idx: number) => (
    <ListItem key={crit.criterion_id} sx={{ px: 0, py: 1, flexDirection: 'column', alignItems: 'flex-start' }}>
      <Box sx={{ width: '100%', display: 'flex', justifyContent: 'space-between', gap: 1 }}>
        <Typography variant="body2" fontWeight={600}>
          {idx + 1}. {crit.name}
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexShrink: 0 }}>
          {flaggedIds.has(crit.criterion_id) && <Chip label={t("Cần xem lại")} size="small" color="error" sx={{ height: 20, fontSize: 11 }} />}
          <Chip label={`${crit.weight_in_group}%`} size="small" sx={{ height: 20, fontSize: 11, backgroundColor: '#F3EEEE' }} />
          {canEditCriteria && (
            <>
              <Button size="small" startIcon={<EditOutlinedIcon />} onClick={() => openEditCriterion(crit)}>{t("Sửa")}</Button>
              <Button size="small" color="error" startIcon={<DeleteOutlineIcon />} aria-label={t("Xóa tiêu chí")}
                onClick={() => setDeletingCriterion(crit)} disabled={(currentCriteria?.criteria.length ?? 0) <= 1}>{t("Xóa")}</Button>
            </>
          )}
        </Box>
      </Box>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
        {crit.description}
      </Typography>
      {crit.jd_reference_text && (
        <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, pl: 1, borderLeft: '2px solid #D0D5DD', fontStyle: 'italic' }}>
          {t("Căn cứ JD:")} “{crit.jd_reference_text}”
        </Typography>
      )}
      {crit.evidence_guidance && (
        <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>{t("Hướng dẫn bằng chứng:")} {crit.evidence_guidance}</Typography>
      )}
      {crit.expected_evidence_keywords?.length > 0 && (
        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mt: 0.5 }}>
          {crit.expected_evidence_keywords.map(keyword => <Chip key={keyword} label={keyword} size="small" variant="outlined" sx={{ height: 20, fontSize: 11 }} />)}
        </Box>
      )}
    </ListItem>
  );

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    setSelectedFiles(files);
    const total = files.reduce((sum, file) => sum + file.size, 0);
    if (files.length > 50) setUploadError(t("Mỗi lô tối đa 50 tệp."));
    else if (files.some(file => file.size > 10_000_000 || file.size === 0)) setUploadError(t("Mỗi tệp phải có dung lượng từ 1 byte đến 10 MB."));
    else if (total > 250_000_000) setUploadError(t("Tổng dung lượng lô không được vượt quá 250 MB."));
    else if (files.some(file => !/\.(pdf|docx)$/i.test(file.name))) setUploadError(t("Chỉ hỗ trợ tệp PDF hoặc DOCX."));
    else setUploadError(null);
  };

  const handleUpload = async () => {
    if (!selectedFiles.length || uploadError) return;
    try {
      setUploading(true); setUploadProgress(0); setUploadError(null);
      const res = await applicationsApi.uploadBatch(positionId, selectedFiles, setUploadProgress);
      setOperationStatus({ operation_id: res.data.operation_id, status: 'PENDING', capability: 'CV_PROCESSING' });
      setUploadOpen(false); setSelectedFiles([]);
      await updateCounts();
    } catch (err: any) {
      setUploadError(err.response?.data?.detail || t("Tải lên không thành công"));
    } finally { setUploading(false); }
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
    return <Alert severity="error" action={<Button onClick={() => loadData(true)}>{t("Thử lại")}</Button>}>{t(error || "Không tìm thấy vị trí")}</Alert>;
  }

  return (
    <Box>
      {/* Breadcrumbs */}
      <Breadcrumbs sx={{ mb: 2 }}>
        <MuiLink component={Link} href="/positions" color="inherit" sx={{ display: 'flex', alignItems: 'center' }}>
          <HomeIcon sx={{ mr: 0.5, fontSize: 16 }} />{t("Danh sách vị trí")}</MuiLink>
        <Typography color="text.primary">{position.title}</Typography>
      </Breadcrumbs>

      {/* Position Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 2, mb: 3 }}>
        <Box>
          <Typography variant="h1" sx={{ fontSize: 28, color: '#0A2B57', mb: 0.5 }}>
            {position.title}
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mt: 1, flexWrap: 'wrap' }}>
            <Typography variant="body2" color="text.secondary" fontFamily="monospace">
              {position.position_code}
            </Typography>
            <StatusBadge
              type={position.status === 'OPEN' ? 'position-open' : position.status === 'PAUSED' ? 'position-paused' : 'position-closed'}
              label={position.status === 'OPEN' ? t("Đang mở") : position.status === 'PAUSED' ? t("Tạm dừng") : t("Đã đóng")}
            />
            {currentCriteria && <StatusBadge type={currentCriteria.status === 'APPROVED' ? 'criteria-approved' : 'criteria-draft'}
              label={{ DRAFT: t("Bản nháp"), PENDING_HR_REVIEW: t("Chờ HR"), PENDING_HM_APPROVAL: t("Chờ HM"), APPROVED: t("Đã duyệt"), REJECTED: t("Đã từ chối") }[currentCriteria.status]} />}
          </Box>
        </Box>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          {isHR && <Button variant="outlined" startIcon={<EditOutlinedIcon />} onClick={() => {
            setPositionTitle(position.title); setPositionStatus(position.status); setPositionStatusReason(''); setPositionEditError(null); setPositionDialogOpen(true);
          }}>{t("Chỉnh sửa vị trí")}</Button>}
          {canCreateNewVersion && (
            <Button variant="outlined" startIcon={creatingVersion ? <CircularProgress size={16} /> : <ContentCopyIcon />}
              onClick={handleCreateNewVersion} disabled={creatingVersion} sx={{ borderColor: '#0A2B57', color: '#0A2B57' }}>
              {t("Tạo phiên bản tiêu chí mới")}
            </Button>
          )}
          <Button
            variant="outlined"
            startIcon={<AutoAwesomeIcon />}
            onClick={handleGenerateCriteria}
            disabled={generating || !isHR || (!!currentCriteria && !criteriaStale && !['REJECTED', 'APPROVED'].includes(currentCriteria.status))}
            sx={{ borderColor: '#0A2B57', color: '#0A2B57' }}
          >
            {generating ? <CircularProgress size={20} sx={{ mr: 1 }} /> : null}
            {t("Đề xuất tiêu chí AI")}
          </Button>
          <Button
            variant="contained"
            color="secondary"
            startIcon={<UploadFileIcon />}
            onClick={() => setUploadOpen(true)}
            disabled={!approvedCriteria || !isHR || position.status !== 'OPEN' || isOperationRunning}
          >{t("Tải lên CV")}</Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {t(error)}
        </Alert>
      )}

      {/* Processing status — operation progress */}
      {operationStatus && operationStatus.status !== 'COMPLETED' && operationStatus.status !== 'FAILED' && (
        <Card sx={{ mb: 3, borderLeft: '4px solid #2599DC' }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <CircularProgress size={18} sx={{ mr: 2 }} />
              <Typography variant="body2" fontWeight={500}>
                {operationStatus.stage === 'ASSESSMENT' || operationStatus.capability === 'ASSESSMENT' || operationStatus.capability === 'RANKING'
                  ? t("Đang đánh giá và tạo xếp hạng…") : t("Đang xử lý CV…")}
              </Typography>
            </Box>
            {operationStatus.progress && (
              <Box sx={{ mt: 1 }}>
                <Typography variant="caption" color="text.secondary">{t("                  Đã xử lý")} {operationStatus.progress.processed}/{operationStatus.progress.total} {t("tệp")}{operationStatus.progress.failed > 0 && t(" ({0} lỗi)", operationStatus.progress.failed)}
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

      {/* Background CV processing (no single operation, worker still parsing files) */}
      {!isOperationRunning && (appCounts?.processing || 0) > 0 && (
        <Card sx={{ mb: 3, borderLeft: '4px solid #B54708' }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <CircularProgress size={18} sx={{ mr: 2 }} />
              <Typography variant="body2" fontWeight={500} color="#B54708">{t("                Có")} {appCounts?.processing} {t("hồ sơ CV đang được bóc tách văn bản... Trang sẽ tự làm mới.")}</Typography>
            </Box>
          </CardContent>
        </Card>
      )}

      {operationStatus?.status === 'COMPLETED' && (
        <Alert severity={operationStatus.progress?.failed ? 'warning' : 'success'} sx={{ mb: 3 }} onClose={() => setOperationStatus(null)}
          action={isHR ? <Button component={Link} href={`/positions/${positionId}/applicants`} color="inherit">{t("Xem xếp hạng")}</Button> : undefined}>
          {operationStatus.progress?.total && !operationStatus.progress?.processed
            ? t("Không có tệp nào được xử lý thành công.") : t("Đã hoàn tất xử lý và cập nhật kết quả.")}
          {operationStatus.progress?.failed ? t(" Có {0} tệp cần kiểm tra.", operationStatus.progress.failed) : ''}
          {(operationStatus.progress?.invalid_files || []).map((file: any, index: number) => (
            <Typography key={`${file.original_filename}-${index}`} variant="caption" display="block">{file.original_filename}: {t("Tệp không hợp lệ hoặc vượt giới hạn.")}</Typography>
          ))}
        </Alert>
      )}

      {/* Processing failed notice */}
      {operationStatus && operationStatus.status === 'FAILED' && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setOperationStatus(null)}>{t("          Xử lý thất bại:")} {operationStatus.error_message ? localizeServerMessage(operationStatus.error_message, locale) : t("Lỗi không xác định")}
        </Alert>
      )}

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={activeTab} onChange={handleTabChange} variant="scrollable" scrollButtons="auto" aria-label={t("Thông tin vị trí")}>
          <Tab label={t("Tiêu chí đánh giá")} />
          <Tab label={t("Danh sách ứng viên")} />
          <Tab label={t("Shortlist đã chia sẻ")} />
          <Tab label={t("Mô tả công việc (JD)")} />
          <Tab label={t("Lịch sử trạng thái")} />
        </Tabs>
      </Box>

      {/* Tab 1: Criteria & Approval */}
      <TabPanel value={activeTab} index={0}>
        {criteriaStale && <Alert severity="warning" sx={{ mb: 2 }}>{t("JD đã thay đổi. Cần tạo và duyệt bộ tiêu chí cho phiên bản mới trước khi tải hoặc đánh giá CV.")}</Alert>}
        {isHM && isSameApprover && currentCriteria?.status === 'PENDING_HM_APPROVAL' && <Alert severity="warning" sx={{ mb: 2 }}>{t("Hai bước duyệt phải do hai tài khoản khác nhau thực hiện. Vui lòng nhờ Hiring Manager khác được phân công duyệt.")}</Alert>}
        {currentCriteria && currentCriteria.status !== 'APPROVED' && (
          <Alert severity="info" sx={{ mb: 2 }}>
            {currentCriteria.origin === 'AI_DRAFT' ? t("AI đề xuất — chưa được phê duyệt.") : t("HR tạo — chưa được phê duyệt.")}{' '}
            {t("Phiên bản")} {currentCriteria.version_number}. {t("Chỉ dùng để đánh giá sau khi HR và Hiring Manager duyệt.")}
          </Alert>
        )}
        {fairnessIssues.length > 0 && (
          <Alert severity="error" sx={{ mb: 2 }}>
            <Typography variant="body2" fontWeight={600}>{t("Có tiêu chí dựa trên thông tin cá nhân không liên quan đến công việc. Cần sửa hoặc xóa trước khi duyệt.")}</Typography>
            {fairnessIssues.map((warning, index) => (
              <Typography key={`${warning.criterion_id}-${index}`} variant="body2">
                • {warning.name}: {warning.attributes.map(code => t(FAIRNESS_ATTRIBUTE_LABELS[code] || code)).join(', ')}
              </Typography>
            ))}
          </Alert>
        )}
        {!currentCriteria ? (
          <Card>
            <CardContent sx={{ textAlign: 'center', py: 8 }}>
              <WarningIcon sx={{ fontSize: 64, color: '#B54708', mb: 2 }} />
              <Typography variant="h4" sx={{ fontSize: 18, mb: 1 }}>{t("Chưa có bộ tiêu chí nào")}</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>{t("Nhấn nút “Đề xuất tiêu chí AI” để AI tự động phân tích JD và tạo bộ tiêu chí nháp")}</Typography>
              <Button
                variant="contained"
                color="secondary"
                startIcon={<AutoAwesomeIcon />}
                onClick={handleGenerateCriteria}
                disabled={generating || !isHR}
              >{t("Tạo đề xuất tiêu chí ngay")}</Button>
            </CardContent>
          </Card>
        ) : (
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Card variant="outlined"><CardContent sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1 }}>
                <Box>
                  <Typography variant="subtitle1" fontWeight={700}>{t("Trọng số nhóm tiêu chí")}</Typography>
                  <Typography variant="body2" color="text.secondary">{t("                    Bắt buộc")} {currentCriteria.mandatory_weight_total}{t("% · Ưu tiên ")}{currentCriteria.nice_to_have_weight_total}%
                  </Typography>
                </Box>
                {isHR && ['DRAFT', 'PENDING_HR_REVIEW'].includes(currentCriteria.status) &&
                  <Button startIcon={<EditOutlinedIcon />} onClick={() => { setMandatoryWeight(String(currentCriteria.mandatory_weight_total)); setWeightError(null); setWeightDialogOpen(true); }}>{t("Điều chỉnh trọng số")}</Button>}
              </CardContent></Card>
            </Grid>
            {/* Mandatory Criteria */}
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                    <Chip
                      label={t("BẮT BUỘC")}
                      size="small"
                      sx={{
                        backgroundColor: '#FDF2F2',
                        color: '#941616',
                        fontWeight: 700,
                        fontSize: 11,
                        mr: 2,
                      }}
                    />
                    <Typography variant="h4" sx={{ fontSize: 16, fontWeight: 600 }}>{t("                      Tiêu chí bắt buộc (")}{currentCriteria.mandatory_weight_total}{t("% tổng điểm)")}</Typography>
                  </Box>
                  <Divider sx={{ mb: 2 }} />
                  <List disablePadding>
                    {currentCriteria.criteria
                      .filter(c => c.category === 'MUST_HAVE')
                      .map(renderCriterion)}
                  </List>
                  {canEditCriteria && (
                    <Button size="small" startIcon={<AddIcon />} sx={{ mt: 1 }} onClick={() => openAddCriterion('MUST_HAVE')}>{t("Thêm tiêu chí bắt buộc")}</Button>
                  )}
                </CardContent>
              </Card>
            </Grid>

            {/* Nice to have Criteria */}
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                    <Chip
                      label={t("ƯU TIÊN")}
                      size="small"
                      sx={{
                        backgroundColor: '#E8F1FC',
                        color: '#0A2B57',
                        fontWeight: 700,
                        fontSize: 11,
                        mr: 2,
                      }}
                    />
                    <Typography variant="h4" sx={{ fontSize: 16, fontWeight: 600 }}>{t("                      Tiêu chí ưu tiên (")}{currentCriteria.nice_to_have_weight_total}{t("% tổng điểm)")}</Typography>
                  </Box>
                  <Divider sx={{ mb: 2 }} />
                  <List disablePadding>
                    {currentCriteria.criteria
                      .filter(c => c.category === 'NICE_TO_HAVE')
                      .map(renderCriterion)}
                  </List>
                  {canEditCriteria && (
                    <Button size="small" startIcon={<AddIcon />} sx={{ mt: 1 }} onClick={() => openAddCriterion('NICE_TO_HAVE')}>{t("Thêm tiêu chí ưu tiên")}</Button>
                  )}
                </CardContent>
              </Card>
            </Grid>

            {approvalHistory.length > 0 && (
              <Grid item xs={12}>
                <Card variant="outlined"><CardContent>
                  <Typography variant="h4" sx={{ mb: 1.5 }}>{t("Lịch sử duyệt tiêu chí")}</Typography>
                  {approvalHistory.map(event => (
                    <Box key={event.event_id} sx={{ py: 1, borderTop: '1px solid #EDF1F5' }}>
                      <Typography variant="body2" fontWeight={600}>
                        {event.reviewer_name || t("Người duyệt")} · {event.reviewer_role === 'HIRING_MANAGER' ? 'Hiring Manager' : 'HR'} ·{' '}
                        {{ APPROVE: t("Đã duyệt"), REQUEST_CHANGES: t("Yêu cầu chỉnh sửa"), REJECT: t("Từ chối") }[event.decision as 'APPROVE' | 'REQUEST_CHANGES' | 'REJECT']}
                      </Typography>
                      <Typography variant="caption">{new Date(event.decided_at).toLocaleString(dateLocale)}</Typography>
                      {event.comment && <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap', mt: 0.5 }}>{event.comment}</Typography>}
                    </Box>
                  ))}
                </CardContent></Card>
              </Grid>
            )}

            {/* Approval Actions — role-aware */}
            {currentCriteria.status !== 'APPROVED' && (
              <Grid item xs={12}>
                <Card sx={{ backgroundColor: '#FFFAEB', border: '1px solid #FEF0C7' }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 2 }}>
                      <Box sx={{ display: 'flex', alignItems: 'flex-start', flex: 1, minWidth: 280 }}>
                        <WarningIcon sx={{ color: '#B54708', mr: 2, mt: 0.3 }} />
                        <Box>
                          <Typography variant="body1" fontWeight={600} color="#B54708">
                            {currentCriteria.status === 'DRAFT' && t("Chờ HR Recruiter rà soát tiêu chí")}
                            {currentCriteria.status === 'PENDING_HR_REVIEW' && t("Chờ HR Recruiter xác nhận quy trình")}
                            {currentCriteria.status === 'PENDING_HM_APPROVAL' && t("Chờ Hiring Manager duyệt chuyên môn")}
                            {currentCriteria.status === 'REJECTED' && t("Bộ tiêu chí đã bị từ chối")}
                          </Typography>
                          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                            {currentCriteria.status === 'PENDING_HM_APPROVAL'
                              ? t("Sau khi HM duyệt, bộ tiêu chí sẽ được khóa và dùng để đánh giá ứng viên.")
                              : t("Sau khi HR duyệt, hệ thống sẽ chuyển sang bước phê duyệt của Hiring Manager.")}
                          </Typography>
                          <Typography variant="caption" color="text.disabled" sx={{ mt: 0.5, display: 'block' }}>{t("                            Vai trò của bạn:")} {[
                              isHR && 'HR Recruiter',
                              isHM && 'Hiring Manager',
                              !isHR && !isHM && (me?.system_roles?.length ? me.system_roles.join(', ') : t("Chưa gán vai trò")),
                            ].filter(Boolean).join(' · ')}
                          </Typography>
                        </Box>
                      </Box>
                      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                        {currentCriteria.status === 'REJECTED' ? (
                          <>
                            {canCreateNewVersion && <Button variant="outlined" startIcon={<ContentCopyIcon />} onClick={handleCreateNewVersion} disabled={creatingVersion}>{t("Sao chép để chỉnh sửa")}</Button>}
                            <Button variant="contained" color="secondary" onClick={handleGenerateCriteria} disabled={generating || !isHR}>{t("Tạo lại đề xuất tiêu chí")}</Button>
                          </>
                        ) : (currentCriteria.status === 'DRAFT' || currentCriteria.status === 'PENDING_HR_REVIEW') ? (
                          <>
                            {isHR && (
                              <>
                                <Button
                                  variant="outlined"
                                  color="error"
                                  onClick={() => { setApprovalComment(''); setApprovalAction('REJECT'); }}
                                  disabled={approving}
                                >{t("Từ chối")}</Button>
                                <Button
                                  variant="contained"
                                  color="secondary"
                                  startIcon={<CheckCircleIcon />}
                                  onClick={() => handleApprove('APPROVE')}
                                  disabled={approving || criteriaStale || fairnessIssues.length > 0}
                                >{t("HR duyệt & gửi HM")}</Button>
                              </>
                            )}
                            {!isHR && (
                              <Typography variant="caption" color="text.secondary" sx={{ alignSelf: 'center' }}>{t("Chờ HR Recruiter rà soát")}</Typography>
                            )}
                          </>
                        ) : currentCriteria.status === 'PENDING_HM_APPROVAL' ? (
                          <>
                            {isHM && (
                              <Button
                                variant="outlined"
                                onClick={() => { setApprovalComment(''); setApprovalAction('REQUEST_CHANGES'); }}
                                disabled={approving}
                                sx={{ borderColor: '#B54708', color: '#B54708' }}
                              >{t("Yêu cầu chỉnh sửa")}</Button>
                            )}
                            {isHM && (
                              <Button
                                variant="contained"
                                color="secondary"
                                startIcon={<CheckCircleIcon />}
                                onClick={() => handleApprove('APPROVE')}
                                  disabled={approving || criteriaStale || isSameApprover || fairnessIssues.length > 0}
                              >{t("HM duyệt chuyên môn")}</Button>
                            )}
                            {!isHM && (
                              <Typography variant="caption" color="text.secondary" sx={{ alignSelf: 'center' }}>{t("Chờ Hiring Manager duyệt")}</Typography>
                            )}
                          </>
                        ) : null}
                      </Box>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            )}
          </Grid>
        )}
      </TabPanel>

      {/* Tab 2: Applications — link to dedicated ranking page + stats */}
      <TabPanel value={activeTab} index={1}>
        {isHR ? <Grid container spacing={3}>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Typography variant="caption" color="text.secondary">{t("Tổng hồ sơ")}</Typography>
                <Typography variant="h4" sx={{ fontSize: 24, fontWeight: 'bold', color: '#0A2B57' }}>{appCounts?.total ?? '—'}</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card sx={{ border: (appCounts?.processing || 0) > 0 ? '1px solid #B54708' : undefined }}>
              <CardContent>
                <Typography variant="caption" color="text.secondary">{t("Đang xử lý CV")}</Typography>
                <Typography variant="h4" sx={{ fontSize: 24, fontWeight: 'bold', color: (appCounts?.processing || 0) > 0 ? '#B54708' : '#667085' }}>{appCounts?.processing ?? '—'}</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card sx={{ border: (appCounts?.needs_review || 0) > 0 ? '1px solid #FECDCA' : undefined }}>
              <CardContent>
                <Typography variant="caption" color="text.secondary">{t("Cần HR xem lại")}</Typography>
                <Typography variant="h4" sx={{ fontSize: 24, fontWeight: 'bold', color: (appCounts?.needs_review || 0) > 0 ? '#C72127' : '#667085' }}>{appCounts?.needs_review ?? '—'}</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Typography variant="caption" color="text.secondary">{t("Đã shortlist")}</Typography>
                <Typography variant="h4" sx={{ fontSize: 24, fontWeight: 'bold', color: '#067647' }}>{appCounts?.shortlisted ?? '—'}</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12}>
            <Card>
              <CardContent sx={{ textAlign: 'center', py: 6 }}>
                <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>{t("Xem bảng xếp hạng, đối chiếu bằng chứng, đánh dấu shortlist và chia sẻ cho Hiring Manager tại trang chuyên dụng.")}</Typography>
                <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', flexWrap: 'wrap' }}>
                  <Button
                    variant="outlined"
                    startIcon={<UploadFileIcon />}
                    onClick={() => setUploadOpen(true)}
                    disabled={!approvedCriteria || !isHR || position.status !== 'OPEN' || isOperationRunning}
                    sx={{ borderColor: '#0A2B57', color: '#0A2B57' }}
                  >{t("Tải lên CV ứng viên")}</Button>
                  {isHR ? <Button component={Link} href={`/positions/${positionId}/applicants`} variant="contained" color="secondary">{t("Mở trang xếp hạng & đánh giá")}</Button> : <Button component={Link} href="/shortlist" variant="contained" color="secondary">{t("Xem shortlist được chia sẻ")}</Button>}
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid> : <Card><CardContent sx={{ textAlign: 'center', py: 6 }}>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>{t("Bạn chỉ xem được hồ sơ đã được HR chia sẻ qua shortlist.")}</Typography>
          <Button component={Link} href="/shortlist" variant="contained" color="secondary">{t("Xem shortlist được chia sẻ")}</Button>
        </CardContent></Card>}
      </TabPanel>

      {/* Tab 3: Shortlist — link to shortlist inbox */}
      <TabPanel value={activeTab} index={2}>
        <Card>
          <CardContent sx={{ textAlign: 'center', py: 8 }}>
            <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>{t("Xem tất cả shortlist đã chia sẻ, trạng thái phản hồi của Hiring Manager tại trang Shortlist.")}</Typography>
            <Button component={Link} href="/shortlist" variant="contained" color="secondary">{t("Đi đến trang Shortlist")}</Button>
          </CardContent>
        </Card>
      </TabPanel>

      <TabPanel value={activeTab} index={3}>
        <Card variant="outlined"><CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap', mb: 2 }}>
            <Typography variant="h4">{t("Mô tả công việc")}</Typography>
            {isHR && <Button variant="outlined" startIcon={<EditOutlinedIcon />} disabled={!latestJd || isOperationRunning}
              onClick={() => { if (latestJd) { setJdContent(latestJd.content_text); setJdLanguage(latestJd.language_code); setJdExpected(latestJd.jd_version_id); setJdError(null); setJdDialogOpen(true); } }}>{t("Tạo phiên bản JD mới")}</Button>}
          </Box>
          {jdVersions.length > 0 ? <>
            <FormControl size="small" sx={{ minWidth: 180, mb: 2 }}><InputLabel id="jd-version-label">{t("Phiên bản JD")}</InputLabel>
              <Select labelId="jd-version-label" label={t("Phiên bản JD")} value={selectedJd?.jd_version_id || ''} onChange={e => setSelectedJdId(e.target.value)}>
                {jdVersions.map(jd => <MenuItem key={jd.jd_version_id} value={jd.jd_version_id}>{t("Phiên bản ")}{jd.version_number}{jd.jd_version_id === latestJd?.jd_version_id ? t(" · mới nhất") : ''}</MenuItem>)}
              </Select></FormControl>
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{selectedJd?.content_text}</Typography>
          </> : <Typography color="text.secondary">{t("Chưa có mô tả công việc.")}</Typography>}
        </CardContent></Card>
      </TabPanel>

      <TabPanel value={activeTab} index={4}>
        <Card variant="outlined"><CardContent>
          <Typography variant="h4" sx={{ mb: 1.5 }}>{t("Lịch sử trạng thái vị trí")}</Typography>
          {statusEvents.length === 0 ? (
            <Typography color="text.secondary">{t("Vị trí chưa thay đổi trạng thái kể từ khi tạo.")}</Typography>
          ) : statusEvents.map(event => {
            const label = (s?: string | null) => s === 'OPEN' ? t("Đang mở") : s === 'PAUSED' ? t("Tạm dừng") : s === 'CLOSED' ? t("Đã đóng") : '—';
            return (
              <Box key={event.event_id} sx={{ py: 1, borderTop: '1px solid #EDF1F5' }}>
                <Typography variant="body2" fontWeight={600}>
                  {label(event.previous_status)} → {label(event.new_status)} · {event.changed_by_name || t("Người thay đổi")}
                </Typography>
                <Typography variant="caption">{new Date(event.changed_at).toLocaleString(dateLocale)}</Typography>
                {event.reason && <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap', mt: 0.5 }}>{event.reason}</Typography>}
              </Box>
            );
          })}
        </CardContent></Card>
      </TabPanel>

      <Dialog open={jdDialogOpen} onClose={() => !savingJd && setJdDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>{t("Tạo phiên bản mô tả công việc mới")}</DialogTitle>
        <DialogContent>
          <Alert severity="info" sx={{ mt: 1, mb: 2 }}>{t("Phiên bản cũ được giữ lại. Sau khi lưu, cần tạo và duyệt tiêu chí mới trước khi xử lý thêm CV.")}</Alert>
          {jdError && <Alert severity="error" sx={{ mb: 2 }}>{t(jdError)}</Alert>}
          <FormControl size="small" sx={{ minWidth: 180, mb: 2 }}><InputLabel id="jd-language-label">{t("Ngôn ngữ JD")}</InputLabel>
            <Select labelId="jd-language-label" label={t("Ngôn ngữ JD")} value={jdLanguage} onChange={e => setJdLanguage(e.target.value as 'vi' | 'en')}><MenuItem value="vi">{t("Tiếng Việt")}</MenuItem><MenuItem value="en">English</MenuItem></Select>
          </FormControl>
          <TextField label={t("Nội dung JD")} required fullWidth multiline minRows={12} value={jdContent} onChange={e => setJdContent(e.target.value)} inputProps={{ maxLength: 100000 }} />
        </DialogContent>
        <DialogActions><Button onClick={() => setJdDialogOpen(false)} disabled={savingJd}>{t("Hủy")}</Button>
          <Button variant="contained" onClick={saveJd} disabled={savingJd || !jdContent.trim()}>{t("Lưu phiên bản mới")}</Button></DialogActions>
      </Dialog>

      <Dialog open={positionDialogOpen} onClose={() => !savingPosition && setPositionDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{t("Chỉnh sửa vị trí tuyển dụng")}</DialogTitle>
        <DialogContent>
          {positionEditError && <Alert severity="error" sx={{ mb: 2 }}>{t(positionEditError)}</Alert>}
          <Box sx={{ display: 'grid', gap: 2, pt: 1 }}>
            <TextField autoFocus fullWidth required label={t("Tên vị trí")} value={positionTitle} inputProps={{ maxLength: 200 }}
              onChange={e => setPositionTitle(e.target.value)} />
            <FormControl fullWidth>
              <InputLabel id="position-status-label">{t("Trạng thái vị trí")}</InputLabel>
              <Select labelId="position-status-label" label={t("Trạng thái vị trí")} value={positionStatus}
                onChange={e => setPositionStatus(e.target.value as Position['status'])}>
                <MenuItem value="OPEN">{t("Đang mở")}</MenuItem>
                <MenuItem value="PAUSED">{t("Tạm dừng")}</MenuItem>
                <MenuItem value="CLOSED">{t("Đã đóng")}</MenuItem>
              </Select>
            </FormControl>
            {positionStatus !== position.status && (
              <TextField fullWidth multiline minRows={2} label={t("Lý do thay đổi trạng thái")} value={positionStatusReason}
                onChange={e => setPositionStatusReason(e.target.value)} inputProps={{ maxLength: 1000 }}
                helperText={t("Được lưu trong lịch sử trạng thái của vị trí.")} />
            )}
            {positionStatus !== 'OPEN' && <Alert severity="info">{t("Vị trí tạm dừng hoặc đóng sẽ không nhận thêm CV; tác vụ đã chạy không tự hủy. Việc lưu trữ và xóa dữ liệu chưa được tự động thực hiện.")}</Alert>}
          </Box>
        </DialogContent>
        <DialogActions><Button onClick={() => setPositionDialogOpen(false)} disabled={savingPosition}>{t("Hủy")}</Button>
          <Button variant="contained" color="secondary" onClick={savePosition} disabled={!positionTitle.trim() || savingPosition}>
            {savingPosition ? t("Đang lưu…") : t("Lưu thay đổi")}</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={weightDialogOpen} onClose={() => !savingWeights && setWeightDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{t("Điều chỉnh trọng số nhóm")}</DialogTitle>
        <DialogContent>
          {weightError && <Alert severity="error" sx={{ mb: 2 }}>{t(weightError)}</Alert>}
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{t("Hai nhóm luôn cộng lại thành 100%. Thay đổi chỉ được dùng sau khi HR và Hiring Manager duyệt phiên bản này.")}</Typography>
          <TextField autoFocus fullWidth required label={t("Nhóm bắt buộc (%)")} type="number" value={mandatoryWeight}
            onChange={e => setMandatoryWeight(e.target.value)} inputProps={{ min: 0.01, max: 100, step: 0.01 }}
            error={mandatoryWeight !== '' && !validWeights} helperText={t("Nhập lớn hơn 0 và tối đa 100, với tối đa 2 chữ số thập phân.")} />
          <Typography variant="body2" sx={{ mt: 2 }}>{t("Nhóm ưu tiên: ")}<strong>{niceWeight === null ? '—' : `${niceWeight}%`}</strong></Typography>
          <Typography variant="caption" color="text.secondary">{t("Nếu một nhóm không có tiêu chí, điểm được chuẩn hóa theo nhóm có tiêu chí.")}</Typography>
        </DialogContent>
        <DialogActions><Button onClick={() => setWeightDialogOpen(false)} disabled={savingWeights}>{t("Hủy")}</Button>
          <Button variant="contained" color="secondary" onClick={saveWeights} disabled={!validWeights || savingWeights}>{savingWeights ? t("Đang lưu…") : t("Lưu trọng số")}</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={!!editingCriterion} onClose={() => !savingCriterion && setEditingCriterion(null)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingCriterion?.criterion_id ? t("Chỉnh sửa tiêu chí nháp") : t("Thêm tiêu chí")}</DialogTitle>
        <DialogContent>
          {criterionError && <Alert severity="error" sx={{ mb: 2 }}>{t(criterionError)}</Alert>}
          {editingCriterion && <Box sx={{ display: 'grid', gap: 2, pt: 1 }}>
            <TextField label={t("Tên tiêu chí")} required fullWidth value={editingCriterion.name}
              onChange={e => setEditingCriterion({ ...editingCriterion, name: e.target.value })} inputProps={{ maxLength: 200 }} />
            <TextField label={t("Mô tả")} required fullWidth multiline minRows={3} value={editingCriterion.description}
              onChange={e => setEditingCriterion({ ...editingCriterion, description: e.target.value })} inputProps={{ maxLength: 4000 }} />
            <FormControl fullWidth>
              <InputLabel id="criterion-category-label">{t("Nhóm tiêu chí")}</InputLabel>
              <Select labelId="criterion-category-label" label={t("Nhóm tiêu chí")} value={editingCriterion.category}
                onChange={e => setEditingCriterion({ ...editingCriterion, category: e.target.value as Criterion['category'] })}>
                <MenuItem value="MUST_HAVE">{t("Bắt buộc")}</MenuItem>
                <MenuItem value="NICE_TO_HAVE">{t("Ưu tiên")}</MenuItem>
              </Select>
            </FormControl>
            <TextField label={t("Trọng số tương đối trong nhóm (%)")} type="number" value={editingCriterion.weight_in_group}
              onChange={e => setEditingCriterion({ ...editingCriterion, weight_in_group: Number(e.target.value) })}
              inputProps={{ min: 0, max: 100, step: 0.1 }} helperText={t("Đây là trọng số tương đối giữa các tiêu chí trong cùng nhóm.")} />
            <TextField label={t("Từ khóa bằng chứng")} fullWidth value={editingCriterion.keywordsText}
              onChange={e => setEditingCriterion({ ...editingCriterion, keywordsText: e.target.value })}
              helperText={t("Phân tách bằng dấu phẩy, tối đa 20 từ khóa.")} />
            <TextField label={t("Đoạn JD làm căn cứ")} fullWidth multiline minRows={2} value={editingCriterion.jd_reference_text || ''}
              onChange={e => setEditingCriterion({ ...editingCriterion, jd_reference_text: e.target.value })} inputProps={{ maxLength: 4000 }} />
            <TextField label={t("Hướng dẫn xác định bằng chứng")} fullWidth multiline minRows={2} value={editingCriterion.evidence_guidance || ''}
              onChange={e => setEditingCriterion({ ...editingCriterion, evidence_guidance: e.target.value })} inputProps={{ maxLength: 4000 }} />
            <Typography variant="caption" color="text.secondary">{t("Không dùng tuổi, giới tính, ngoại hình, hôn nhân, tính cách hoặc “phù hợp văn hóa” làm tiêu chí.")}</Typography>
          </Box>}
        </DialogContent>
        <DialogActions><Button onClick={() => setEditingCriterion(null)} disabled={savingCriterion}>{t("Hủy")}</Button>
          <Button variant="contained" color="secondary" onClick={saveCriterion} disabled={savingCriterion || !editingCriterion?.name.trim() || !editingCriterion?.description.trim() || editingCriterion.weight_in_group < 0 || editingCriterion.weight_in_group > 100}>
            {savingCriterion ? t("Đang lưu…") : t("Lưu tiêu chí")}</Button></DialogActions>
      </Dialog>

      <Dialog open={!!deletingCriterion} onClose={() => !deletingBusy && setDeletingCriterion(null)} maxWidth="xs" fullWidth>
        <DialogTitle>{t("Xóa tiêu chí")}</DialogTitle>
        <DialogContent>
          <Typography variant="body2">{t("Xóa tiêu chí “{0}” khỏi bản nháp này?", deletingCriterion?.name || '')}</Typography>
        </DialogContent>
        <DialogActions><Button onClick={() => setDeletingCriterion(null)} disabled={deletingBusy}>{t("Hủy")}</Button>
          <Button variant="contained" color="error" onClick={confirmDeleteCriterion} disabled={deletingBusy}>{t("Xóa")}</Button></DialogActions>
      </Dialog>

      <Dialog open={!!approvalAction} onClose={() => !approving && setApprovalAction(null)} maxWidth="sm" fullWidth>
        <DialogTitle>{approvalAction === 'REJECT' ? t("Từ chối bộ tiêu chí") : t("Yêu cầu chỉnh sửa")}</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{t("Lý do sẽ được lưu trong lịch sử duyệt để người phụ trách tiếp tục xử lý.")}</Typography>
          <TextField autoFocus fullWidth multiline minRows={3} label={t("Lý do")} value={approvalComment}
            onChange={e => setApprovalComment(e.target.value)} inputProps={{ maxLength: 2000 }} />
        </DialogContent>
        <DialogActions><Button onClick={() => setApprovalAction(null)} disabled={approving}>{t("Hủy")}</Button>
          <Button variant="contained" color="secondary" disabled={!approvalComment.trim() || approving}
            onClick={() => approvalAction && handleApprove(approvalAction, approvalComment.trim())}>{t("Xác nhận")}</Button></DialogActions>
      </Dialog>

      {/* Upload CV Dialog */}
      <Dialog open={uploadOpen} onClose={() => { if (!uploading) setUploadOpen(false); }} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ color: '#0A2B57' }}>{t("Tải lên hồ sơ CV")}</DialogTitle>
        <DialogContent dividers>
          {uploadError && <Alert severity="error" sx={{ mb: 2 }}>{t(uploadError)}</Alert>}
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
              <Button component="span" variant="outlined" sx={{ mb: 2 }}>{t("Chọn tệp CV")}</Button>
            </label>
            <Typography variant="body2" color="text.secondary" sx={{ display: 'block', mb: 1 }}>{t("Hỗ trợ PDF, DOCX (tiếng Anh)")}</Typography>
            <Typography variant="caption" color="text.disabled">{t("Tối đa 50 file, mỗi file ≤ 10MB, tổng lô ≤ 250MB")}</Typography>

            {selectedFiles.length > 0 && (
              <Box sx={{ mt: 3, textAlign: 'left' }}>
                <Typography variant="body2" fontWeight={600} sx={{ mb: 1 }}>{t("                  Đã chọn")} {selectedFiles.length} {t("tệp:")}</Typography>
                {selectedFiles.slice(0, 5).map((file, i) => (
                  <Typography key={i} variant="caption" display="block" color="text.secondary">
                    • {file.name} ({(file.size / 1_000_000).toFixed(2)} MB)
                  </Typography>
                ))}
                {selectedFiles.length > 5 && (
                  <Typography variant="caption" color="text.disabled">{t("                    ...và")} {selectedFiles.length - 5} {t("tệp khác")}</Typography>
                )}
              </Box>
            )}

            {uploading && (
              <Box sx={{ mt: 3, width: '100%' }}>
                <LinearProgress variant="determinate" value={uploadProgress} />
                <Typography variant="caption" sx={{ mt: 1, display: 'block' }}>{t("                  Đang tải lên:")} {uploadProgress}%
                </Typography>
              </Box>
            )}
          </Box>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setUploadOpen(false)} disabled={uploading}>{t("Hủy")}</Button>
          <Button
            onClick={handleUpload}
            variant="contained"
            color="secondary"
            disabled={selectedFiles.length === 0 || uploading || !!uploadError}
          >
            {uploading ? t("Đang tải...") : t("Bắt đầu xử lý")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

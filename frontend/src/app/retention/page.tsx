'use client';

import { useI18n } from '@/i18n/I18nProvider';
import * as React from 'react';
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle,
  MenuItem, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useCallback, useEffect, useState } from 'react';
import { retentionApi } from '@/lib/api';

type CaseStatus = 'PENDING' | 'SCHEDULED_FOR_DELETION' | 'DELETED' | 'CANCELLED';

interface RetentionCase {
  retention_case_id: string;
  position_id: string;
  position_title: string;
  position_code: string;
  application_opaque_id?: string | null;
  policy_version: string;
  position_closed_at?: string | null;
  due_date?: string | null;
  status: CaseStatus;
  is_due: boolean;
  confirmed_at?: string | null;
  can_confirm: boolean;
}

interface ClosedPosition { position_id: string; title: string; position_code: string; closed_at?: string | null }

const STATUS_LABELS: Record<CaseStatus, string> = {
  PENDING: 'Chờ xác nhận',
  SCHEDULED_FOR_DELETION: 'Đã xác nhận — chờ xóa',
  DELETED: 'Đã xóa',
  CANCELLED: 'Đã hủy',
};
const STATUS_COLORS: Record<CaseStatus, 'warning' | 'error' | 'default' | 'success'> = {
  PENDING: 'warning', SCHEDULED_FOR_DELETION: 'error', DELETED: 'default', CANCELLED: 'success',
};

type Action = { kind: 'confirm' | 'cancel' | 'execute'; item: RetentionCase };

export default function RetentionPage() {
  const { t, dateLocale } = useI18n();
  const [cases, setCases] = useState<RetentionCase[]>([]);
  const [positions, setPositions] = useState<ClosedPosition[]>([]);
  const [statusFilter, setStatusFilter] = useState<'ALL' | CaseStatus>('ALL');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [scanPosition, setScanPosition] = useState('');
  const [busy, setBusy] = useState(false);
  const [action, setAction] = useState<Action | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await retentionApi.queue(statusFilter === 'ALL' ? undefined : statusFilter);
      setCases(res.data.cases || []);
      setPositions(res.data.closed_positions || []);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể tải danh sách retention"));
    } finally { setLoading(false); }
  }, [statusFilter, t]);

  useEffect(() => { load(); }, [load]);

  const scan = async () => {
    if (!scanPosition || busy) return;
    try {
      setBusy(true); setError(null); setNotice(null);
      const res = await retentionApi.generate(scanPosition);
      setNotice(t("Đã quét vị trí: {0} hồ sơ mới đến hạn.", res.data.created_count ?? 0));
      await load();
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể quét hồ sơ đến hạn"));
    } finally { setBusy(false); }
  };

  const runAction = async () => {
    if (!action || busy) return;
    const id = action.item.retention_case_id;
    try {
      setBusy(true); setError(null); setNotice(null);
      if (action.kind === 'confirm') await retentionApi.confirm(id);
      else if (action.kind === 'cancel') await retentionApi.cancel(id);
      else await retentionApi.execute(id);
      setNotice(action.kind === 'confirm' ? t("Đã xác nhận xóa. Hồ sơ chờ thực hiện xóa.")
        : action.kind === 'cancel' ? t("Đã hủy yêu cầu xóa.") : t("Đã xóa dữ liệu ứng viên của hồ sơ này."));
      setAction(null);
      await load();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : t("Thao tác retention không thành công"));
      setAction(null);
    } finally { setBusy(false); }
  };

  const fmt = (value?: string | null) => value ? new Date(value).toLocaleDateString(dateLocale) : '—';

  if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 10 }}><CircularProgress color="secondary" /></Box>;

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap', mb: 3 }}>
        <Box>
          <Typography variant="h1" sx={{ fontSize: 28, color: '#0A2B57', mb: 0.5 }}>{t("Lưu trữ & xóa dữ liệu")}</Typography>
          <Typography variant="body2" color="text.secondary">{t("Hồ sơ ứng tuyển đến hạn xem xét retention. Hệ thống không tự xóa: người có quyền phải xác nhận rồi thực hiện xóa, và mọi thao tác đều được ghi audit.")}</Typography>
        </Box>
        <Button variant="outlined" startIcon={<RefreshIcon />} onClick={() => load()}>{t("Làm mới")}</Button>
      </Box>

      <Alert severity="info" sx={{ mb: 2 }}>
        {t("Thời hạn 12 tháng tính từ ngày đóng vị trí là đề xuất, chưa được Legal/Privacy xác nhận. Xóa một hồ sơ không ảnh hưởng hồ sơ của cùng ứng viên ở vị trí khác.")}
      </Alert>
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{t(error)}</Alert>}
      {notice && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setNotice(null)}>{notice}</Alert>}

      <Card variant="outlined" sx={{ mb: 3 }}><CardContent sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <TextField select size="small" label={t("Vị trí đã đóng")} value={scanPosition} sx={{ minWidth: 320 }}
          onChange={e => setScanPosition(e.target.value)} disabled={positions.length === 0}
          helperText={positions.length === 0 ? t("Không có vị trí đã đóng trong phạm vi của bạn.") : t("Quét để đưa các hồ sơ đã đến hạn vào danh sách chờ xác nhận.")}>
          {positions.map(p => (
            <MenuItem key={p.position_id} value={p.position_id}>{p.title} · {p.position_code} ({t("đóng")} {fmt(p.closed_at)})</MenuItem>
          ))}
        </TextField>
        <Button variant="contained" color="secondary" onClick={scan} disabled={!scanPosition || busy}>{t("Quét hồ sơ đến hạn")}</Button>
      </CardContent></Card>

      <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
        <TextField select size="small" label={t("Trạng thái")} value={statusFilter} sx={{ minWidth: 220 }}
          onChange={e => { setLoading(true); setStatusFilter(e.target.value as 'ALL' | CaseStatus); }}>
          <MenuItem value="ALL">{t("Tất cả")}</MenuItem>
          {(Object.keys(STATUS_LABELS) as CaseStatus[]).map(key => <MenuItem key={key} value={key}>{t(STATUS_LABELS[key])}</MenuItem>)}
        </TextField>
      </Box>

      <TableContainer component={Paper} sx={{ borderRadius: 2, boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <Table aria-label={t("Danh sách hồ sơ retention")}>
          <TableHead>
            <TableRow>
              <TableCell>{t("Vị trí")}</TableCell>
              <TableCell>{t("Hồ sơ")}</TableCell>
              <TableCell>{t("Ngày đóng")}</TableCell>
              <TableCell>{t("Ngày đến hạn")}</TableCell>
              <TableCell>{t("Trạng thái")}</TableCell>
              <TableCell align="right">{t("Thao tác")}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {cases.length === 0 ? (
              <TableRow><TableCell colSpan={6} align="center" sx={{ py: 6, color: 'text.secondary' }}>{t("Không có hồ sơ nào trong danh sách retention")}</TableCell></TableRow>
            ) : cases.map(item => (
              <TableRow key={item.retention_case_id} hover>
                <TableCell>
                  <Typography variant="body2" fontWeight={600}>{item.position_title}</Typography>
                  <Typography variant="caption" color="text.secondary" fontFamily="monospace">{item.position_code}</Typography>
                </TableCell>
                {/* Only an opaque identifier: candidate PII is never shown in this queue. */}
                <TableCell><Typography variant="caption" fontFamily="monospace">{(item.application_opaque_id || '').slice(0, 12) || '—'}</Typography></TableCell>
                <TableCell>{fmt(item.position_closed_at)}</TableCell>
                <TableCell>
                  {fmt(item.due_date)}
                  {item.is_due && <Chip size="small" color="error" label={t("Đến hạn")} sx={{ ml: 1, height: 20 }} />}
                </TableCell>
                <TableCell><Chip size="small" color={STATUS_COLORS[item.status]} label={t(STATUS_LABELS[item.status])} /></TableCell>
                <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                  {item.can_confirm && item.status === 'PENDING' && (
                    <Button size="small" color="error" disabled={!item.is_due || busy} onClick={() => setAction({ kind: 'confirm', item })}>{t("Xác nhận xóa")}</Button>
                  )}
                  {item.can_confirm && item.status === 'SCHEDULED_FOR_DELETION' && (
                    <Button size="small" variant="contained" color="error" disabled={busy} onClick={() => setAction({ kind: 'execute', item })}>{t("Thực hiện xóa")}</Button>
                  )}
                  {item.can_confirm && ['PENDING', 'SCHEDULED_FOR_DELETION'].includes(item.status) && (
                    <Button size="small" disabled={busy} onClick={() => setAction({ kind: 'cancel', item })}>{t("Hủy")}</Button>
                  )}
                  {!item.can_confirm && ['PENDING', 'SCHEDULED_FOR_DELETION'].includes(item.status) && (
                    <Typography variant="caption" color="text.secondary">{t("Cần HR Lead hoặc người được cấp quyền xác nhận")}</Typography>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={!!action} onClose={() => !busy && setAction(null)} maxWidth="sm" fullWidth>
        <DialogTitle>
          {action?.kind === 'confirm' ? t("Xác nhận xóa hồ sơ này?") : action?.kind === 'execute' ? t("Thực hiện xóa dữ liệu?") : t("Hủy yêu cầu xóa?")}
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            {action?.kind === 'cancel'
              ? t("Hồ sơ sẽ được giữ lại và rời khỏi danh sách chờ xóa.")
              : t("Phạm vi xóa (chỉ hồ sơ ứng tuyển này, theo policy {0}): tệp CV gốc và văn bản trích xuất; hồ sơ trích xuất, kết quả đánh giá, xếp hạng và cảnh báo trùng; thông tin định danh, lịch sử trạng thái và ghi chú riêng của HR; mục shortlist, phản hồi và scorecard liên quan. Chỉ còn lại bằng chứng ẩn danh trong nhật ký. Thao tác xóa không hoàn tác được.", action?.item.policy_version || '')}
          </Typography>
          {action && <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>{action.item.position_title} · {action.item.position_code}</Typography>}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAction(null)} disabled={busy}>{t("Quay lại")}</Button>
          <Button variant="contained" color={action?.kind === 'cancel' ? 'primary' : 'error'} onClick={runAction} disabled={busy}>
            {busy ? t("Đang xử lý…") : t("Đồng ý")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

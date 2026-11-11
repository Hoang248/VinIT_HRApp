'use client';

import { useI18n } from '@/i18n/I18nProvider';

import * as React from 'react';
import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import {
  Alert, Box, Card, CardContent, Chip, FormControl, Grid, InputLabel, MenuItem, Select, Skeleton,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography,
} from '@mui/material';
import { qaApi } from '@/lib/api';
import PageHeader from '@/components/common/PageHeader';
import EmptyState from '@/components/common/EmptyState';
import type { QaQueueItem, QaSummary } from '@/types';
import { QA_REASON_LABELS, QA_STATUS_LABELS } from '@/lib/qa';

const percent = (value: number | null | undefined) => (value == null ? '—' : `${Math.round(value * 100)}%`);

export default function QaQueuePage() {
  const { t } = useI18n();
  const [items, setItems] = useState<QaQueueItem[]>([]);
  const [summary, setSummary] = useState<QaSummary | null>(null);
  const [canReview, setCanReview] = useState(false);
  const [status, setStatus] = useState('PENDING');
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const queue = await qaApi.getQueue({ status: status || undefined, reason: reason || undefined });
      setItems(queue.data.items || []);
      setCanReview(Boolean(queue.data.can_review));
      setError(null);
      if (queue.data.can_review) {
        const res = await qaApi.getSummary();
        setSummary(res.data);
      } else {
        setSummary(null);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể tải hàng đợi kiểm định."));
    } finally {
      setLoading(false);
    }
  }, [status, reason, t]);

  useEffect(() => { load(); }, [load]);

  return (
    <Box>
      <PageHeader eyebrow={t("Kiểm định chất lượng")} title={t("Hàng đợi kiểm định OCR & matching")}
        description={t("Hệ thống tự trích 10% hồ sơ ngẫu nhiên mỗi đợt CV và toàn bộ hồ sơ rủi ro cao để HR Lead đối chiếu với CV gốc.")} />
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {!canReview && !loading && !error && (
        <Alert severity="info" sx={{ mb: 2 }}>{t("Bạn chỉ xem được kết quả kiểm định của vị trí mình phụ trách. HR Lead thực hiện kiểm định.")}</Alert>
      )}
      {summary && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          {[
            { label: t("Chờ kiểm định"), value: String(summary.pending_items) },
            { label: t("Quá 7 ngày chưa kiểm định"), value: String(summary.overdue_items) },
            { label: t("Đã kiểm định"), value: String(summary.reviewed_items) },
            { label: t("Tỷ lệ có cờ lỗi"), value: percent(summary.flagged_items.rate),
              hint: summary.flagged_items.wilson95 ? `95% CI ${percent(summary.flagged_items.wilson95[0])}–${percent(summary.flagged_items.wilson95[1])}` : undefined },
          ].map(card => (
            <Grid item xs={6} md={3} key={card.label}>
              <Card><CardContent>
                <Typography variant="body2" color="text.secondary">{card.label}</Typography>
                <Typography variant="h2" sx={{ color: '#0A2B57', mt: 0.5 }}>{card.value}</Typography>
                {card.hint && <Typography variant="caption" color="text.secondary">{card.hint}</Typography>}
              </CardContent></Card>
            </Grid>
          ))}
          {summary.small_sample_warning && summary.reviewed_items > 0 && (
            <Grid item xs={12}>
              <Alert severity="warning">{t("Mới kiểm định dưới 30 hồ sơ, tỷ lệ lỗi chưa đủ tin cậy để kết luận.")}</Alert>
            </Grid>
          )}
        </Grid>
      )}
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel id="qa-status">{t("Trạng thái")}</InputLabel>
          <Select labelId="qa-status" label={t("Trạng thái")} value={status} onChange={e => setStatus(e.target.value)}>
            <MenuItem value="">{t("Tất cả")}</MenuItem>
            {Object.entries(QA_STATUS_LABELS).map(([key, label]) => <MenuItem key={key} value={key}>{t(label)}</MenuItem>)}
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 260 }}>
          <InputLabel id="qa-reason">{t("Lý do chọn mẫu")}</InputLabel>
          <Select labelId="qa-reason" label={t("Lý do chọn mẫu")} value={reason} onChange={e => setReason(e.target.value)}>
            <MenuItem value="">{t("Tất cả")}</MenuItem>
            {Object.entries(QA_REASON_LABELS).map(([key, label]) => <MenuItem key={key} value={key}>{t(label)}</MenuItem>)}
          </Select>
        </FormControl>
      </Box>
      {loading ? <Skeleton variant="rounded" height={240} /> : items.length === 0 ? (
        <EmptyState title={t("Không có hồ sơ trong hàng đợi")} description={t("Mẫu kiểm định được tạo khi một đợt CV đã được đánh giá xong.")} />
      ) : (
        <TableContainer component={Card}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>{t("Ứng viên")}</TableCell>
                <TableCell>{t("Vị trí")}</TableCell>
                <TableCell>{t("Lý do chọn mẫu")}</TableCell>
                <TableCell>{t("Độ phủ bằng chứng")}</TableCell>
                <TableCell>{t("Trạng thái")}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {items.map(item => (
                <TableRow key={item.sample_item_id} hover>
                  <TableCell>
                    <Link href={`/qa/${item.sample_item_id}`}>{item.display_name || t("Ứng viên")}</Link>
                  </TableCell>
                  <TableCell>{item.position_title}</TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                      {item.reasons.map(r => <Chip key={r} size="small" variant="outlined" label={t(QA_REASON_LABELS[r] || r)} />)}
                    </Box>
                  </TableCell>
                  <TableCell>{percent(item.evidence_coverage)}</TableCell>
                  <TableCell>
                    {t(QA_STATUS_LABELS[item.status] || item.status)}
                    {item.overdue && <Typography variant="caption" color="error" sx={{ display: 'block' }}>{t("Quá 7 ngày")}</Typography>}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}

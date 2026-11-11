'use client';

import { useI18n } from '@/i18n/I18nProvider';

import * as React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import {
  Alert, Box, Button, Card, CardContent, Chip, Dialog, DialogActions, DialogContent, DialogTitle, FormControl,
  Grid, InputLabel, MenuItem, Select, Skeleton, Tab, Tabs, TextField, Typography,
} from '@mui/material';
import { applicationsApi, qaApi } from '@/lib/api';
import { highlightSegments, OUTCOME_LABELS, QA_FLAG_LABELS, QA_REASON_LABELS, QA_STATUS_LABELS } from '@/lib/qa';
import PageHeader from '@/components/common/PageHeader';
import CVDocumentViewer from '@/components/candidates/CVDocumentViewer';
import type { QaCriterionResult, QaEvidence, QaItemDetail } from '@/types';

interface FlagDraft {
  criterion?: QaCriterionResult;
  evidence?: QaEvidence;
}

export default function QaInspectionPage() {
  const { t } = useI18n();
  const params = useParams<{ itemId: string }>();
  const itemId = params.itemId;
  const [item, setItem] = useState<QaItemDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [cvUrl, setCvUrl] = useState<string | null>(null);
  const [cvError, setCvError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [tab, setTab] = useState(0);
  const [draft, setDraft] = useState<FlagDraft | null>(null);
  const [flagType, setFlagType] = useState('INCORRECT_EVIDENCE');
  const [expected, setExpected] = useState('');
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const blobUrl = useRef<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await qaApi.getItem(itemId);
      setItem(res.data);
      setError(null);
      try {
        const cv = await applicationsApi.getCvUrl(res.data.application_id);
        if (blobUrl.current) { URL.revokeObjectURL(blobUrl.current); blobUrl.current = null; }
        if (typeof cv.data.signed_url === 'string') setCvUrl(cv.data.signed_url);
        else if (cv.data.source === 'local') {
          const file = await applicationsApi.getCvBlob(res.data.application_id);
          blobUrl.current = URL.createObjectURL(file.data);
          setCvUrl(blobUrl.current);
        } else setCvError(t("Không thể lấy đường dẫn CV."));
      } catch {
        setCvUrl(null);
        setCvError(t("Không thể tải CV gốc. Vui lòng thử lại sau."));
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể tải hồ sơ kiểm định."));
    } finally {
      setLoading(false);
    }
  }, [itemId, t]);

  useEffect(() => {
    load();
    return () => { if (blobUrl.current) { URL.revokeObjectURL(blobUrl.current); blobUrl.current = null; } };
  }, [load]);

  const quotes = useMemo(() => (item?.criterion_results || []).flatMap(r => r.evidence.map(e => e.verbatim_quote)), [item]);
  const segments = useMemo(() => highlightSegments(item?.extracted_text || '', quotes), [item, quotes]);
  const isPdf = item?.document?.mime_type === 'application/pdf' || /\.pdf$/i.test(item?.document?.original_filename || '');

  const openFlag = (criterion?: QaCriterionResult, evidence?: QaEvidence) => {
    setDraft({ criterion, evidence });
    setFlagType(evidence ? 'INCORRECT_EVIDENCE' : criterion ? 'MISSED_CONTENT' : 'OCR_ERROR');
    setExpected('');
    setNote('');
  };

  const submitFlag = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      await qaApi.addFlag(itemId, {
        flag_type: flagType,
        criterion_result_id: draft.criterion?.result_id,
        evidence_id: draft.evidence?.evidence_id,
        expected_outcome: expected || undefined,
        note: note.trim() || undefined,
      });
      setDraft(null);
      setNotice(t("Đã gắn cờ. Nếu kết luận của hồ sơ bị sai, hãy cập nhật trạng thái tuyển dụng ngay."));
      await load();
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể gắn cờ."));
    } finally {
      setSaving(false);
    }
  };

  const markPassed = async () => {
    setSaving(true);
    try {
      await qaApi.markPassed(itemId);
      setNotice(t("Đã đánh dấu hồ sơ đạt kiểm định."));
      await load();
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể cập nhật kết quả kiểm định."));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <Skeleton variant="rounded" height={480} />;
  if (!item) return <Alert severity="error">{error || t("Không thể tải hồ sơ kiểm định.")}</Alert>;

  return (
    <Box>
      <PageHeader eyebrow={t("Kiểm định chất lượng")} title={t("Đối soát CV gốc và bằng chứng AI")}
        description={`${t(QA_STATUS_LABELS[item.status] || item.status)} · ${item.reasons.map(r => t(QA_REASON_LABELS[r] || r)).join(' · ')}`}
        actions={<>
          <Button component={Link} href="/qa" variant="outlined">{t("Về hàng đợi")}</Button>
          <Button component={Link} href={`/positions/${item.position_id}/applicants/${item.application_id}`} variant="outlined">{t("Mở hồ sơ ứng viên")}</Button>
          {item.can_review && <Button variant="outlined" color="error" onClick={() => openFlag()}>{t("Gắn cờ lỗi OCR")}</Button>}
          {item.can_review && item.status !== 'FLAGGED' && (
            <Button variant="contained" disabled={saving || item.status === 'PASSED'} onClick={markPassed}>{t("Đánh dấu Đạt")}</Button>
          )}
        </>} />
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}
      {notice && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setNotice(null)}>{notice}</Alert>}
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <CVDocumentViewer cvUrl={cvUrl} cvError={cvError} isPdf={isPdf} canViewCv selectedPage={page} onPageChange={setPage} />
        </Grid>
        <Grid item xs={12} md={6}>
          <Tabs value={tab} onChange={(_, value) => setTab(value)} sx={{ mb: 2 }}>
            <Tab label={t("Bằng chứng theo tiêu chí")} />
            <Tab label={t("Văn bản trích xuất")} />
          </Tabs>
          {tab === 0 ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, maxHeight: 'calc(100vh - 250px)', overflow: 'auto' }}>
              {item.criterion_results.map(result => (
                <Card key={result.result_id} variant="outlined">
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1, flexWrap: 'wrap' }}>
                      <Typography sx={{ fontWeight: 600, color: '#0A2B57' }}>{result.criterion_name}</Typography>
                      <Box sx={{ display: 'flex', gap: 0.5 }}>
                        <Chip size="small" variant="outlined" label={result.category === 'MUST_HAVE' ? t("Bắt buộc") : t("Ưu tiên")} />
                        <Chip size="small" label={t(OUTCOME_LABELS[result.outcome] || result.outcome)} />
                      </Box>
                    </Box>
                    {result.reasoning && <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>{result.reasoning}</Typography>}
                    {result.evidence.map(ev => (
                      <Box key={ev.evidence_id} sx={{ mt: 1, p: 1, borderLeft: '3px solid #0A2B57', backgroundColor: '#F5F8FC' }}>
                        <Typography variant="body2">“{ev.verbatim_quote}”</Typography>
                        <Box sx={{ display: 'flex', gap: 1, mt: 0.5 }}>
                          {ev.page_number && (
                            <Button size="small" onClick={() => setPage(ev.page_number || 1)}>{t("Trang {0}", ev.page_number)}</Button>
                          )}
                          {item.can_review && <Button size="small" color="error" onClick={() => openFlag(result, ev)}>{t("Bằng chứng không chính xác")}</Button>}
                        </Box>
                      </Box>
                    ))}
                    {item.can_review && (
                      <Button size="small" color="error" sx={{ mt: 1 }} onClick={() => openFlag(result)}>{t("Gắn cờ tiêu chí này")}</Button>
                    )}
                    {item.flags.filter(f => f.criterion_result_id === result.result_id).map(f => (
                      <Alert key={f.flag_id} severity="warning" sx={{ mt: 1 }}>
                        {t(QA_FLAG_LABELS[f.flag_type] || f.flag_type)}{f.expected_outcome ? ` → ${t(OUTCOME_LABELS[f.expected_outcome] || f.expected_outcome)}` : ''}
                        {f.note ? ` · ${f.note}` : ''}{f.author_name ? ` · ${f.author_name}` : ''}
                      </Alert>
                    ))}
                  </CardContent>
                </Card>
              ))}
              {item.flags.filter(f => !f.criterion_result_id).map(f => (
                <Alert key={f.flag_id} severity="warning">{t(QA_FLAG_LABELS[f.flag_type] || f.flag_type)}{f.note ? ` · ${f.note}` : ''}</Alert>
              ))}
            </Box>
          ) : (
            <Card variant="outlined" sx={{ maxHeight: 'calc(100vh - 250px)', overflow: 'auto' }}>
              <CardContent>
                {item.document?.extraction_type && (
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                    {t("Phương thức trích xuất")}: {item.document.extraction_type}
                  </Typography>
                )}
                {item.extracted_text ? (
                  <Typography component="pre" variant="body2" sx={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', m: 0 }}>
                    {segments.map((s, i) => s.mark
                      ? <Box component="mark" key={i} sx={{ backgroundColor: '#FFE8A3' }}>{s.text}</Box>
                      : <React.Fragment key={i}>{s.text}</React.Fragment>)}
                  </Typography>
                ) : <Typography variant="body2" color="text.secondary">{t("Không có văn bản trích xuất.")}</Typography>}
              </CardContent>
            </Card>
          )}
        </Grid>
      </Grid>
      <Dialog open={Boolean(draft)} onClose={() => setDraft(null)} fullWidth maxWidth="sm">
        <DialogTitle>{t("Gắn cờ kiểm định")}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '8px !important' }}>
          {draft?.criterion && <Typography variant="body2">{t("Tiêu chí")}: {draft.criterion.criterion_name}</Typography>}
          <FormControl fullWidth size="small">
            <InputLabel id="qa-flag-type">{t("Loại lỗi")}</InputLabel>
            <Select labelId="qa-flag-type" label={t("Loại lỗi")} value={flagType} onChange={e => setFlagType(e.target.value)}>
              {Object.entries(QA_FLAG_LABELS).map(([key, label]) => <MenuItem key={key} value={key}>{t(label)}</MenuItem>)}
            </Select>
          </FormControl>
          {draft?.criterion && (
            <FormControl fullWidth size="small">
              <InputLabel id="qa-expected">{t("Kết luận đúng theo HR")}</InputLabel>
              <Select labelId="qa-expected" label={t("Kết luận đúng theo HR")} value={expected} onChange={e => setExpected(e.target.value)}>
                <MenuItem value="">{t("Không chọn")}</MenuItem>
                {Object.entries(OUTCOME_LABELS).map(([key, label]) => <MenuItem key={key} value={key}>{t(label)}</MenuItem>)}
              </Select>
            </FormControl>
          )}
          <TextField label={t("Ghi chú cho đội kỹ thuật")} multiline minRows={3} value={note} inputProps={{ maxLength: 2000 }}
            helperText={t("Không ghi họ tên, email hay số điện thoại của ứng viên.")} onChange={e => setNote(e.target.value)} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDraft(null)}>{t("Hủy")}</Button>
          <Button variant="contained" color="error" disabled={saving} onClick={submitFlag}>{t("Gắn cờ")}</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

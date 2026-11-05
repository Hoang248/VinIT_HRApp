'use client';

import { useI18n } from '@/i18n/I18nProvider';

import * as React from 'react';
import { useCallback, useEffect, useState } from 'react';
import { Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, CircularProgress, TextField, Typography } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { applicationsApi } from '@/lib/api';

type Note = { note_id: string; content: string; created_at: string; author_name: string | null };

export default function HRNotesPanel({ applicationId }: { applicationId: string }) {
  const { t, dateLocale } = useI18n();
  const [notes, setNotes] = useState<Note[]>([]);
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try { setError(null); setNotes((await applicationsApi.getPrivateNotes(applicationId)).data); }
    catch (err: any) { setError(err.response?.data?.detail || t("Không thể tải ghi chú nội bộ.")); }
    finally { setLoading(false); }
  }, [applicationId, t]);
  useEffect(() => { load(); }, [load]);
  const add = async () => {
    if (!content.trim() || saving) return;
    try { setSaving(true); setError(null); await applicationsApi.addPrivateNote(applicationId, content.trim()); setContent(''); await load(); }
    catch (err: any) { setError(err.response?.data?.detail || t("Không thể lưu ghi chú.")); }
    finally { setSaving(false); }
  };
  return <Accordion disableGutters elevation={0} sx={{ mb: 3, border: '1px solid #E4E7EC', borderRadius: '8px !important', '&:before': { display: 'none' } }}>
    <AccordionSummary expandIcon={<ExpandMoreIcon />}><Typography fontWeight={600}>{t("Ghi chú nội bộ HR ")}{notes.length > 0 ? `(${notes.length})` : ''}</Typography></AccordionSummary>
    <AccordionDetails>
      <Alert severity="info" sx={{ mb: 2 }}>{t("Chỉ HR phụ trách và HR Lead được xem. Ghi chú không được chia sẻ với Hiring Manager hoặc gửi cho AI. Các ghi chú được lưu nối tiếp để giữ lịch sử.")}</Alert>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{t(error)}</Alert>}
      <TextField label={t("Thêm ghi chú nội bộ")} fullWidth multiline minRows={2} value={content} onChange={e => setContent(e.target.value)} inputProps={{ maxLength: 5000 }} />
      <Button variant="outlined" size="small" sx={{ mt: 1.5, mb: 2 }} onClick={add} disabled={saving || !content.trim()}>{t("Thêm ghi chú")}</Button>
      {loading ? <Box><CircularProgress size={20} /></Box> : notes.length === 0 ? <Typography variant="body2" color="text.secondary">{t("Chưa có ghi chú nội bộ.")}</Typography> : notes.map(note => <Box key={note.note_id} sx={{ borderTop: '1px solid #EDF1F5', py: 1.5 }}>
        <Typography variant="caption" color="text.secondary">{note.author_name || 'HR'} · {new Date(note.created_at).toLocaleString(dateLocale)}</Typography>
        <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{note.content}</Typography>
      </Box>)}
    </AccordionDetails>
  </Accordion>;
}

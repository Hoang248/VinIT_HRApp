// F2.04 QA sample inspection labels (Vietnamese keys, translated through en.json).
export const QA_REASON_LABELS: Record<string, string> = {
  RANDOM: 'Mẫu ngẫu nhiên 10%',
  SINGLE_MUST_HAVE_FAIL: 'Trượt đúng 1 tiêu chí bắt buộc',
  COVERAGE_NEAR_THRESHOLD: 'Độ phủ bằng chứng sát ngưỡng 70%',
};

export const QA_STATUS_LABELS: Record<string, string> = {
  PENDING: 'Chờ kiểm định',
  PASSED: 'Đạt',
  FLAGGED: 'Có cờ lỗi',
};

export const QA_FLAG_LABELS: Record<string, string> = {
  INCORRECT_EVIDENCE: 'Bằng chứng không chính xác',
  MISSED_CONTENT: 'Bỏ sót nội dung',
  OCR_ERROR: 'Lỗi OCR / trích xuất văn bản',
};

export const OUTCOME_LABELS: Record<string, string> = {
  STRONG_MATCH: 'Đáp ứng tốt',
  MATCH: 'Đáp ứng',
  UNCLEAR: 'Chưa rõ',
  NO_MATCH: 'Chưa đáp ứng',
};

/** Split text into plain and highlighted segments for every quote found (case-insensitive). */
export function highlightSegments(textValue: string, quotes: string[]): { text: string; mark: boolean }[] {
  const needles = Array.from(new Set(quotes.map(q => q.trim()).filter(q => q.length >= 3)));
  if (!textValue || needles.length === 0) return [{ text: textValue || '', mark: false }];
  const lower = textValue.toLowerCase();
  const ranges: [number, number][] = [];
  for (const needle of needles) {
    const n = needle.toLowerCase();
    for (let at = lower.indexOf(n); at !== -1; at = lower.indexOf(n, at + n.length)) ranges.push([at, at + n.length]);
  }
  ranges.sort((a, b) => a[0] - b[0]);
  const merged: [number, number][] = [];
  for (const range of ranges) {
    const last = merged[merged.length - 1];
    if (last && range[0] <= last[1]) last[1] = Math.max(last[1], range[1]);
    else merged.push([range[0], range[1]]);
  }
  const segments: { text: string; mark: boolean }[] = [];
  let cursor = 0;
  for (const [start, end] of merged) {
    if (start > cursor) segments.push({ text: textValue.slice(cursor, start), mark: false });
    segments.push({ text: textValue.slice(start, end), mark: true });
    cursor = end;
  }
  if (cursor < textValue.length) segments.push({ text: textValue.slice(cursor), mark: false });
  return segments;
}

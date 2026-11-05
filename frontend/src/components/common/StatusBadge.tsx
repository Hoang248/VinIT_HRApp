'use client';

import { Box } from '@mui/material';
import Chip from '@mui/material/Chip';

type BadgeType =
  | 'file-completed'
  | 'file-processing'
  | 'file-review'
  | 'file-error'
  | 'match-meets'
  | 'match-verify'
  | 'match-mismatch'
  | 'app-new'
  | 'app-review'
  | 'app-shortlist'
  | 'app-rejected'
  | 'position-open'
  | 'position-paused'
  | 'position-closed'
  | 'criteria-draft'
  | 'criteria-approved';

interface StatusBadgeProps {
  type: BadgeType;
  label: string;
}

const colorMap: Record<BadgeType, { bg: string; text: string }> = {
  'file-completed': { bg: '#ECFDF3', text: '#067647' },
  'file-processing': { bg: '#EFF8FF', text: '#134D8B' },
  'file-review': { bg: '#FFFAEB', text: '#B54708' },
  'file-error': { bg: '#FEF3F2', text: '#B42318' },
  'match-meets': { bg: '#E8F1FC', text: '#0A2B57' },
  'match-verify': { bg: '#FFFAEB', text: '#B54708' },
  'match-mismatch': { bg: '#FDF2F2', text: '#941616' },
  'app-new': { bg: '#F2F4F7', text: '#475467' },
  'app-review': { bg: '#EFF8FF', text: '#175CD3' },
  'app-shortlist': { bg: '#ECFDF3', text: '#067647' },
  'app-rejected': { bg: '#FEF3F2', text: '#B42318' },
  'position-open': { bg: '#ECFDF3', text: '#067647' },
  'position-paused': { bg: '#FFFAEB', text: '#B54708' },
  'position-closed': { bg: '#F2F4F7', text: '#475467' },
  'criteria-draft': { bg: '#FFFAEB', text: '#B54708' },
  'criteria-approved': { bg: '#ECFDF3', text: '#067647' },
};

export default function StatusBadge({ type, label }: StatusBadgeProps) {
  const colors = colorMap[type];
  return (
    <Chip
      label={label}
      size="small"
      sx={{
        backgroundColor: colors.bg,
        color: colors.text,
        fontWeight: 700,
        fontSize: 11,
        textTransform: 'uppercase',
        borderRadius: '4px',
        height: 24,
      }}
    />
  );
}

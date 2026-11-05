import type { BadgeType } from '@/components/common/StatusBadge';

export type ApplicationStatus = 'NEW' | 'IN_REVIEW' | 'SHORTLIST' | 'REJECTED_SCREENING' |
  'INTERVIEW' | 'REJECTED_INTERVIEW' | 'OFFERED' | 'ACCEPTED';

export const APPLICATION_STATUSES: Record<ApplicationStatus, { label: string; badge: BadgeType }> = {
  NEW: { label: 'Mới', badge: 'app-new' },
  IN_REVIEW: { label: 'Đang xem', badge: 'app-review' },
  SHORTLIST: { label: 'Shortlist', badge: 'app-shortlist' },
  REJECTED_SCREENING: { label: 'Loại vòng sàng lọc', badge: 'app-rejected' },
  INTERVIEW: { label: 'Đang phỏng vấn', badge: 'app-review' },
  REJECTED_INTERVIEW: { label: 'Không trúng tuyển', badge: 'app-rejected' },
  OFFERED: { label: 'Đã gửi đề nghị', badge: 'app-review' },
  ACCEPTED: { label: 'Đã nhận việc', badge: 'app-shortlist' },
};

// Keep this in sync with the server's VALID_TRANSITIONS. Terminal states have no next step.
export const APPLICATION_TRANSITIONS: Record<ApplicationStatus, ApplicationStatus[]> = {
  NEW: ['IN_REVIEW', 'REJECTED_SCREENING'],
  IN_REVIEW: ['SHORTLIST', 'REJECTED_SCREENING'],
  SHORTLIST: ['IN_REVIEW', 'INTERVIEW', 'REJECTED_SCREENING'],
  INTERVIEW: ['REJECTED_INTERVIEW', 'OFFERED'],
  OFFERED: ['ACCEPTED'],
  REJECTED_SCREENING: [],
  REJECTED_INTERVIEW: [],
  ACCEPTED: [],
};

export function isApplicationStatus(value: string): value is ApplicationStatus {
  return Object.prototype.hasOwnProperty.call(APPLICATION_STATUSES, value);
}

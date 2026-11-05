export interface Position {
  position_id: string;
  position_code: string;
  title: string;
  job_family?: string;
  org_unit?: string;
  level?: string;
  work_location?: string;
  work_mode?: string;
  employment_type?: string;
  headcount?: number;
  status: 'OPEN' | 'PAUSED' | 'CLOSED';
  created_by: string;
  opened_at?: string;
  closed_at?: string;
  created_at: string;
  updated_at?: string;
}

export interface Criterion {
  criterion_id: string;
  criteria_version_id: string;
  name: string;
  description: string;
  category: 'MUST_HAVE' | 'NICE_TO_HAVE';
  weight_in_group: number;
  expected_evidence_keywords: string[];
  evidence_guidance?: string;
  jd_reference_text?: string;
  display_order: number;
}

export interface CriteriaVersion {
  criteria_version_id: string;
  position_id: string;
  jd_version_id: string;
  version_number: number;
  origin: 'AI_DRAFT' | 'HR_CREATED';
  status: 'DRAFT' | 'PENDING_HR_REVIEW' | 'PENDING_HM_APPROVAL' | 'APPROVED' | 'REJECTED';
  mandatory_weight_total: number;
  nice_to_have_weight_total: number;
  approved_by_hr?: string;
  approved_by_hm?: string;
  approved_by_hr_at?: string;
  approved_by_hm_at?: string;
  created_at: string;
  criteria: Criterion[];
}

export interface Application {
  application_id: string;
  position_id: string;
  source_code: string;
  application_status: string;
  created_at: string;
  updated_at?: string;
}

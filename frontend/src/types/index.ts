export interface JDVersion {
  jd_version_id: string;
  position_id: string;
  version_number: number;
  content_text: string;
  language_code: 'vi' | 'en';
  created_by: string;
  created_at: string;
}

export interface Position {
  position_id: string;
  position_code: string;
  title: string;
  job_family?: string;
  job_family_id?: string | null;
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
  criteria_status?: 'DRAFT' | 'PENDING_HR_REVIEW' | 'PENDING_HM_APPROVAL' | 'APPROVED' | 'REJECTED' | null;
  criteria_approved?: boolean;
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
  origin: 'AI_DRAFT' | 'HR_CREATED' | 'TEMPLATE_CLONE';
  source_template_version_id?: string | null;
  status: 'DRAFT' | 'PENDING_HR_REVIEW' | 'PENDING_HM_APPROVAL' | 'APPROVED' | 'REJECTED';
  mandatory_weight_total: number;
  nice_to_have_weight_total: number;
  approved_by_hr?: string;
  approved_by_hm?: string;
  approved_by_hr_at?: string;
  approved_by_hm_at?: string;
  created_at: string;
  criteria: Criterion[];
  fairness_warnings?: FairnessWarning[];
}

export interface FairnessWarning {
  criterion_id?: string | null;
  name?: string | null;
  attributes: string[];
}

export interface PositionStatusEvent {
  event_id: string;
  position_id: string;
  previous_status?: Position['status'] | null;
  new_status: Position['status'];
  changed_by: string;
  changed_by_name?: string | null;
  reason?: string | null;
  changed_at: string;
}

export interface CriterionInput {
  name: string;
  description: string;
  category: Criterion['category'];
  weight_in_group: number;
  expected_evidence_keywords: string[];
  evidence_guidance?: string | null;
  jd_reference_text?: string | null;
}

export interface Application {
  application_id: string;
  position_id: string;
  source_code: string;
  application_status: string;
  created_at: string;
  updated_at?: string;
}

export interface RankingItem {
  rank_number: number | null;
  application_id: string;
  candidate_name: string;
  matching_status: 'NOT_ASSESSED' | 'NEEDS_HR_VERIFICATION' | 'POSSIBLE_MISMATCH' | 'MEETS_MANDATORY';
  matching_score: number | null;
  evidence_coverage: number | null;
  needs_verification: boolean;
  has_mismatch: boolean;
  file_processing_status?: 'COMPLETED' | 'PROCESSING' | 'NEEDS_HR_REVIEW' | 'UNKNOWN';
  file_error?: string;
  has_duplicate_warning?: boolean;
  is_shortlisted?: boolean;
  application_status?: string;
}

export interface UserSummary {
  user_id: string;
  display_name: string;
  position_roles?: string[];
  system_roles?: string[];
}

export interface EvidenceItem {
  evidence_id: string;
  verbatim_quote: string;
  page_number: number | null;
  verification_status: string | null;
}

export interface CriterionResult {
  criterion_id: string;
  criterion_name: string;
  category: string;
  outcome: 'STRONG_MATCH' | 'MATCH' | 'UNCLEAR' | 'NO_MATCH';
  score: number | null;
  confidence: number | null;
  reasoning: string | null;
  requires_verification: boolean;
  verbatim_quote?: string;
  page_number?: number;
  evidence?: EvidenceItem[];
}

export interface ApplicationWithAssessment {
  application_id: string;
  position_id: string;
  source_code: string;
  application_status: string;
  created_at: string;
  updated_at?: string;
  candidate_name?: string;
  matching_status?: string;
  matching_score?: number | null;
  evidence_coverage?: number | null;
  identity?: {
    display_name?: string;
    email?: string;
    phone?: string;
  };
  latest_assessment?: AssessmentDetail | null;
  file_processing_status?: 'COMPLETED' | 'PROCESSING' | 'NEEDS_HR_REVIEW' | 'UNKNOWN';
  file_error?: string | null;
  has_duplicate_warning?: boolean;
  can_view_cv?: boolean;
  can_view_assessment_evidence?: boolean;
  can_update_status?: boolean;
  can_manage_hr_notes?: boolean;
  documents?: Array<{
    document_id: string;
    document_type: string;
    original_filename: string;
    mime_type?: string;
    page_count?: number;
  }>;
}

export interface AssessmentDetail {
  assessment_id: string;
  position_id: string;
  application_id: string;
  matching_status: string;
  matching_score: number | null;
  evidence_coverage: number | null;
  summary: string | null;
  criterion_results: CriterionResult[];
}

export interface RosterItem {
  roster_id: string;
  position_id: string;
  application_id: string;
  candidate_name: string;
  matching_score: number;
  roster_status: string;
  added_at: string;
  recommended_decision: string;
  hm_notes?: string;
}



// ---------- F2.01 Rubric library ----------
export interface JobFamily {
  job_family_id: string;
  code: string;
  name: string;
  description?: string | null;
  status: 'ACTIVE' | 'INACTIVE';
  display_order: number;
  template_count?: number;
}

export interface RubricTemplateSummary {
  template_id: string;
  job_family_id: string;
  job_family_name: string;
  title: string;
  level_band?: string | null;
  created_by_name?: string | null;
  published_version_id?: string | null;
  published_version_number?: number | null;
  published_at?: string | null;
  published_item_count?: number;
  draft_version_id?: string | null;
  draft_version_number?: number | null;
}

export interface RubricTemplateVersionSummary {
  template_version_id: string;
  version_number: number;
  status: 'DRAFT' | 'PUBLISHED' | 'ARCHIVED';
  mandatory_weight_total: number;
  nice_to_have_weight_total: number;
  change_note?: string | null;
  created_by: string;
  created_by_name?: string | null;
  published_by_name?: string | null;
  published_at?: string | null;
  item_count: number;
}

export interface RubricTemplateDetail extends RubricTemplateSummary {
  versions: RubricTemplateVersionSummary[];
}

export interface TemplateItem {
  template_item_id: string;
  template_version_id: string;
  name: string;
  description: string;
  category: 'MUST_HAVE' | 'NICE_TO_HAVE';
  weight_in_group: number;
  expected_evidence_keywords: string[];
  evidence_guidance?: string | null;
  display_order: number;
}

export interface TemplateItemInput {
  name: string;
  description: string;
  category: 'MUST_HAVE' | 'NICE_TO_HAVE';
  weight_in_group: number;
  expected_evidence_keywords: string[];
  evidence_guidance?: string | null;
}

export interface RubricTemplateVersion extends Omit<RubricTemplateVersionSummary, 'item_count'> {
  template_id: string;
  title: string;
  level_band?: string | null;
  job_family_name: string;
  items: TemplateItem[];
  review_events: Array<{ event_id: string; decision: 'PUBLISH' | 'ARCHIVE' | 'REQUEST_CHANGES'; comment?: string | null; decided_at: string; reviewer_name?: string | null }>;
  fairness_warnings: FairnessWarning[];
  publish_errors: string[];
}

export interface TemplateMatch {
  template_version_id: string;
  template_id: string;
  version_number: number;
  title: string;
  level_band?: string | null;
  job_family_name: string;
  mandatory_weight_total: number;
  nice_to_have_weight_total: number;
  must_have_count: number;
  nice_to_have_count: number;
  family_match: boolean;
  level_match: boolean;
  published_at?: string | null;
}

// ---------- F2.02 Scorecards ----------
export type ScorecardStatus = 'NOT_STARTED' | 'IN_PROGRESS' | 'SUBMITTED';
export type Recommendation = 'STRONG_YES' | 'YES' | 'NO' | 'STRONG_NO';

export interface ScorecardCriterion {
  criterion_id: string;
  name: string;
  description: string;
  category: 'MUST_HAVE' | 'NICE_TO_HAVE';
  weight_in_group: number;
  rating?: number | null;
  evidence_assessment?: 'INSUFFICIENT_EVIDENCE' | null;
  comment?: string | null;
}

export interface Scorecard {
  scorecard_id: string;
  share_id: string;
  position_id: string;
  application_id: string;
  assessment_id?: string | null;
  criteria_version_id?: string | null;
  criteria_version_number?: number | null;
  reviewer_user_id: string;
  reviewer_name?: string | null;
  status: ScorecardStatus;
  overall_recommendation?: Recommendation | null;
  strengths?: string | null;
  concerns?: string | null;
  due_at: string;
  is_overdue: boolean;
  submitted_at?: string | null;
  reopened_at?: string | null;
  reopened_by_name?: string | null;
  reopen_reason?: string | null;
  position_title: string;
  position_code: string;
  candidate_name: string;
  matching_status?: string | null;
  matching_score?: number | null;
  share_status: 'ACTIVE' | 'REVOKED';
  criteria?: ScorecardCriterion[];
  can_edit?: boolean;
  can_reopen?: boolean;
  completion_errors?: string[];
}

export interface ScorecardUpdateInput {
  criteria?: Array<{ criterion_id: string; rating?: number | null; insufficient_evidence?: boolean; comment?: string | null }>;
  overall_recommendation?: Recommendation | null;
  strengths?: string | null;
  concerns?: string | null;
}

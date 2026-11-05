-- Migration 00001: Initial schema for VinUni HRA
-- Creates schemas, core tables for users, positions, criteria, applications, and assessments
-- Uses UUIDs, UTC timestamps, and Row Level Security where applicable

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create schema for private application tables
CREATE SCHEMA IF NOT EXISTS app_private;

-- ========================================
-- 1. USER PROFILES & ROLES
-- ========================================

-- Link Supabase auth users to application profiles
CREATE TABLE app_private.user_profiles (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    preferred_locale TEXT DEFAULT 'vi' CHECK (preferred_locale IN ('vi', 'en')),
    account_status TEXT DEFAULT 'ACTIVE' CHECK (account_status IN ('ACTIVE', 'INACTIVE', 'SUSPENDED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

-- System-wide role assignments (ADMIN, HR_LEAD, VIEWER, etc.)
CREATE TABLE app_private.user_role_assignments (
    assignment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role_code TEXT NOT NULL CHECK (role_code IN ('ADMIN', 'HR_LEAD', 'HR_RECRUITER', 'HIRING_MANAGER', 'VIEWER')),
    granted_by UUID REFERENCES auth.users(id),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    UNIQUE(user_id, role_code)
);

-- Position-specific role assignments (who is recruiter/HM for this requisition)
CREATE TABLE app_private.position_assignments (
    assignment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_id UUID NOT NULL,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    position_role TEXT NOT NULL CHECK (position_role IN ('HR_RECRUITER', 'HIRING_MANAGER', 'HR_LEAD')),
    assigned_by UUID REFERENCES auth.users(id),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    UNIQUE(position_id, user_id, position_role)
);

-- Granular access grants for specific permissions (e.g. confirm deletion)
CREATE TABLE app_private.position_access_grants (
    grant_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_id UUID NOT NULL,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    permission_code TEXT NOT NULL,
    reason TEXT,
    granted_by UUID REFERENCES auth.users(id),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    UNIQUE(position_id, user_id, permission_code)
);

-- ========================================
-- 2. POSITIONS, JD & CRITERIA
-- ========================================

CREATE TABLE app_private.positions (
    position_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    job_family TEXT,
    org_unit TEXT,
    level TEXT,
    work_location TEXT,
    work_mode TEXT,
    employment_type TEXT,
    headcount INTEGER DEFAULT 1 CHECK (headcount >= 1),
    status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'PAUSED', 'CLOSED')),
    created_by UUID NOT NULL REFERENCES auth.users(id),
    opened_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE TABLE app_private.position_status_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_id UUID NOT NULL REFERENCES app_private.positions(position_id) ON DELETE CASCADE,
    previous_status TEXT,
    new_status TEXT NOT NULL,
    changed_by UUID NOT NULL REFERENCES auth.users(id),
    reason TEXT,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- JD Versions
CREATE TABLE app_private.jd_versions (
    jd_version_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_id UUID NOT NULL REFERENCES app_private.positions(position_id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    content_text TEXT NOT NULL,
    language_code TEXT NOT NULL DEFAULT 'en',
    content_hash TEXT,
    created_by UUID NOT NULL REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(position_id, version_number)
);

-- Criteria/Rubric Versions
CREATE TABLE app_private.criteria_versions (
    criteria_version_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_id UUID NOT NULL REFERENCES app_private.positions(position_id) ON DELETE CASCADE,
    jd_version_id UUID NOT NULL REFERENCES app_private.jd_versions(jd_version_id),
    version_number INTEGER NOT NULL,
    origin TEXT NOT NULL DEFAULT 'AI_DRAFT' CHECK (origin IN ('AI_DRAFT', 'HR_CREATED')),
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN (
        'DRAFT', 'PENDING_HR_REVIEW', 'PENDING_HM_APPROVAL', 'APPROVED', 'REJECTED'
    )),
    mandatory_weight_total NUMERIC(5,2) NOT NULL DEFAULT 70.0,
    nice_to_have_weight_total NUMERIC(5,2) NOT NULL DEFAULT 30.0,
    assessment_policy_version TEXT,
    approved_by_hr UUID REFERENCES auth.users(id),
    approved_by_hm UUID REFERENCES auth.users(id),
    approved_by_hr_at TIMESTAMPTZ,
    approved_by_hm_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    UNIQUE(position_id, version_number)
);

-- Individual criteria items
CREATE TABLE app_private.criteria_items (
    criterion_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    criteria_version_id UUID NOT NULL REFERENCES app_private.criteria_versions(criteria_version_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('MUST_HAVE', 'NICE_TO_HAVE')),
    weight_in_group NUMERIC(5,2) NOT NULL CHECK (weight_in_group >= 0 AND weight_in_group <= 100),
    expected_evidence_keywords JSONB DEFAULT '[]'::jsonb,
    evidence_guidance TEXT,
    jd_reference_text TEXT,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Criteria approval audit trail
CREATE TABLE app_private.criteria_approval_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    criteria_version_id UUID NOT NULL REFERENCES app_private.criteria_versions(criteria_version_id) ON DELETE CASCADE,
    reviewed_by UUID NOT NULL REFERENCES auth.users(id),
    reviewer_role TEXT NOT NULL CHECK (reviewer_role IN ('HR_RECRUITER', 'HIRING_MANAGER', 'HR_LEAD')),
    decision TEXT NOT NULL CHECK (decision IN ('APPROVE', 'REJECT', 'REQUEST_CHANGES')),
    comment TEXT,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ========================================
-- 3. CV BATCHES, APPLICATIONS & DOCUMENTS
-- ========================================

-- Async operation tracking
CREATE TABLE app_private.operations (
    operation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    capability TEXT NOT NULL CHECK (capability IN ('CV_PROCESSING', 'CRITERIA_GENERATION', 'ASSESSMENT', 'RANKING', 'DELETION')),
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')),
    requested_by UUID REFERENCES auth.users(id),
    correlation_id UUID DEFAULT uuid_generate_v4(),
    idempotency_key TEXT UNIQUE,
    error_code TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- CV Upload batches
CREATE TABLE app_private.cv_batches (
    batch_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_id UUID NOT NULL REFERENCES app_private.positions(position_id),
    uploaded_by UUID NOT NULL REFERENCES auth.users(id),
    operation_id UUID REFERENCES app_private.operations(operation_id),
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'PARTIALLY_COMPLETED', 'FAILED')),
    total_files INTEGER NOT NULL,
    total_size_bytes BIGINT NOT NULL,
    processed_files INTEGER DEFAULT 0,
    failed_files INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Individual items in a batch
CREATE TABLE app_private.cv_batch_items (
    batch_item_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    batch_id UUID NOT NULL REFERENCES app_private.cv_batches(batch_id) ON DELETE CASCADE,
    original_filename TEXT NOT NULL,
    declared_mime_type TEXT,
    detected_mime_type TEXT,
    size_bytes BIGINT NOT NULL,
    validation_result TEXT,
    error_code TEXT,
    application_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Applications (candidate applications to a position)
CREATE TABLE app_private.applications (
    application_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_id UUID NOT NULL REFERENCES app_private.positions(position_id),
    source_code TEXT NOT NULL DEFAULT 'DIRECT_UPLOAD',
    application_status TEXT NOT NULL DEFAULT 'NEW' CHECK (application_status IN (
        'NEW', 'IN_REVIEW', 'SHORTLIST', 'REJECTED_SCREENING',
        'INTERVIEW', 'REJECTED_INTERVIEW', 'OFFERED', 'ACCEPTED'
    )),
    created_by UUID NOT NULL REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

-- Candidate contact information (no global candidate table in Phase 1)
CREATE TABLE app_private.application_identities (
    identity_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL UNIQUE REFERENCES app_private.applications(application_id) ON DELETE CASCADE,
    display_name TEXT,
    email TEXT,
    phone TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Application status history
CREATE TABLE app_private.application_status_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES app_private.applications(application_id) ON DELETE CASCADE,
    previous_status TEXT,
    new_status TEXT NOT NULL,
    changed_by UUID NOT NULL REFERENCES auth.users(id),
    reason_code TEXT,
    note TEXT,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Application documents (CV files)
CREATE TABLE app_private.application_documents (
    document_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES app_private.applications(application_id) ON DELETE CASCADE,
    document_type TEXT NOT NULL DEFAULT 'CV',
    bucket TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    position_fingerprint TEXT,
    file_processing_status TEXT NOT NULL DEFAULT 'RECEIVED' CHECK (file_processing_status IN (
        'RECEIVED', 'PROCESSING', 'COMPLETED', 'NEEDS_HR_REVIEW', 'ERROR_UNSUPPORTED'
    )),
    processing_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Document processing runs (track OCR/extraction versions)
CREATE TABLE app_private.document_processing_runs (
    run_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES app_private.application_documents(document_id) ON DELETE CASCADE,
    operation_id UUID REFERENCES app_private.operations(operation_id),
    extraction_type TEXT NOT NULL,
    processor_version TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',
    error_code TEXT,
    extracted_text_storage_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Extracted candidate profile versions
CREATE TABLE app_private.profile_versions (
    profile_version_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES app_private.applications(application_id) ON DELETE CASCADE,
    source_document_id UUID NOT NULL REFERENCES app_private.application_documents(document_id),
    version_number INTEGER NOT NULL,
    extraction_config JSONB,
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(application_id, version_number)
);

-- Individual structured facts from candidate profile
CREATE TABLE app_private.profile_facts (
    fact_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    profile_version_id UUID NOT NULL REFERENCES app_private.profile_versions(profile_version_id) ON DELETE CASCADE,
    fact_type TEXT NOT NULL CHECK (fact_type IN (
        'EDUCATION', 'WORK_EXPERIENCE', 'SKILL', 'CERTIFICATION', 'LANGUAGE', 'PROJECT'
    )),
    fact_value JSONB NOT NULL,
    source_page_number INTEGER,
    confidence NUMERIC(3,2)
);

-- Duplicate CV signals within same position
CREATE TABLE app_private.duplicate_signals (
    signal_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_id UUID NOT NULL REFERENCES app_private.positions(position_id),
    application_id_1 UUID NOT NULL REFERENCES app_private.applications(application_id),
    application_id_2 UUID NOT NULL REFERENCES app_private.applications(application_id),
    signal_type TEXT NOT NULL,
    confidence NUMERIC(3,2) NOT NULL,
    detector_version TEXT,
    review_status TEXT DEFAULT 'PENDING' CHECK (review_status IN ('PENDING', 'CONFIRMED_DUPLICATE', 'FALSE_POSITIVE', 'DISMISSED')),
    reviewed_by UUID REFERENCES auth.users(id),
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (application_id_1 != application_id_2)
);

-- ========================================
-- 4. AI ASSESSMENT & RANKING
-- ========================================

-- Assessment policy versions (rubric scoring rules)
CREATE TABLE app_private.assessment_policy_versions (
    policy_version TEXT PRIMARY KEY,
    score_mapping JSONB NOT NULL,
    min_evidence_coverage NUMERIC(3,2) NOT NULL DEFAULT 0.70,
    confidence_thresholds JSONB,
    ranking_rules TEXT,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    approved_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- AI Policy and model configuration
CREATE TABLE app_private.ai_policy_versions (
    policy_version TEXT PRIMARY KEY,
    allowed_providers JSONB NOT NULL,
    data_handling_rules JSONB NOT NULL,
    external_api_allowed BOOLEAN DEFAULT FALSE,
    training_opt_out BOOLEAN DEFAULT TRUE,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    approved_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE app_private.ai_configuration_versions (
    config_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    model_version TEXT,
    deployment_mode TEXT NOT NULL,
    ai_policy_version TEXT REFERENCES app_private.ai_policy_versions(policy_version),
    status TEXT NOT NULL DEFAULT 'DRAFT',
    enabled_at TIMESTAMPTZ,
    disabled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Assessment runs (AI evaluation of one application against approved rubric)
CREATE TABLE app_private.assessment_runs (
    assessment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_id UUID NOT NULL REFERENCES app_private.positions(position_id),
    application_id UUID NOT NULL REFERENCES app_private.applications(application_id),
    jd_version_id UUID NOT NULL REFERENCES app_private.jd_versions(jd_version_id),
    criteria_version_id UUID NOT NULL REFERENCES app_private.criteria_versions(criteria_version_id),
    profile_version_id UUID NOT NULL REFERENCES app_private.profile_versions(profile_version_id),
    policy_version TEXT REFERENCES app_private.assessment_policy_versions(policy_version),
    ai_config_id UUID REFERENCES app_private.ai_configuration_versions(config_id),
    operation_id UUID REFERENCES app_private.operations(operation_id),
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')),
    matching_status TEXT CHECK (matching_status IN (
        'NOT_ASSESSED', 'NEEDS_HR_VERIFICATION', 'POSSIBLE_MISMATCH', 'MEETS_MANDATORY'
    )),
    matching_score NUMERIC(5,1),
    evidence_coverage NUMERIC(3,2),
    confidence NUMERIC(3,2),
    summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Individual criterion assessment results
CREATE TABLE app_private.criterion_assessment_results (
    result_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assessment_id UUID NOT NULL REFERENCES app_private.assessment_runs(assessment_id) ON DELETE CASCADE,
    criterion_id UUID NOT NULL REFERENCES app_private.criteria_items(criterion_id),
    outcome TEXT NOT NULL CHECK (outcome IN ('STRONG_MATCH', 'MATCH', 'UNCLEAR', 'NO_MATCH')),
    score NUMERIC(5,1),
    confidence NUMERIC(3,2),
    confidence_band TEXT,
    requires_hr_verification BOOLEAN DEFAULT FALSE,
    reasoning TEXT,
    UNIQUE(assessment_id, criterion_id)
);

-- Evidence items supporting each criterion result
CREATE TABLE app_private.evidence_items (
    evidence_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    criterion_result_id UUID NOT NULL REFERENCES app_private.criterion_assessment_results(result_id) ON DELETE CASCADE,
    source_document_id UUID NOT NULL REFERENCES app_private.application_documents(document_id),
    verbatim_quote TEXT NOT NULL,
    page_number INTEGER,
    position_in_text INTEGER,
    evidence_type TEXT DEFAULT 'TEXT_QUOTE',
    verification_status TEXT DEFAULT 'PENDING' CHECK (verification_status IN ('PENDING', 'VERIFIED', 'FAILED', 'MANUAL_FIX')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ranking runs (ranked list of applications for a position at a point in time)
CREATE TABLE app_private.ranking_runs (
    ranking_run_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_id UUID NOT NULL REFERENCES app_private.positions(position_id),
    criteria_version_id UUID NOT NULL REFERENCES app_private.criteria_versions(criteria_version_id),
    policy_version TEXT,
    ai_config_id UUID REFERENCES app_private.ai_configuration_versions(config_id),
    operation_id UUID REFERENCES app_private.operations(operation_id),
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Individual items in a ranking
CREATE TABLE app_private.ranking_items (
    ranking_item_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ranking_run_id UUID NOT NULL REFERENCES app_private.ranking_runs(ranking_run_id) ON DELETE CASCADE,
    position_id UUID NOT NULL REFERENCES app_private.positions(position_id),
    application_id UUID NOT NULL REFERENCES app_private.applications(application_id),
    assessment_id UUID REFERENCES app_private.assessment_runs(assessment_id),
    rank_number INTEGER,
    ranking_status TEXT,
    matching_score NUMERIC(5,1),
    evidence_coverage NUMERIC(3,2),
    confidence NUMERIC(3,2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ========================================
-- 5. SHARING & COLLABORATION
-- ========================================

CREATE TABLE app_private.shortlist_shares (
    share_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_id UUID NOT NULL REFERENCES app_private.positions(position_id),
    created_by UUID NOT NULL REFERENCES auth.users(id),
    shared_with UUID NOT NULL REFERENCES auth.users(id),
    note TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'REVOKED')),
    allow_cv_view BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ
);

CREATE TABLE app_private.shortlist_share_items (
    share_item_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    share_id UUID NOT NULL REFERENCES app_private.shortlist_shares(share_id) ON DELETE CASCADE,
    position_id UUID NOT NULL REFERENCES app_private.positions(position_id),
    application_id UUID NOT NULL REFERENCES app_private.applications(application_id),
    assessment_id UUID REFERENCES app_private.assessment_runs(assessment_id),
    ranking_item_id UUID REFERENCES app_private.ranking_items(ranking_item_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE app_private.shortlist_feedback (
    feedback_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    share_id UUID NOT NULL REFERENCES app_private.shortlist_shares(share_id) ON DELETE CASCADE,
    application_id UUID REFERENCES app_private.applications(application_id),
    feedback_from UUID NOT NULL REFERENCES auth.users(id),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ========================================
-- 6. RETENTION & AUDIT
-- ========================================

CREATE TABLE app_private.retention_policy_versions (
    policy_version TEXT PRIMARY KEY,
    retention_months INTEGER NOT NULL DEFAULT 12,
    trigger_event TEXT NOT NULL DEFAULT 'POSITION_CLOSED',
    status TEXT NOT NULL DEFAULT 'DRAFT',
    approved_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE app_private.application_retention_cases (
    retention_case_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES app_private.applications(application_id) ON DELETE CASCADE,
    policy_version TEXT NOT NULL REFERENCES app_private.retention_policy_versions(policy_version),
    position_closed_at TIMESTAMPTZ NOT NULL,
    due_date TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'SCHEDULED_FOR_DELETION', 'DELETED', 'CANCELLED')),
    confirmed_by UUID REFERENCES auth.users(id),
    confirmed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE app_private.deletion_jobs (
    job_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    retention_case_id UUID NOT NULL REFERENCES app_private.application_retention_cases(retention_case_id),
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')),
    files_deleted BOOLEAN DEFAULT FALSE,
    data_deleted BOOLEAN DEFAULT FALSE,
    result_summary JSONB,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE app_private.deletion_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_opaque_id TEXT NOT NULL,
    confirmed_by UUID NOT NULL REFERENCES auth.users(id),
    policy_version TEXT NOT NULL,
    confirmed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    result TEXT NOT NULL
);

CREATE TABLE app_private.audit_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor_user_id UUID REFERENCES auth.users(id),
    action_type TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_id UUID,
    position_id UUID REFERENCES app_private.positions(position_id),
    outcome TEXT,
    correlation_id UUID,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ========================================
-- 7. INDEXES for Performance
-- ========================================

-- Applications
CREATE INDEX idx_applications_position_status ON app_private.applications(position_id, application_status, created_at);

-- Assessments/Ranking
CREATE INDEX idx_assessments_application ON app_private.assessment_runs(application_id, created_at DESC);
CREATE INDEX idx_assessments_position ON app_private.assessment_runs(position_id);
CREATE INDEX idx_ranking_items_run ON app_private.ranking_items(ranking_run_id, rank_number);

-- Positions & Assignments
CREATE INDEX idx_position_assignments_user ON app_private.position_assignments(user_id);
CREATE INDEX idx_positions_status ON app_private.positions(status, created_at DESC);

-- Documents & Processing
CREATE INDEX idx_documents_application ON app_private.application_documents(application_id);
CREATE INDEX idx_documents_status ON app_private.application_documents(file_processing_status);

-- Retention
CREATE INDEX idx_retention_due ON app_private.application_retention_cases(status, due_date);

-- Audit
CREATE INDEX idx_audit_time ON app_private.audit_events(created_at DESC);
CREATE INDEX idx_audit_actor ON app_private.audit_events(actor_user_id, created_at DESC);
CREATE INDEX idx_audit_object ON app_private.audit_events(object_type, object_id);

-- ========================================
-- 8. INITIAL DEFAULT POLICY
-- ========================================

-- Insert default scoring policy
INSERT INTO app_private.assessment_policy_versions (
    policy_version,
    score_mapping,
    min_evidence_coverage,
    confidence_thresholds,
    ranking_rules,
    status
) VALUES (
    'v1.0',
    '{"STRONG_MATCH": 100, "MATCH": 80, "NO_MATCH": 0, "UNCLEAR": null}'::jsonb,
    0.70,
    '{"HIGH": 0.80, "MEDIUM": 0.60, "LOW": 0.0}'::jsonb,
    'Priority 1: Mandatory criteria met; Priority 2: Weighted score; Priority 3: Evidence coverage',
    'APPROVED'
);

-- Insert default retention policy
INSERT INTO app_private.retention_policy_versions (
    policy_version,
    retention_months,
    trigger_event,
    status
) VALUES (
    'v1.0-12month',
    12,
    'POSITION_CLOSED',
    'APPROVED'
);

-- Create Storage buckets (must be done via Supabase dashboard or SQL if available)
-- These are noted here for reference:
-- INSERT INTO storage.buckets (id, name, public) VALUES ('cv-originals', 'cv-originals', false);
-- INSERT INTO storage.buckets (id, name, public) VALUES ('cv-extracted-text', 'cv-extracted-text', false);

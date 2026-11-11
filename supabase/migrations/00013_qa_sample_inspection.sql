-- F2.04 Quality Assurance & Sample Inspection.
--
-- A sample run selects, for one CV batch (one "đợt"), a deterministic 10%
-- random sample plus every high-risk assessment:
--   * SINGLE_MUST_HAVE_FAIL: exactly one MUST_HAVE criterion is NO_MATCH;
--   * COVERAGE_NEAR_THRESHOLD: evidence coverage in [coverage_band_low, coverage_band_high).
-- Random selection uses the smallest sha256(sample_run_id || ':' || application_id),
-- so a run can be re-derived during an audit without storing a random seed.
-- Reviewers (HR_LEAD/ADMIN) mark items PASSED or FLAGGED; flags feed the
-- technical team's rule/prompt regression set through a redacted export.

CREATE TABLE IF NOT EXISTS app_private.qa_sample_runs (
    sample_run_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_id UUID NOT NULL REFERENCES app_private.positions(position_id) ON DELETE CASCADE,
    batch_id UUID REFERENCES app_private.cv_batches(batch_id) ON DELETE SET NULL,
    criteria_version_id UUID REFERENCES app_private.criteria_versions(criteria_version_id) ON DELETE SET NULL,
    trigger_type TEXT NOT NULL CHECK (trigger_type IN ('AUTO', 'MANUAL')),
    sampling_rules_version TEXT NOT NULL,
    random_rate NUMERIC(4,3) NOT NULL CHECK (random_rate > 0 AND random_rate <= 1),
    coverage_band_low NUMERIC(3,2) NOT NULL,
    coverage_band_high NUMERIC(3,2) NOT NULL,
    population_size INTEGER NOT NULL CHECK (population_size >= 0),
    sample_size INTEGER NOT NULL CHECK (sample_size >= 0),
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (coverage_band_low < coverage_band_high)
);

-- At most one automatic run per batch and rubric version.
CREATE UNIQUE INDEX IF NOT EXISTS uq_qa_sample_runs_auto_batch
    ON app_private.qa_sample_runs (batch_id, criteria_version_id)
    WHERE trigger_type = 'AUTO';
CREATE INDEX IF NOT EXISTS idx_qa_sample_runs_position
    ON app_private.qa_sample_runs (position_id, created_at DESC);

CREATE TABLE IF NOT EXISTS app_private.qa_sample_items (
    sample_item_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sample_run_id UUID NOT NULL REFERENCES app_private.qa_sample_runs(sample_run_id) ON DELETE CASCADE,
    application_id UUID NOT NULL REFERENCES app_private.applications(application_id) ON DELETE CASCADE,
    assessment_id UUID NOT NULL REFERENCES app_private.assessment_runs(assessment_id) ON DELETE CASCADE,
    reasons TEXT[] NOT NULL CHECK (
        cardinality(reasons) > 0
        AND reasons <@ ARRAY['RANDOM', 'SINGLE_MUST_HAVE_FAIL', 'COVERAGE_NEAR_THRESHOLD']::TEXT[]
    ),
    selection_sha256 TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PASSED', 'FLAGGED')),
    reviewer_id UUID REFERENCES auth.users(id),
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (sample_run_id, application_id)
);

CREATE INDEX IF NOT EXISTS idx_qa_sample_items_status
    ON app_private.qa_sample_items (status, created_at);
CREATE INDEX IF NOT EXISTS idx_qa_sample_items_application
    ON app_private.qa_sample_items (application_id);

CREATE TABLE IF NOT EXISTS app_private.qa_flags (
    flag_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sample_item_id UUID NOT NULL REFERENCES app_private.qa_sample_items(sample_item_id) ON DELETE CASCADE,
    criterion_result_id UUID REFERENCES app_private.criterion_assessment_results(result_id) ON DELETE CASCADE,
    evidence_id UUID REFERENCES app_private.evidence_items(evidence_id) ON DELETE CASCADE,
    flag_type TEXT NOT NULL CHECK (flag_type IN ('INCORRECT_EVIDENCE', 'MISSED_CONTENT', 'OCR_ERROR')),
    expected_outcome TEXT CHECK (expected_outcome IN ('STRONG_MATCH', 'MATCH', 'UNCLEAR', 'NO_MATCH')),
    note TEXT CHECK (note IS NULL OR char_length(note) <= 2000),
    created_by UUID NOT NULL REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    exported_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_qa_flags_item ON app_private.qa_flags (sample_item_id);
CREATE INDEX IF NOT EXISTS idx_qa_flags_export ON app_private.qa_flags (exported_at, created_at);

COMMENT ON TABLE app_private.qa_sample_runs IS
    'F2.04 sample runs: deterministic sha256 random sample plus all high-risk assessments for one CV batch.';
COMMENT ON TABLE app_private.qa_flags IS
    'F2.04 reviewer flags. Notes are HR-authored and may contain candidate context; export only through scripts/export_qa_flags.py.';

ALTER TABLE app_private.qa_sample_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_private.qa_sample_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_private.qa_flags ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON app_private.qa_sample_runs, app_private.qa_sample_items, app_private.qa_flags
    FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT ON app_private.qa_sample_runs TO service_role;
GRANT SELECT, INSERT, UPDATE ON app_private.qa_sample_items TO service_role;
GRANT SELECT, INSERT, UPDATE ON app_private.qa_flags TO service_role;
GRANT DELETE ON app_private.qa_sample_runs, app_private.qa_sample_items, app_private.qa_flags TO service_role;

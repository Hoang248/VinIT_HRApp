-- Migration 00002: Audit fixes - indexes, RLS policies for operations tables

-- Add missing indexes for operation polling performance
CREATE INDEX IF NOT EXISTS idx_operations_status_created
ON app_private.operations(status, created_at)
WHERE status = 'PENDING';

CREATE INDEX IF NOT EXISTS idx_cv_batches_operation
ON app_private.cv_batches(operation_id);

CREATE INDEX IF NOT EXISTS idx_assessment_status_completed
ON app_private.assessment_runs(position_id, status, completed_at DESC);

-- Enable RLS on operations tables
ALTER TABLE app_private.operations ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_private.cv_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_private.cv_batch_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_private.document_processing_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_private.profile_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_private.profile_facts ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_private.ranking_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_private.ranking_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_private.duplicate_signals ENABLE ROW LEVEL SECURITY;

-- RLS Policies for operations
CREATE POLICY operations_select ON app_private.operations
    FOR SELECT USING (
        requested_by = auth.uid()
        OR EXISTS (
            SELECT 1 FROM app_private.user_role_assignments ur
            WHERE ur.user_id = auth.uid() AND ur.revoked_at IS NULL AND ur.role_code IN ('ADMIN', 'HR_LEAD')
        )
    );

-- HR can create/view batches for positions they have access to
CREATE POLICY batches_select ON app_private.cv_batches
    FOR SELECT USING (
        app_private.has_position_access(position_id, ARRAY['HR_RECRUITER', 'HIRING_MANAGER', 'HR_LEAD'])
    );

CREATE POLICY batches_insert ON app_private.cv_batches
    FOR INSERT WITH CHECK (
        app_private.has_position_access(position_id, ARRAY['HR_RECRUITER'])
        AND uploaded_by = auth.uid()
    );

CREATE POLICY batch_items_select ON app_private.cv_batch_items
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM app_private.cv_batches b
            WHERE b.batch_id = cv_batch_items.batch_id
            AND app_private.has_position_access(b.position_id, NULL)
        )
    );

CREATE POLICY doc_runs_select ON app_private.document_processing_runs
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM app_private.application_documents d
            JOIN app_private.applications a ON a.application_id = d.application_id
            WHERE d.document_id = document_processing_runs.document_id
            AND app_private.has_position_access(a.position_id, NULL)
        )
    );

CREATE POLICY profile_select ON app_private.profile_versions
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM app_private.applications a
            WHERE a.application_id = profile_versions.application_id
            AND app_private.has_position_access(a.position_id, NULL)
        )
    );

CREATE POLICY profile_facts_select ON app_private.profile_facts
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM app_private.profile_versions pv
            JOIN app_private.applications a ON a.application_id = pv.application_id
            WHERE pv.profile_version_id = profile_facts.profile_version_id
            AND app_private.has_position_access(a.position_id, NULL)
        )
    );

CREATE POLICY ranking_runs_select ON app_private.ranking_runs
    FOR SELECT USING (
        app_private.has_position_access(position_id, NULL)
    );

CREATE POLICY ranking_items_select ON app_private.ranking_items
    FOR SELECT USING (
        app_private.has_position_access(position_id, NULL)
    );

CREATE POLICY duplicate_signals_select ON app_private.duplicate_signals
    FOR SELECT USING (
        app_private.has_position_access(position_id, ARRAY['HR_RECRUITER', 'HR_LEAD'])
    );

-- Create local storage directory for development
-- This is noted here but must be created on the server filesystem

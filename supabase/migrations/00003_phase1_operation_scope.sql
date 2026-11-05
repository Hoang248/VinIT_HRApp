-- Associate background work with its own position. Never infer a position from
-- the newest batch or some other user's completed assessment.
ALTER TABLE app_private.operations
    ADD COLUMN IF NOT EXISTS position_id UUID REFERENCES app_private.positions(position_id);

-- Backfill operations where there is an unambiguous existing relationship.
UPDATE app_private.operations op SET position_id = b.position_id
FROM app_private.cv_batches b
WHERE b.operation_id = op.operation_id AND op.position_id IS NULL;
UPDATE app_private.operations op SET position_id = r.position_id
FROM app_private.ranking_runs r
WHERE r.operation_id = op.operation_id AND op.position_id IS NULL;
UPDATE app_private.operations op SET position_id = a.position_id
FROM app_private.assessment_runs a
WHERE a.operation_id = op.operation_id AND op.position_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_operations_position_status
    ON app_private.operations(position_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_duplicate_signals_application_1
    ON app_private.duplicate_signals(position_id, application_id_1) WHERE review_status = 'PENDING';
CREATE INDEX IF NOT EXISTS idx_duplicate_signals_application_2
    ON app_private.duplicate_signals(position_id, application_id_2) WHERE review_status = 'PENDING';

-- The backend's service-role PostgREST client accesses public views over the
-- private tables. Make a clean migration reproducible, and refresh the view of
-- operations so the new column is included. Never expose these views to anon
-- or authenticated clients: the backend enforces position-level permissions.
-- Browser clients must not bypass the backend's position, approval and CV
-- checks via exposed private tables/functions, even if older deployments
-- granted authenticated direct access. The service role is backend-only.
REVOKE ALL ON ALL TABLES IN SCHEMA app_private FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA app_private FROM PUBLIC, anon, authenticated;
REVOKE USAGE ON SCHEMA app_private FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA app_private TO service_role;
GRANT ALL ON ALL TABLES IN SCHEMA app_private TO service_role;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA app_private TO service_role;
DO $$
DECLARE tbl record; existing_kind "char";
BEGIN
    FOR tbl IN SELECT tablename FROM pg_tables WHERE schemaname = 'app_private' LOOP
        SELECT c.relkind INTO existing_kind FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relname = tbl.tablename;
        IF existing_kind IS NULL OR existing_kind = 'v' THEN
            EXECUTE format('CREATE OR REPLACE VIEW public.%I WITH (security_invoker=true) AS SELECT * FROM app_private.%I', tbl.tablename, tbl.tablename);
            EXECUTE format('REVOKE ALL ON public.%I FROM PUBLIC, anon, authenticated', tbl.tablename);
            EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO service_role', tbl.tablename);
        END IF;
        existing_kind := NULL;
    END LOOP;
END $$;

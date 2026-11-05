-- Stop/drain every pre-00004 worker before deploying this migration and the
-- fenced worker. Old workers do not acquire the advisory locks used below.
ALTER TABLE app_private.operations
    ADD COLUMN IF NOT EXISTS worker_token UUID,
    ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS recovery_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS attempt_started_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_operations_worker_queue
    ON app_private.operations(status, created_at)
    WHERE status IN ('PENDING', 'PROCESSING') AND capability IN ('CV_PROCESSING', 'ASSESSMENT', 'RANKING');

-- The backend still owns authorization. The view is not browser-readable.
CREATE OR REPLACE VIEW public.operations WITH (security_invoker=true) AS SELECT * FROM app_private.operations;
REVOKE ALL ON public.operations FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.operations TO service_role;

-- One row per actual recovery, committed atomically with the new claim. This
-- makes the trailing-24-hour metric accurate even after multiple attempts.
CREATE TABLE IF NOT EXISTS app_private.operation_recovery_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    operation_id UUID NOT NULL REFERENCES app_private.operations(operation_id) ON DELETE CASCADE,
    recovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_operation_recovery_events_time
    ON app_private.operation_recovery_events(recovered_at);
ALTER TABLE app_private.operation_recovery_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON app_private.operation_recovery_events FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT ON app_private.operation_recovery_events TO service_role;

-- Runtime versions contain no credentials. Runtime choices remain bounded by
-- an operator-controlled environment allowlist and network egress policy.
ALTER TABLE app_private.ai_configuration_versions
    ADD COLUMN IF NOT EXISTS api_base TEXT,
    ADD COLUMN IF NOT EXISTS temperature_default NUMERIC(3,2),
    ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES auth.users(id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_ai_configuration
    ON app_private.ai_configuration_versions ((status)) WHERE status = 'ACTIVE';
ALTER TABLE app_private.operations
    ADD COLUMN IF NOT EXISTS ai_config_id UUID REFERENCES app_private.ai_configuration_versions(config_id),
    ADD COLUMN IF NOT EXISTS ai_config_snapshot JSONB;

CREATE OR REPLACE VIEW public.ai_configuration_versions WITH (security_invoker=true) AS SELECT * FROM app_private.ai_configuration_versions;
REVOKE ALL ON public.ai_configuration_versions FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.ai_configuration_versions TO service_role;
CREATE OR REPLACE VIEW public.operations WITH (security_invoker=true) AS SELECT * FROM app_private.operations;
REVOKE ALL ON public.operations FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.operations TO service_role;

-- HR-only append-only notes are intentionally not exposed as a public view.
CREATE TABLE IF NOT EXISTS app_private.application_private_notes (
    note_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES app_private.applications(application_id) ON DELETE CASCADE,
    created_by UUID NOT NULL REFERENCES auth.users(id),
    content TEXT NOT NULL CHECK (char_length(content) BETWEEN 1 AND 5000),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_private_notes_application ON app_private.application_private_notes(application_id, created_at DESC);
ALTER TABLE app_private.application_private_notes ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON app_private.application_private_notes FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT ON app_private.application_private_notes TO service_role;

ALTER TABLE app_private.profile_versions ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES auth.users(id);
CREATE OR REPLACE VIEW public.profile_versions WITH (security_invoker=true) AS SELECT * FROM app_private.profile_versions;
REVOKE ALL ON public.profile_versions FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.profile_versions TO service_role;

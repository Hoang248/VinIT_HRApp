-- Account provisioning requires a durable, one-way bootstrap marker. Do not
-- reset this marker when an administrator is disabled, revoked or deleted.
-- Back up and review existing roles/position assignments before applying.
CREATE TABLE app_private.account_initialization (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    initialized_at TIMESTAMPTZ,
    initialized_by UUID
);
ALTER TABLE app_private.account_initialization ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON app_private.account_initialization FROM PUBLIC, anon, authenticated;
GRANT SELECT, UPDATE ON app_private.account_initialization TO service_role;

-- Any existing ADMIN assignment, including a revoked one, closes setup.
-- A historical admin who was deleted before this migration may not be
-- detectable; review the Auth/role history before enabling bootstrap.
INSERT INTO app_private.account_initialization (singleton, initialized_at, initialized_by)
SELECT TRUE,
       CASE WHEN existing.user_id IS NOT NULL THEN NOW() ELSE NULL END,
       existing.user_id
FROM (SELECT 1) AS one
LEFT JOIN LATERAL (
    SELECT user_id FROM app_private.user_role_assignments
    WHERE role_code = 'ADMIN' ORDER BY granted_at LIMIT 1
) AS existing ON TRUE;

-- Also close setup when an ADMIN is provisioned outside the bootstrap route.
-- initialized_by deliberately has no cascading FK: deleting a user must never
-- reopen setup. Only a privileged DBA can intentionally reset this table.
CREATE FUNCTION app_private.mark_admin_initialized() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, app_private AS $$
BEGIN
    UPDATE app_private.account_initialization
       SET initialized_at = COALESCE(initialized_at, NOW()),
           initialized_by = COALESCE(initialized_by, NEW.user_id)
     WHERE singleton = TRUE;
    RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION app_private.mark_admin_initialized() FROM PUBLIC, anon, authenticated;
CREATE TRIGGER mark_admin_initialized
AFTER INSERT OR UPDATE OF role_code ON app_private.user_role_assignments
FOR EACH ROW WHEN (NEW.role_code = 'ADMIN')
EXECUTE FUNCTION app_private.mark_admin_initialized();

-- Temporary passwords created by an ADMIN cannot access business endpoints
-- until the owner changes the password. tokens_valid_after prevents an older
-- app access token becoming valid again after password/status changes.
ALTER TABLE app_private.user_profiles
    ADD COLUMN must_change_password BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN tokens_valid_after TIMESTAMPTZ;

-- Preserve discoverability for existing position HMs, without restoring any
-- system role explicitly revoked in the past. HR_LEAD is NOT backfilled: the
-- global role has broader access than a position-specific HR_LEAD assignment.
INSERT INTO app_private.user_role_assignments (user_id, role_code)
SELECT DISTINCT user_id, 'HIRING_MANAGER'
FROM app_private.position_assignments
WHERE position_role = 'HIRING_MANAGER' AND revoked_at IS NULL
ON CONFLICT (user_id, role_code) DO NOTHING;

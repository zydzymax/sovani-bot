-- BI Read-only User Setup
--
-- This script creates a read-only database user for BI tools (Power BI, Metabase, etc.)
--
-- Usage:
--   psql -U postgres -d sovani -f deploy/sql/bi_readonly.sql
--
-- SECURITY NOTE:
--   - Set a strong password in production (replace '***set_in_ops***')
--   - Store password in secrets manager (not in git)
--   - Rotate credentials quarterly
--   - Monitor access via pg_stat_statements

-- Create read-only role if not exists
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'bi_reader') THEN
    -- Create role with login capability
    CREATE ROLE bi_reader LOGIN PASSWORD '***set_in_ops***';

    RAISE NOTICE 'Created role: bi_reader';
    RAISE NOTICE 'IMPORTANT: Change password in production!';
  ELSE
    RAISE NOTICE 'Role bi_reader already exists';
  END IF;
END$$;

-- Grant connection to database
GRANT CONNECT ON DATABASE sovani TO bi_reader;

-- Grant schema usage
GRANT USAGE ON SCHEMA public TO bi_reader;

-- Grant SELECT on all existing tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO bi_reader;

-- Grant SELECT on all existing sequences (for id columns)
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO bi_reader;

-- Automatically grant SELECT on future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO bi_reader;

-- Revoke write permissions (safety check)
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM bi_reader;

-- Verify permissions
DO $$
DECLARE
    table_count INTEGER;
    view_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE';

    SELECT COUNT(*) INTO view_count
    FROM information_schema.views
    WHERE table_schema = 'public';

    RAISE NOTICE 'Granted SELECT access to:';
    RAISE NOTICE '  - % tables', table_count;
    RAISE NOTICE '  - % views', view_count;
END$$;

-- Create read-only user configuration
COMMENT ON ROLE bi_reader IS 'Read-only access for BI tools (Power BI, Metabase, Tableau, etc.)';

-- Performance: Set work_mem for BI queries (optional, adjust based on workload)
ALTER ROLE bi_reader SET work_mem = '32MB';

-- Timeout: Prevent long-running queries from blocking (optional)
ALTER ROLE bi_reader SET statement_timeout = '300000';  -- 5 minutes

-- Show final grants
\echo
\echo '=== BI Reader Permissions ==='
\echo
SELECT
    grantee,
    table_schema,
    table_name,
    privilege_type
FROM information_schema.role_table_grants
WHERE grantee = 'bi_reader'
    AND table_schema = 'public'
ORDER BY table_name, privilege_type;

\echo
\echo '=== Connection String ==='
\echo 'Host: <your-database-host>'
\echo 'Port: 5432'
\echo 'Database: sovani'
\echo 'User: bi_reader'
\echo 'Password: ***set_in_ops***'
\echo 'SSL Mode: require'
\echo
\echo '!!! IMPORTANT: Update password before deploying to production !!!'
\echo

-- Production checklist:
-- [ ] Change default password
-- [ ] Test connection from BI tool
-- [ ] Configure SSL/TLS
-- [ ] Set up firewall rules (allow BI server IP only)
-- [ ] Enable pg_stat_statements for query monitoring
-- [ ] Document credentials in secrets vault

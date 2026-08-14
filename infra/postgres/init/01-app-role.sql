-- Runs once, as the cluster superuser, on first container start.
--
-- Creates the least-privileged runtime role. Migrations run as the owner (POSTGRES_USER);
-- the API and workers connect as demarc_app, which is not the table owner and has no
-- BYPASSRLS, so row-level security actually applies to it. See docs/adr/0001.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'demarc_app') THEN
        CREATE ROLE demarc_app LOGIN PASSWORD 'demarc_app' NOBYPASSRLS;
    END IF;
END
$$;

GRANT CONNECT ON DATABASE demarc TO demarc_app;
GRANT USAGE ON SCHEMA public TO demarc_app;

-- Table-level grants are issued per table by the migrations, so a new table is
-- unreachable until someone deliberately grants access to it.

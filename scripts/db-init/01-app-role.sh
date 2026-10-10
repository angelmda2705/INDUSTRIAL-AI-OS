#!/usr/bin/env bash
# Runs once, when the PostgreSQL volume is first initialized (docker-entrypoint-initdb.d).
# Creates the non-superuser application role that owns the schema. Row-level
# security is FORCEd by the migrations, so it applies to this role.
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v app_password="$IIOS_DB_APP_PASSWORD" -v dbname="$POSTGRES_DB" <<'SQL'
CREATE ROLE iios_app LOGIN PASSWORD :'app_password' NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB;
ALTER DATABASE :"dbname" OWNER TO iios_app;
ALTER SCHEMA public OWNER TO iios_app;
SQL

#!/usr/bin/env bash
# Backup of the PostgreSQL database and the file storage (uploads + reports).
#
# Usage:  IIOS_BACKUP_DATABASE_URL=postgresql://admin:...@host:5432/iios \
#         IIOS_STORAGE_DIR=/var/lib/iios/storage scripts/backup.sh [output_dir]
#
# IIOS_BACKUP_DATABASE_URL must use a role with BYPASSRLS (or a superuser):
# tenant tables have FORCE ROW LEVEL SECURITY, so the application role cannot
# read every organization's rows (by design). See docs/DEPLOYMENT.md.
set -euo pipefail

DB_URL="${IIOS_BACKUP_DATABASE_URL:?Set IIOS_BACKUP_DATABASE_URL (role with BYPASSRLS)}"
DB_URL="${DB_URL/postgresql+psycopg:/postgresql:}"
STORAGE_DIR="${IIOS_STORAGE_DIR:-backend/data/storage}"
OUT_ROOT="${1:-backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${OUT_ROOT}/${STAMP}"

mkdir -p "$OUT"
umask 077

echo "→ Base de datos"
pg_dump --format=custom --file "$OUT/database.dump" "$DB_URL"

echo "→ Archivos ($STORAGE_DIR)"
if [ -d "$STORAGE_DIR" ]; then
  tar -czf "$OUT/storage.tar.gz" -C "$STORAGE_DIR" .
else
  echo "  (no existe; se omite)"
fi

( cd "$OUT" && sha256sum ./* > SHA256SUMS )
echo "Respaldo completo en $OUT"

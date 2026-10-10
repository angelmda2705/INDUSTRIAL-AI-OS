#!/usr/bin/env bash
# Restore a backup created by scripts/backup.sh.
#
# Usage:  IIOS_RESTORE_DATABASE_URL=postgresql://admin:...@host:5432/iios_restored \
#         IIOS_STORAGE_DIR=/var/lib/iios/storage scripts/restore.sh backups/20250101T000000Z
#
# * The target database must exist and be EMPTY, and the application role
#   (owner of the objects in the dump) must already exist in the cluster.
# * IIOS_RESTORE_DATABASE_URL must use a superuser or a role with BYPASSRLS:
#   loading data into tables with FORCE ROW LEVEL SECURITY is otherwise refused.
# * Stop the application while restoring.
set -euo pipefail

DIR="${1:?Indica el directorio del respaldo}"
DB_URL="${IIOS_RESTORE_DATABASE_URL:?Set IIOS_RESTORE_DATABASE_URL}"
DB_URL="${DB_URL/postgresql+psycopg:/postgresql:}"
STORAGE_DIR="${IIOS_STORAGE_DIR:-backend/data/storage}"

echo "→ Verificando sumas SHA-256"
( cd "$DIR" && sha256sum --check --quiet SHA256SUMS )

echo "→ Restaurando base de datos"
pg_restore --exit-on-error --dbname "$DB_URL" "$DIR/database.dump"

if [ -f "$DIR/storage.tar.gz" ]; then
  echo "→ Restaurando archivos en $STORAGE_DIR"
  mkdir -p "$STORAGE_DIR"
  tar -xzf "$DIR/storage.tar.gz" -C "$STORAGE_DIR"
fi
echo "Restauración completa. Verifica con: python -m app.cli migrate (debe indicar que no hay cambios) y GET /api/v1/system/health"

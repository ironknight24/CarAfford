#!/usr/bin/env bash
# =============================================================================
# CarAfford PostgreSQL Database Restore Script
# Restores the PostgreSQL database from a compressed .sql.gz dump.
# =============================================================================

set -eo pipefail

if [ -z "$1" ]; then
    echo "❌ Usage: $0 <path_to_backup.sql.gz>"
    exit 1
fi

BACKUP_FILE="$1"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-carafford_postgres}"
POSTGRES_DB="${POSTGRES_DB:-carafford_db}"
POSTGRES_USER="${POSTGRES_USER:-carafford_user}"

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "❌ Backup file '${BACKUP_FILE}' not found!"
    exit 1
fi

echo "⚠️  Starting PostgreSQL restore to database '${POSTGRES_DB}' from '${BACKUP_FILE}'..."
gunzip -c "${BACKUP_FILE}" | docker exec -i "${POSTGRES_CONTAINER}" psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}"

echo "✅ Database restored successfully from ${BACKUP_FILE}!"

#!/usr/bin/env bash
# =============================================================================
# CarAfford PostgreSQL Database Backup Script
# Creates a compressed, timestamped dump of the PostgreSQL database.
# =============================================================================

set -eo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-carafford_postgres}"
POSTGRES_DB="${POSTGRES_DB:-carafford_db}"
POSTGRES_USER="${POSTGRES_USER:-carafford_user}"
BACKUP_FILE="${BACKUP_DIR}/carafford_backup_${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

echo "📦 Starting PostgreSQL backup for database '${POSTGRES_DB}'..."
docker exec -t "${POSTGRES_CONTAINER}" pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" --clean --if-exists | gzip > "${BACKUP_FILE}"

FILESIZE="$(ls -lh "${BACKUP_FILE}" | awk '{print $5}')"
echo "✅ Database backup created successfully!"
echo "📁 File: ${BACKUP_FILE} (${FILESIZE})"

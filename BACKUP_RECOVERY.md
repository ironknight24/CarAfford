# CarAfford Database Backup & Disaster Recovery Runbook

This runbook outlines automated and manual procedures for backing up and restoring PostgreSQL databases within the **CarAfford** ecosystem.

---

## 1. Automated Database Backups

CarAfford provides an automated backup script in `scripts/backup_db.sh`. It performs full SQL dumps with compression and timestamping.

### Manual Execution

```bash
# Execute local database backup
./scripts/backup_db.sh

# Target a specific container / host
TARGET_CONTAINER=carafford_postgres ./scripts/backup_db.sh
```

### Backup Artifacts
- **Directory**: `backups/`
- **Naming Pattern**: `carafford_backup_YYYYMMDD_HHMMSS.sql.gz`
- **Retention**: Script automatically retains the most recent 30 backup snapshots and prunes older archives.

---

## 2. Scheduled Cron Backups

To establish automated daily backups at 02:00 UTC, add a crontab entry on the host:

```bash
# Add to crontab (crontab -e)
0 2 * * * cd /opt/carafford && ./scripts/backup_db.sh >> /var/log/carafford_backup.log 2>&1
```

---

## 3. Database Restoration & Disaster Recovery

To restore a database from a previously generated backup archive:

```bash
# Execute restoration
./scripts/restore_db.sh backups/carafford_backup_YYYYMMDD_HHMMSS.sql.gz
```

### Safety Confirmations
The restore script requires explicit confirmation (`Type 'RESTORE' to proceed`) before terminating active connections, dropping existing tables, and restoring the database state.

---

## 4. Recovery Time Objective (RTO) & Recovery Point Objective (RPO)

- **Target RPO**: 24 hours (Daily automated snapshots) / Real-time with WAL archiving.
- **Target RTO**: < 5 minutes to restore a standard database snapshot.

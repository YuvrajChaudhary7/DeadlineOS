# Backup and restore

DeadlineOS backups include the database and local uploaded files in one checksummed ZIP archive. Backups can contain student submissions and personal information. Keep them outside Git, restrict access, encrypt storage, and follow the institution's retention rules.

## Create a backup

1. Copy `.env.example` to `.env` and configure `DATABASE_URL` for the database to back up.
2. Stop application writes during the backup for a consistent database/files snapshot.
3. Run from the repository root:

   ```powershell
   .\.venv\Scripts\python.exe scripts\backup.py
   ```

The default archive is saved under `backups/`, which Git ignores. Pass `--output D:\safe-backups\deadlineos.zip` to choose a different location. PostgreSQL backups need the PostgreSQL client tools (`pg_dump`); restores need `pg_restore`. Credentials are read from the database URL through `PGPASSWORD`, not printed as command-line arguments.

## Restore a backup

Restore is intentionally explicit. Stop the application and confirm the target database and upload directory before proceeding. Existing non-empty targets are refused unless `--overwrite` is supplied.

```powershell
.\.venv\Scripts\python.exe scripts\restore.py .\backups\deadlineos-20261124T120000Z.zip --confirm-restore
```

To replace existing data:

```powershell
.\.venv\Scripts\python.exe scripts\restore.py .\backups\deadlineos-20261124T120000Z.zip --overwrite --confirm-restore
```

Restore validates every file hash before changing the target. SQLite archives also pass `PRAGMA integrity_check`. Existing SQLite DBs and upload directories are copied beside their targets with a `.pre-restore-<UTC timestamp>` suffix before replacement. PostgreSQL restore requires an empty database unless `--overwrite` is given; overwrite creates a sibling safety dump before applying the archive. Database restore and filesystem replacement cannot be one atomic transaction, so keep the application stopped and retain the source backup until the app has been checked.

## Azure deployment

The GitHub deployment workflow only updates a configured Azure Container App. Configure scheduled database backups and persistent upload storage separately in Azure. The repository workflow does not enable Azure Database backups or Azure Files snapshots for you. See [GitHub Actions deployment setup](deployment/github-actions-azure.md).

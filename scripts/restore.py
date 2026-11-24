"""Restore a verified archive; destructive actions require an explicit confirmation flag."""
import argparse
import os
from pathlib import Path
from dotenv import load_dotenv

from backup_restore import DEFAULT_UPLOADS, restore_backup
from backup_restore import ROOT


def main():
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--database", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--uploads", type=Path, default=DEFAULT_UPLOADS)
    parser.add_argument("--overwrite", action="store_true", help="replace existing data after saving a local safety copy")
    parser.add_argument("--confirm-restore", action="store_true", help="required acknowledgement; stop the app before restoring")
    args = parser.parse_args()
    if not args.database: parser.error("set DATABASE_URL or pass --database")
    if not args.confirm_restore: parser.error("stopping the app and reviewing the target are required; pass --confirm-restore to continue")
    result = restore_backup(args.archive, args.database, args.uploads, overwrite=args.overwrite)
    print(f"Restored verified {result['database_type']} backup from {result['created_at']}")


if __name__ == "__main__": main()

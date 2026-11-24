"""Create a database and uploads archive using DATABASE_URL."""
import argparse
import os
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

from backup_restore import DEFAULT_UPLOADS, create_backup
from backup_restore import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="archive path (defaults to backups/deadlineos-UTCSTAMP.zip)")
    parser.add_argument("--uploads", type=Path, default=DEFAULT_UPLOADS)
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    url = os.getenv("DATABASE_URL")
    if not url: parser.error("DATABASE_URL must be set")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or Path("backups") / f"deadlineos-{stamp}.zip"
    result = create_backup(url, args.uploads, output)
    print(f"Backup written and checksummed: {result}")


if __name__ == "__main__": main()

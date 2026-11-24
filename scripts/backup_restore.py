"""Verified, portable SQLite/PostgreSQL plus upload-directory backups."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import subprocess
from contextlib import closing
import stat
import tempfile
from urllib.parse import unquote
import zipfile

from sqlalchemy.engine import make_url


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UPLOADS = ROOT / "backend" / "instance" / "uploads"


def _database(url):
    parsed = make_url(url)
    if parsed.drivername.startswith("sqlite"):
        if not parsed.database or parsed.database == ":memory:":
            raise ValueError("A file-backed SQLite database is required for backup and restore")
        path = Path(unquote(parsed.database))
        if not path.is_absolute():
            path = ROOT / "backend" / "instance" / path
        return "sqlite", parsed, path
    if parsed.drivername.startswith("postgresql"):
        return "postgresql", parsed, None
    raise ValueError("Only SQLite and PostgreSQL database URLs are supported")


def _pg_environment(parsed):
    environment = os.environ.copy()
    if parsed.password is not None: environment["PGPASSWORD"] = parsed.password
    for key, value in (("PGHOST", parsed.host), ("PGPORT", parsed.port), ("PGUSER", parsed.username), ("PGDATABASE", parsed.database)):
        if value is not None: environment[key] = str(value)
    for key, value in (parsed.query or {}).items():
        if key == "sslmode": environment["PGSSLMODE"] = value
    return environment


def _pg_args(parsed):
    args = []
    for flag, value in (("--host", parsed.host), ("--port", parsed.port), ("--username", parsed.username), ("--dbname", parsed.database)):
        if value is not None: args.extend((flag, str(value)))
    return args


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()


def _dump_database(kind, parsed, sqlite_path, target):
    if kind == "sqlite":
        if not sqlite_path.is_file(): raise FileNotFoundError(f"SQLite database not found: {sqlite_path}")
        with closing(sqlite3.connect(sqlite_path)) as source, closing(sqlite3.connect(target)) as destination:
            source.backup(destination)
            destination.commit()
        return
    subprocess.run(["pg_dump", *_pg_args(parsed), "--format=custom", "--no-owner", "--no-acl", "--file", str(target)],
                   env=_pg_environment(parsed), check=True)


def create_backup(database_url, uploads_dir, output_path):
    kind, parsed, sqlite_path = _database(database_url)
    uploads = Path(uploads_dir)
    if uploads.is_symlink() or (uploads.exists() and not uploads.is_dir()): raise ValueError("The uploads source must be a normal directory")
    uploads = uploads.resolve()
    output = Path(output_path).resolve()
    if kind == "sqlite" and output == sqlite_path.resolve(): raise ValueError("Backup output cannot overwrite the source database")
    if uploads.exists() and output.is_relative_to(uploads.resolve()): raise ValueError("Backup archive cannot be written inside the uploads directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="deadlineos-backup-") as temporary:
        database_file = Path(temporary) / ("database.sqlite3" if kind == "sqlite" else "database.dump")
        _dump_database(kind, parsed, sqlite_path, database_file)
        entries = {f"database/{database_file.name}": _sha256(database_file)}
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            archive.write(database_file, f"database/{database_file.name}")
            if uploads.exists():
                for file in sorted(uploads.rglob("*")):
                    if file.is_file() and not file.is_symlink():
                        relative = file.relative_to(uploads).as_posix()
                        archive_name = f"uploads/{relative}"
                        archive.write(file, archive_name)
                        entries[archive_name] = _sha256(file)
            manifest = {"format_version": 1, "database_type": kind, "created_at": datetime.now(timezone.utc).isoformat(), "sha256": entries}
            archive.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
    return output


def _read_and_validate(archive_path, temporary):
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        infos = {item.filename: item for item in archive.infolist()}
        if len(names) != len(set(names)): raise ValueError("Backup contains duplicate archive paths")
        if sum(item.file_size for item in archive.infolist()) > 10 * 1024 * 1024 * 1024:
            raise ValueError("Backup expands beyond the 10 GiB restore safety limit")
        for name in names:
            path = PurePosixPath(name)
            mode = infos[name].external_attr >> 16
            if "\\" in name or ":" in name or "\x00" in name or stat.S_ISLNK(mode) or path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] not in {"database", "uploads", "manifest.json"}:
                raise ValueError(f"Unsafe backup archive path: {name}")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("format_version") != 1 or manifest.get("database_type") not in {"sqlite", "postgresql"}:
            raise ValueError("Unsupported backup format")
        expected = manifest.get("sha256", {})
        if set(names) - {"manifest.json"} != set(expected): raise ValueError("Backup manifest entries do not match archive contents")
        extracted = {}
        for name, checksum in expected.items():
            target = Path(temporary).joinpath(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as source, target.open("wb") as destination: shutil.copyfileobj(source, destination)
            if _sha256(target) != checksum: raise ValueError(f"Backup integrity check failed for {name}")
            extracted[name] = target
    database_entries = [name for name in extracted if name.startswith("database/")]
    if len(database_entries) != 1: raise ValueError("Backup must contain exactly one database image")
    return manifest, extracted[database_entries[0]], extracted


def _postgresql_has_user_tables(parsed):
    import psycopg
    connection = psycopg.connect(host=parsed.host, port=parsed.port, user=parsed.username,
                                 password=parsed.password, dbname=parsed.database,
                                 sslmode=(parsed.query or {}).get("sslmode", "prefer"))
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema')")
            return cursor.fetchone()[0] > 0
    finally: connection.close()


def restore_backup(archive_path, database_url, uploads_dir, overwrite=False):
    kind, parsed, sqlite_path = _database(database_url)
    uploads = Path(uploads_dir)
    if uploads.is_symlink() or (uploads.exists() and not uploads.is_dir()):
        raise ValueError("The uploads target must be a normal directory, not a file or symbolic link")
    uploads = uploads.resolve()
    if uploads.exists() and any(uploads.iterdir()) and not overwrite:
        raise FileExistsError(f"Upload directory is not empty: {uploads}; pass --overwrite after making a safety backup")
    if kind == "sqlite" and sqlite_path.exists() and not overwrite:
        raise FileExistsError(f"Database already exists: {sqlite_path}; pass --overwrite after making a safety backup")
    if kind == "postgresql" and _postgresql_has_user_tables(parsed) and not overwrite:
        raise FileExistsError("PostgreSQL target already contains tables; pass --overwrite after taking a separate safety backup")

    with tempfile.TemporaryDirectory(prefix="deadlineos-restore-") as temporary:
        manifest, database_file, extracted = _read_and_validate(archive_path, temporary)
        if manifest["database_type"] != kind: raise ValueError("Backup database type does not match the selected target")
        staged_uploads = Path(temporary) / "restored-uploads"
        staged_uploads.mkdir()
        for name, file in extracted.items():
            if name.startswith("uploads/"):
                relative = PurePosixPath(name).parts[1:]
                target = staged_uploads.joinpath(*relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, target)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        if kind == "sqlite":
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            staged_database = sqlite_path.with_name(f".{sqlite_path.name}.restore-{stamp}")
            with closing(sqlite3.connect(database_file)) as check:
                result = check.execute("PRAGMA integrity_check").fetchone()[0]
                if result != "ok": raise ValueError(f"SQLite backup is invalid: {result}")
            shutil.copy2(database_file, staged_database)
            if sqlite_path.exists(): shutil.copy2(sqlite_path, sqlite_path.with_name(f"{sqlite_path.name}.pre-restore-{stamp}"))
            os.replace(staged_database, sqlite_path)
        else:
            if _postgresql_has_user_tables(parsed):
                safety_dump = Path(archive_path).with_name(f"{Path(archive_path).stem}.pre-restore-{stamp}.dump")
                _dump_database(kind, parsed, None, safety_dump)
            subprocess.run(["pg_restore", *_pg_args(parsed), "--exit-on-error", "--no-owner", "--no-acl",
                            *( ["--clean", "--if-exists"] if overwrite else [] ), str(database_file)],
                           env=_pg_environment(parsed), check=True)
        uploads.parent.mkdir(parents=True, exist_ok=True)
        if uploads.exists():
            if any(uploads.iterdir()):
                backup_dir = uploads.with_name(f"{uploads.name}.pre-restore-{stamp}")
                shutil.copytree(uploads, backup_dir, dirs_exist_ok=False)
            shutil.rmtree(uploads)
        os.replace(staged_uploads, uploads)
    return manifest

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
import zipfile
from contextlib import closing

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from backup_restore import create_backup, restore_backup  # noqa: E402


class BackupRestoreTests(unittest.TestCase):
    def test_sqlite_and_uploads_round_trip_and_preserves_pre_restore_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "deadlineos.db"
            uploads = root / "uploads"
            uploads.mkdir()
            with closing(sqlite3.connect(database)) as connection:
                connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
                connection.execute("INSERT INTO sample VALUES ('before')")
                connection.commit()
            (uploads / "assignment.txt").write_text("before file", encoding="utf-8")
            archive = create_backup(f"sqlite:///{database.as_posix()}", uploads, root / "backup.zip")
            with closing(sqlite3.connect(database)) as connection:
                connection.execute("UPDATE sample SET value='after'")
                connection.commit()
            (uploads / "assignment.txt").write_text("after file", encoding="utf-8")

            manifest = restore_backup(archive, f"sqlite:///{database.as_posix()}", uploads, overwrite=True)
            with closing(sqlite3.connect(database)) as connection:
                self.assertEqual(connection.execute("SELECT value FROM sample").fetchone()[0], "before")
            self.assertEqual((uploads / "assignment.txt").read_text(encoding="utf-8"), "before file")
            self.assertEqual(manifest["database_type"], "sqlite")
            self.assertTrue(list(root.glob("deadlineos.db.pre-restore-*")))
            self.assertTrue(list(root.glob("uploads.pre-restore-*")))

    def test_corrupt_archive_fails_before_target_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "deadlineos.db"
            uploads = root / "uploads"
            uploads.mkdir()
            with closing(sqlite3.connect(database)) as connection:
                connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
                connection.execute("INSERT INTO sample VALUES ('keep')")
                connection.commit()
            archive = create_backup(f"sqlite:///{database.as_posix()}", uploads, root / "backup.zip")
            with closing(sqlite3.connect(database)) as connection:
                connection.execute("UPDATE sample SET value='still here'")
                connection.commit()
            tampered = root / "tampered.zip"
            with zipfile.ZipFile(archive) as source, zipfile.ZipFile(tampered, "w") as target:
                for item in source.infolist():
                    data = source.read(item.filename)
                    if item.filename.startswith("database/"): data = data[:-1] + bytes([data[-1] ^ 0x01])
                    target.writestr(item.filename, data)
            with self.assertRaises(ValueError):
                restore_backup(tampered, f"sqlite:///{database.as_posix()}", uploads, overwrite=True)
            with closing(sqlite3.connect(database)) as connection:
                self.assertEqual(connection.execute("SELECT value FROM sample").fetchone()[0], "still here")


if __name__ == "__main__": unittest.main()

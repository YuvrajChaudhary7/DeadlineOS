"""Rehearse a clean seeded install using a disposable SQLite file."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
CHECK = """
import sys
sys.path.insert(0, 'backend')
from app import app
from database import schema_version
from models import Course, Deadline, PersonalTask, Project, User
with app.app_context():
    assert schema_version() == 4, schema_version()
    assert User.query.count() == 2, User.query.count()
    assert Course.query.count() == 1, Course.query.count()
    assert Deadline.query.count() == 1, Deadline.query.count()
    assert Project.query.count() == 1, Project.query.count()
    assert PersonalTask.query.count() == 2, PersonalTask.query.count()
    print(f'Clean install OK: schema v{schema_version()}, 2 demo users, 1 course, 1 deadline, 1 project, 2 tasks')
"""


def main():
    with tempfile.TemporaryDirectory(prefix="deadlineos-clean-install-") as temporary:
        database = Path(temporary) / "clean-install.db"
        environment = os.environ.copy()
        environment.update({"DATABASE_URL": f"sqlite:///{database.as_posix()}", "SEED_DEMO": "true",
                           "JWT_SECRET_KEY": "temporary-clean-install-check-key-123456"})
        subprocess.run([PYTHON, "-c", CHECK], cwd=ROOT, env=environment, check=True)


if __name__ == "__main__":
    main()

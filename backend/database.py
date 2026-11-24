import os
from pathlib import Path
from datetime import datetime, timedelta, timezone

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash

db = SQLAlchemy()
LATEST_SCHEMA_VERSION = 4


def _columns(connection, table_name):
    return {column["name"] for column in inspect(connection).get_columns(table_name)}


def _add_column(connection, table_name, name, definition):
    if name not in _columns(connection, table_name):
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {name} {definition}"))


def _apply_schema_migrations(app):
    """Apply ordered, additive migrations; every version is recorded transactionally."""
    with db.engine.begin() as connection:
        connection.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, name VARCHAR(120) NOT NULL, applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"))
        current = connection.execute(text("SELECT COALESCE(MAX(version), 0) FROM schema_migrations")).scalar_one()
        if current > LATEST_SCHEMA_VERSION:
            raise RuntimeError(f"Database schema version {current} is newer than this application supports (max {LATEST_SCHEMA_VERSION})")

        if current < 1:
            # Compatibility with pre-migration installations: storage metadata and account/task fields.
            if "submissions" in inspect(connection).get_table_names():
                _add_column(connection, "submissions", "object_key", "VARCHAR(255)")
                _add_column(connection, "submissions", "file_name", "VARCHAR(255)")
            if "users" in inspect(connection).get_table_names():
                _add_column(connection, "users", "is_active", "BOOLEAN NOT NULL DEFAULT TRUE")
            if "personal_tasks" in inspect(connection).get_table_names():
                _add_column(connection, "personal_tasks", "recurrence", "VARCHAR(10) NOT NULL DEFAULT 'none'")
            connection.execute(text("INSERT INTO schema_migrations(version,name) VALUES (1,'legacy upload, account and recurrence fields')"))
            current = 1

        if current < 2:
            if "personal_tasks" in inspect(connection).get_table_names():
                _add_column(connection, "personal_tasks", "is_archived", "BOOLEAN NOT NULL DEFAULT FALSE")
                _add_column(connection, "personal_tasks", "project_id", "INTEGER REFERENCES projects(id) ON DELETE SET NULL")
            if "deadlines" in inspect(connection).get_table_names():
                _add_column(connection, "deadlines", "allow_resubmissions", "BOOLEAN NOT NULL DEFAULT FALSE")
                _add_column(connection, "deadlines", "max_attempts", "INTEGER NOT NULL DEFAULT 1")
            if "submissions" in inspect(connection).get_table_names():
                _add_column(connection, "submissions", "attempt_count", "INTEGER NOT NULL DEFAULT 1")
            connection.execute(text("INSERT INTO schema_migrations(version,name) VALUES (2,'projects, task archive and submission policy')"))
            current = 2

        if current < 3:
            if "project_files" in inspect(connection).get_table_names():
                _add_column(connection, "project_files", "size_bytes", "INTEGER NOT NULL DEFAULT 0")
            if "submissions" in inspect(connection).get_table_names():
                _add_column(connection, "submissions", "file_size_bytes", "INTEGER NOT NULL DEFAULT 0")
            if "submission_attempts" in inspect(connection).get_table_names():
                _add_column(connection, "submission_attempts", "file_size_bytes", "INTEGER NOT NULL DEFAULT 0")
            # Preserve the current submission as attempt 1 when upgrading old databases.
            if {"submissions", "submission_attempts"}.issubset(inspect(connection).get_table_names()):
                connection.execute(text("""
                    INSERT INTO submission_attempts(submission_id,attempt_number,submitted_at,note,file_key,file_name,status,file_size_bytes)
                    SELECT s.id,1,s.submitted_at,s.note,s.object_key,s.file_name,s.status,s.file_size_bytes
                    FROM submissions s LEFT JOIN submission_attempts a ON a.submission_id=s.id
                    WHERE a.id IS NULL
                """))
            connection.execute(text("INSERT INTO schema_migrations(version,name) VALUES (3,'file sizes and submission attempt backfill')"))
            current = 3

        if current < 4:
            # create_all above creates the indexed auth_failures table for existing installations.
            connection.execute(text("INSERT INTO schema_migrations(version,name) VALUES (4,'hashed login failure tracking')"))

    # Recover byte counts for files already on the local disk so upgrades preserve quota accounting.
    from models import ProjectFile, Submission, SubmissionAttempt
    upload_dir = Path(app.instance_path) / "uploads"
    for record in ProjectFile.query.filter_by(size_bytes=0).all():
        path = upload_dir / record.file_key
        if path.is_file(): record.size_bytes = path.stat().st_size
    for record in SubmissionAttempt.query.filter_by(file_size_bytes=0).all():
        path = upload_dir / record.file_key if record.file_key else None
        if path and path.is_file(): record.file_size_bytes = path.stat().st_size
    for record in Submission.query.filter_by(file_size_bytes=0).all():
        path = upload_dir / record.file_key if record.file_key else None
        if path and path.is_file(): record.file_size_bytes = path.stat().st_size
    db.session.commit()


def schema_version():
    if "schema_migrations" not in inspect(db.engine).get_table_names():
        return 0
    return db.session.execute(text("SELECT COALESCE(MAX(version), 0) FROM schema_migrations")).scalar_one()


def initialize_database(app):
    db.init_app(app)
    with app.app_context():
        from models import ActivityLog, Announcement, AuthFailure, Course, Deadline, Enrollment, Notification, PersonalTask, Project, ProjectDeadline, ProjectFile, ReminderLog, Submission, SubmissionAttempt, TaskCompletion, TaskSubtask, User

        # create_all creates new tables for upgrades; versioned migrations add columns to existing tables.
        db.create_all()
        _apply_schema_migrations(app)
        if os.getenv("SEED_DEMO", "true").lower() != "true" or User.query.first():
            return
        staff = User(email="staff@university.edu", password_hash=generate_password_hash("StaffPass123!"), role="staff", first_name="Demo", last_name="Instructor")
        student = User(email="alice@university.edu", password_hash=generate_password_hash("StudentPass123!"), role="student", first_name="Alice", last_name="Student")
        db.session.add_all([staff, student]); db.session.flush()
        course = Course(code="CS101", name="Introduction to Programming", description="Programming fundamentals", staff_id=staff.id, credits=4)
        db.session.add(course); db.session.flush()
        db.session.add(Enrollment(user_id=student.id, course_id=course.id))
        deadline = Deadline(course_id=course.id, title="Python Fundamentals", description="Submit your solution as a file.", due_at=datetime.now(timezone.utc) + timedelta(days=7), max_marks=100, created_by=staff.id)
        db.session.add(deadline)
        project = Project(user_id=student.id, name="DP-900 Study Plan", description="Review data concepts, practice queries and prepare the final demo.", color="#167354")
        db.session.add(project); db.session.flush()
        task_one = PersonalTask(user_id=student.id, project_id=project.id, title="Review relational data concepts", description="Revise tables, keys, normalization and transactions.", due_at=datetime.now(timezone.utc) + timedelta(days=2), priority="high")
        task_two = PersonalTask(user_id=student.id, project_id=project.id, title="Prepare Azure data services notes", due_at=datetime.now(timezone.utc) + timedelta(days=5), priority="medium", recurrence="weekly")
        db.session.add_all([task_one, task_two]); db.session.flush()
        db.session.add_all([TaskSubtask(task_id=task_one.id, title="Review primary and foreign keys"), TaskSubtask(task_id=task_one.id, title="Practice a join query")])
        db.session.commit()

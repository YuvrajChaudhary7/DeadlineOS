import os
from datetime import datetime, timedelta, timezone

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash

db = SQLAlchemy()


def initialize_database(app):
    db.init_app(app)
    with app.app_context():
        from models import ActivityLog, Announcement, Course, Deadline, Enrollment, Notification, PersonalTask, ReminderLog, Submission, TaskSubtask, User

        db.create_all()
        # Additive migration for local databases created before private file uploads existed.
        columns = {item["name"] for item in inspect(db.engine).get_columns("submissions")}
        with db.engine.begin() as connection:
            if "object_key" not in columns:
                connection.execute(text("ALTER TABLE submissions ADD COLUMN object_key VARCHAR(255)"))
            if "file_name" not in columns:
                connection.execute(text("ALTER TABLE submissions ADD COLUMN file_name VARCHAR(255)"))
            user_columns = {item["name"] for item in inspect(db.engine).get_columns("users")}
            if "is_active" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE"))
            task_columns = {item["name"] for item in inspect(db.engine).get_columns("personal_tasks")}
            if "recurrence" not in task_columns:
                connection.execute(text("ALTER TABLE personal_tasks ADD COLUMN recurrence VARCHAR(10) NOT NULL DEFAULT 'none'"))
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
        db.session.commit()


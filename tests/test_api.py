"""Focused API integration checks for authorization and new planner workflows."""
import os
import sys
import unittest
from io import BytesIO
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", "sqlite://")
os.environ["SEED_DEMO"] = "false"
os.environ["JWT_SECRET_KEY"] = "tests-only-secret-key-for-hmac-256"
os.environ["ENABLE_REMINDERS"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app import app as flask_app, create_app, db  # noqa: E402
from models import AuthFailure, Course, Deadline, Enrollment, Notification, ProjectFile, User  # noqa: E402
from database import schema_version  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402


class DeadlineOSApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        flask_app.config.update(TESTING=True)
        cls.context = flask_app.app_context()
        cls.context.push()
        cls.client = flask_app.test_client()

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        cls.context.pop()

    def setUp(self):
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.student_token = self.register_and_login("student@example.edu")

    def register_and_login(self, email):
        response = self.client.post("/api/auth/register", json={
            "email": email, "password": "StrongTestPass123!", "first_name": "Test", "last_name": "Student"
        })
        self.assertEqual(response.status_code, 201)
        response = self.client.post("/api/auth/login", json={"email": email, "password": "StrongTestPass123!"})
        self.assertEqual(response.status_code, 200)
        return response.get_json()["access_token"]

    @staticmethod
    def auth(token):
        return {"Authorization": f"Bearer {token}"}

    def test_student_project_and_task_are_private_and_archivable(self):
        response = self.client.post("/api/projects", headers=self.auth(self.student_token), json={"name": "Capstone"})
        self.assertEqual(response.status_code, 201)
        project_id = response.get_json()["id"]
        task_due = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        response = self.client.post("/api/personal-tasks", headers=self.auth(self.student_token), json={
            "title": "Draft report", "due_at": task_due, "project_id": project_id
        })
        self.assertEqual(response.status_code, 201)
        task_id = response.get_json()["id"]
        self.assertIn("risk", self.client.get("/api/personal-tasks", headers=self.auth(self.student_token)).get_json()[0])
        self.assertEqual(self.client.patch(f"/api/personal-tasks/{task_id}", headers=self.auth(self.student_token), json={"is_complete": True}).status_code, 200)
        self.assertGreaterEqual(self.client.get("/api/dashboard", headers=self.auth(self.student_token)).get_json()["streak"]["current"], 1)
        archived = self.client.patch(f"/api/personal-tasks/{task_id}", headers=self.auth(self.student_token), json={"is_archived": True})
        self.assertEqual(archived.status_code, 200)
        self.assertEqual(self.client.get("/api/personal-tasks", headers=self.auth(self.student_token)).get_json(), [])
        self.assertEqual(len(self.client.get("/api/personal-tasks?archived=true", headers=self.auth(self.student_token)).get_json()), 1)

        another_student = self.register_and_login("other@example.edu")
        self.assertEqual(self.client.get("/api/projects", headers=self.auth(another_student)).get_json(), [])
        self.assertEqual(self.client.patch(f"/api/projects/{project_id}", headers=self.auth(another_student), json={"name": "Hijack"}).status_code, 404)
        self.assertEqual(self.client.get("/api/personal-tasks?archived=true", headers=self.auth(another_student)).get_json(), [])

    def test_login_page_does_not_publish_demo_staff_password(self):
        response = self.client.get("/login.html")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"StaffPass123!", response.data)

    def test_task_due_offset_is_normalized_to_utc(self):
        due_utc = datetime.now(timezone.utc) + timedelta(days=3)
        local_due = due_utc.astimezone(timezone(timedelta(hours=5, minutes=30)))
        response = self.client.post("/api/personal-tasks", headers=self.auth(self.student_token), json={
            "title": "Timezone check", "due_at": local_due.isoformat()
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(datetime.fromisoformat(response.get_json()["due_at"]), due_utc)

    def test_early_weekly_completion_advances_the_next_occurrence(self):
        due = datetime.now(timezone.utc) + timedelta(days=5)
        created = self.client.post("/api/personal-tasks", headers=self.auth(self.student_token), json={
            "title": "Weekly task", "due_at": due.isoformat(), "recurrence": "weekly"
        })
        self.assertEqual(created.status_code, 201)
        response = self.client.patch(f"/api/personal-tasks/{created.get_json()['id']}",
                                     headers=self.auth(self.student_token), json={"is_complete": True})
        self.assertEqual(response.status_code, 200)
        tasks = self.client.get("/api/personal-tasks", headers=self.auth(self.student_token)).get_json()
        next_task = next(task for task in tasks if task["id"] == response.get_json()["next_task_id"])
        self.assertEqual(datetime.fromisoformat(next_task["due_at"]), due + timedelta(days=7))

    def test_task_risk_uses_open_workload_for_the_due_day(self):
        due = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        for index in range(4):
            response = self.client.post("/api/personal-tasks", headers=self.auth(self.student_token), json={
                "title": f"Busy day task {index}", "due_at": due
            })
            self.assertEqual(response.status_code, 201)
        tasks = self.client.get("/api/personal-tasks", headers=self.auth(self.student_token)).get_json()
        self.assertTrue(all(any("4 open items fall on this day" in reason for reason in task["risk"]["reasons"]) for task in tasks))

    def test_instructor_resubmission_policy_records_bounded_attempt_history(self):
        staff = User(email="staff@example.edu", password_hash=generate_password_hash("StaffTestPass123!"), role="staff", first_name="Staff", last_name="User")
        db.session.add(staff)
        db.session.flush()
        course = Course(code="TEST1", name="Test course", staff_id=staff.id)
        db.session.add(course)
        db.session.flush()
        enrollment = Enrollment(user_id=User.query.filter_by(email="student@example.edu").one().id, course_id=course.id)
        db.session.add(enrollment)
        deadline = Deadline(course_id=course.id, title="Report", due_at=datetime.now(timezone.utc) + timedelta(days=4), max_marks=100,
                            created_by=staff.id, allow_resubmissions=True, max_attempts=2)
        db.session.add(deadline)
        db.session.commit()

        first = self.client.post("/api/submissions", headers=self.auth(self.student_token), json={"deadline_id": deadline.id, "note": "first"})
        self.assertEqual(first.status_code, 201)
        submission_id = first.get_json()["id"]
        second = self.client.post("/api/submissions", headers=self.auth(self.student_token), json={"deadline_id": deadline.id, "note": "revised"})
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.get_json()["attempt_number"], 2)
        third = self.client.post("/api/submissions", headers=self.auth(self.student_token), json={"deadline_id": deadline.id})
        self.assertEqual(third.status_code, 409)
        attempts = self.client.get(f"/api/submissions/{submission_id}/attempts", headers=self.auth(self.student_token))
        self.assertEqual([item["attempt_number"] for item in attempts.get_json()], [1, 2])
        another_student = self.register_and_login("attempt-reader@example.edu")
        self.assertEqual(self.client.get(f"/api/submissions/{submission_id}/attempts", headers=self.auth(another_student)).status_code, 403)
        staff_login = self.client.post("/api/auth/login", json={"email": "staff@example.edu", "password": "StaffTestPass123!"})
        staff_token = staff_login.get_json()["access_token"]
        closed = self.client.patch(f"/api/deadlines/{deadline.id}", headers=self.auth(staff_token), json={"is_active": False})
        self.assertEqual(closed.status_code, 200)
        self.assertEqual(self.client.post("/api/submissions", headers=self.auth(self.student_token), json={"deadline_id": deadline.id}).status_code, 404)

    def test_project_files_are_only_downloadable_by_owner(self):
        project = self.client.post("/api/projects", headers=self.auth(self.student_token), json={"name": "Private files"}).get_json()
        upload = self.client.post(f"/api/projects/{project['id']}/files", headers=self.auth(self.student_token),
                                  data={"file": (BytesIO(b"private notes"), "notes.txt")}, content_type="multipart/form-data")
        self.assertEqual(upload.status_code, 201)
        file_id = upload.get_json()["id"]
        download = self.client.get(f"/api/projects/{project['id']}/files/{file_id}", headers=self.auth(self.student_token))
        self.assertEqual(download.status_code, 200)
        download.close()
        stored_file = db.session.get(ProjectFile, file_id)
        (Path(flask_app.instance_path) / "uploads" / stored_file.file_key).unlink(missing_ok=True)
        db.session.delete(stored_file)
        db.session.commit()
        another_student = self.register_and_login("file-reader@example.edu")
        self.assertEqual(self.client.get(f"/api/projects/{project['id']}/files/{file_id}", headers=self.auth(another_student)).status_code, 404)

    def test_upload_validation_delete_and_pagination_contract(self):
        project = self.client.post("/api/projects", headers=self.auth(self.student_token), json={"name": "Upload checks"}).get_json()
        mismatch = self.client.post(f"/api/projects/{project['id']}/files", headers=self.auth(self.student_token),
                                    data={"file": (BytesIO(b"not a PDF"), "notes.pdf")}, content_type="multipart/form-data")
        self.assertEqual(mismatch.status_code, 400)
        good = self.client.post(f"/api/projects/{project['id']}/files", headers=self.auth(self.student_token),
                                data={"file": (BytesIO(b"valid UTF-8 notes"), "notes.txt")}, content_type="multipart/form-data")
        self.assertEqual(good.status_code, 201)
        file_id = good.get_json()["id"]
        paged = self.client.get("/api/projects?page=1&per_page=1", headers=self.auth(self.student_token))
        self.assertEqual(paged.status_code, 200)
        self.assertEqual(len(paged.get_json()), 1)
        self.assertEqual(paged.headers.get("X-Pagination"), '{"page": 1, "per_page": 1, "total": 1, "pages": 1, "has_previous": false, "has_next": false}')
        deleted = self.client.delete(f"/api/projects/{project['id']}/files/{file_id}", headers=self.auth(self.student_token))
        self.assertEqual(deleted.status_code, 200)
        self.assertIsNone(db.session.get(ProjectFile, file_id))

    def test_submission_grading_and_notification_end_to_end(self):
        student = User.query.filter_by(email="student@example.edu").one()
        staff = User(email="grader@example.edu", password_hash=generate_password_hash("StaffTestPass123!"), role="staff", first_name="Grace", last_name="Grader")
        db.session.add(staff); db.session.flush()
        course = Course(code="FLOW1", name="Flow test", staff_id=staff.id)
        db.session.add(course); db.session.flush()
        db.session.add(Enrollment(user_id=student.id, course_id=course.id))
        deadline = Deadline(course_id=course.id, title="End-to-end assignment", due_at=datetime.now(timezone.utc) + timedelta(days=2), max_marks=20, created_by=staff.id)
        db.session.add(deadline); db.session.commit()
        submission = self.client.post("/api/submissions", headers=self.auth(self.student_token), json={"deadline_id": deadline.id, "note": "completed"})
        self.assertEqual(submission.status_code, 201)
        staff_login = self.client.post("/api/auth/login", json={"email": "grader@example.edu", "password": "StaffTestPass123!"})
        staff_token = staff_login.get_json()["access_token"]
        graded = self.client.put(f"/api/submissions/{submission.get_json()['id']}/grade", headers=self.auth(staff_token), json={"marks_obtained": 18, "feedback": "Good work"})
        self.assertEqual(graded.status_code, 200)
        notifications = self.client.get("/api/notifications", headers=self.auth(self.student_token)).get_json()
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]["kind"], "grade")

    def test_database_has_versioned_schema(self):
        self.assertEqual(schema_version(), 4)

    def test_login_failures_are_limited_and_persist_only_hashed_identifiers(self):
        flask_app.config["LOGIN_EMAIL_FAILURE_LIMIT"] = 2
        try:
            for _ in range(2):
                response = self.client.post("/api/auth/login", json={"email": "student@example.edu", "password": "wrong"})
                self.assertEqual(response.status_code, 401)
            blocked = self.client.post("/api/auth/login", json={"email": "student@example.edu", "password": "wrong"})
            self.assertEqual(blocked.status_code, 429)
            self.assertEqual(blocked.headers["Retry-After"], "900")
            failure = AuthFailure.query.first()
            self.assertNotIn("student@example.edu", failure.email_hash)
            self.assertEqual(len(failure.email_hash), 64)
        finally:
            flask_app.config["LOGIN_EMAIL_FAILURE_LIMIT"] = 5

    def test_health_and_security_headers_are_actionable(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.get_json()["database"], "ok")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")

    def test_production_refuses_the_local_jwt_secret(self):
        from unittest.mock import patch
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "JWT_SECRET_KEY": "weak-secret"}):
            with self.assertRaises(RuntimeError):
                create_app()


if __name__ == "__main__":
    unittest.main()

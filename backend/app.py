import os
import re
import uuid
import calendar
import json
import hmac
import hashlib
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, jwt_required
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from database import db, initialize_database
from models import ActivityLog, Announcement, AuthFailure, Course, Deadline, Enrollment, Notification, PersonalTask, Project, ProjectDeadline, ProjectFile, ReminderLog, Submission, SubmissionAttempt, TaskCompletion, TaskSubtask, User
from uploads import ScannerUnavailable, UploadRejected, validate_upload

load_dotenv()


def as_utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def create_app():
    app = Flask(__name__)
    environment = os.getenv("ENVIRONMENT", "development").lower()
    allowed_origins = os.getenv("FRONTEND_ORIGIN", "*" if environment != "production" else "")
    if allowed_origins:
        CORS(app, resources={r"/api/*": {"origins": allowed_origins}}, expose_headers=["X-Pagination"])
    jwt_secret = os.getenv("JWT_SECRET_KEY", "local-development-secret-change-me")
    if environment == "production" and (len(jwt_secret) < 32 or jwt_secret == "local-development-secret-change-me"):
        raise RuntimeError("Production requires a randomly generated JWT_SECRET_KEY with at least 32 characters")
    app.config.update(SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///deadlineos.db"), SQLALCHEMY_TRACK_MODIFICATIONS=False,
                      JWT_SECRET_KEY=jwt_secret, JWT_ACCESS_TOKEN_EXPIRES=timedelta(minutes=15),
                      MAX_CONTENT_LENGTH=16 * 1024 * 1024, MAX_USER_STORAGE_BYTES=int(os.getenv("MAX_USER_STORAGE_BYTES", str(200 * 1024 * 1024))),
                      MAX_USER_FILES=int(os.getenv("MAX_USER_FILES", "100")), MAX_UPLOAD_BYTES=16 * 1024 * 1024,
                      LOGIN_EMAIL_FAILURE_LIMIT=int(os.getenv("LOGIN_EMAIL_FAILURE_LIMIT", "5")),
                      LOGIN_IP_FAILURE_LIMIT=int(os.getenv("LOGIN_IP_FAILURE_LIMIT", "30")),
                      LOGIN_WINDOW_MINUTES=int(os.getenv("LOGIN_WINDOW_MINUTES", "15")))
    JWTManager(app)
    initialize_database(app)
    upload_dir = Path(app.instance_path) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    def user_storage_usage(user_id):
        objects = {}
        project_files = ProjectFile.query.join(Project).filter(Project.user_id == user_id).all()
        for item in project_files:
            objects[item.file_key] = max(objects.get(item.file_key, 0), item.size_bytes or 0)
        attempts = SubmissionAttempt.query.join(Submission).filter(Submission.user_id == user_id).all()
        for item in attempts:
            if item.file_key:
                objects[item.file_key] = max(objects.get(item.file_key, 0), item.file_size_bytes or 0)
        return sum(objects.values()), len(objects)

    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

    @app.get("/")
    def frontend_home(): return send_from_directory(frontend_dir, "index.html")

    @app.get("/<path:asset>")
    def frontend_asset(asset):
        if asset.startswith("api/"): return jsonify(error="not found"), 404
        return send_from_directory(frontend_dir, asset)

    def current_user():
        return db.session.get(User, int(get_jwt_identity()))

    def roles(*allowed):
        def decorator(fn):
            @wraps(fn)
            @jwt_required()
            def wrapped(*args, **kwargs):
                user = current_user()
                if not user or not user.is_active or user.role not in allowed:
                    return jsonify(error="forbidden"), 403
                return fn(*args, **kwargs)
            return wrapped
        return decorator

    def audit(user_id, action, entity_type, entity_id=None):
        db.session.add(ActivityLog(user_id=user_id, action=action, entity_type=entity_type, entity_id=entity_id, ip_address=request.remote_addr))

    def rate_key(namespace, value):
        secret = app.config["JWT_SECRET_KEY"].encode("utf-8")
        return hmac.new(secret, f"{namespace}:{value}".encode("utf-8"), hashlib.sha256).hexdigest()

    def paginate(query):
        try:
            page = max(1, int(request.args.get("page", "1")))
            per_page = max(1, min(100, int(request.args.get("per_page", "25"))))
        except (TypeError, ValueError):
            page, per_page = 1, 25
        total = query.order_by(None).count()
        pages = (total + per_page - 1) // per_page
        if pages and page > pages: page = pages
        rows = query.offset((page - 1) * per_page).limit(per_page).all()
        metadata = {"page": page, "per_page": per_page, "total": total, "pages": pages,
                    "has_previous": page > 1, "has_next": page < pages}
        return rows, metadata

    def list_page(query):
        """Keep legacy list responses intact unless a client explicitly requests paging."""
        if "page" not in request.args and "per_page" not in request.args:
            return query.all(), None
        return paginate(query)

    def paginated_json(rows, metadata):
        response = jsonify(rows)
        response.headers["X-Pagination"] = json.dumps(metadata)
        return response

    def build_task_risk_context(user, tasks):
        task_ids = [task.id for task in tasks]
        subtasks_by_task = {task_id: [] for task_id in task_ids}
        if not task_ids:
            return {"subtasks_by_task": subtasks_by_task, "load_by_day": {}}

        for subtask in TaskSubtask.query.filter(TaskSubtask.task_id.in_(task_ids)).order_by(TaskSubtask.id).all():
            subtasks_by_task[subtask.task_id].append(subtask)

        load_by_day = {}
        open_tasks = PersonalTask.query.filter_by(user_id=user.id, is_archived=False, is_complete=False).all()
        for item in open_tasks:
            day = as_utc(item.due_at).date()
            load_by_day[day] = load_by_day.get(day, 0) + 1

        course_ids = [row[0] for row in db.session.query(Enrollment.course_id).filter_by(user_id=user.id, status="active").all()]
        if course_ids:
            deadlines = Deadline.query.filter(Deadline.course_id.in_(course_ids), Deadline.is_active).all()
            deadline_ids = [item.id for item in deadlines]
            submitted_ids = set()
            if deadline_ids:
                submitted_ids = {row[0] for row in db.session.query(Submission.deadline_id).filter(
                    Submission.user_id == user.id, Submission.deadline_id.in_(deadline_ids)
                ).all()}
            for deadline in deadlines:
                if deadline.id not in submitted_ids:
                    day = as_utc(deadline.due_at).date()
                    load_by_day[day] = load_by_day.get(day, 0) + 1
        return {"subtasks_by_task": subtasks_by_task, "load_by_day": load_by_day}

    def task_risk(task, user, context):
        if task.is_complete or task.is_archived:
            return {"score": 0, "label": "complete", "reasons": ["Task is complete or archived"]}
        now = datetime.now(timezone.utc)
        due = as_utc(task.due_at)
        days_left = (due.date() - now.date()).days
        score = 0
        reasons = []
        if days_left < 0:
            score += 45; reasons.append("Past due")
        elif days_left == 0:
            score += 38; reasons.append("Due today")
        elif days_left <= 2:
            score += 27; reasons.append("Due within two days")
        elif days_left <= 7:
            score += 14; reasons.append("Due this week")
        if task.priority == "high":
            score += 18; reasons.append("High priority")
        elif task.priority == "medium":
            score += 8
        subtasks = context["subtasks_by_task"].get(task.id, [])
        if subtasks:
            remaining = sum(not item.is_complete for item in subtasks)
            if remaining:
                score += min(20, round(20 * remaining / len(subtasks)))
                reasons.append(f"{remaining} checklist step(s) remain")
        same_day_load = context["load_by_day"].get(due.date(), 0)
        if same_day_load >= 4:
            score += min(20, (same_day_load - 3) * 5); reasons.append(f"{same_day_load} open items fall on this day")
        return {"score": min(score, 100), "label": "at risk" if score >= 55 else "watch" if score >= 30 else "on track",
                "reasons": reasons or ["No immediate risk factors"], "days_left": days_left}

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'")
        return response

    @app.get("/api/health")
    def health():
        try:
            db.session.execute(select(1))
            return jsonify(status="ok", service="DeadlineOS API", database="ok")
        except Exception:
            db.session.rollback()
            app.logger.exception("Database health check failed")
            return jsonify(status="degraded", service="DeadlineOS API", database="unavailable"), 503

    @app.post("/api/auth/register")
    def register():
        data = request.get_json(silent=True) or {}; email = str(data.get("email", "")).strip().lower(); password = str(data.get("password", ""))
        first_name = str(data.get("first_name", "")).strip(); last_name = str(data.get("last_name", "")).strip()
        if not email or len(email) > 254 or "@" not in email or len(password) < 12 or len(password) > 256:
            return jsonify(error="valid email and password of at least 12 characters required"), 400
        if not first_name or len(first_name) > 80 or not last_name or len(last_name) > 80:
            return jsonify(error="first and last names are required and must be 80 characters or fewer"), 400
        if User.query.filter_by(email=email).first(): return jsonify(error="email already registered"), 409
        # Public signup must never grant privileged staff access.
        role = data.get("role", "student")
        if role != "student": return jsonify(error="staff accounts must be provisioned by an administrator"), 403
        user = User(email=email, password_hash=generate_password_hash(password), role=role, first_name=first_name, last_name=last_name)
        db.session.add(user); db.session.flush(); audit(user.id, "register", "user", user.id)
        try: db.session.commit()
        except IntegrityError: db.session.rollback(); return jsonify(error="email already registered"), 409
        return jsonify(id=user.id, email=user.email, role=user.role), 201

    @app.post("/api/auth/login")
    def login():
        data = request.get_json(silent=True) or {}; email = str(data.get("email", "")).strip().lower()[:254]; password = str(data.get("password", ""))
        now = datetime.now(timezone.utc); cutoff = now - timedelta(minutes=app.config["LOGIN_WINDOW_MINUTES"])
        ip_hash = rate_key("ip", request.remote_addr or "unknown"); email_hash = rate_key("email", email)
        # Keep only a day of failure metadata; email/IP values are never stored in clear text.
        AuthFailure.query.filter(AuthFailure.occurred_at < now - timedelta(days=1)).delete(synchronize_session=False)
        ip_failures = AuthFailure.query.filter(AuthFailure.ip_hash == ip_hash, AuthFailure.occurred_at >= cutoff).count()
        email_failures = AuthFailure.query.filter(AuthFailure.email_hash == email_hash, AuthFailure.occurred_at >= cutoff).count()
        if ip_failures >= app.config["LOGIN_IP_FAILURE_LIMIT"] or email_failures >= app.config["LOGIN_EMAIL_FAILURE_LIMIT"]:
            db.session.commit()
            response = jsonify(error="too many sign-in attempts; wait before trying again")
            response.headers["Retry-After"] = str(app.config["LOGIN_WINDOW_MINUTES"] * 60)
            return response, 429
        user = User.query.filter_by(email=email).first() if email else None
        valid = bool(user and user.is_active and len(password) <= 256 and check_password_hash(user.password_hash, password))
        if not valid:
            db.session.add(AuthFailure(ip_hash=ip_hash, email_hash=email_hash, occurred_at=now))
            db.session.commit()
            return jsonify(error="invalid credentials"), 401
        AuthFailure.query.filter_by(email_hash=email_hash).delete(synchronize_session=False)
        token = create_access_token(identity=str(user.id)); audit(user.id, "login", "user", user.id); db.session.commit()
        return jsonify(access_token=token, user={"id": user.id, "email": user.email, "role": user.role, "name": f"{user.first_name} {user.last_name}"})

    @app.get("/api/auth/me")
    @jwt_required()
    def me():
        user = current_user(); return jsonify(id=user.id, email=user.email, role=user.role, first_name=user.first_name, last_name=user.last_name)

    @app.post("/api/auth/logout")
    @jwt_required()
    def logout():
        user = current_user(); audit(user.id, "logout", "user", user.id); db.session.commit()
        return jsonify(message="signed out")

    @app.get("/api/courses")
    @jwt_required()
    def list_courses():
        user = current_user()
        query = Course.query.filter_by(staff_id=user.id) if user.role == "staff" else Course.query
        courses = query.order_by(Course.code).all()
        return jsonify([{"id": c.id, "code": c.code, "name": c.name, "description": c.description, "staff_id": c.staff_id,
                        "enrolled": bool(Enrollment.query.filter_by(course_id=c.id, user_id=user.id, status="active").first()),
                        "enrollment_count": Enrollment.query.filter_by(course_id=c.id, status="active").count()} for c in courses])

    @app.post("/api/courses")
    @roles("staff")
    def create_course():
        user = current_user(); data = request.get_json(silent=True) or {}; code = str(data.get("code", "")).strip().upper(); name = str(data.get("name", "")).strip()
        if not code or len(code) > 20 or not name or len(name) > 120: return jsonify(error="course code (20 characters max) and name (120 characters max) are required"), 400
        try:
            raw_credits = data.get("credits", 3)
            if isinstance(raw_credits, bool) or isinstance(raw_credits, float): raise ValueError
            credits = int(raw_credits)
        except (ValueError, TypeError): return jsonify(error="credits must be an integer"), 400
        if not 1 <= credits <= 10: return jsonify(error="credits must be between 1 and 10"), 400
        if Course.query.filter_by(code=code).first(): return jsonify(error="course code already exists"), 409
        course = Course(code=code, name=name, description=str(data.get("description", ""))[:2000], staff_id=user.id, credits=credits)
        db.session.add(course)
        try:
            db.session.flush(); audit(user.id, "create", "course", course.id); db.session.commit()
        except IntegrityError: db.session.rollback(); return jsonify(error="course code already exists"), 409
        return jsonify(id=course.id, code=course.code, name=course.name), 201

    @app.post("/api/courses/<int:course_id>/enroll")
    @roles("student")
    def enroll(course_id):
        user = current_user()
        if not db.session.get(Course, course_id): return jsonify(error="course not found"), 404
        if Enrollment.query.filter_by(course_id=course_id, user_id=user.id).first(): return jsonify(error="already enrolled"), 409
        enrollment = Enrollment(course_id=course_id, user_id=user.id); db.session.add(enrollment)
        try:
            db.session.flush(); audit(user.id, "enroll", "course", course_id); db.session.commit()
        except IntegrityError: db.session.rollback(); return jsonify(error="already enrolled"), 409
        return jsonify(id=enrollment.id, status="active"), 201

    @app.get("/api/deadlines")
    @jwt_required()
    def list_deadlines():
        user = current_user()
        include_closed = user.role == "staff" and request.args.get("include_closed", "false").lower() == "true"
        query = Deadline.query if include_closed else Deadline.query.filter_by(is_active=True)
        if user.role == "student": query = query.join(Course).join(Enrollment, Enrollment.course_id == Course.id).filter(Enrollment.user_id == user.id, Enrollment.status == "active")
        else: query = query.join(Course).filter(Course.staff_id == user.id)
        rows, page = list_page(query.order_by(Deadline.due_at))
        result = []
        for deadline in rows:
            course = db.session.get(Course, deadline.course_id)
            student_submission = Submission.query.filter_by(deadline_id=deadline.id, user_id=user.id).first() if user.role == "student" else None
            result.append({"id": deadline.id, "course_id": deadline.course_id, "course_code": course.code, "title": deadline.title,
                           "description": deadline.description, "due_at": as_utc(deadline.due_at).isoformat(), "max_marks": deadline.max_marks, "is_active": deadline.is_active,
                           "allow_resubmissions": deadline.allow_resubmissions, "max_attempts": deadline.max_attempts,
                           "submission_status": student_submission.status if student_submission else None,
                           "marks_obtained": student_submission.marks_obtained if student_submission else None,
                           "submission_attempt_count": student_submission.attempt_count if student_submission else 0})
        return paginated_json(result, page) if page else jsonify(result)

    @app.post("/api/deadlines")
    @roles("staff")
    def create_deadline():
        user = current_user(); data = request.get_json(silent=True) or {}
        try:
            course_id = int(data["course_id"])
            due_raw = data["due_at"]
            if not isinstance(due_raw, str): raise ValueError
            raw_marks = data["max_marks"]
            if isinstance(raw_marks, bool) or isinstance(raw_marks, float): raise ValueError
            due = as_utc(datetime.fromisoformat(due_raw.replace("Z", "+00:00"))); marks = int(raw_marks)
        except (KeyError, ValueError, TypeError): return jsonify(error="due_at (ISO-8601) and integer max_marks are required"), 400
        course = db.session.get(Course, course_id)
        if not course or course.staff_id != user.id: return jsonify(error="course not found or not owned by you"), 404
        if marks <= 0: return jsonify(error="max_marks must be positive"), 400
        allow_resubmissions = data.get("allow_resubmissions", False)
        try:
            max_attempts = int(data.get("max_attempts", 2 if allow_resubmissions else 1))
        except (ValueError, TypeError): return jsonify(error="max_attempts must be an integer"), 400
        if not isinstance(allow_resubmissions, bool) or not 1 <= max_attempts <= 10 or (allow_resubmissions and max_attempts < 2) or (not allow_resubmissions and max_attempts != 1):
            return jsonify(error="resubmission policy must be a boolean with 1–10 attempts; disabled policy allows one attempt"), 400
        title = str(data.get("title", "")).strip(); description = str(data.get("description", ""))
        if not title or len(title) > 160 or len(description) > 4000: return jsonify(error="title (160 characters max) and description (4000 characters max) are required"), 400
        deadline = Deadline(course_id=course.id, title=title, description=description, due_at=due, max_marks=marks, created_by=user.id,
                            allow_resubmissions=allow_resubmissions, max_attempts=max_attempts)
        db.session.add(deadline); db.session.flush(); audit(user.id, "create", "deadline", deadline.id)
        recipients = Enrollment.query.filter_by(course_id=course.id, status="active").all()
        for enrollment in recipients:
            db.session.add(Notification(user_id=enrollment.user_id, deadline_id=deadline.id, message=f"New assignment: {deadline.title}", kind="deadline"))
        db.session.commit()
        return jsonify(id=deadline.id, title=deadline.title), 201

    @app.patch("/api/deadlines/<int:deadline_id>")
    @roles("staff")
    def update_deadline(deadline_id):
        user = current_user(); deadline = db.session.get(Deadline, deadline_id); data = request.get_json(silent=True) or {}
        if not deadline: return jsonify(error="deadline not found"), 404
        course = db.session.get(Course, deadline.course_id)
        if not course or course.staff_id != user.id: return jsonify(error="deadline not found"), 404
        next_resubmissions = data.get("allow_resubmissions", deadline.allow_resubmissions)
        if not isinstance(next_resubmissions, bool): return jsonify(error="allow_resubmissions must be a boolean"), 400
        try: next_attempts = int(data.get("max_attempts", deadline.max_attempts))
        except (ValueError, TypeError): return jsonify(error="max_attempts must be an integer"), 400
        if isinstance(data.get("max_attempts", deadline.max_attempts), bool) or isinstance(data.get("max_attempts"), float):
            return jsonify(error="max_attempts must be an integer"), 400
        if not 1 <= next_attempts <= 10 or (next_resubmissions and next_attempts < 2):
            return jsonify(error="resubmissions require 2–10 maximum attempts"), 400
        changes = {}
        if "title" in data:
            title = str(data["title"]).strip()
            if not title or len(title) > 160: return jsonify(error="title is required and must be 160 characters or fewer"), 400
            changes["title"] = title
        if "description" in data:
            description = str(data["description"])
            if len(description) > 4000: return jsonify(error="description is too long"), 400
            changes["description"] = description
        if "due_at" in data:
            try: changes["due_at"] = as_utc(datetime.fromisoformat(str(data["due_at"]).replace("Z", "+00:00")))
            except ValueError: return jsonify(error="due_at must be ISO-8601"), 400
        if "max_marks" in data:
            try:
                if isinstance(data["max_marks"], (bool, float)): raise ValueError
                marks = int(data["max_marks"])
            except (ValueError, TypeError): return jsonify(error="max_marks must be a positive integer"), 400
            if marks <= 0: return jsonify(error="max_marks must be positive"), 400
            changes["max_marks"] = marks
        active = data.get("is_active", deadline.is_active)
        if not isinstance(active, bool): return jsonify(error="is_active must be a boolean"), 400
        old_title = deadline.title; old_due = as_utc(deadline.due_at); old_active = deadline.is_active
        deadline.title = changes.get("title", deadline.title)
        deadline.description = changes.get("description", deadline.description)
        deadline.due_at = changes.get("due_at", deadline.due_at)
        deadline.max_marks = changes.get("max_marks", deadline.max_marks)
        deadline.allow_resubmissions = next_resubmissions
        deadline.max_attempts = next_attempts if next_resubmissions else 1
        deadline.is_active = active
        if old_active != deadline.is_active or old_title != deadline.title or old_due != as_utc(deadline.due_at):
            if old_active != deadline.is_active:
                message = f"Assignment reopened: {deadline.title}" if deadline.is_active else f"Assignment closed: {deadline.title}"
            else:
                message = f"Assignment updated: {deadline.title}"
            course_students = Enrollment.query.filter_by(course_id=course.id, status="active").all()
            for enrollment in course_students:
                db.session.add(Notification(user_id=enrollment.user_id, deadline_id=deadline.id, message=message, kind="deadline"))
        audit(user.id, "update", "deadline", deadline.id); db.session.commit()
        return jsonify(id=deadline.id, title=deadline.title, is_active=deadline.is_active, due_at=as_utc(deadline.due_at).isoformat(),
                       allow_resubmissions=deadline.allow_resubmissions, max_attempts=deadline.max_attempts)

    @app.get("/api/projects")
    @roles("student")
    def list_projects():
        user = current_user()
        archived = request.args.get("archived", "false").lower() == "true"
        rows, page = list_page(Project.query.filter_by(user_id=user.id, is_archived=archived).order_by(Project.created_at.desc()))
        result = []
        for project in rows:
            tasks = PersonalTask.query.filter_by(user_id=user.id, project_id=project.id, is_archived=False).all()
            files = ProjectFile.query.filter_by(project_id=project.id).order_by(ProjectFile.uploaded_at.desc()).all()
            linked = ProjectDeadline.query.filter_by(user_id=user.id, project_id=project.id).all()
            result.append({"id": project.id, "name": project.name, "description": project.description, "color": project.color,
                           "task_count": len(tasks), "completed_count": sum(task.is_complete for task in tasks),
                           "files": [{"id": item.id, "file_name": item.file_name, "uploaded_at": as_utc(item.uploaded_at).isoformat()} for item in files],
                           "deadlines": [{"id": item.deadline_id, "title": db.session.get(Deadline, item.deadline_id).title} for item in linked if db.session.get(Deadline, item.deadline_id)]})
        return paginated_json(result, page) if page else jsonify(result)

    @app.post("/api/projects")
    @roles("student")
    def create_project():
        user = current_user(); data = request.get_json(silent=True) or {}
        name = str(data.get("name", "")).strip(); description = str(data.get("description", "")).strip()
        color = str(data.get("color", "#167354"))
        if not name or len(name) > 120: return jsonify(error="project name is required and must be 120 characters or fewer"), 400
        if len(description) > 2000 or not re.fullmatch(r"#[0-9a-fA-F]{6}", color): return jsonify(error="description or color is invalid"), 400
        project = Project(user_id=user.id, name=name, description=description, color=color)
        db.session.add(project); db.session.flush(); audit(user.id, "create", "project", project.id); db.session.commit()
        return jsonify(id=project.id, name=project.name), 201

    @app.patch("/api/projects/<int:project_id>")
    @roles("student")
    def update_project(project_id):
        user = current_user(); project = db.session.get(Project, project_id); data = request.get_json(silent=True) or {}
        if not project or project.user_id != user.id: return jsonify(error="project not found"), 404
        changes = {}
        if "name" in data:
            name = str(data["name"]).strip()
            if not name or len(name) > 120: return jsonify(error="project name is required and must be 120 characters or fewer"), 400
            changes["name"] = name
        if "description" in data:
            description = str(data["description"]).strip()
            if len(description) > 2000: return jsonify(error="description is too long"), 400
            changes["description"] = description
        if "color" in data:
            color = str(data["color"])
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", color): return jsonify(error="color must be a six-digit hex value"), 400
            changes["color"] = color
        if "is_archived" in data:
            if not isinstance(data["is_archived"], bool): return jsonify(error="is_archived must be a boolean"), 400
            changes["is_archived"] = data["is_archived"]
        for field, value in changes.items(): setattr(project, field, value)
        audit(user.id, "update", "project", project.id); db.session.commit()
        return jsonify(id=project.id, name=project.name, is_archived=project.is_archived)

    @app.post("/api/projects/<int:project_id>/files")
    @roles("student")
    def upload_project_file(project_id):
        user = current_user(); project = db.session.get(Project, project_id)
        if not project or project.user_id != user.id or project.is_archived: return jsonify(error="active project not found"), 404
        uploaded = request.files.get("file")
        allowed = {"pdf", "docx", "txt", "zip", "py", "java", "cpp", "c", "js", "md", "png", "jpg", "jpeg", "csv", "xlsx"}
        try: file_name, file_size = validate_upload(uploaded, allowed, app.config["MAX_UPLOAD_BYTES"])
        except UploadRejected as error: return jsonify(error=str(error)), error.status_code
        except ScannerUnavailable as error: return jsonify(error=str(error)), 503
        used_bytes, file_count = user_storage_usage(user.id)
        if file_count >= app.config["MAX_USER_FILES"]: return jsonify(error="your account has reached its stored-file limit"), 413
        if used_bytes + file_size > app.config["MAX_USER_STORAGE_BYTES"]: return jsonify(error="your account storage quota would be exceeded"), 413
        file_key = f"project_{uuid.uuid4().hex}_{file_name}"
        uploaded.save(upload_dir / file_key)
        row = ProjectFile(project_id=project.id, file_key=file_key, file_name=file_name, size_bytes=file_size); db.session.add(row)
        try:
            db.session.flush(); audit(user.id, "upload", "project_file", row.id); db.session.commit()
        except Exception:
            db.session.rollback(); (upload_dir / file_key).unlink(missing_ok=True); raise
        return jsonify(id=row.id, file_name=row.file_name), 201

    @app.get("/api/projects/<int:project_id>/files/<int:file_id>")
    @roles("student")
    def download_project_file(project_id, file_id):
        user = current_user(); project = db.session.get(Project, project_id); row = db.session.get(ProjectFile, file_id)
        if not project or project.user_id != user.id or not row or row.project_id != project.id: return jsonify(error="file not found"), 404
        path = upload_dir / row.file_key
        if not path.is_file(): return jsonify(error="file not found"), 404
        return send_file(path, as_attachment=True, download_name=row.file_name)

    @app.delete("/api/projects/<int:project_id>/files/<int:file_id>")
    @roles("student")
    def delete_project_file(project_id, file_id):
        user = current_user(); project = db.session.get(Project, project_id); row = db.session.get(ProjectFile, file_id)
        if not project or project.user_id != user.id or not row or row.project_id != project.id: return jsonify(error="file not found"), 404
        file_key = row.file_key
        audit(user.id, "delete", "project_file", row.id); db.session.delete(row); db.session.commit()
        (upload_dir / file_key).unlink(missing_ok=True)
        return jsonify(message="project file deleted")

    @app.post("/api/projects/<int:project_id>/deadlines/<int:deadline_id>")
    @roles("student")
    def link_project_deadline(project_id, deadline_id):
        user = current_user(); project = db.session.get(Project, project_id); deadline = db.session.get(Deadline, deadline_id)
        if not project or project.user_id != user.id or project.is_archived or not deadline or not deadline.is_active: return jsonify(error="active project or deadline not found"), 404
        enrolled = Enrollment.query.filter_by(user_id=user.id, course_id=deadline.course_id, status="active").first()
        if not enrolled: return jsonify(error="enrollment required"), 403
        if ProjectDeadline.query.filter_by(user_id=user.id, project_id=project.id, deadline_id=deadline.id).first(): return jsonify(error="deadline already linked"), 409
        link = ProjectDeadline(user_id=user.id, project_id=project.id, deadline_id=deadline.id); db.session.add(link)
        audit(user.id, "link", "project_deadline", link.id); db.session.commit()
        return jsonify(project_id=project.id, deadline_id=deadline.id), 201

    @app.delete("/api/projects/<int:project_id>/deadlines/<int:deadline_id>")
    @roles("student")
    def unlink_project_deadline(project_id, deadline_id):
        user = current_user(); link = ProjectDeadline.query.filter_by(user_id=user.id, project_id=project_id, deadline_id=deadline_id).first()
        if not link: return jsonify(error="linked deadline not found"), 404
        project = db.session.get(Project, project_id)
        if not project or project.user_id != user.id: return jsonify(error="project not found"), 404
        db.session.delete(link); audit(user.id, "unlink", "project_deadline", link.id); db.session.commit()
        return jsonify(message="deadline unlinked")

    @app.get("/api/personal-tasks")
    @roles("student")
    def list_personal_tasks():
        user = current_user()
        archived = request.args.get("archived", "false").lower() == "true"
        tasks, page = list_page(PersonalTask.query.filter_by(user_id=user.id, is_archived=archived).order_by(PersonalTask.is_complete, PersonalTask.due_at))
        risk_context = build_task_risk_context(user, tasks)
        result = []
        for task in tasks:
            subtasks = risk_context["subtasks_by_task"].get(task.id, [])
            result.append({"id": task.id, "title": task.title, "description": task.description, "due_at": as_utc(task.due_at).isoformat(),
                           "priority": task.priority, "recurrence": task.recurrence, "is_complete": task.is_complete, "is_archived": task.is_archived,
                           "project_id": task.project_id, "risk": task_risk(task, user, risk_context),
                           "subtasks": [{"id": sub.id, "title": sub.title, "is_complete": sub.is_complete} for sub in subtasks]})
        return paginated_json(result, page) if page else jsonify(result)

    @app.post("/api/personal-tasks")
    @roles("student")
    def create_personal_task():
        user = current_user(); data = request.get_json(silent=True) or {}
        title = str(data.get("title", "")).strip()
        try:
            due_raw = data["due_at"]
            if not isinstance(due_raw, str): raise ValueError
            due = as_utc(datetime.fromisoformat(due_raw.replace("Z", "+00:00")))
        except (KeyError, ValueError, TypeError): return jsonify(error="due_at in ISO-8601 format is required"), 400
        priority = data.get("priority", "medium")
        recurrence = data.get("recurrence", "none")
        project_id = data.get("project_id")
        if not title or len(title) > 160: return jsonify(error="title is required and must be 160 characters or fewer"), 400
        if priority not in ("low", "medium", "high"): return jsonify(error="priority must be low, medium, or high"), 400
        if recurrence not in ("none", "weekly", "monthly"): return jsonify(error="recurrence must be none, weekly, or monthly"), 400
        if isinstance(project_id, bool): return jsonify(error="project_id must be an integer"), 400
        try: project_id = int(project_id) if project_id else None
        except (ValueError, TypeError): return jsonify(error="project_id must be an integer"), 400
        project = db.session.get(Project, project_id) if project_id else None
        if project_id and (not project or project.user_id != user.id or project.is_archived): return jsonify(error="project not found"), 404
        task = PersonalTask(user_id=user.id, title=title, description=str(data.get("description", ""))[:2000], due_at=due, priority=priority, recurrence=recurrence, project_id=project.id if project else None)
        db.session.add(task); db.session.flush(); audit(user.id, "create", "personal_task", task.id); db.session.commit()
        return jsonify(id=task.id, title=task.title, due_at=as_utc(task.due_at).isoformat(), priority=task.priority, is_complete=False), 201

    @app.patch("/api/personal-tasks/<int:task_id>")
    @roles("student")
    def update_personal_task(task_id):
        user = current_user(); task = db.session.get(PersonalTask, task_id)
        if not task or task.user_id != user.id: return jsonify(error="task not found"), 404
        data = request.get_json(silent=True) or {}
        changes = {}
        if "title" in data:
            title = str(data["title"]).strip()
            if not title or len(title) > 160: return jsonify(error="title is required and must be 160 characters or fewer"), 400
            changes["title"] = title
        if "description" in data: changes["description"] = str(data["description"])[:2000]
        if "priority" in data:
            if data["priority"] not in ("low", "medium", "high"): return jsonify(error="priority must be low, medium, or high"), 400
            changes["priority"] = data["priority"]
        if "recurrence" in data:
            if data["recurrence"] not in ("none", "weekly", "monthly"): return jsonify(error="recurrence must be none, weekly, or monthly"), 400
            changes["recurrence"] = data["recurrence"]
        if "project_id" in data:
            raw_project_id = data["project_id"]
            if isinstance(raw_project_id, bool): return jsonify(error="project_id must be an integer"), 400
            try: parsed_project_id = int(raw_project_id) if raw_project_id else None
            except (ValueError, TypeError): return jsonify(error="project_id must be an integer"), 400
            project = db.session.get(Project, parsed_project_id) if parsed_project_id else None
            if parsed_project_id and (not project or project.user_id != user.id or project.is_archived): return jsonify(error="project not found"), 404
            changes["project_id"] = project.id if project else None
        if "is_archived" in data:
            if not isinstance(data["is_archived"], bool): return jsonify(error="is_archived must be a boolean"), 400
            changes["is_archived"] = data["is_archived"]
        if "due_at" in data:
            if not isinstance(data["due_at"], str): return jsonify(error="due_at must be ISO-8601"), 400
            try: changes["due_at"] = as_utc(datetime.fromisoformat(data["due_at"].replace("Z", "+00:00")))
            except ValueError: return jsonify(error="due_at must be ISO-8601"), 400
        if "is_complete" in data and not isinstance(data["is_complete"], bool): return jsonify(error="is_complete must be a boolean"), 400
        for field, value in changes.items(): setattr(task, field, value)
        create_next = False
        if "is_complete" in data:
            create_next = data["is_complete"] and not task.is_complete and task.recurrence != "none"
            task.is_complete = data["is_complete"]
            if data["is_complete"] and not TaskCompletion.query.filter_by(task_id=task.id).first():
                db.session.add(TaskCompletion(user_id=user.id, task_id=task.id))
        next_task = None
        if create_next:
            next_due = task.due_at
            now = datetime.now(timezone.utc)
            if task.recurrence == "weekly":
                next_due += timedelta(days=7)
                while as_utc(next_due) <= now: next_due += timedelta(days=7)
            else:
                def next_month(value):
                    month = (value.month % 12) + 1
                    year = value.year + (1 if value.month == 12 else 0)
                    return value.replace(year=year, month=month, day=min(value.day, calendar.monthrange(year, month)[1]))
                next_due = next_month(next_due)
                while as_utc(next_due) <= now:
                    next_due = next_month(next_due)
            next_task = PersonalTask(user_id=user.id, title=task.title, description=task.description, due_at=next_due, priority=task.priority, recurrence=task.recurrence, project_id=task.project_id)
            db.session.add(next_task)
            db.session.flush()
            for old_subtask in TaskSubtask.query.filter_by(task_id=task.id).all():
                db.session.add(TaskSubtask(task_id=next_task.id, title=old_subtask.title))
        audit(user.id, "update", "personal_task", task.id); db.session.commit()
        return jsonify(id=task.id, title=task.title, due_at=as_utc(task.due_at).isoformat(), priority=task.priority, recurrence=task.recurrence, project_id=task.project_id, is_archived=task.is_archived,
                       is_complete=task.is_complete, next_task_id=next_task.id if next_task else None)

    @app.delete("/api/personal-tasks/<int:task_id>")
    @roles("student")
    def delete_personal_task(task_id):
        user = current_user(); task = db.session.get(PersonalTask, task_id)
        if not task or task.user_id != user.id: return jsonify(error="task not found"), 404
        audit(user.id, "delete", "personal_task", task.id)
        TaskSubtask.query.filter_by(task_id=task.id).delete(synchronize_session=False)
        db.session.delete(task); db.session.commit()
        return jsonify(message="task deleted")

    @app.post("/api/personal-tasks/<int:task_id>/subtasks")
    @roles("student")
    def create_subtask(task_id):
        user = current_user(); task = db.session.get(PersonalTask, task_id)
        if not task or task.user_id != user.id: return jsonify(error="task not found"), 404
        data = request.get_json(silent=True) or {}; title = str(data.get("title", "")).strip()
        if not title or len(title) > 160: return jsonify(error="subtask title is required and must be 160 characters or fewer"), 400
        subtask = TaskSubtask(task_id=task.id, title=title); db.session.add(subtask); db.session.flush()
        audit(user.id, "create", "task_subtask", subtask.id); db.session.commit()
        return jsonify(id=subtask.id, title=subtask.title, is_complete=False), 201

    @app.patch("/api/personal-tasks/<int:task_id>/subtasks/<int:subtask_id>")
    @roles("student")
    def update_subtask(task_id, subtask_id):
        user = current_user(); task = db.session.get(PersonalTask, task_id); subtask = db.session.get(TaskSubtask, subtask_id)
        if not task or task.user_id != user.id or not subtask or subtask.task_id != task.id: return jsonify(error="subtask not found"), 404
        data = request.get_json(silent=True) or {}
        changes = {}
        if "is_complete" in data:
            if not isinstance(data["is_complete"], bool): return jsonify(error="is_complete must be a boolean"), 400
            changes["is_complete"] = data["is_complete"]
        if "title" in data:
            title = str(data["title"]).strip()
            if not title or len(title) > 160: return jsonify(error="subtask title is required"), 400
            changes["title"] = title
        for field, value in changes.items(): setattr(subtask, field, value)
        audit(user.id, "update", "task_subtask", subtask.id); db.session.commit()
        return jsonify(id=subtask.id, title=subtask.title, is_complete=subtask.is_complete)

    @app.get("/api/dashboard")
    @roles("student")
    def student_dashboard():
        user = current_user(); now = datetime.now(timezone.utc); horizon = now + timedelta(days=90)
        course_deadlines = Deadline.query.join(Course).join(Enrollment, Enrollment.course_id == Course.id).filter(
            Enrollment.user_id == user.id, Enrollment.status == "active", Deadline.is_active, Deadline.due_at <= horizon
        ).all()
        events = []
        for deadline in course_deadlines:
            course = db.session.get(Course, deadline.course_id)
            submission = Submission.query.filter_by(user_id=user.id, deadline_id=deadline.id).first()
            events.append({"id": f"deadline-{deadline.id}", "title": deadline.title, "due_at": as_utc(deadline.due_at).isoformat(),
                           "kind": "course", "course_code": course.code, "is_complete": bool(submission), "status": submission.status if submission else "todo"})
        tasks = PersonalTask.query.filter_by(user_id=user.id, is_archived=False).filter(PersonalTask.due_at <= horizon).all()
        risk_context = build_task_risk_context(user, tasks)
        for task in tasks:
            events.append({"id": f"task-{task.id}", "title": task.title, "due_at": as_utc(task.due_at).isoformat(),
                           "kind": "personal", "priority": task.priority, "project_id": task.project_id, "is_complete": task.is_complete,
                           "status": "complete" if task.is_complete else "todo", "risk": task_risk(task, user, risk_context)})
        events.sort(key=lambda item: item["due_at"])
        workload = {}
        for event in events:
            day = datetime.fromisoformat(event["due_at"]).date().isoformat()
            workload[day] = workload.get(day, 0) + int(not event["is_complete"])
        suggestions = []
        busy_days = {day: count for day, count in workload.items() if count >= 4}
        for day, count in sorted(busy_days.items()):
            candidate = next((event for event in events if event["kind"] == "personal" and not event["is_complete"]
                              and datetime.fromisoformat(event["due_at"]).date().isoformat() == day), None)
            if not candidate: continue
            due_day = datetime.fromisoformat(candidate["due_at"]).date()
            for offset in range(1, 8):
                target = (due_day + timedelta(days=offset)).isoformat()
                if workload.get(target, 0) < 3:
                    suggestions.append({"task_id": int(candidate["id"].split("-")[1]), "title": candidate["title"],
                                        "from": day, "suggested_date": target, "source_day_load": count,
                                        "target_day_load": workload.get(target, 0)})
                    break
        open_events = [event for event in events if not event["is_complete"]]
        overdue = [event for event in open_events if datetime.fromisoformat(event["due_at"]) < now]
        today_items = [event for event in open_events if datetime.fromisoformat(event["due_at"]).date() == now.date()]
        upcoming = [event for event in open_events if now <= datetime.fromisoformat(event["due_at"]) <= now + timedelta(days=7)]
        completions = TaskCompletion.query.filter_by(user_id=user.id).order_by(TaskCompletion.completed_at.desc()).all()
        completion_days = sorted({as_utc(item.completed_at).date() for item in completions}, reverse=True)
        current_streak = 0; cursor = now.date() if completion_days and completion_days[0] == now.date() else now.date() - timedelta(days=1)
        for day in completion_days:
            if day == cursor: current_streak += 1; cursor -= timedelta(days=1)
            elif day < cursor: break
        best_streak = 0; run = 0; previous = None
        for day in sorted(set(completion_days)):
            run = run + 1 if previous and day == previous + timedelta(days=1) else 1
            best_streak = max(best_streak, run); previous = day
        briefing = {"overdue": [{"title": e["title"], "kind": e["kind"], "due_at": e["due_at"]} for e in overdue[:5]],
                    "today": [{"title": e["title"], "kind": e["kind"], "due_at": e["due_at"]} for e in today_items[:5]],
                    "next_7_days": [{"title": e["title"], "kind": e["kind"], "due_at": e["due_at"], "risk": e.get("risk", {}).get("label", "on track")} for e in upcoming[:5]],
                    "message": "You have overdue work to review." if overdue else "Start with today's items." if today_items else "You are clear today. Preview the next seven days."}
        return jsonify(events=events, workload=workload, suggestions=suggestions, briefing=briefing,
                       streak={"current": current_streak, "best": best_streak, "completed_days": len(completion_days)},
                       summary={"open": len(open_events), "overdue": len(overdue), "next_7_days": len(upcoming), "due_today": len(today_items)})

    @app.get("/api/announcements")
    @jwt_required()
    def list_announcements():
        user = current_user(); query = Announcement.query.join(Course)
        if user.role == "student": query = query.join(Enrollment, Enrollment.course_id == Course.id).filter(Enrollment.user_id == user.id, Enrollment.status == "active")
        elif user.role == "staff": query = query.filter(Course.staff_id == user.id)
        rows = query.order_by(Announcement.created_at.desc()).limit(100).all()
        return jsonify([{"id": a.id, "course_id": a.course_id, "course_code": db.session.get(Course, a.course_id).code,
                        "title": a.title, "body": a.body, "created_at": as_utc(a.created_at).isoformat()} for a in rows])

    @app.post("/api/courses/<int:course_id>/announcements")
    @roles("staff")
    def create_announcement(course_id):
        user = current_user(); course = db.session.get(Course, course_id)
        if not course or course.staff_id != user.id: return jsonify(error="course not found or not owned by you"), 404
        data = request.get_json(silent=True) or {}; title = str(data.get("title", "")).strip(); body = str(data.get("body", "")).strip()
        if not title or len(title) > 160 or not body or len(body) > 4000: return jsonify(error="title and body are required and within length limits"), 400
        announcement = Announcement(course_id=course.id, author_id=user.id, title=title, body=body); db.session.add(announcement); db.session.flush()
        audit(user.id, "create", "announcement", announcement.id)
        for enrollment in Enrollment.query.filter_by(course_id=course.id, status="active").all():
            db.session.add(Notification(user_id=enrollment.user_id, message=f"Course update: {title}", kind="announcement"))
        db.session.commit(); return jsonify(id=announcement.id, title=announcement.title), 201

    @app.get("/api/analytics/overview")
    @roles("staff")
    def analytics_overview():
        user = current_user(); courses = Course.query.filter_by(staff_id=user.id).order_by(Course.code).all(); result=[]
        for course in courses:
            enrolled = Enrollment.query.filter_by(course_id=course.id, status="active").count()
            deadlines = Deadline.query.filter_by(course_id=course.id, is_active=True).all()
            deadline_data=[]
            for deadline in deadlines:
                submissions=Submission.query.filter_by(deadline_id=deadline.id).all()
                marks=[s.marks_obtained for s in submissions if s.marks_obtained is not None]
                deadline_data.append({"id":deadline.id,"title":deadline.title,"due_at":as_utc(deadline.due_at).isoformat(),"max_marks":deadline.max_marks,"enrolled":enrolled,
                                      "submitted":len(submissions),"late":sum(as_utc(s.submitted_at)>as_utc(deadline.due_at) for s in submissions),
                                      "submission_rate":round(100*len(submissions)/enrolled,1) if enrolled else 0,
                                      "average_mark":round(sum(marks)/len(marks),1) if marks else None})
            result.append({"id":course.id,"code":course.code,"name":course.name,"enrolled":enrolled,"deadlines":deadline_data})
        return jsonify(courses=result)

    @app.get("/api/admin/staff")
    @roles("admin")
    def list_staff_accounts():
        users=User.query.filter_by(role="staff").order_by(User.email).all()
        return jsonify([{"id":u.id,"email":u.email,"first_name":u.first_name,"last_name":u.last_name,"is_active":u.is_active} for u in users])

    @app.post("/api/admin/staff")
    @roles("admin")
    def create_staff_account():
        admin=current_user(); data=request.get_json(silent=True) or {}; email=str(data.get("email","")).strip().lower(); password=str(data.get("password",""))
        first=str(data.get("first_name","")).strip(); last=str(data.get("last_name","")).strip()
        if not email or "@" not in email or len(email)>254 or len(password)<12 or not first or not last:
            return jsonify(error="valid email, names, and password of at least 12 characters are required"),400
        if User.query.filter_by(email=email).first(): return jsonify(error="email already exists"),409
        staff=User(email=email,password_hash=generate_password_hash(password),role="staff",first_name=first,last_name=last)
        db.session.add(staff)
        try:
            db.session.flush(); audit(admin.id,"provision_staff","user",staff.id); db.session.commit()
        except IntegrityError: db.session.rollback(); return jsonify(error="email already exists"),409
        return jsonify(id=staff.id,email=staff.email,role=staff.role,is_active=True),201

    @app.patch("/api/admin/staff/<int:staff_id>")
    @roles("admin")
    def update_staff_account(staff_id):
        admin=current_user(); staff=db.session.get(User,staff_id); data=request.get_json(silent=True) or {}
        if not staff or staff.role!="staff": return jsonify(error="staff account not found"),404
        if not isinstance(data.get("is_active"),bool): return jsonify(error="is_active boolean is required"),400
        staff.is_active=data["is_active"]; audit(admin.id,"update_staff_status","user",staff.id); db.session.commit()
        return jsonify(id=staff.id,is_active=staff.is_active)

    @app.get("/api/submissions")
    @jwt_required()
    def list_submissions():
        user = current_user()
        query = Submission.query.join(Deadline)
        if user.role == "student":
            query = query.filter(Submission.user_id == user.id)
        else:
            query = query.join(Course, Course.id == Deadline.course_id).filter(Course.staff_id == user.id)
        rows, page = list_page(query.order_by(Submission.submitted_at.desc()))
        results = []
        for row in rows:
            deadline = db.session.get(Deadline, row.deadline_id)
            course = db.session.get(Course, deadline.course_id)
            student = db.session.get(User, row.user_id)
            results.append({"id": row.id, "deadline_id": row.deadline_id, "deadline_title": deadline.title,
                            "course_code": course.code, "student_name": f"{student.first_name} {student.last_name}",
                            "submitted_at": as_utc(row.submitted_at).isoformat(), "status": row.status, "note": row.note,
                            "file_name": row.file_name, "marks_obtained": row.marks_obtained,
                            "attempt_count": row.attempt_count,
                            "max_marks": deadline.max_marks, "feedback": row.feedback})
        return paginated_json(results, page) if page else jsonify(results)

    @app.get("/api/notifications")
    @jwt_required()
    def list_notifications():
        user = current_user(); rows, page = list_page(Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()))
        result = [{"id": n.id, "message": n.message, "kind": n.kind, "is_read": n.is_read, "created_at": as_utc(n.created_at).isoformat()} for n in rows]
        return paginated_json(result, page) if page else jsonify(result)

    @app.put("/api/notifications/<int:notification_id>/read")
    @jwt_required()
    def mark_notification_read(notification_id):
        user = current_user(); notification = db.session.get(Notification, notification_id)
        if not notification or notification.user_id != user.id: return jsonify(error="notification not found"), 404
        notification.is_read = True; db.session.commit()
        return jsonify(id=notification.id, is_read=True)

    @app.post("/api/submissions")
    @roles("student")
    def submit():
        user = current_user()
        data = request.form if request.content_type and request.content_type.startswith("multipart/form-data") else (request.get_json(silent=True) or {})
        try: deadline_id = int(data.get("deadline_id", ""))
        except (ValueError, TypeError): return jsonify(error="deadline_id is required"), 400
        deadline = db.session.get(Deadline, deadline_id)
        if not deadline or not deadline.is_active: return jsonify(error="deadline not found or closed"), 404
        if not Enrollment.query.filter_by(user_id=user.id, course_id=deadline.course_id, status="active").first(): return jsonify(error="enrollment required"), 403
        row = Submission.query.filter_by(user_id=user.id, deadline_id=deadline.id).first()
        if row and (not deadline.allow_resubmissions or row.attempt_count >= deadline.max_attempts):
            return jsonify(error="resubmission is not available for this assignment"), 409
        submitted_at = datetime.now(timezone.utc)
        due_at = deadline.due_at if deadline.due_at.tzinfo else deadline.due_at.replace(tzinfo=timezone.utc)
        status = "late" if submitted_at > due_at else "submitted"
        uploaded = request.files.get("file") if request.files else None
        file_key = file_name = None
        file_size = 0
        if uploaded and uploaded.filename:
            allowed = {"pdf", "docx", "txt", "zip", "py", "java", "cpp", "c", "js", "md"}
            try: file_name, file_size = validate_upload(uploaded, allowed, app.config["MAX_UPLOAD_BYTES"])
            except UploadRejected as error: return jsonify(error=str(error)), error.status_code
            except ScannerUnavailable as error: return jsonify(error=str(error)), 503
            used_bytes, file_count = user_storage_usage(user.id)
            if file_count >= app.config["MAX_USER_FILES"]: return jsonify(error="your account has reached its stored-file limit"), 413
            if used_bytes + file_size > app.config["MAX_USER_STORAGE_BYTES"]: return jsonify(error="your account storage quota would be exceeded"), 413
            file_key = f"{uuid.uuid4().hex}_{file_name}"
            uploaded.save(upload_dir / file_key)
        attempt_number = row.attempt_count + 1 if row else 1
        if row:
            row.note = str(data.get("note", ""))[:4000]
            if file_key: row.file_key = file_key; row.file_name = file_name; row.file_size_bytes = file_size
            row.status = status; row.submitted_at = submitted_at; row.marks_obtained = None; row.feedback = None; row.graded_by = None
            row.attempt_count = attempt_number
        else:
            row = Submission(user_id=user.id, deadline_id=deadline.id, note=str(data.get("note", ""))[:4000], file_key=file_key, file_name=file_name,
                             file_size_bytes=file_size, status=status, submitted_at=submitted_at, attempt_count=1)
            db.session.add(row)
        try:
            db.session.flush()
            db.session.add(SubmissionAttempt(submission_id=row.id, attempt_number=attempt_number, submitted_at=submitted_at,
                                             note=row.note, file_key=row.file_key, file_name=row.file_name, file_size_bytes=row.file_size_bytes, status=status))
            audit(user.id, "resubmit" if attempt_number > 1 else "submit", "submission", row.id); db.session.commit()
        except IntegrityError:
            db.session.rollback()
            if file_key and (upload_dir / file_key).exists(): (upload_dir / file_key).unlink()
            return jsonify(error="submission already exists"), 409
        return jsonify(id=row.id, status=row.status, submitted_at=as_utc(row.submitted_at).isoformat(), attempt_number=attempt_number), 201

    @app.get("/api/submissions/<int:submission_id>/attempts")
    @jwt_required()
    def list_submission_attempts(submission_id):
        user = current_user(); row = db.session.get(Submission, submission_id)
        if not row: return jsonify(error="submission not found"), 404
        deadline = db.session.get(Deadline, row.deadline_id); course = db.session.get(Course, deadline.course_id)
        if user.role not in ("student", "staff"): return jsonify(error="forbidden"), 403
        if user.role == "student" and row.user_id != user.id: return jsonify(error="forbidden"), 403
        if user.role == "staff" and course.staff_id != user.id: return jsonify(error="forbidden"), 403
        attempts = SubmissionAttempt.query.filter_by(submission_id=row.id).order_by(SubmissionAttempt.attempt_number).all()
        return jsonify([{"attempt_number": a.attempt_number, "submitted_at": as_utc(a.submitted_at).isoformat(), "status": a.status,
                        "note": a.note, "file_name": a.file_name} for a in attempts])

    @app.get("/api/submissions/<int:submission_id>/attempts/<int:attempt_number>/file")
    @jwt_required()
    def download_submission_attempt_file(submission_id, attempt_number):
        user = current_user(); row = db.session.get(Submission, submission_id)
        if not row: return jsonify(error="submission not found"), 404
        deadline = db.session.get(Deadline, row.deadline_id); course = db.session.get(Course, deadline.course_id)
        if user.role not in ("student", "staff"): return jsonify(error="forbidden"), 403
        if user.role == "student" and row.user_id != user.id: return jsonify(error="forbidden"), 403
        if user.role == "staff" and course.staff_id != user.id: return jsonify(error="forbidden"), 403
        attempt = SubmissionAttempt.query.filter_by(submission_id=row.id, attempt_number=attempt_number).first()
        if not attempt or not attempt.file_key: return jsonify(error="file not found"), 404
        path = upload_dir / attempt.file_key
        if not path.is_file(): return jsonify(error="file not found"), 404
        return send_file(path, as_attachment=True, download_name=attempt.file_name or "submission")

    @app.get("/api/submissions/<int:submission_id>/file")
    @jwt_required()
    def download_submission(submission_id):
        user = current_user(); row = db.session.get(Submission, submission_id)
        if not row or not row.file_key: return jsonify(error="file not found"), 404
        deadline = db.session.get(Deadline, row.deadline_id); course = db.session.get(Course, deadline.course_id)
        if user.role not in ("student", "staff"): return jsonify(error="forbidden"), 403
        if user.role == "student" and row.user_id != user.id: return jsonify(error="forbidden"), 403
        if user.role == "staff" and course.staff_id != user.id: return jsonify(error="forbidden"), 403
        path = upload_dir / row.file_key
        if not path.is_file(): return jsonify(error="file not found"), 404
        return send_file(path, as_attachment=True, download_name=row.file_name or "submission")

    @app.put("/api/submissions/<int:submission_id>/grade")
    @roles("staff")
    def grade(submission_id):
        user = current_user(); row = db.session.get(Submission, submission_id)
        if not row: return jsonify(error="submission not found"), 404
        deadline = db.session.get(Deadline, row.deadline_id); course = db.session.get(Course, deadline.course_id)
        if course.staff_id != user.id: return jsonify(error="forbidden"), 403
        data = request.get_json(silent=True) or {}
        try:
            if isinstance(data.get("marks_obtained"), bool) or isinstance(data.get("marks_obtained"), float): raise ValueError
            marks = int(data["marks_obtained"])
        except (KeyError, ValueError, TypeError): return jsonify(error="integer marks_obtained required"), 400
        if marks < 0 or marks > deadline.max_marks: return jsonify(error="marks out of range"), 400
        row.marks_obtained = marks; row.feedback = str(data.get("feedback", ""))[:4000]; row.graded_by = user.id; row.status = "graded"
        audit(user.id, "grade", "submission", row.id)
        db.session.add(Notification(user_id=row.user_id, deadline_id=deadline.id, message=f"Your work for {deadline.title} has been graded", kind="grade"))
        db.session.commit(); return jsonify(id=row.id, status=row.status, marks_obtained=marks)

    @app.get("/api/activity-logs")
    @roles("staff")
    def activity_logs():
        rows, page = list_page(ActivityLog.query.order_by(ActivityLog.occurred_at.desc()))
        result = [{"id": x.id, "user_id": x.user_id, "action": x.action, "entity_type": x.entity_type, "entity_id": x.entity_id, "occurred_at": as_utc(x.occurred_at).isoformat()} for x in rows]
        return paginated_json(result, page) if page else jsonify(result)

    @app.errorhandler(404)
    def not_found(_): return jsonify(error="not found"), 404

    @app.errorhandler(413)
    def too_large(_): return jsonify(error="file exceeds the 16 MB upload limit"), 413

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error("Request failed with an internal error: %s", error)
        db.session.rollback()
        return jsonify(error="internal server error; try again later"), 500

    return app


app = create_app()
if __name__ == "__main__":
    from reminders import start_reminder_scheduler
    reminder_scheduler = start_reminder_scheduler(app)
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")), debug=False)

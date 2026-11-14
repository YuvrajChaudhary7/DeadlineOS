import os
import uuid
import calendar
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, jwt_required
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from database import db, initialize_database
from models import ActivityLog, Announcement, Course, Deadline, Enrollment, Notification, PersonalTask, ReminderLog, Submission, TaskSubtask, User

load_dotenv()


def as_utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": os.getenv("FRONTEND_ORIGIN", "*")}})
    app.config.update(SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///deadlineos.db"), SQLALCHEMY_TRACK_MODIFICATIONS=False,
                      JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY", "local-development-secret-change-me"), JWT_ACCESS_TOKEN_EXPIRES=timedelta(minutes=15), MAX_CONTENT_LENGTH=16 * 1024 * 1024)
    JWTManager(app)
    initialize_database(app)
    upload_dir = Path(app.instance_path) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

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

    @app.get("/api/health")
    def health(): return jsonify(status="ok", service="DeadlineOS API")

    @app.post("/api/auth/register")
    def register():
        data = request.get_json(silent=True) or {}; email = str(data.get("email", "")).strip().lower(); password = str(data.get("password", ""))
        if not email or len(email) > 254 or "@" not in email or len(password) < 12:
            return jsonify(error="valid email and password of at least 12 characters required"), 400
        if User.query.filter_by(email=email).first(): return jsonify(error="email already registered"), 409
        # Public signup must never grant privileged staff access.
        role = data.get("role", "student")
        if role != "student": return jsonify(error="staff accounts must be provisioned by an administrator"), 403
        user = User(email=email, password_hash=generate_password_hash(password), role=role, first_name=str(data.get("first_name", "")).strip(), last_name=str(data.get("last_name", "")).strip())
        if not user.first_name or not user.last_name: return jsonify(error="first_name and last_name are required"), 400
        db.session.add(user); db.session.flush(); audit(user.id, "register", "user", user.id)
        try: db.session.commit()
        except IntegrityError: db.session.rollback(); return jsonify(error="email already registered"), 409
        return jsonify(id=user.id, email=user.email, role=user.role), 201

    @app.post("/api/auth/login")
    def login():
        data = request.get_json(silent=True) or {}; user = User.query.filter_by(email=str(data.get("email", "")).lower()).first()
        if not user or not user.is_active or not check_password_hash(user.password_hash, str(data.get("password", ""))): return jsonify(error="invalid credentials"), 401
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
        if not code or not name: return jsonify(error="code and name are required"), 400
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
        user = current_user(); query = Deadline.query.filter_by(is_active=True)
        if user.role == "student": query = query.join(Course).join(Enrollment, Enrollment.course_id == Course.id).filter(Enrollment.user_id == user.id, Enrollment.status == "active")
        else: query = query.join(Course).filter(Course.staff_id == user.id)
        rows = query.order_by(Deadline.due_at).all()
        result = []
        for deadline in rows:
            course = db.session.get(Course, deadline.course_id)
            student_submission = Submission.query.filter_by(deadline_id=deadline.id, user_id=user.id).first() if user.role == "student" else None
            result.append({"id": deadline.id, "course_id": deadline.course_id, "course_code": course.code, "title": deadline.title,
                           "description": deadline.description, "due_at": as_utc(deadline.due_at).isoformat(), "max_marks": deadline.max_marks,
                           "submission_status": student_submission.status if student_submission else None,
                           "marks_obtained": student_submission.marks_obtained if student_submission else None})
        return jsonify(result)

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
            due = datetime.fromisoformat(due_raw.replace("Z", "+00:00")); marks = int(raw_marks)
        except (KeyError, ValueError, TypeError): return jsonify(error="due_at (ISO-8601) and integer max_marks are required"), 400
        course = db.session.get(Course, course_id)
        if not course or course.staff_id != user.id: return jsonify(error="course not found or not owned by you"), 404
        if marks <= 0: return jsonify(error="max_marks must be positive"), 400
        deadline = Deadline(course_id=course.id, title=str(data.get("title", "")).strip(), description=data.get("description"), due_at=due, max_marks=marks, created_by=user.id)
        if not deadline.title: return jsonify(error="title is required"), 400
        db.session.add(deadline); db.session.flush(); audit(user.id, "create", "deadline", deadline.id)
        recipients = Enrollment.query.filter_by(course_id=course.id, status="active").all()
        for enrollment in recipients:
            db.session.add(Notification(user_id=enrollment.user_id, deadline_id=deadline.id, message=f"New assignment: {deadline.title}", kind="deadline"))
        db.session.commit()
        return jsonify(id=deadline.id, title=deadline.title), 201

    @app.get("/api/personal-tasks")
    @roles("student")
    def list_personal_tasks():
        user = current_user()
        tasks = PersonalTask.query.filter_by(user_id=user.id).order_by(PersonalTask.is_complete, PersonalTask.due_at).all()
        result = []
        for task in tasks:
            subtasks = TaskSubtask.query.filter_by(task_id=task.id).order_by(TaskSubtask.id).all()
            result.append({"id": task.id, "title": task.title, "description": task.description, "due_at": as_utc(task.due_at).isoformat(),
                           "priority": task.priority, "recurrence": task.recurrence, "is_complete": task.is_complete,
                           "subtasks": [{"id": sub.id, "title": sub.title, "is_complete": sub.is_complete} for sub in subtasks]})
        return jsonify(result)

    @app.post("/api/personal-tasks")
    @roles("student")
    def create_personal_task():
        user = current_user(); data = request.get_json(silent=True) or {}
        title = str(data.get("title", "")).strip()
        try:
            due_raw = data["due_at"]
            if not isinstance(due_raw, str): raise ValueError
            due = datetime.fromisoformat(due_raw.replace("Z", "+00:00"))
        except (KeyError, ValueError, TypeError): return jsonify(error="due_at in ISO-8601 format is required"), 400
        priority = data.get("priority", "medium")
        recurrence = data.get("recurrence", "none")
        if not title or len(title) > 160: return jsonify(error="title is required and must be 160 characters or fewer"), 400
        if priority not in ("low", "medium", "high"): return jsonify(error="priority must be low, medium, or high"), 400
        if recurrence not in ("none", "weekly", "monthly"): return jsonify(error="recurrence must be none, weekly, or monthly"), 400
        task = PersonalTask(user_id=user.id, title=title, description=str(data.get("description", ""))[:2000], due_at=due, priority=priority, recurrence=recurrence)
        db.session.add(task); db.session.flush(); audit(user.id, "create", "personal_task", task.id); db.session.commit()
        return jsonify(id=task.id, title=task.title, due_at=as_utc(task.due_at).isoformat(), priority=task.priority, is_complete=False), 201

    @app.patch("/api/personal-tasks/<int:task_id>")
    @roles("student")
    def update_personal_task(task_id):
        user = current_user(); task = db.session.get(PersonalTask, task_id)
        if not task or task.user_id != user.id: return jsonify(error="task not found"), 404
        data = request.get_json(silent=True) or {}
        if "title" in data:
            title = str(data["title"]).strip()
            if not title or len(title) > 160: return jsonify(error="title is required and must be 160 characters or fewer"), 400
            task.title = title
        if "description" in data: task.description = str(data["description"])[:2000]
        if "priority" in data:
            if data["priority"] not in ("low", "medium", "high"): return jsonify(error="priority must be low, medium, or high"), 400
            task.priority = data["priority"]
        if "recurrence" in data:
            if data["recurrence"] not in ("none", "weekly", "monthly"): return jsonify(error="recurrence must be none, weekly, or monthly"), 400
            task.recurrence = data["recurrence"]
        if "due_at" in data:
            if not isinstance(data["due_at"], str): return jsonify(error="due_at must be ISO-8601"), 400
            try: task.due_at = datetime.fromisoformat(data["due_at"].replace("Z", "+00:00"))
            except ValueError: return jsonify(error="due_at must be ISO-8601"), 400
        create_next = False
        if "is_complete" in data:
            if not isinstance(data["is_complete"], bool): return jsonify(error="is_complete must be a boolean"), 400
            create_next = data["is_complete"] and not task.is_complete and task.recurrence != "none"
            task.is_complete = data["is_complete"]
        next_task = None
        if create_next:
            next_due = task.due_at
            now = datetime.now(timezone.utc)
            if task.recurrence == "weekly":
                while as_utc(next_due) <= now: next_due += timedelta(days=7)
            else:
                while as_utc(next_due) <= now:
                    month = (next_due.month % 12) + 1
                    year = next_due.year + (1 if next_due.month == 12 else 0)
                    next_due = next_due.replace(year=year, month=month, day=min(next_due.day, calendar.monthrange(year, month)[1]))
            next_task = PersonalTask(user_id=user.id, title=task.title, description=task.description, due_at=next_due, priority=task.priority, recurrence=task.recurrence)
            db.session.add(next_task)
            db.session.flush()
            for old_subtask in TaskSubtask.query.filter_by(task_id=task.id).all():
                db.session.add(TaskSubtask(task_id=next_task.id, title=old_subtask.title))
        audit(user.id, "update", "personal_task", task.id); db.session.commit()
        return jsonify(id=task.id, title=task.title, due_at=as_utc(task.due_at).isoformat(), priority=task.priority, recurrence=task.recurrence,
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
        if "is_complete" in data:
            if not isinstance(data["is_complete"], bool): return jsonify(error="is_complete must be a boolean"), 400
            subtask.is_complete = data["is_complete"]
        if "title" in data:
            title = str(data["title"]).strip()
            if not title or len(title) > 160: return jsonify(error="subtask title is required"), 400
            subtask.title = title
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
        tasks = PersonalTask.query.filter_by(user_id=user.id).filter(PersonalTask.due_at <= horizon).all()
        for task in tasks:
            events.append({"id": f"task-{task.id}", "title": task.title, "due_at": as_utc(task.due_at).isoformat(),
                           "kind": "personal", "priority": task.priority, "is_complete": task.is_complete, "status": "complete" if task.is_complete else "todo"})
        events.sort(key=lambda item: item["due_at"])
        return jsonify(events=events, summary={"open": sum(not event["is_complete"] for event in events),
                                             "overdue": sum(not event["is_complete"] and as_utc(datetime.fromisoformat(event["due_at"])) < now for event in events),
                                             "next_7_days": sum(not event["is_complete"] and as_utc(datetime.fromisoformat(event["due_at"])) <= now + timedelta(days=7) for event in events)})

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
        rows = query.order_by(Submission.submitted_at.desc()).all()
        results = []
        for row in rows:
            deadline = db.session.get(Deadline, row.deadline_id)
            course = db.session.get(Course, deadline.course_id)
            student = db.session.get(User, row.user_id)
            results.append({"id": row.id, "deadline_id": row.deadline_id, "deadline_title": deadline.title,
                            "course_code": course.code, "student_name": f"{student.first_name} {student.last_name}",
                            "submitted_at": as_utc(row.submitted_at).isoformat(), "status": row.status, "note": row.note,
                            "file_name": row.file_name, "marks_obtained": row.marks_obtained,
                            "max_marks": deadline.max_marks, "feedback": row.feedback})
        return jsonify(results)

    @app.get("/api/notifications")
    @jwt_required()
    def list_notifications():
        user = current_user(); rows = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).limit(50).all()
        return jsonify([{"id": n.id, "message": n.message, "kind": n.kind, "is_read": n.is_read, "created_at": as_utc(n.created_at).isoformat()} for n in rows])

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
        if not deadline or not deadline.is_active: return jsonify(error="deadline not found"), 404
        if not Enrollment.query.filter_by(user_id=user.id, course_id=deadline.course_id, status="active").first(): return jsonify(error="enrollment required"), 403
        if Submission.query.filter_by(user_id=user.id, deadline_id=deadline.id).first(): return jsonify(error="submission already exists"), 409
        submitted_at = datetime.now(timezone.utc)
        due_at = deadline.due_at if deadline.due_at.tzinfo else deadline.due_at.replace(tzinfo=timezone.utc)
        status = "late" if submitted_at > due_at else "submitted"
        uploaded = request.files.get("file") if request.files else None
        file_key = file_name = None
        if uploaded and uploaded.filename:
            file_name = secure_filename(uploaded.filename)
            allowed = {"pdf", "docx", "txt", "zip", "py", "java", "cpp", "c", "js", "md"}
            if not file_name or "." not in file_name or file_name.rsplit(".", 1)[1].lower() not in allowed:
                return jsonify(error="file type not allowed"), 400
            file_key = f"{uuid.uuid4().hex}_{file_name}"
            uploaded.save(upload_dir / file_key)
        row = Submission(user_id=user.id, deadline_id=deadline.id, note=str(data.get("note", ""))[:4000], file_key=file_key, file_name=file_name, status=status, submitted_at=submitted_at)
        db.session.add(row)
        try:
            db.session.flush(); audit(user.id, "submit", "submission", row.id); db.session.commit()
        except IntegrityError:
            db.session.rollback()
            if file_key and (upload_dir / file_key).exists(): (upload_dir / file_key).unlink()
            return jsonify(error="submission already exists"), 409
        return jsonify(id=row.id, status=row.status, submitted_at=as_utc(row.submitted_at).isoformat()), 201

    @app.get("/api/submissions/<int:submission_id>/file")
    @jwt_required()
    def download_submission(submission_id):
        user = current_user(); row = db.session.get(Submission, submission_id)
        if not row or not row.file_key: return jsonify(error="file not found"), 404
        deadline = db.session.get(Deadline, row.deadline_id); course = db.session.get(Course, deadline.course_id)
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
        rows = ActivityLog.query.order_by(ActivityLog.occurred_at.desc()).limit(100).all()
        return jsonify([{"id": x.id, "user_id": x.user_id, "action": x.action, "entity_type": x.entity_type, "entity_id": x.entity_id, "occurred_at": as_utc(x.occurred_at).isoformat()} for x in rows])

    @app.errorhandler(404)
    def not_found(_): return jsonify(error="not found"), 404

    @app.errorhandler(413)
    def too_large(_): return jsonify(error="file exceeds the 16 MB upload limit"), 413

    return app


app = create_app()
if __name__ == "__main__":
    from reminders import start_reminder_scheduler
    reminder_scheduler = start_reminder_scheduler(app)
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")), debug=False)

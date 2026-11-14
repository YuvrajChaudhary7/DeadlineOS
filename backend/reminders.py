from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.exc import IntegrityError

from database import db
from models import Deadline, Enrollment, Notification, PersonalTask, ReminderLog, Submission


def send_due_reminders(app):
    """Create one in-app reminder per user and source when due within 24 hours."""
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=24)
    with app.app_context():
        for task in PersonalTask.query.filter(PersonalTask.is_complete.is_(False), PersonalTask.due_at > now, PersonalTask.due_at <= cutoff).all():
            exists = ReminderLog.query.filter_by(user_id=task.user_id, source_type="personal_task", source_id=task.id).first()
            if exists: continue
            db.session.add(ReminderLog(user_id=task.user_id, source_type="personal_task", source_id=task.id))
            db.session.add(Notification(user_id=task.user_id, message=f"Due soon: {task.title}", kind="reminder"))
        deadlines = Deadline.query.filter(Deadline.is_active.is_(True), Deadline.due_at > now, Deadline.due_at <= cutoff).all()
        for deadline in deadlines:
            for enrollment in Enrollment.query.filter_by(course_id=deadline.course_id, status="active").all():
                if Submission.query.filter_by(user_id=enrollment.user_id, deadline_id=deadline.id).first(): continue
                exists = ReminderLog.query.filter_by(user_id=enrollment.user_id, source_type="deadline", source_id=deadline.id).first()
                if exists: continue
                db.session.add(ReminderLog(user_id=enrollment.user_id, source_type="deadline", source_id=deadline.id))
                db.session.add(Notification(user_id=enrollment.user_id, deadline_id=deadline.id, message=f"Due within 24 hours: {deadline.title}", kind="reminder"))
        try: db.session.commit()
        except IntegrityError: db.session.rollback()


def start_reminder_scheduler(app):
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(send_due_reminders, "interval", minutes=15, args=[app], id="deadlineos_due_reminders", replace_existing=True,
                      next_run_time=datetime.now(timezone.utc))
    scheduler.start()
    return scheduler

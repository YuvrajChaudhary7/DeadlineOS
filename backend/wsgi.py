"""Production WSGI entry point; one web worker also owns the reminder scheduler."""
import os

from app import app


reminder_scheduler = None
if os.getenv("ENABLE_REMINDERS", "true").lower() == "true":
    from reminders import start_reminder_scheduler

    reminder_scheduler = start_reminder_scheduler(app)

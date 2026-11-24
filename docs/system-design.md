# System design

## Problem and scope
DeadlineOS gives students a course deadline/submission workflow, a personal planner and project workspaces, and instructors a controlled publishing/grading workflow. The semester MVP supports registration/login, course enrollment, deadlines, policy-controlled resubmission history, grading, staff audit review, private personal tasks, recurrence, subtasks, project files, dashboard workload guidance and task archive history. Email and password recovery remain outside the MVP.

## Requirements
Functional: authenticate users; enforce role and ownership boundaries; create courses and assignments; enroll students; list relevant deadlines; capture timestamped submissions and late status; allow only instructor-configured bounded resubmissions; preserve attempt metadata; grade within maximum marks; retain audit events; derive course submission rates; let students manage private recurring tasks and subtasks in project workspaces; attach project files and relevant course dates; archive and restore personal work; combine course and personal dates in heatmap calendar; provide a deterministic quick-capture parser, explainable task risk estimate, optional workload rescheduling suggestions, daily briefing and private activity streak; remind students of dates; allow staff announcements and admin-provisioned instructor accounts.

Quality goals: relational integrity, ownership checks on writes, clear API errors, low-cost local demo, portable cloud path, protect credentials and student data, provide evaluation evidence.

## Data and transactions
Normalized entities are in `database/schema.sql`. Enrollment and current submission uniqueness are enforced in the database; a separate attempt table retains each resubmission. Project-to-deadline links are unique per student. Completion history has a unique task key so toggling a completed task cannot inflate streaks. Submission and grading operations are transactional. Passwords use Werkzeug password hashing. Deadlines use timezone-aware timestamps; clients send ISO-8601 offsets.

## Reminders and task planning
Student personal tasks are separate from academic deadlines. Optional weekly/monthly recurrence creates a future task when the current occurrence is completed; subtasks break large assignments into checkable steps. Project workspaces group tasks, course deadline links and private files. Risk scores are transparent heuristics using due date, priority, remaining subtasks and same-day open load. Workload suggestions only move personal tasks after a user action. The daily briefing is a live summary, not an email or scheduled job. A 15-minute in-process scheduler creates idempotent in-app reminders within 24 hours of due dates. For multi-replica production, move the scheduler to a single worker/managed job and deliver email through a queued provider; the unique reminder key protects against duplicate sends.

## Scale and availability
The MVP is one Flask API and relational DB, suitable for a classroom demo. First scaling step: stateless API replicas behind TLS ingress and managed PostgreSQL/Azure SQL. Add pooling, backups, monitoring and a queue for reminders. Store assignment binaries in private Blob Storage and keep only object metadata/key in SQL. Use SQL views initially for analytics, then a governed Power BI model. Split notification delivery only when independent scale or availability needs justify it.

## Trade-offs
SQLite simplifies setup but has limited concurrent writes; Docker targets PostgreSQL. Relational SQL is authoritative for academic state because integrity, joins and transactions matter. Cosmos DB is optional for flexible high-volume notifications, not a second source of truth. UI demo token uses browser session storage; production should use a secure HttpOnly cookie or managed identity provider with CSRF defenses.

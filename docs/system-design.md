# System design

## Problem and scope
DeadlineOS gives students a course deadline and submission workflow and instructors a controlled grading workflow. The semester MVP supports registration/login, course listing/creation/enrollment, deadline creation/listing, one submission per student per assignment, grading and staff audit review. Binary upload, email and password recovery are outside the current MVP.

## Requirements
Functional: authenticate users; enforce role and ownership boundaries; create courses and assignments; enroll students; list relevant deadlines; capture timestamped submissions and late status; grade within maximum marks; retain audit events; derive course submission rates; let students manage private recurring tasks and subtasks; combine course and personal dates in a calendar; remind students of dates; allow staff announcements and admin-provisioned instructor accounts.

Quality goals: relational integrity, ownership checks on writes, clear API errors, low-cost local demo, portable cloud path, protect credentials and student data, provide evaluation evidence.

## Data and transactions
Seven normalized entities are in `database/schema.sql`. Enrollment and submission uniqueness are enforced in the database, so concurrent duplicate requests cannot silently create duplicates. Submission and grading operations are transactional. Passwords use Werkzeug password hashing. Deadlines use timezone-aware timestamps; clients send ISO-8601 offsets.

## Reminders and task planning
Student personal tasks are separate from academic deadlines. Optional weekly/monthly recurrence creates a future task when the current occurrence is completed; subtasks break large assignments into checkable steps. A 15-minute in-process scheduler creates idempotent in-app reminders within 24 hours of due dates. For multi-replica production, move the scheduler to a single worker/managed job and deliver email through a queued provider; the unique reminder key protects against duplicate sends.

## Scale and availability
The MVP is one Flask API and relational DB, suitable for a classroom demo. First scaling step: stateless API replicas behind TLS ingress and managed PostgreSQL/Azure SQL. Add pooling, backups, monitoring and a queue for reminders. Store assignment binaries in private Blob Storage and keep only object metadata/key in SQL. Use SQL views initially for analytics, then a governed Power BI model. Split notification delivery only when independent scale or availability needs justify it.

## Trade-offs
SQLite simplifies setup but has limited concurrent writes; Docker targets PostgreSQL. Relational SQL is authoritative for academic state because integrity, joins and transactions matter. Cosmos DB is optional for flexible high-volume notifications, not a second source of truth. UI demo token uses browser session storage; production should use a secure HttpOnly cookie or managed identity provider with CSRF defenses.

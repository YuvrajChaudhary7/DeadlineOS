# Evaluation evidence pack

Use this checklist during the final presentation. Capture screenshots from the running application and keep the original files in a `docs/evaluation/evidence/` folder. Do not use demo-only screenshots as evidence of Azure deployment.

## Verified in this checkout

- Clean-install rehearsal: `python scripts/clean_install_check.py`
- Result: `Clean install OK: schema v4, 2 demo users, 1 course, 1 deadline, 1 project, 2 tasks`
- API/backup integration suite: `python -m unittest discover -s tests -v` (11 passing checks against local SQLite in this checkout).
- GitHub Actions is configured to repeat the suite against both SQLite and PostgreSQL and build the Docker image; the PostgreSQL job has not run from this workstation.
- Covered flows: student task/project ownership, archive behavior, instructor resubmission limits, closed-deadline rejection, private file access, upload content rejection and deletion, pagination metadata, login throttling, security/health headers, submission grading and notification delivery, SQLite backup/restore, corruption detection and preservation of pre-restore copies.
- Storage target in the local setup: SQLite. Docker Compose targets PostgreSQL; run the suite against PostgreSQL before claiming cross-database verification.

## Screenshots to capture during the live demo

1. Student dashboard showing workload heatmap, briefing and risk explanation.
2. Student project workspace with linked deadline, task and uploaded reference file.
3. Student submission history and received grade/feedback.
4. Instructor deadline and submission-management views.
5. Admin staff-account view and staff audit log.
6. VS Code terminal showing the clean-install check and passing test summary.
7. Database client showing `schema_migrations` and the relational tables / key constraints.

## Query evidence to capture

Run the corresponding examples from `database/queries.sql` and save screenshots or copy the actual result rows here after running against the demo database:

- Enrollments joined to courses and students.
- Upcoming deadlines scoped to enrolled courses.
- Submission status and marks by course.
- Workload count by due date.
- Audit events ordered by timestamp.

## Claims and limits to state

- The product flow and local database are implemented and tested; Azure SQL, Blob Storage, Cosmos DB and Power BI are architecture/design mappings unless the team separately provisions and demonstrates those services.
- ClamAV integration is optional. A configured scanner is fail-closed, but the scanner service itself was not exercised by the test suite.
- Workload/risk values are transparent heuristics, not predictive models. Suggestions only affect student-owned personal tasks after a user action.
- No screenshot is included until a student captures it from the real running application.

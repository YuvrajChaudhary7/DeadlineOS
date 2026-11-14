# API reference (MVP)

Base URL: `http://127.0.0.1:5000/api`. JSON requests use `Content-Type: application/json`; protected calls send `Authorization: Bearer <access_token>`. Login tokens expire after 15 minutes.

| Method/path | Role | Body / result |
|---|---|---|
| POST `/auth/register` | Public | `{email,password,first_name,last_name}`; creates student; staff role returns 403 |
| POST `/auth/login` | Public | `{email,password}`; token and profile |
| GET `/auth/me` | Signed in | Current profile |
| POST `/auth/logout` | Signed in | Records logout; client discards short-lived token |
| GET `/courses` | Signed in | Course list |
| POST `/courses` | Staff | `{code,name,description,credits?}` |
| POST `/courses/{id}/enroll` | Student | Enroll; duplicate returns 409 |
| GET `/deadlines` | Signed in | Staff active deadlines; students' enrolled-course deadlines |
| POST `/deadlines` | Course staff | `{course_id,title,due_at,max_marks,description?}` |
| POST `/submissions` | Student | Multipart `{deadline_id,note?,file?}`; allowed files up to 16 MB; duplicate 409; timestamp/status server-set |
| GET `/submissions` | Signed in | Own submissions for students; own course submissions for staff |
| GET `/submissions/{id}/file` | Submission owner or course staff | Downloads uploaded work; extension allowlist, 16 MB maximum |
| GET `/notifications` | Signed in | Current user's latest 50 notifications |
| PUT `/notifications/{id}/read` | Signed in | Marks own notification as read |
| GET `/personal-tasks` | Student | Own personal task list with subtasks |
| POST `/personal-tasks` | Student | `{title,due_at,description?,priority?,recurrence?}`; recurrence none/weekly/monthly |
| PATCH `/personal-tasks/{id}` | Owner student | Update fields/completion; completing a recurring task creates its next occurrence |
| DELETE `/personal-tasks/{id}` | Owner student | Delete a personal task |
| POST `/personal-tasks/{id}/subtasks` | Owner student | `{title}` |
| PATCH `/personal-tasks/{id}/subtasks/{subtask_id}` | Owner student | Update title or completion |
| GET `/dashboard` | Student | Combined 90-day course and personal deadline events and summary counts |
| GET `/announcements` | Signed in | Updates for the user's courses; admin can review all |
| POST `/courses/{id}/announcements` | Course staff | `{title,body}`; notifies enrolled students |
| GET `/analytics/overview` | Staff | Per-course enrollment, submission, late and grade metrics |
| GET `/admin/staff` | Admin | Staff account list |
| POST `/admin/staff` | Admin | Provision staff account with a temporary password |
| PATCH `/admin/staff/{id}` | Admin | Activate or suspend a staff account |
| PUT `/submissions/{id}/grade` | Owning course staff | `{marks_obtained,feedback?}` |
| GET `/activity-logs` | Staff | Latest 100 audit events |
| GET `/health` | Public | Service health |

Errors return JSON `{error}` with 400 validation, 401 unauthenticated, 403 role/ownership restriction, 404 missing resource, 409 duplicate. Production should add pagination, rate limits, request IDs and versioned schemas.

In-app due reminders run every 15 minutes while the API is started with `python backend/app.py` or Docker. A unique reminder source record prevents duplicate notifications. Email delivery is not configured.

# API reference (MVP)

Base URL: `http://127.0.0.1:5000/api`. JSON requests use `Content-Type: application/json`; protected calls send `Authorization: Bearer <access_token>`. Login tokens expire after 15 minutes.

| Method/path | Role | Body / result |
|---|---|---|
| POST `/auth/register` | Public | `{email,password,first_name,last_name}`; creates student; staff role returns 403 |
| POST `/auth/login` | Public | `{email,password}`; token and profile. Repeated failures are throttled per account/IP for the configured window (default: 5 account failures / 15 minutes); returns 429 with `Retry-After` |
| GET `/auth/me` | Signed in | Current profile |
| POST `/auth/logout` | Signed in | Records logout; client discards short-lived token |
| GET `/courses` | Signed in | Course list |
| POST `/courses` | Staff | `{code,name,description,credits?}` |
| POST `/courses/{id}/enroll` | Student | Enroll; duplicate returns 409 |
| GET `/deadlines` | Signed in | Staff active deadlines; students' enrolled-course deadlines. Staff may pass `?include_closed=true` to review closed work |
| POST `/deadlines` | Course staff | `{course_id,title,due_at,max_marks,description?,allow_resubmissions?,max_attempts?}` |
| PATCH `/deadlines/{id}` | Owning course staff | Edit title/date/marks/policy or set `is_active:false` to close; closed deadlines are hidden from students |
| POST `/submissions` | Student | Multipart `{deadline_id,note?,file?}`; policy-controlled resubmission appends an attempt and updates the current submission |
| GET `/submissions` | Signed in | Own submissions for students; own course submissions for staff |
| GET `/submissions/{id}/attempts` | Owner or course staff | Submission attempt number, time, status, note and file metadata |
| GET `/submissions/{id}/attempts/{number}/file` | Owner or course staff | Downloads that particular retained submission version |
| GET `/submissions/{id}/file` | Submission owner or course staff | Downloads uploaded work; extension allowlist, 16 MB maximum |
| GET `/notifications` | Signed in | Current user's notifications |
| PUT `/notifications/{id}/read` | Signed in | Marks own notification as read |
| GET `/personal-tasks?archived=true` | Student | Own active tasks (default) or archived history, with risk estimate and subtasks |
| POST `/personal-tasks` | Student | `{title,due_at,description?,priority?,recurrence?,project_id?}`; recurrence none/weekly/monthly |
| PATCH `/personal-tasks/{id}` | Owner student | Update fields, archive status or completion; completion logs streak activity and recurring task creates next occurrence |
| DELETE `/personal-tasks/{id}` | Owner student | Delete a personal task |
| POST `/personal-tasks/{id}/subtasks` | Owner student | `{title}` |
| PATCH `/personal-tasks/{id}/subtasks/{subtask_id}` | Owner student | Update title or completion |
| GET `/projects?archived=true` | Student | Own active workspaces (default) or archived workspaces with task/file/deadline summaries |
| POST `/projects` | Student | Create private project workspace |
| PATCH `/projects/{id}` | Owner student | Edit or archive workspace |
| POST `/projects/{id}/files` | Owner student | Upload an allowlisted private reference file (16 MB max) |
| GET `/projects/{id}/files/{file_id}` | Owner student | Download a private project file after ownership check |
| DELETE `/projects/{id}/files/{file_id}` | Owner student | Delete the private project file and its local stored object |
| POST/DELETE `/projects/{id}/deadlines/{deadline_id}` | Enrolled student | Link/unlink an enrolled course deadline to a workspace |
| GET `/dashboard` | Student | 90-day events, daily briefing, UTC workload counts, rescheduling suggestions and private streak summary |
| GET `/announcements` | Signed in | Updates for the user's courses; admin can review all |
| POST `/courses/{id}/announcements` | Course staff | `{title,body}`; notifies enrolled students |
| GET `/analytics/overview` | Staff | Per-course enrollment, submission, late and grade metrics |
| GET `/admin/staff` | Admin | Staff account list |
| POST `/admin/staff` | Admin | Provision staff account with a temporary password |
| PATCH `/admin/staff/{id}` | Admin | Activate or suspend a staff account |
| PUT `/submissions/{id}/grade` | Owning course staff | `{marks_obtained,feedback?}` |
| GET `/activity-logs` | Staff | Staff audit events |
| GET `/health` | Public | Checks API and database readiness; returns 503 when the database is unavailable |

Deadline, project, personal-task, submission, notification and activity-log list endpoints accept optional `?page=1&per_page=25` (page starts at 1; per-page is bounded to 100). They return the same JSON array shape and add an `X-Pagination` response header containing `page`, `per_page`, `total`, `pages`, `has_previous` and `has_next`. Omitting these parameters preserves the unpaged response for the current UI. Errors return JSON `{error}` with 400 validation, 401 unauthenticated, 403 role/ownership restriction, 404 missing resource, 409 duplicate or 429 throttled. Login throttling does not replace edge-level rate limiting for a public production service.

Task risk is a heuristic (due date, priority, unfinished subtasks and same-day open workload), not a prediction model. Dashboard heatmap colors are based on open due items. Workload suggestions move only student-owned personal tasks and require a user click; instructor deadlines are never changed by the balancer. Quick capture parses a bounded set of local date/time phrases in the browser and sends a normal validated task request; no AI service receives task text. Project binaries are local private files in this demo. Uploads enforce an extension allowlist, file-signature/format validation, a 16 MiB per-file limit, and configurable per-user byte/file quotas. Optional ClamAV INSTREAM scanning can be enabled; when configured, scanner failure rejects uploads. Production should use private Blob storage.

In-app due reminders run every 15 minutes while the API is started with `python backend/app.py` or Docker. A unique reminder source record prevents duplicate notifications. Email delivery is not configured.

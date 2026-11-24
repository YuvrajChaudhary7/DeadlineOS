# Entity relationship model

```mermaid
erDiagram
 USERS ||--o{ COURSES : teaches
 USERS ||--o{ ENROLLMENTS : joins
 COURSES ||--o{ ENROLLMENTS : contains
 COURSES ||--o{ DEADLINES : defines
 USERS ||--o{ DEADLINES : creates
 DEADLINES ||--o{ SUBMISSIONS : receives
 USERS ||--o{ SUBMISSIONS : submits
 USERS ||--o{ NOTIFICATIONS : receives
 USERS ||--o{ ACTIVITY_LOGS : performs
 USERS ||--o{ SUBMISSIONS : grades
 USERS ||--o{ PERSONAL_TASKS : plans
 PERSONAL_TASKS ||--o{ TASK_SUBTASKS : breaks_into
 USERS ||--o{ PROJECTS : owns
 PROJECTS ||--o{ PERSONAL_TASKS : groups
 PROJECTS ||--o{ PROJECT_FILES : contains
 PROJECTS ||--o{ PROJECT_DEADLINES : organizes
 DEADLINES ||--o{ PROJECT_DEADLINES : linked_to
 SUBMISSIONS ||--o{ SUBMISSION_ATTEMPTS : versions
 USERS ||--o{ TASK_COMPLETIONS : earns_private_activity
 PERSONAL_TASKS ||--o| TASK_COMPLETIONS : completes_once
 COURSES ||--o{ ANNOUNCEMENTS : publishes
 USERS ||--o{ REMINDER_LOGS : receives
```

The relational design separates accounts, coursework, planning workspaces and append-only history. `enrollments(user_id,course_id)`, current `submissions(deadline_id,user_id)`, submission attempt number and project-deadline links are constrained as unique keys. Project binaries stay outside the relational store; SQL retains opaque keys and metadata. Task completion has one event per task, preventing repeated toggles from inflating a streak. Course staff data is referenced, not copied into deadlines. See `database/schema.sql` for constraints and referential actions.

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
 COURSES ||--o{ ANNOUNCEMENTS : publishes
 USERS ||--o{ REMINDER_LOGS : receives
```

Seven core tables use surrogate primary keys. `enrollments(user_id,course_id)` and `submissions(deadline_id,user_id)` are candidate keys enforced as unique constraints. Each table stores attributes about one entity or relationship. Course staff data is referenced, not copied into deadlines. The documented attributes avoid repeating groups and transitive dependencies, giving a practical 3NF example. See `database/schema.sql` for checks and referential actions.

# Two-person work distribution

Both teammates should understand and review the whole system. Keep ownership clear to reduce merge conflicts; pair on integration and the final demo.

| Person A — backend, data model, system design | Person B — frontend, cloud security, DP-900 |
|---|---|
| `backend/app.py`, `backend/database.py`, `backend/models/`, reminder worker and account management | `frontend/` including dashboard/calendar, personal planner and staff screens |
| `database/` scripts and `docs/er-diagram.md` | `azure/` design notes and DP-900 data mapping |
| `docs/system-design.md`, `docs/architecture.md`, `docs/api-documentation.md` | `docs/threat-model.md`, `docs/security-checklist.md`, `docs/data-classification.md` |
| Docker/database integration, migrations, analytics and API contracts | Announcements, role-aware UI, usability/accessibility review and cloud deployment checklist |

## Shared milestones

1. Agree payloads and schema changes before parallel edits.
2. Person A merges a working API contract; Person B connects UI against it using seeded local accounts.
3. Review each other's changes, especially authorization boundaries, SQL changes and data exposure.
4. Run the demo guide together, record evidence (screenshots/query output), and list limitations honestly.

Suggested branches: `feature/person-a-backend` and `feature/person-b-frontend`. Use pull requests and `feat:`, `fix:`, `docs:`, `security:` commit prefixes. Each person reviews the other's changes.

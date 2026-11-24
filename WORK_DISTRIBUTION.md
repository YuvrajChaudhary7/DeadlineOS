# Two-person work distribution

Both teammates should understand and review the whole system. Keep ownership clear to reduce merge conflicts; pair on integration and the final demo.

| Person A — backend, data model, system design | Person B — frontend, cloud security, DP-900 |
|---|---|
| `backend/app.py`, `backend/database.py`, `backend/models/`, reminder worker and account management | `frontend/` including dashboard/calendar, personal planner and staff screens |
| `database/` scripts and `docs/er-diagram.md` | `azure/` design notes and DP-900 data mapping |
| `docs/system-design.md`, `docs/architecture.md`, `docs/api-documentation.md` | `docs/threat-model.md`, `docs/security-checklist.md`, `docs/data-classification.md` |
| Docker/database integration, migrations, analytics and API contracts | Announcements, role-aware UI, usability/accessibility review and cloud deployment checklist |

## Added semester features

| Person A — API, schema and integrity | Person B — student experience and cloud/DP-900 evidence |
|---|---|
| Project/task/file/submission-attempt/completion-event tables and additive migration | Project workspace screens, private file workflow and linked course deadlines |
| Ownership checks for workspace files, task archive, deadline edits and bounded resubmissions | Quick capture, heatmap, briefing, workload suggestions, risk labels, streak and archive UI |
| Explainable risk/workload responses, completion-history calculation and API integration checks | Accessible responsive controls and project/data classification/cloud storage documentation |
| DB schema/index/query updates and API contract | Demo walkthrough, responsive review and screenshots from the running app |
| Versioned schema migrations, upload validation/scanning hooks, quotas and paginated list APIs | Pagination controls in list screens, file delete controls, evaluation evidence pack and demo rehearsal |
| API/security regression tests and database clean-install behavior | UI accessibility review, screenshot capture and clean-install rehearsal on teammate's laptop |
| PostgreSQL CI workflow, login throttling, headers and backup/restore implementation | Azure OIDC resource setup, deployment workflow run, cloud storage/DB configuration and live demo evidence |

These rows describe proposed implementation/review ownership, not commit authorship. Each person should commit only changes they personally reviewed and made; the shared working copy does not prove who authored a feature.

## Shared milestones

1. Agree payloads and schema changes before parallel edits.
2. Person A merges a working API contract; Person B connects UI against it using seeded local accounts.
3. Review each other's changes, especially authorization boundaries, SQL changes and data exposure.
4. Run the demo guide together, record evidence (screenshots/query output), and list limitations honestly.

Suggested branches: `feature/person-a-backend` and `feature/person-b-frontend`. Use pull requests and `feat:`, `fix:`, `docs:`, `security:` commit prefixes. Each person reviews the other's changes.

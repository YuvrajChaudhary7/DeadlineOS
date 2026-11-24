# DP-900 data classification and service mapping

| Data | Shape | Example | Proposed store / reason |
|---|---|---|---|
| Accounts, enrollments, deadlines, grades | Structured relational | user, course, due date, marks | PostgreSQL locally; Azure SQL target for constraints, joins and transactions |
| Notifications, optional event envelopes | Semi-structured JSON | `{userId,kind,createdAt,read}` | Cosmos DB only if flexible high-scale access merits it; SQL remains authoritative for academic state |
| Assignment files | Unstructured binary | PDF, source archive | Private Azure Blob; SQL stores opaque object key and metadata |
| Course performance summaries | Curated analytical data | submissions per course, late rate | SQL views initially; Power BI model/report for visuals |
| Student personal task list | Structured relational | private title, due date, completion and priority | Same relational store; filter and enforce ownership by user ID |
| Project workspaces | Structured relational | private project names, descriptions, task/deadline associations | Same relational store; every read/write scoped to owner; archive by status |
| Project reference files | Unstructured binary plus metadata | notes, PDFs, code and spreadsheet attachments | Local private upload volume in demo; private Azure Blob target, SQL stores object key only |
| Submission attempts | Structured relational metadata plus private binary versions | attempt number, server timestamp, status, note and file metadata | SQL preserves resubmission history; private Blob target stores each version separately |
| Task activity streak | Structured event history | UTC task completion date | Relational event rows; private aggregate only, no public leaderboard |
| Course announcements and reminder state | Structured relational | course update, recipient, deduplication key | SQL for ownership, delivery history and duplicate prevention |

DP-900 concepts demonstrated: relational vs non-relational workloads, transactional vs analytical use, structured/semi-structured/unstructured classification and choosing storage from access patterns. Avoid secrets and unrestricted student details in reports. Apply least privilege, retention, encryption and privacy requirements before cloud use.

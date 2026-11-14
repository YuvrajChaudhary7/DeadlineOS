# DP-900 data classification and service mapping

| Data | Shape | Example | Proposed store / reason |
|---|---|---|---|
| Accounts, enrollments, deadlines, grades | Structured relational | user, course, due date, marks | PostgreSQL locally; Azure SQL target for constraints, joins and transactions |
| Notifications, optional event envelopes | Semi-structured JSON | `{userId,kind,createdAt,read}` | Cosmos DB only if flexible high-scale access merits it; SQL remains authoritative for academic state |
| Assignment files | Unstructured binary | PDF, source archive | Private Azure Blob; SQL stores opaque object key and metadata |
| Course performance summaries | Curated analytical data | submissions per course, late rate | SQL views initially; Power BI model/report for visuals |
| Student personal task list | Structured relational | private title, due date, completion and priority | Same relational store; filter and enforce ownership by user ID |
| Course announcements and reminder state | Structured relational | course update, recipient, deduplication key | SQL for ownership, delivery history and duplicate prevention |

DP-900 concepts demonstrated: relational vs non-relational workloads, transactional vs analytical use, structured/semi-structured/unstructured classification and choosing storage from access patterns. Avoid secrets and unrestricted student details in reports. Apply least privilege, retention, encryption and privacy requirements before cloud use.

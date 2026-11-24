# Threat model (STRIDE)

| Threat | Example | Current mitigation / follow-up |
|---|---|---|
| Spoofing | Stolen credentials or forged identity | Password hashes, JWT verification, short expiry and persistent login failure throttling. Add MFA/managed identity in production. |
| Tampering | Student edits another student's grade | Role and ownership checks, server-set submission timestamp/status, DB constraints. Add immutable centralized audit retention. |
| Repudiation | Staff denies changing grade | Actor/action/entity audit entries. Add before/after details and protected log export. |
| Information disclosure | Student reads another student's project file or submission attempt | Project file and attempt downloads check owner/course staff. Local files are private behind API checks; production must keep Blob public access disabled and use managed identity or short-lived scoped access. |
| Denial of service | Login or submission flood | Login throttling, request/body/file limits and per-user file quotas; production still needs WAF, monitoring and rate limiting on other sensitive routes. |
| Elevation of privilege | Student changes role or grades | Public registration accepts student role only; only admins provision staff, and the first admin is created through a trusted local CLI. Add MFA/managed identity before production. |

Trust boundaries: browser to API; API to database; cloud app to managed services. Treat browser input and client clocks as hostile. Credentials and student work are sensitive. HTTPS, secret injection, least privilege, backups and incident logging are deployment requirements.

## Added planner-specific cases

- **Tampering with a resubmission policy:** only the course owner can edit the deadline; API validation bounds attempts to 2–10 when enabled and the database check constraint encodes the policy for new databases. Existing SQLite databases receive additive columns and still rely on API validation.
- **Untrusted project attachment:** validate allowed extensions and basic content signatures/archive structure, sanitize display names, generate random storage keys, cap upload size and enforce per-user quotas. Optional ClamAV scanning rejects files when the configured scanner is unavailable. A production storage pipeline should quarantine and scan before downloads.
- **Misleading workload estimate:** risk scores use visible factors (due date, priority, incomplete steps and same-day load). Recommendations are suggestions, and only the student can move a personal task. They do not predict grades or automatically change course deadlines.
- **Private activity leakage:** completion streaks are derived from student-owned completion events and are shown only to that student; no public ranking endpoint exists.

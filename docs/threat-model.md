# Threat model (STRIDE)

| Threat | Example | Current mitigation / follow-up |
|---|---|---|
| Spoofing | Stolen credentials or forged identity | Password hashes, JWT verification and short expiry. Add MFA/managed identity and login throttling in production. |
| Tampering | Student edits another student's grade | Role and ownership checks, server-set submission timestamp/status, DB constraints. Add immutable centralized audit retention. |
| Repudiation | Staff denies changing grade | Actor/action/entity audit entries. Add before/after details and protected log export. |
| Information disclosure | Student sees another course's deadlines | Student deadline query filters active enrollments. Add object checks for every future read and private blob access. |
| Denial of service | Login or submission flood | Unique constraints; production must add rate limits, WAF, quotas and monitoring. |
| Elevation of privilege | Student changes role or grades | Public registration accepts student role only; only admins provision staff, and the first admin is created through a trusted local CLI. Add MFA/managed identity before production. |

Trust boundaries: browser to API; API to database; cloud app to managed services. Treat browser input and client clocks as hostile. Credentials and student work are sensitive. HTTPS, secret injection, least privilege, backups and incident logging are deployment requirements.

# Security checklist

- [x] Passwords use one-way Werkzeug hashes.
- [x] JWT access tokens expire after 15 minutes.
- [x] Role checks protect staff and student actions.
- [x] Staff ownership is checked for deadline creation and grading.
- [x] ORM-bound values avoid SQL string concatenation for input.
- [x] Unique and check constraints enforce business rules.
- [x] Activity log records authentication and key writes; read is staff-only.
- [x] `.env` is ignored and `.env.example` uses placeholders.
- [x] Public registration cannot assign the privileged staff role.
- [x] Personal task routes are student-only and return or mutate only the signed-in user's tasks.
- [x] Staff accounts can only be provisioned by a logged-in admin; bootstrap the first admin through the trusted local CLI.
- [x] Staff analytics and course announcements are scoped to courses owned by the signed-in staff member.
- [x] Due reminder generation is idempotent per user/source through a unique database constraint.
- [x] Project workspaces, project files, tasks and task history are scoped to the authenticated student.
- [x] Project file downloads verify workspace ownership; object names are generated server-side and filenames sanitized.
- [x] Course deadlines can only be edited/closed by their owning instructor; student resubmission count is enforced by server policy.
- [x] Submission attempts retain server timestamps and per-attempt metadata; downloads continue to check student/staff ownership.
- [x] Task completion history uses a unique task event to prevent repeat-toggle streak inflation.
- [x] Quick capture uses a local deterministic parser; raw task text is not sent to a third-party service.
- [x] Risk scores and workload suggestions are advisory, explainable, and do not move academic deadlines.
- [ ] Replace local JWT fallback; inject production secrets from a secret manager.
- [x] Set CSP, clickjacking, MIME-sniffing and referrer-policy headers; GitHub deployment health-checks HTTPS ingress.
- [x] Persist login failure counts with keyed hashes and short-window account/IP limits.
- [ ] Move JWTs from sessionStorage to an HttpOnly session design and add CSRF protection before a broader public rollout.
- [ ] Provision DB private networking, encryption, backups, firewall and managed identity.
- [x] Validate upload extensions and basic file signatures/archive structure; cap upload size and per-user storage/file quotas.
- [x] Provide optional ClamAV INSTREAM scanning; when configured, scanner errors reject uploads. Compose scanner service is opt-in under the `security` profile.
- [x] Let the owning student delete private project files and remove the corresponding local object.
- [ ] Add retention/deletion controls for archived workspaces, tasks and submission-attempt files.
- [x] Add checksum-verified SQLite/PostgreSQL plus uploads backup/restore tools, with explicit restore acknowledgement and pre-restore copies.
- [x] API integration checks cover task/project isolation, private file download ownership, bounded resubmission, closed deadlines, upload rejection/deletion, pagination headers, and submit-grade-notify flow.
- [ ] Expand route coverage to every project/deadline action and test against PostgreSQL before deployment.

This describes code and remaining deployment work; it is not a security certification.

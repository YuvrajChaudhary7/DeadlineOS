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
- [ ] Replace local JWT fallback; inject production secrets from a secret manager.
- [ ] Require HTTPS, secure HttpOnly cookies or equivalent, CSRF defense and CSP headers.
- [ ] Add rate limiting/lockout controls.
- [ ] Provision DB private networking, encryption, backups, firewall and managed identity.
- [ ] Add upload scanning and private Blob access before file upload is enabled.

This describes code and remaining deployment work; it is not a security certification.

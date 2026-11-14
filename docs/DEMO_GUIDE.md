# Evaluation demo guide

1. Start with `run.bat`; visit `/` and `/api/health`. Explain SQLite is the local setup option.
2. Sign in as staff and create a course from **Courses**, then publish an assignment from **Deadlines**.
3. Sign in as student, join that course, and view its deadlines; point out that unjoined courses do not expose assignments.
4. Open **My Tasks** as the student, add a personal project deadline, set its priority, and mark it complete. Explain how personal tasks remain separate from instructor assignments.
5. Create a recurring task and add checklist subtasks; complete it and show the next occurrence.
6. Submit a file and note; explain server timestamps, late calculation, private download authorization and unique `(deadline,user)` protection.
7. Sign back in as staff, review the submission list, download work, grade within maximum marks, then show the student notification and feedback.
8. Post a course announcement and show the student inbox update. Review staff analytics and activity history.
9. Show the combined calendar, the due-soon reminder in Inbox (for an item due within 24 hours), and the admin staff account page. Bootstrap an admin with `python backend/manage.py create-admin` if one is not already provisioned.
10. Show schema, join query, views, indexes and PostgreSQL procedure/trigger examples. Explain local ORM creates SQLite schema. Present architecture, STRIDE and DP-900 data mapping; point out cloud controls still to configure.

Capture real screenshots and query output after running the demo. Local uploads are stored under Flask's instance directory; production should replace this with private Blob Storage. No cloud resources are provisioned.

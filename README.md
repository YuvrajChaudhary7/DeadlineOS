# DeadlineOS

DeadlineOS is a student and staff deadline management app built as a two-person semester project. Students enroll in courses, see deadlines, submit work and review grades. Staff create courses and deadlines, grade submissions and review an audit trail.

## Live demo

[Open DeadlineOS](https://deadlineos-app.wonderfulpond-3d54e124.centralindia.azurecontainerapps.io/)

## Run locally (Windows)

1. Install Python 3.10 or later.
2. Start the app from the project folder. If PowerShell is currently in the parent folder that contains `DeadlineOS`, run:

   ```powershell
   .\DeadlineOS\run.bat
   ```

   Or enter the project folder first, then run the launcher:

   ```powershell
   cd .\DeadlineOS
   .\run.bat
   ```

   You can also double-click `run.bat` from inside the `DeadlineOS` folder.
3. Keep the terminal window open while the app is running. Open `http://127.0.0.1:5000/` for the app, or `http://127.0.0.1:5000/api/health` to verify the API. Press **Ctrl+C** in the terminal to stop it.

The app includes student and instructor flows for course enrollment, editable/closable assignments, policy-bounded resubmission history, private file submission, grading, feedback, announcements and staff activity review. Students have private project workspaces for personal tasks, linked course dates and files; a task planner with subtasks, recurring tasks, archive history and a private consistency streak; and a combined heatmap calendar with daily briefing, explainable risk estimates and optional workload rescheduling suggestions. Quick capture parses a limited set of date phrases locally in the browser and does not send task text to an AI service. Staff analytics and admin-managed staff accounts are included. Demo login (local only): `staff@university.edu` / `StaffPass123!` or `alice@university.edu` / `StudentPass123!`. Demo seeding is enabled by default. Set `SEED_DEMO=false` for non-demo use. Replace the development JWT key before deployment. Local assignment and project files are stored under Flask's instance directory.

To bootstrap the first administrator, run `python backend/manage.py create-admin` from the project folder and follow the prompts. Admins can provision or suspend instructor accounts from the Admin page. The API creates in-app due reminders every 15 minutes; email is not configured.

## Docker

Copy `.env.example` to `.env`, set a strong `JWT_SECRET_KEY` and `POSTGRES_PASSWORD`, then run `docker compose up --build`. Docker Compose uses PostgreSQL. Local `run.bat` uses SQLite. SQL examples document PostgreSQL concepts. Open `http://127.0.0.1:5000/` after the containers start.

## Repository layout

- backend/: Flask API, database models, authentication and admin commands.
- frontend/: browser app, styles and client-side flows.
- database/: relational SQL examples and query notes.
- docs/: architecture, API, security, deployment and evaluation guides.
- azure/: Azure storage, Cosmos DB and Power BI design notes.
- tests/: API, database and backup/restore checks.
- scripts/: clean-install and maintenance helpers.

## Evaluation map

- DBMS: normalized relational schema, constraints, indexes, joins, views, transaction-oriented routines and audit trigger examples in `database/`.
- System design: requirements, architecture, API boundaries, scaling choices and ERD in `docs/`.
- Cloud security: password hashing, short-lived JWT, role and ownership checks, ORM access, audit trail and threat model.
- DP-900: data mapping plus Azure SQL, Blob, Cosmos DB and Power BI design notes in `azure/`.

See `WORK_DISTRIBUTION.md` for the team plan and `docs/DEMO_GUIDE.md` for an evaluation walkthrough. A hosted demo is available above. The Azure reference notes describe architecture and setup; they don't imply every documented service or control is active in the demo.

For a disposable clean-install rehearsal, run `python scripts/clean_install_check.py` from the project root (or use the active virtual environment's Python). It creates a temporary SQLite database, verifies schema version 4 and the demo seed, then removes the temporary database. Existing databases are upgraded on application startup through additive, versioned migrations recorded in `schema_migrations`. Login throttling, defensive security headers, request/input limits, and actionable health/error responses are included. Run `python -m unittest discover -s tests -v` for API and backup/restore checks.

GitHub Actions runs the integration checks against SQLite and PostgreSQL on pushes and pull requests. After configuring Azure OIDC and an existing Container App as described in [`docs/deployment/github-actions-azure.md`](docs/deployment/github-actions-azure.md), deploy manually from the **Actions** tab. GitHub Pages cannot host the Flask API/database. Use [`docs/backup-restore.md`](docs/backup-restore.md) to back up both the database and uploaded files.

Run focused API checks with `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` on Windows or `python -m unittest discover -s tests -v` where `python` is available. Risk is a heuristic, workload guidance is advisory, and streaks are private; none of these should be presented as prediction or competition features.

# DeadlineOS

DeadlineOS is a deadline and coursework workspace for students and instructors. Students enroll in courses, plan personal work, submit assignments, and review grades. Instructors publish coursework, review submissions, and provide feedback. Administrators manage instructor access.

**Live demo:** [Open DeadlineOS](https://deadlineos-app.wonderfulpond-3d54e124.centralindia.azurecontainerapps.io/)

## What it includes

- Course enrollment, assignment deadlines, private submissions, resubmission history, grading, and feedback
- Student projects, private files, personal tasks, subtasks, recurrence, archiving, and linked course deadlines
- A calendar heatmap, daily briefing, workload suggestions, and explainable task risk labels
- Course announcements, in-app reminders, staff analytics, and activity history
- Student data download and account deletion controls
- Staff CSV export for submissions and grades
- Optional email-based password recovery

Task risk is a heuristic and workload suggestions are advisory. They are not predictions. Quick Capture parses supported date phrases in the browser; task text is not sent to an AI service.

## Run locally on Windows

### 1. Install Python

Install Python 3.10 or later. During installation, enable **Add Python to PATH**.

### 2. Start the app

Open PowerShell in the repository folder (the folder containing `run.bat`) and run:

```powershell
.\run.bat
```

If your terminal is in the parent folder that contains the repository folder named `DeadlineOS`, run:

```powershell
.\DeadlineOS\run.bat
```

The launcher creates `.venv`, installs the backend requirements, and starts Flask. Keep the terminal open while using the app. Press **Ctrl+C** there to stop the server.

Open the app at [http://127.0.0.1:5000/](http://127.0.0.1:5000/). Check API health at [http://127.0.0.1:5000/api/health](http://127.0.0.1:5000/api/health).

### Demo accounts

On a new local database, demo data is seeded by default:

| Role | Email | Password |
|---|---|---|
| Instructor | `staff@university.edu` | `StaffPass123!` |
| Student | `alice@university.edu` | `StudentPass123!` |

These are local demo credentials. Do not use them for a public deployment. Set `SEED_DEMO=false` for a non-demo database. Seeding happens only when the database has no users.

To create the first administrator, run this from the repository folder:

```powershell
.\.venv\Scripts\python.exe backend\manage.py create-admin
```

Follow the prompts to set the admin email and password. Administrators can provision or suspend instructor accounts in the **Admin** page.

## Run locally on macOS or Linux

From the repository folder, with Python 3.10 or later installed:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
python backend/app.py
```

Then open `http://127.0.0.1:5000/`. The local setup uses SQLite and does not require PostgreSQL.

## Optional configuration

Copy `.env.example` to `.env` and edit the values as needed. Local SQLite is the default. Existing databases are upgraded through versioned migrations when the app starts.

Password recovery is disabled until SMTP is configured. Set `APP_PUBLIC_URL`, `SMTP_HOST`, `SMTP_PORT`, and `SMTP_FROM`; add `SMTP_USERNAME` and `SMTP_PASSWORD` if your provider requires authentication. Set `SMTP_USE_SSL=true` for implicit TLS. Reset links expire after 30 minutes. Without SMTP, users need an administrator to help recover access.

Local uploads are stored under Flask's instance directory. The reminder worker creates in-app due reminders every 15 minutes; email reminders are not configured by default.

## Run with Docker Compose

Docker Compose runs the app with PostgreSQL. From the repository folder:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set a strong `JWT_SECRET_KEY` and a `POSTGRES_PASSWORD`, then start the services:

```powershell
docker compose up --build
```

Open `http://127.0.0.1:5000/`. Stop the services with **Ctrl+C**. Local `run.bat` uses SQLite; Docker Compose uses PostgreSQL. To enable the optional ClamAV service, configure `CLAMAV_HOST=clamav` and `CLAMAV_REQUIRED=true`, then start with:

```powershell
docker compose --profile security up --build
```

The first ClamAV startup can take time while it downloads signatures.

## Development and checks

Install dependencies using the local setup steps above, then run the integration checks from the repository folder:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

On macOS or Linux, activate `.venv` first and run:

```bash
python -m unittest discover -s tests -v
```

For a disposable SQLite clean-install rehearsal, run:

```powershell
.\.venv\Scripts\python.exe scripts\clean_install_check.py
```

This check uses and removes a temporary database. It does not reset the regular app database. GitHub Actions also runs integration checks against SQLite and PostgreSQL.

## Repository map

| Path | Contents |
|---|---|
| `backend/` | Flask API, SQLAlchemy models, authentication, upload handling, and admin commands |
| `frontend/` | Browser pages, styles, and JavaScript |
| `database/` | SQL schema, query, index, view, trigger, and procedure examples |
| `docs/` | System design, API reference, security, deployment, backup, and demo guides |
| `azure/` | Design notes for Azure Storage, Cosmos DB, and Power BI |
| `scripts/` | Setup, clean-install, backup, and restore helpers |
| `tests/` | API and backup/restore integration checks |

## Project and deployment notes

The project covers a normalized relational model, indexes and SQL examples, API boundaries, role and ownership checks, password hashing, short-lived JWTs, audit history, and cloud data design. See [`WORK_DISTRIBUTION.md`](WORK_DISTRIBUTION.md) for team responsibilities and [`docs/DEMO_GUIDE.md`](docs/DEMO_GUIDE.md) for an evaluation walkthrough.

The Azure documents describe a deployment design; they do not mean every Azure service is provisioned or active. The GitHub Actions deployment workflow requires the Azure resources and OIDC setup described in [`docs/deployment/github-actions-azure.md`](docs/deployment/github-actions-azure.md). GitHub Pages cannot host the Flask API, database, reminder worker, or private uploads. Use [`docs/backup-restore.md`](docs/backup-restore.md) to back up both the database and uploaded files.

Before deployment, set `ENVIRONMENT=production`, use a randomly generated `JWT_SECRET_KEY` with at least 32 characters, set `SEED_DEMO=false`, configure a production database and durable private file storage, and follow the security and networking guidance in the deployment docs. The hosted demo and Azure notes should not be treated as proof that production controls have been deployed.

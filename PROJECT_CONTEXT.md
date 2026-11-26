# DeadlineOS project context

DeadlineOS is a Flask application for managing course deadlines, submissions and personal student work. Students enroll in courses, submit work, review grades, and manage private projects and tasks. Staff manage courses, deadlines, submissions, grading, announcements and activity history.

The hosted demo is available at [DeadlineOS](https://deadlineos-app.wonderfulpond-3d54e124.centralindia.azurecontainerapps.io/). The demo URL identifies a deployed app; optional Azure integrations documented in this repository may still require separate configuration.

## Repository map

- backend/: Flask application, SQLAlchemy models, authentication and admin tooling.
- frontend/: browser interface, JavaScript and styles.
- database/: schema and PostgreSQL-oriented SQL examples.
- docs/: architecture, API, security, backup/restore, deployment and demo documentation.
- azure/: Azure storage, Cosmos DB and Power BI design references.
- tests/: application and backup/restore checks.
- scripts/: clean-install and supporting scripts.
- Dockerfile, docker-compose.yml: container setup with PostgreSQL.

## Main workflows

- Course enrollment, assignment publishing, private submissions, grading and feedback.
- Announcements, in-app due reminders, staff analytics and activity review.
- Private project workspaces, task planning, subtasks, recurrence, archive and completion history.
- Calendar heatmap, daily briefing and advisory workload/risk information.

Task risk is heuristic, workload suggestions are advisory, and personal streak information is private. Describe these features accordingly.

## Local development

On Windows, run run.bat; it creates a local virtual environment if needed, installs backend/requirements.txt, and starts the app. Visit http://127.0.0.1:5000/ or /api/health. The local runner uses SQLite. Docker Compose uses PostgreSQL and reads configuration from .env, which can be created from .env.example.

Demo seeding is enabled by default for an empty local database. The seeded login credentials in the README are for local evaluation only. Set a strong JWT_SECRET_KEY and disable demo seeding for non-demo use. Local uploads are stored in Flask's instance directory.

For the clean-install rehearsal and test commands, see the README. For a feature walkthrough, see docs/DEMO_GUIDE.md. Azure deployment setup and workflow details are in docs/deployment/github-actions-azure.md.
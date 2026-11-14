# DeadlineOS - Complete Project Context

## 1. PROJECT OVERVIEW

**Project Name:** DeadlineOS - Student & Staff Deadline Management System  
**Repository Location:** `C:\Users\amans\Downloads\Yuvraj\DeadlineOS-Cline`  
**Type:** Two-person team project  
**Evaluation Subjects:** DBMS, System Design, Cloud Security, DP-900 (PBL-III)

### What We're Building
DeadlineOS is a deadline management platform (NOT e-commerce) where staff create courses, set assignment deadlines, view submissions, and grade work; students enroll in courses, view upcoming/overdue deadlines, and submit assignments. System tracks late submissions, grades, feedback, and maintains a full activity audit trail.

---

## 2. COMPLETE FILE STRUCTURE (43 Files)

```
DeadlineOS-Cline/
├── run.bat
├── README.md
├── WORK_DISTRIBUTION.md
├── PROJECT_CONTEXT.md
├── .env.example
├── .gitignore
├── docker-compose.yml
├── backend/
│   ├── app.py
│   ├── auth.py
│   ├── database.py
│   ├── models/__init__.py
│   └── requirements.txt
├── database/
│   ├── schema.sql
│   ├── stored_procedures.sql
│   ├── triggers.sql
│   ├── views.sql
│   ├── indexes.sql
│   └── queries.sql
├── frontend/
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── deadlines.html
│   ├── courses.html
│   ├── css/style.css
│   ├── js/app.js
│   ├── js/auth.js
│   ├── js/register.js
│   ├── js/deadlines.js
│   └── js/courses.js
├── azure/
│   ├── storage/README.md
│   ├── cosmos-db/README.md
│   └── power-bi/README.md
├── scripts/
│   ├── setup.sh
│   └── deploy.sh
└── docs/
    ├── system-design.md
    ├── architecture.md
    ├── er-diagram.md
    ├── api-documentation.md
    ├── threat-model.md
    ├── security-checklist.md
    └── data-classification.md
```

## 3. DATABASE SCHEMA (7 Tables in 3NF)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| users | Student & staff accounts | user_id, username, email, password_hash, role, first_name, last_name, student_id, staff_id |
| courses | Course catalog | course_id, course_code, course_name, description, staff_id, credits |
| enrollments | Student-course relationships | enrollment_id, user_id, course_id, enrolled_at, status |
| deadlines | Assignments created by staff | deadline_id, course_id, title, description, due_date, max_marks, created_by, is_active |
| submissions | Student assignment submissions | submission_id, deadline_id, user_id, submitted_at, file_path, status, marks_obtained, feedback, graded_by |
| notifications | System notifications | notification_id, user_id, deadline_id, message, type, is_read, created_at |
| activity_logs | Audit trail | log_id, user_id, action, entity_type, entity_id, timestamp, ip_address |

---

## 4. BACKEND API ENDPOINTS (13+ Endpoints)

### Authentication
| Method | Endpoint | Auth | Role |
|--------|----------|------|------|
| POST | /api/auth/register | No | Public |
| POST | /api/auth/login | No | Public |
| POST | /api/auth/logout | Yes | All |
| GET | /api/auth/me | Yes | All |

### Courses
| Method | Endpoint | Auth | Role |
|--------|----------|------|------|
| GET | /api/courses | Yes | All |
| POST | /api/courses | Yes | Staff |
| POST | /api/courses/<id>/enroll | Yes | Student |

### Deadlines
| Method | Endpoint | Auth | Role |
|--------|----------|------|------|
| GET | /api/deadlines | Yes | All |
| POST | /api/deadlines | Yes | Staff |
| GET | /api/deadlines/<id> | Yes | All |

### Submissions
| Method | Endpoint | Auth | Role |
|--------|----------|------|------|
| POST | /api/submissions | Yes | Student |
| PUT | /api/submissions/<id>/grade | Yes | Staff |

### Activity Logs
| Method | Endpoint | Auth | Role |
|--------|----------|------|------|
| GET | /api/activity-logs | Yes | All |

## 5. SECURITY FEATURES IMPLEMENTED

| Feature | Implementation |
|---------|---------------|
| Role-Based Access Control | Student/Staff roles with middleware |
| Hashed Passwords | bcrypt with 12 rounds |
| JWT Authentication | Short-lived tokens (15 min expiry) |
| HTTPS Enforcement | Nginx SSL + HSTS header |
| SQL Injection Prevention | Parameterized queries via SQLAlchemy ORM |
| XSS Prevention | Output encoding + Content Security Policy |
| Secrets Management | .env file, excluded from git |
| Database Firewall | Azure SQL firewall + NSG |
| Activity Logging | ACTIVITY_LOGS table tracks all user actions |
| Course Ownership | Staff can only manage their own courses |

---

## 6. STORED PROCEDURES

| Procedure | Purpose |
|-----------|---------|
| submit_assignment() | Student submission with deadline validation |
| grade_submission() | Staff grades submissions with marks/feedback |
| create_deadline() | Staff creates deadlines with ownership verification |

---

## 7. TRIGGERS

| Trigger | Purpose |
|---------|---------|
| update_updated_at_column() | Auto-updates timestamps on changes |
| log_deadline_creation() | Logs deadline creation to audit trail |
| log_submission() | Logs submissions to activity_logs |
| prevent_duplicate_submission() | Prevents duplicate submissions |

---

## 8. VIEWS

| View | Purpose |
|------|---------|
| upcoming_deadlines | Student dashboard with submission status |
| submission_stats | Power BI analytics - submission rates per course |
| overdue_deadlines | Staff view of overdue submissions |


## 9. DEMO DATA (Auto-Seeded on First Run)

| Account | Email | Password | Role |
|---------|-------|----------|------|
| Staff | staff@university.edu | StaffPass123! | Staff |
| Student | alice@university.edu | StudentPass123! | Student |

Demo Courses: CS101 (Intro to Programming), MATH201 (Calculus II)
Demo Deadlines: 3 deadlines (including 1 overdue)
Demo Submission: 1 graded submission with feedback

---

## 10. HOW TO RUN (One-Click for Non-Tech Users)

1. Install Python from https://python.org (check "Add to PATH" during install)
2. Double-click run.bat in the project folder
3. Open browser to http://localhost:5000
4. Login with demo accounts above

What run.bat does:
- Checks Python is installed
- Installs Python requirements (pip install -r requirements.txt)
- Starts Flask backend
- Auto-creates SQLite database (no PostgreSQL needed)
- Auto-seeds demo data


## 11. TEAM WORK DISTRIBUTION (2 People)

### Person A (Backend/Database/System Design)
- System design documentation
- ER diagram and 3NF schema
- Stored procedures, triggers, views, indexes
- Backend Flask application
- API routes and database models
- Docker configuration

### Person B (Frontend/Cloud Security/Azure)
- Threat model (STRIDE analysis)
- Security checklist verification
- Data classification (structured/semi-structured/unstructured)
- Frontend HTML/CSS/JavaScript
- Role-based access implementation
- Azure Blob Storage, Cosmos DB, Power BI configurations
- .env.example, .gitignore, deployment scripts

---

## 12. SUBMISSION CHECKLIST (For Evaluation)

| Subject | Deliverable | Location | Status |
|---------|-------------|----------|--------|
| System Design | Design document with architecture diagram | docs/system-design.md, docs/architecture.md | Complete |
| RDBMS (DBMS) | ER diagram, schema script, query file | docs/er-diagram.md, database/schema.sql, database/queries.sql | Complete |
| DP-900 | Data classification note, Azure screenshots | docs/data-classification.md, azure/ | Complete |
| Cloud Security | Threat model, security checklist | docs/threat-model.md, docs/security-checklist.md | Complete |

Mentor's Note: "Mentioning a subject on a slide does not count. Each subject's minimum must be visible in your running application or its design."

---

## 13. RECOMMENDED IMPROVEMENTS (Optional)

### High Priority:
1. Dockerfile for backend (referenced in docker-compose.yml but missing)
2. Nginx configuration for HTTPS/SSL termination
3. Unit tests for authentication and API endpoints
4. Activity log page in frontend (visible Cloud Security requirement)
5. File upload for assignment submissions

### Medium Priority:
6. Email notifications for deadline reminders
7. Password reset functionality
8. Profile management (update user details)
9. Course deletion and editing
10. Bulk student enrollment

### Low Priority:
11. Calendar view for deadlines
12. File attachment viewing/download
13. Export submissions to CSV/Excel
14. Mobile-responsive improvements
15. Dark mode toggle


## 14. GIT WORKFLOW FOR 2-PERSON TEAM

1. Person A creates branch: feature/person-a-backend
2. Person B creates branch: feature/person-b-frontend
3. Work on assigned files
4. Create pull request to merge into main
5. Other person reviews and approves
6. Merge after approval
7. Use conventional commits: feat:, fix:, docs:, security:

---

## 15. KEY FILES BY SUBJECT

**System Design:** docs/system-design.md, docs/architecture.md, docs/api-documentation.md  
**RDBMS (DBMS):** docs/er-diagram.md, database/schema.sql, database/queries.sql, database/views.sql, database/stored_procedures.sql, database/triggers.sql, database/indexes.sql  
**DP-900:** docs/data-classification.md, azure/storage/README.md, azure/cosmos-db/README.md, azure/power-bi/README.md  
**Cloud Security:** docs/threat-model.md, docs/security-checklist.md, backend/auth.py, backend/app.py

---

*This document was generated as part of the DeadlineOS project setup. Save this file and convert to PDF if needed for submission.*


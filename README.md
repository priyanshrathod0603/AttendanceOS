# Face Attendance Management System

<p align="center">
  <strong>Real-time, camera-based attendance for schools — with face recognition, time rules, enterprise reporting, and a modern Flask dashboard.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Status-Active%20Development-007AFF?style=for-the-badge" alt="Active development">
  <img src="https://img.shields.io/badge/Python-3.14%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.14+">
  <img src="https://img.shields.io/badge/Flask-3.x-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/AI-InsightFace-6F42C1?style=for-the-badge" alt="InsightFace">
  <img src="https://img.shields.io/badge/Database-SQLite%20%7C%20PostgreSQL-336791?style=for-the-badge&logo=postgresql&logoColor=white" alt="Database support">
</p>

<p align="center">
  <a href="#-features">Features</a> ·
  <a href="#-installation">Installation</a> ·
  <a href="#-architecture">Architecture</a> ·
  <a href="#-api-endpoints">API</a> ·
  <a href="#-product-roadmap">Roadmap</a>
</p>

---

## ✨ Overview

Face Attendance Management System is a Flask-based school attendance application that processes live camera frames with **InsightFace** and **OpenCV**, matches enrolled student and teacher embeddings, and records daily IN/OUT attendance. It includes a responsive Jinja2 dashboard, camera management, student and teacher enrolment, attendance time rules, audit trails, reports, exports, and a local attendance-query assistant.

The application starts with SQLite by default (`krishna_erp.db`) and can use PostgreSQL when `DATABASE_URL` is configured. It is designed as a working school ERP attendance module; broader HR, payroll, mobile, cloud, and biometric capabilities are vision items, not implemented features.

> [!IMPORTANT]
> The project currently has no authentication, role-based login, liveness detection, QR/RFID capture, or outbound notification integration. Some of these names appear as persisted settings; they do not activate a corresponding implementation.

## 📚 Table of Contents

- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Architecture](#-architecture)
- [Folder Structure](#-folder-structure)
- [Installation](#-installation)
- [Configuration](#%EF%B8%8F-configuration)
- [Database](#%EF%B8%8F-database)
- [API Endpoints](#-api-endpoints)
- [Screenshots & Visual Prompts](#%EF%B8%8F-screenshots--visual-prompts)
- [Attendance Workflow](#-attendance-workflow)
- [Recognition Pipeline](#-recognition-pipeline)
- [Time Management Workflow](#%EF%B8%8F-time-management-workflow)
- [Export Formats](#-export-formats)
- [Enterprise Features](#-enterprise-features)
- [Security Notes](#-security-notes)
- [Product Roadmap](#-product-roadmap)
- [Why Choose This System?](#-why-choose-this-system)
- [Requirements](#-requirements)
- [How to Run](#-how-to-run)
- [Contributing](#-contributing)
- [License](#-license)
- [Author](#-author)

---

## 🚀 Features

### 🤖 Face Recognition

- InsightFace `buffalo_l` detects faces and generates **512-dimensional, L2-normalized embeddings**.
- Enrols the largest detected face from uploaded student and teacher images.
- Uses cosine similarity matching against active student and teacher embeddings.
- Supports a configurable match threshold in `config.py` (`FACE_MATCH_THRESHOLD`; default `0.35`).
- Refreshes running recognizers after face enrolment or data changes.
- Runs a recognition worker per managed camera and overlays names/confidence on MJPEG streams.

### 🏫 Enterprise Attendance

- Maintains separate normalized daily attendance records for students and teachers.
- Records immutable IN/OUT `attendance_events` with camera and confidence metadata.
- Supports manual enterprise attendance entry through the API.
- Provides filtered daily attendance, session, event, and enterprise summary endpoints.
- Shows live KPI cards, trends, hourly entries, attendance heatmap data, activity feed, camera health, and recognition statistics.

### 🎓 Student Management

- Create, search, filter, update, deactivate, and delete student records.
- Stores roll number, name, class, section, contact details, image path, activity state, and face embedding.
- Enforces unique roll numbers and normalizes class/section values.
- Uploads a student photo and creates an embedding only when a face is found.

### 👩‍🏫 Teacher Management

- Create, search, update, deactivate, and delete teacher records.
- Stores teacher ID, subject, department, designation, assigned classes, contacts, image path, and embedding.
- Supports teacher photo enrolment for live recognition.

### 📹 Camera Management & Live Monitoring

- Add, edit, delete, start, stop, test, and list camera sources.
- Supports numeric device indexes, RTSP/RTMP/HTTP(S) streams, local paths, and `file://` sources.
- Avoids duplicate physical camera sources through normalized source comparison.
- Exposes camera status including live-frame state, detected, recognized, and unknown face counts.
- Streams annotated live video as MJPEG at `/stream/<camera-id>`.
- Reconnects a capture after repeated frame-read failures.

### ⏱️ Time Management & Attendance Rules

- Configurable student and teacher time rules: office start/end, late, half-day, absent-after, OUT window, early exit, overtime, and minimum working minutes.
- Computes IN, OUT, late, half-day, early exit, overtime, and working duration for enterprise attendance.
- Supports weekly-off configuration and scoped holiday calendar records in the time-management module.
- Provides auditable edits for sessions, legacy attendance rows, rules, and holidays.
- Prevents an OUT mark until the configured OUT detection window opens.

### 📊 Reports, Dashboard & Search

- Standard dashboard metrics for students, teachers, attendance, unknown faces, cameras, entries, and exits.
- Enterprise dashboard widgets for seven-day trends, hourly entries, top late students, overtime teachers, early exits, working-hour distribution, and class heatmap data.
- Attendance and session filtering by date, class, section, department, designation, status, event type, camera, confidence, and search term (where supported by each endpoint).
- Report preview and exports for daily, weekly, monthly, yearly, class, department, student, teacher, late, half-day, working-hours, early-exit, overtime, and summary report types.

### 👤 Unknown Faces & AI Assistant

- Stores an `unknown_faces` model and exposes review/action APIs for unknown-face records.
- Unknown-face review actions are audited in `attendance_logs`.
- Includes an offline rule-based chat assistant for common attendance questions.
- Optionally falls back to a local Ollama model for unrecognized questions when enabled.

### 📤 Export Features

- Legacy attendance export to CSV, with PDF when `reportlab` is available.
- Enterprise report export to CSV, Excel (`openpyxl` required), PDF (`reportlab` required), printable HTML, or JSON.
- Graceful CSV fallback when optional PDF/Excel dependencies are absent.

### 📌 Not implemented yet

QR attendance, RFID, WhatsApp/SMS/email delivery, anti-spoofing, liveness detection, actual alert delivery, login/authentication, and mobile applications are **not implemented**. The enterprise settings endpoint can store toggles for several of these concepts, but it does not provide their operational integration.

---

## 🧰 Tech Stack

| Layer | Technology in this repository |
|---|---|
| **Backend** | Python, Flask, Flask-SQLAlchemy |
| **Frontend** | Jinja2 templates, vanilla JavaScript, CSS, Lucide icons, Google Inter font |
| **Database** | SQLite by default; PostgreSQL supported through SQLAlchemy + psycopg v3 |
| **AI models** | InsightFace `buffalo_l` model pack via ONNX Runtime |
| **Vision** | OpenCV, NumPy, Pillow |
| **NLP** | Rule-based local intent parser; optional Ollama HTTP fallback |
| **Reporting** | CSV built-ins; optional `openpyxl` and `reportlab` at runtime |
| **Tools/scripts** | pgAdmin SQL initializer, schema migration, seed data, smoke test, pytest tests |
| **Operating-system notes** | macOS/Apple Silicon is documented and explicitly handled for local webcam capture; OpenCV sources are also coded for non-macOS systems |

---

## 🏗️ Architecture

```mermaid
flowchart TD
    UI["Jinja2 + Vanilla JS Dashboard"] --> Flask["Flask Application\nRoutes & JSON APIs"]
    Flask --> Camera["RecognitionManager\nOne worker per camera"]
    Camera --> CV["OpenCV VideoCapture\nLive frames / MJPEG"]
    CV --> Engine["InsightFace buffalo_l\nDetection + 512-d embeddings"]
    Engine --> Matcher["Cosine similarity\nStudent / Teacher embeddings"]
    Matcher --> Service["attendance_service.py\nIN/OUT rules & derived fields"]
    Service --> DB[("SQLAlchemy\nSQLite or PostgreSQL")]
    DB --> Flask
    Flask --> UI
```

```mermaid
sequenceDiagram
    participant Browser as Dashboard
    participant API as Flask API
    participant DB as Database
    Browser->>API: GET /api/enterprise/summary
    API->>DB: Query daily student/teacher attendance
    DB-->>API: Attendance data
    API-->>Browser: JSON KPIs
```

### Frontend → backend → recognition → database → dashboard

1. Jinja templates load `styles.css`, `common.js`, `app.js`, and page-specific JavaScript.
2. Browser calls Flask JSON APIs for records, filters, dashboards, reports, and management actions.
3. `RecognitionManager` owns a `FaceRecognizer` for each active camera.
4. The recognizer detects/matches faces and calls `record_recognition()`.
5. The attendance service updates normalized daily attendance and event tables.
6. Dashboard and report queries read those rows back into live UI views.

---

## 🗂️ Folder Structure

The tree below reflects the tracked application structure. Runtime caches, the local SQLite database, and sample enrolled photos are omitted for clarity.

```text
kes/
├── app.py                         # Flask factory, pages, APIs, exports, MJPEG stream
├── attendance_service.py           # Enterprise IN/OUT write path and calculations
├── config.py                       # Environment-driven Flask, DB, camera, AI settings
├── enterprise_query.py              # Enterprise dashboard/report query builders
├── requirements.txt
├── MIGRATION.md
├── walkthrough.md
├── assets/
│   └── .gitkeep                    # Reserved for future README screenshots
├── camera/
│   ├── __init__.py
│   └── stream.py                   # Multi-camera recognizer manager
├── database/
│   ├── __init__.py
│   ├── db.py                       # SQLAlchemy instance
│   ├── models.py                   # Core student, teacher, camera, attendance models
│   └── enterprise_models.py         # Normalized enterprise attendance models
├── migrations/
│   └── README.md
├── recognition/
│   ├── __init__.py
│   ├── encoder.py                  # InsightFace image/frame encoding
│   └── recognizer.py               # Background OpenCV recognition worker
├── scripts/
│   ├── init_db.py
│   ├── init_pgadmin.sql
│   ├── migrate.py
│   ├── seed_students.py
│   └── smoke_test.py
├── slm/
│   ├── __init__.py
│   └── nlp_engine.py               # Offline intents + optional Ollama fallback
├── static/
│   ├── known_faces/                # Uploaded/enrolled face images
│   ├── app.js
│   ├── attendance_extended.js
│   ├── attendance_v2.js
│   ├── common.js
│   ├── enterprise_dashboard.js
│   ├── reports.js
│   ├── reports_enterprise.js
│   ├── styles.css
│   └── time_rules.js
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   ├── dashboard_enterprise.html
│   ├── attendance.html
│   ├── attendance_extended.html
│   ├── students.html
│   ├── teachers.html
│   ├── cameras.html
│   ├── reports.html
│   ├── reports_enterprise.html
│   ├── time_rules.html
│   ├── settings.html
│   ├── chat.html
│   ├── present_students.html
│   └── 404.html
├── tests/
│   └── test_camera_source.py
└── time_management/
    ├── __init__.py
    ├── api.py                      # Time rules, holidays, sessions, audit, reports
    ├── models.py
    └── service.py
```

---

## 📦 Installation

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd kes
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate              # macOS / Linux
# .venv\Scripts\activate               # Windows PowerShell
```

### 3. Install required packages

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Choose a database

**Fast local start:** no database configuration is required. The app defaults to SQLite at `krishna_erp.db`.

**PostgreSQL:** create a database, then set `DATABASE_URL` before running the application.

```sql
-- In pgAdmin Query Tool, or run scripts/init_pgadmin.sql
CREATE DATABASE faceid_db;
```

```bash
export DATABASE_URL='postgresql://USER:PASSWORD@localhost:5432/faceid_db'
```

> `config.py` converts `postgresql://` and `postgres://` URLs to the SQLAlchemy psycopg v3 dialect automatically.

### 5. Initialize / upgrade the schema

`app.py` creates missing tables at startup and runs its additive compatibility checks. Run either helper when you want an explicit initialization step:

```bash
python scripts/init_db.py
# or
python scripts/migrate.py
```

### 6. Start the application

```bash
python app.py
```

### 7. Open the browser

Open [http://localhost:5000](http://localhost:5000).

### 8. Enrol people and start a camera

1. Add a student or teacher from the dashboard.
2. Upload a clear, front-facing image; a face embedding is created only when detection succeeds.
3. Add/configure a camera source and start it.
4. Use the dashboard stream and attendance views to monitor IN/OUT events.

<details>
<summary>Optional: seed the included demo student records</summary>

```bash
python scripts/seed_students.py
```

The script creates demo student records and encodes files only if matching `static/known_faces/<ROLL>.jpg` photos exist.
</details>

---

## ⚙️ Configuration

Configuration is centralized in [`config.py`](config.py). It loads a project-root `.env` when present and supplies development defaults.

| Variable | Default | Purpose |
|---|---|---|
| `FLASK_SECRET` | `dev-secret-change-me` | Flask secret key; replace in every non-local deployment |
| `DATABASE_URL` | local SQLite URI | SQLite by default; PostgreSQL URL when set |
| `CAMERA_SOURCE` | `0` | Initial camera source: device index, RTSP/HTTP URL, or path |
| `ATTENDANCE_COOLDOWN_SECONDS` | `300` | Per-person recognition cooldown in `FaceRecognizer` configuration |
| `FACE_MATCH_THRESHOLD` | `0.35` | Cosine-similarity threshold for recognition |
| `USE_OLLAMA` | `false` | Enables local Ollama fallback for assistant questions |
| `OLLAMA_MODEL` | `phi3:mini` | Ollama model name |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama service base URL |
| `PORT` | `5000` | Development server port; app tries `5001` if 5000 is unavailable |

### Camera source examples

```dotenv
CAMERA_SOURCE=0
# CAMERA_SOURCE=rtsp://user:password@192.168.1.10:554/stream
# CAMERA_SOURCE=http://192.168.1.3:8080
```

For HTTP sources, the recognizer appends `/video` when it is not already present. Blank or invalid text falls back to camera index `0`.

### Known faces directory

Uploaded photos are saved under `static/known_faces/`; `Config.KNOWN_FACES_DIR` points there. Do not expose the application publicly without considering biometric-data retention, access controls, and consent requirements.

### Optional report dependencies

`requirements.txt` does not include `openpyxl` or `reportlab`. Install them when you need native Excel/PDF output:

```bash
pip install openpyxl reportlab
```

Without them, the relevant export handler falls back to CSV.

---

## 🗃️ Database

### Core entities

| Table | Purpose | Key relationships |
|---|---|---|
| `students` | Enrolled students and InsightFace embeddings | One student has legacy `attendance` rows; one daily `student_attendance` row per date |
| `teachers` | Enrolled teachers and embeddings | One teacher has one `teacher_attendance` row per date |
| `cameras` | Named local/network sources | Referenced by attendance, unknown faces, events, daily attendance, and camera sessions |
| `attendance` | Legacy detection-oriented student attendance records | References `students` and optionally `cameras`; can link to `attendance_session` |
| `unknown_faces` | Unrecognized-face review records | Optionally references a camera |

### Enterprise and time-management entities

| Table | Purpose |
|---|---|
| `student_attendance` | One normalized student attendance row per student/date; unique constraint enforces the daily record |
| `teacher_attendance` | One normalized teacher attendance row per teacher/date |
| `attendance_events` | IN/OUT event log linked by attendance type and attendance ID; stores camera and confidence |
| `attendance_session` | Separate legacy-compatible student daily IN/OUT session layer |
| `attendance_time_rules` | Per-scope (`student`/`teacher`) time rule and feature-toggle rows |
| `student_time_rules` / `teacher_time_rules` | Enterprise rule tables used by `attendance_service.py` |
| `attendance_holiday` | Scoped holidays for the time-management module |
| `holiday_calendar` / `weekly_off` | Additional enterprise holiday/week-off schema; present in models but not used by the main time-rule UI/service path |
| `attendance_audit_log` | Audit records for the time-management API |
| `attendance_logs` | Enterprise edits and unknown-face actions |
| `attendance_corrections` | Correction schema; no route currently creates or manages it |
| `camera_sessions` | Camera session schema; no route currently writes it |
| `notifications` | Notification queue schema; no sender/worker implementation exists |
| `attendance_settings` | Boolean feature-toggle persistence for enterprise settings |

### ER diagram

```mermaid
erDiagram
    STUDENTS ||--o{ ATTENDANCE : has
    CAMERAS ||--o{ ATTENDANCE : records
    CAMERAS ||--o{ UNKNOWN_FACES : observes
    STUDENTS ||--o{ STUDENT_ATTENDANCE : receives
    TEACHERS ||--o{ TEACHER_ATTENDANCE : receives
    CAMERAS ||--o{ STUDENT_ATTENDANCE : source
    CAMERAS ||--o{ TEACHER_ATTENDANCE : source
    CAMERAS ||--o{ ATTENDANCE_EVENTS : source
    STUDENTS ||--o{ ATTENDANCE_SESSION : has
    CAMERAS ||--o{ CAMERA_SESSIONS : has
```

---

## 🔌 API Endpoints

All JSON APIs are served by Flask. Mutating endpoints under the time-management blueprint check `X-User-Role`; when that header is absent, the code treats the caller as `admin`. This is a compatibility stub, **not a full authentication system**.

### Pages and stream

| Method | Endpoint | Description | Example |
|---|---|---|---|
| GET | `/` | Standard dashboard page | `http://localhost:5000/` |
| GET | `/attendance` | Enterprise attendance page | `/attendance` |
| GET | `/students` | Student management page | `/students` |
| GET | `/students/class/<class_name>` | Class-scoped students page | `/students/class/Class%201` |
| GET | `/teachers` | Teacher management page | `/teachers` |
| GET | `/cameras` | Camera management page | `/cameras` |
| GET | `/reports` | Standard reports page | `/reports` |
| GET | `/settings` | Settings UI page | `/settings` |
| GET | `/chat` | Attendance assistant page | `/chat` |
| GET | `/time-rules/<scope>` | Student/teacher time-rules page | `/time-rules/student` |
| GET | `/dashboard-enterprise` | Enterprise dashboard page | `/dashboard-enterprise` |
| GET | `/reports-enterprise` | Enterprise reports page | `/reports-enterprise` |
| GET | `/attendance-extended` | Extended attendance page | `/attendance-extended` |
| GET | `/stream/<cid>` | Annotated MJPEG stream | `/stream/1` |

### Core management and attendance

| Method | Endpoint | Description | Example |
|---|---|---|---|
| GET | `/api/meta` | Available class/section metadata | `/api/meta` |
| GET | `/api/stats` | Standard dashboard KPIs; optional class/section | `/api/stats?class_name=Class%201&section=A` |
| GET, POST | `/api/cameras` | List or create cameras | `POST /api/cameras` |
| PUT, DELETE | `/api/cameras/<cid>` | Update or remove a camera | `PUT /api/cameras/1` |
| POST | `/api/cameras/<cid>/start` | Activate/start recognizer | `POST /api/cameras/1/start` |
| POST | `/api/cameras/<cid>/stop` | Stop recognizer/deactivate camera | `POST /api/cameras/1/stop` |
| POST | `/api/cameras/<cid>/test` | Validate configured source presence | `POST /api/cameras/1/test` |
| GET | `/api/cameras/status` | Live recognition status per camera | `/api/cameras/status` |
| GET, POST | `/api/students` | List/filter or create students | `/api/students?q=Aarav` |
| PUT, DELETE | `/api/students/<sid>` | Update, deactivate, or delete student | `PUT /api/students/1` |
| POST | `/api/students/<sid>/photo` | Upload and encode student photo | `POST /api/students/1/photo` |
| GET | `/api/attendance` | Query legacy attendance rows | `/api/attendance?date=2026-07-14` |
| PUT, DELETE | `/api/attendance/<aid>` | Update/delete legacy attendance | `PUT /api/attendance/42` |
| GET | `/api/attendance/today` | Today’s legacy attendance rows | `/api/attendance/today` |
| GET | `/api/attendance/export` | Download legacy CSV/PDF attendance | `/api/attendance/export?format=csv` |
| GET | `/api/unknown-faces` | List latest unknown-face records | `/api/unknown-faces` |
| POST, DELETE | `/api/unknown-faces/<uid>/action` | Review action or delete unknown face | `POST /api/unknown-faces/1/action` |
| GET, POST | `/api/teachers` | List/filter or create teachers | `/api/teachers?q=Math` |
| PUT, DELETE | `/api/teachers/<tid>` | Update, deactivate, or delete teacher | `PUT /api/teachers/1` |
| POST | `/api/teachers/<tid>/photo` | Upload and encode teacher photo | `POST /api/teachers/1/photo` |
| POST | `/api/ask` | Ask the attendance assistant | `POST /api/ask` |

### Enterprise dashboard, reports, and settings

| Method | Endpoint | Description | Example |
|---|---|---|---|
| GET, POST | `/api/enterprise/attendance` | Query or manually mark normalized attendance | `/api/enterprise/attendance?type=student` |
| GET | `/api/enterprise/dashboard` | Enterprise dashboard summary | `/api/enterprise/dashboard?date=2026-07-14` |
| GET | `/api/enterprise/summary` | Summary payload used by dashboard | `/api/enterprise/summary` |
| GET | `/api/enterprise/widgets` | Trend, heatmap, feed, camera-health widgets | `/api/enterprise/widgets` |
| GET | `/api/enterprise/sessions` | Filtered normalized session list | `/api/enterprise/sessions?type=teacher` |
| GET | `/api/enterprise/events` | Student/teacher IN/OUT event feed | `/api/enterprise/events?type=student` |
| GET, PUT | `/api/enterprise/settings` | Read/store feature-toggle values | `PUT /api/enterprise/settings` |
| GET, PUT | `/api/enterprise/time-rules/<kind>` | Read/update enterprise time rules | `/api/enterprise/time-rules/student` |
| GET | `/api/reports/preview` | JSON preview for enterprise report | `/api/reports/preview?type=daily` |
| GET | `/api/reports/export` | CSV/XLSX/PDF/print/JSON enterprise exports | `/api/reports/export?type=daily&format=csv` |

### Time-management blueprint (`/api`)

| Method | Endpoint | Description | Example |
|---|---|---|---|
| GET, PUT | `/api/time-rules/<scope>` | Read/update time-management rule | `/api/time-rules/student` |
| POST | `/api/time-rules/<scope>/reset` | Reset a scope’s rules | `POST /api/time-rules/student/reset` |
| GET, POST | `/api/holidays` | List/create scoped holidays | `/api/holidays?scope=student` |
| PUT, DELETE | `/api/holidays/<hid>` | Update/delete a holiday | `DELETE /api/holidays/1` |
| GET | `/api/sessions` | Filter legacy-compatible attendance sessions | `/api/sessions?date=2026-07-14` |
| GET, PUT | `/api/sessions/<sid>` | Get/update one session | `PUT /api/sessions/1` |
| GET | `/api/attendance/extended` | Legacy attendance joined with session details | `/api/attendance/extended?event_type=in` |
| POST | `/api/attendance/<aid>/edit` | Audited attendance/session correction | `POST /api/attendance/42/edit` |
| GET | `/api/audit-log` | Query time-management audit records | `/api/audit-log?entity_type=rule` |
| GET | `/api/dashboard/summary` | Time-management dashboard summary | `/api/dashboard/summary?date=2026-07-14` |
| GET | `/api/reports/<rptype>` | CSV/JSON/PDF-style time reports | `/api/reports/daily?format=csv` |

> Valid `rptype` values are `daily`, `weekly`, `monthly`, `teacher`, `student`, `late`, `half_day`, `working_hours`, `early_exit`, `overtime`, `holiday`, and `summary`.

### API flow

```mermaid
flowchart LR
    Client[Browser / API client] --> Routes[Flask routes]
    Routes --> Validate[Validation & role stub]
    Validate --> Query[ORM query / service call]
    Query --> DB[(SQLite / PostgreSQL)]
    DB --> JSON[JSON, stream, or file response]
    JSON --> Client
```

---

## 🖼️ Screenshots & Visual Prompts

No committed product screenshots were found in this repository. The `assets/` directory is intentionally included as a placeholder for future, truthful screenshots. The image references below are **not shipped image files yet**; generate or capture them before publishing a public README.

| Screen | Placeholder | Production-ready visual prompt |
|---|---|---|
| Dashboard | ![Dashboard placeholder](assets/dashboard-preview.png) | `Ultra-modern school attendance dashboard, Apple-inspired glass UI, blue gradient, attendance KPI cards, live camera tiles, charts, premium SaaS interface, 4K realistic product mockup` |
| Attendance | ![Attendance placeholder](assets/attendance-preview.png) | `Enterprise face attendance management table, IN OUT times, search filters, confidence badges, clean blue and white SaaS UI, realistic web application mockup` |
| Students | ![Students placeholder](assets/students-preview.png) | `Student management SaaS screen, class and section filters, profile table, face enrolment actions, elegant glassmorphism, premium education ERP UI` |
| Teachers | ![Teachers placeholder](assets/teachers-preview.png) | `Teacher management dashboard, department and designation records, face enrolment, premium school ERP web UI, modern blue accents` |
| Cameras | ![Cameras placeholder](assets/cameras-preview.png) | `Multi-camera monitoring console for school entrances, live video tiles, camera health badges, face boxes, premium enterprise SaaS UI` |
| Unknown faces | ![Unknown faces placeholder](assets/unknown-faces.png) | `Unknown face detection review queue, blurred face thumbnails, approve and assign actions, secure enterprise attendance dashboard UI` |
| Reports | ![Reports placeholder](assets/reports-preview.png) | `Attendance reporting workspace, date filters, export controls, bar charts and data table, polished enterprise SaaS design` |
| Analytics | ![Analytics placeholder](assets/analytics.png) | `Executive attendance analytics dashboard, seven-day trend, hourly entries, class heatmap, premium data visualization UI` |
| Time rules | ![Time management placeholder](assets/time-management.png) | `Attendance time rules settings screen, office hours, late threshold, overtime configuration, holiday calendar, modern admin SaaS UI` |
| Mobile vision | ![Mobile placeholder](assets/mobile-app.png) | `Future mobile attendance companion app, student check-in overview, face attendance status, iOS and Android premium product mockup` |
| Login (future) | `assets/login-screen.png` | `Secure enterprise SaaS login page for attendance system, elegant blue gradient, biometric-inspired illustration, minimal premium UI` |
| Settings | `assets/settings-preview.png` | `School ERP settings screen, organization profile, database and camera configuration, refined enterprise admin interface` |
| AI assistant | `assets/chat-assistant.png` | `AI attendance assistant chat panel in enterprise dashboard, concise attendance insights, premium glassmorphism web UI` |
| Payroll (future) | `assets/payroll-dashboard.png` | `Future payroll management dashboard, salary cards, payslip status, tax overview, enterprise HR SaaS, premium UI` |
| HR (future) | `assets/hr-dashboard.png` | `Future human resources dashboard, employee lifecycle metrics, recruitment pipeline, onboarding cards, premium enterprise SaaS` |

---

## ✅ Attendance Workflow

```mermaid
flowchart TD
    A[Camera frame] --> B[Face detected]
    B --> C[InsightFace embedding]
    C --> D{Cosine similarity ≥ threshold?}
    D -- No --> U[Keep UI detection as Unknown]
    D -- Yes --> E[Identify active student or teacher]
    E --> F{Cooldown elapsed?}
    F -- No --> G[Ignore repeated recognition]
    F -- Yes --> H[Load daily attendance row and time rule]
    H --> I{New IN, valid OUT, or duplicate?}
    I --> J[Create daily IN + event]
    I --> K[Update OUT + working time / status]
    I --> L[Ignore or reject]
    J --> M[(Database)]
    K --> M
    M --> N[Dashboard / reports read updated rows]
```

1. A `FaceRecognizer` receives an OpenCV frame from a configured camera.
2. InsightFace returns all detected faces and their normalized embeddings.
3. The recognizer compares each embedding with enrolled active student and teacher vectors.
4. A match must meet the configured similarity threshold; unmatched faces remain “Unknown” in the live detection overlay.
5. A 300-second default per-person cooldown prevents repeated writes from the same running recognizer.
6. `record_recognition()` creates an IN record, ignores a pre-OUT-window repeat, updates the OUT record, or rejects a completed daily record according to the time rule.
7. The service persists a normalized daily record and, for valid IN/OUT, an `attendance_events` record.
8. Dashboard, event feed, reports, and export routes query the stored data.

> Unknown-face persistence is modeled and review APIs exist, but the live recognizer currently does **not** insert an `UnknownFace` row when a match fails.

---

## 🧠 Recognition Pipeline

```mermaid
flowchart LR
    Camera[Camera source] --> OpenCV[OpenCV VideoCapture]
    OpenCV --> InsightFace[InsightFace detection + recognition]
    InsightFace --> Embed[512-d normalized embedding]
    Embed --> Match[NumPy cosine similarity]
    Match --> Service[Attendance service]
    Service --> Database[(Database)]
```

### Pipeline details

- **Camera:** `FaceRecognizer` normalizes source values, opens a capture, warms it up, and retries after repeated failures.
- **OpenCV:** reads BGR frames; encoder converts to RGB for InsightFace.
- **InsightFace:** `FaceAnalysis` is lazily constructed once per process with `buffalo_l`, CPU execution provider, `detection` and `recognition` modules, and 640×640 detection size.
- **Encoding:** largest-face encoding is used during enrolment; all faces are processed in live frames.
- **Matching:** L2-normalized vectors are compared by dot product (cosine similarity).
- **Attendance service:** applies daily IN/OUT and time rule logic to the matched student or teacher.
- **Database:** stores attendance, event, and reporting state through SQLAlchemy.

---

## ⏰ Time Management Workflow

```mermaid
flowchart TD
    Recognition[Matched recognition] --> Rule[Load student/teacher rule]
    Rule --> Window{Within IN window?}
    Window -- Before start --> Reject[Reject]
    Window -- After absent-after --> Absent[Create absent-status daily row]
    Window -- Valid --> In[Create IN]
    In --> Status[Present / Late / Half day]
    Status --> OutWindow{OUT window open?}
    OutWindow -- No --> Ignore[Ignore duplicate]
    OutWindow -- Yes --> Out[Set OUT]
    Out --> Calc[Calculate working minutes]
    Calc --> Flags[Early exit / Overtime / Half day]
    Flags --> Event[Write attendance event]
```

| Outcome | Current implementation |
|---|---|
| **IN** | First valid recognition at/after `office_start` creates daily attendance and an IN event. |
| **OUT** | A later recognition only becomes OUT at/after `out_detection_start`. |
| **Late** | First IN at/after `late_time` is marked late. |
| **Half day** | First IN at/after `half_day_time` is marked half day; completed records can also become half day when below minimum working minutes. |
| **Early exit** | OUT before `early_exit_time` is flagged. |
| **Overtime** | OUT after `overtime_start`, when enabled, yields overtime minutes. |
| **Working hours** | Difference between UTC-aware IN and OUT timestamps, stored in minutes and seconds. |
| **Breaks** | `break_minutes` exists but remains zero; break event capture is not implemented. |
| **Holidays / weekly off** | The separate `time_management` service checks `attendance_holiday` and its rule’s weekly-off values. The active live enterprise writer uses `student_time_rules`/`teacher_time_rules` and does not call that holiday checker. |

---

## 📤 Export Formats

| Format | Status | Route |
|---|---|---|
| CSV | ✅ Available | `/api/attendance/export`, `/api/reports/export` |
| Excel (`.xlsx`) | ✅ Available when `openpyxl` is installed; otherwise CSV fallback | `/api/reports/export?format=excel` |
| PDF | ✅ Available when `reportlab` is installed; otherwise CSV fallback | `/api/attendance/export?format=pdf`, `/api/reports/export?format=pdf` |
| Printable HTML | ✅ Available | `/api/reports/export?format=print` |
| JSON | ✅ Available for enterprise report export | `/api/reports/export?format=json` |

---

## 🏢 Enterprise Features

| Module | What is implemented |
|---|---|
| Normalized attendance | Separate daily student/teacher tables, one record per person/date, with IN/OUT, working time, late, early-exit, and overtime fields. |
| Attendance event ledger | IN/OUT event rows with type, time, source camera, and confidence. |
| Enterprise dashboard | Summary, trends, hourly entries, top late/overtime/early exit, working distribution, activity, camera health, recognition stats, and heatmap query data. |
| Time rules | Two model families exist: rules used by the live writer and rules used by the additive time-management API. Both expose student/teacher timing concepts. |
| Auditability | Audit tables and audited endpoints for rule, holiday, session, and legacy attendance edits. |
| Unknown-face review | Read/action/delete endpoints and logging; live unmatched detections are not automatically stored. |
| Feature settings | Persisted booleans for face recognition, QR, RFID, manual attendance, WhatsApp, SMS, email, anti-spoofing, liveness, and unknown-face alerts. Only face recognition is operational in the provided code. |
| Notifications / corrections / camera sessions | Database models exist, but application workflows and API operations are not implemented. |

---

## 🔐 Security Notes

### Present in code

- Required-field validation for camera and student creation.
- Unique constraints/checks for student roll numbers, teacher IDs, daily attendance records, rule scopes, holiday scope/date, and camera source conflict handling.
- `secure_filename()` for uploaded face-image filenames.
- Face image rejection when no face can be encoded.
- Database foreign keys and SQLAlchemy relationships across core entities.
- Recognition cooldown and daily-record logic to reduce duplicate attendance writes.
- Audit logging for several time-management, attendance, and unknown-face actions.
- Configurable face-match threshold.

### Not implemented yet — deployment caution

- Authentication and robust authorization (the `X-User-Role` behavior defaults missing callers to admin).
- Role-based access control, multi-factor authentication, CSRF protection, rate limiting, encrypted biometric storage, liveness detection, anti-spoofing, and retention/consent workflows.
- The default Flask secret is development-only. Set a strong `FLASK_SECRET`, use TLS/reverse-proxy hardening, and perform a security review before any production deployment.

---

# 🚀 Product Roadmap

> Product direction, not a statement of current capability. The roadmap intentionally separates **available now**, **in development/not wired**, and **planned** work.

## ✅ Current Features

`████████████████████░░░░` **Implemented attendance foundation**

- [x] Camera-based face detection and cosine-similarity recognition
- [x] Student and teacher enrolment with photo encoding
- [x] Multi-camera manager, status data, and MJPEG monitoring route
- [x] Student and teacher daily IN/OUT attendance
- [x] Late, half-day, early-exit, overtime, and working-time calculations
- [x] Attendance events, time rules, holidays, sessions, and audit data paths
- [x] Standard and enterprise dashboard/report interfaces
- [x] CSV, optional Excel/PDF, printable HTML, and JSON report outputs
- [x] Offline attendance-query assistant with optional local Ollama fallback

## 🚧 In Development / Not Yet Wired

`████████░░░░░░░░░░░░░░░░` **Models/settings exist; end-to-end delivery does not**

- [ ] Automatic persistence of unmatched live detections into the unknown-face review queue
- [ ] Operational notification dispatch for notification records/settings
- [ ] Attendance correction workflow over the `attendance_corrections` model
- [ ] Camera-session lifecycle records
- [ ] Required dependency packaging for native PDF and Excel exports
- [ ] Consolidation of the two overlapping time-rule / attendance-session implementations

## 🔮 Planned Features

`██░░░░░░░░░░░░░░░░░░░░░░` **Future enterprise product vision — not implemented**

<details>
<summary><strong>HR & Payroll</strong></summary>

- [ ] Payroll management · salary processing · payslip generator
- [ ] Tax calculation · PF / ESI management · leave encashment
- [ ] Bonus & incentive management · employee loans · reimbursement system
</details>

<details>
<summary><strong>Human Resource</strong></summary>

- [ ] Employee management · recruitment module · job portal
- [ ] Interview tracking · offer-letter generator · employee onboarding
- [ ] Exit management · performance review · promotions · appraisal management
</details>

<details>
<summary><strong>Attendance</strong></summary>

- [ ] GPS attendance · QR attendance · RFID attendance
- [ ] Fingerprint integration · iris scanner support · multi-device attendance
- [ ] Mobile attendance · offline attendance sync · geofencing
- [ ] Live attendance analytics
</details>

<details>
<summary><strong>Leave Management</strong></summary>

- [ ] Leave requests · approval workflow · holiday calendar management
- [ ] Shift management · roster planning · comp off
- [ ] Work from home · remote attendance
</details>

<details>
<summary><strong>AI Features</strong></summary>

- [ ] AI attendance insights · employee analytics · report generator
- [ ] Face quality detection · attendance prediction · shift recommendation
- [ ] Anomaly detection · fraud detection
- [ ] Enhanced AI chat assistant
</details>

<details>
<summary><strong>Reports & Analytics</strong></summary>

- [ ] Executive, HR, and payroll dashboards
- [ ] Department analytics · attendance heatmaps · productivity reports
- [ ] Scheduled reports · email reports
- [ ] Broader PDF / Excel / CSV delivery workflows
</details>

<details>
<summary><strong>Notifications</strong></summary>

- [ ] WhatsApp alerts · SMS alerts · email notifications
- [ ] Push notifications · Telegram integration
</details>

<details>
<summary><strong>Security</strong></summary>

- [ ] Face liveness detection · anti-spoofing · mask detection
- [ ] Multi-factor authentication · role-based access control
- [ ] Comprehensive audit logs · end-to-end encryption
</details>

<details>
<summary><strong>Multi-organization</strong></summary>

- [ ] Multi-school support · multi-company support · branch management
- [ ] Franchise management · cloud sync
</details>

<details>
<summary><strong>Mobile apps</strong></summary>

- [ ] Android app · iOS app · parent app · teacher app
- [ ] Employee self-service app · admin app
</details>

<details>
<summary><strong>Integrations</strong></summary>

- [ ] Google Workspace · Microsoft 365 · Slack · Zoom
- [ ] Biometric devices · UPI payments · Razorpay · Stripe
- [ ] SAP · Tally · ERP integrations
</details>

<details>
<summary><strong>Enterprise operations</strong></summary>

- [ ] Visitor management · gate pass · asset and inventory management
- [ ] Meeting-room booking · transport · hostel · library · canteen management
- [ ] Student ERP · school ERP · company ERP expansion
</details>

<details>
<summary><strong>Deployment</strong></summary>

- [ ] Docker · Kubernetes · AWS · Azure · Google Cloud
- [ ] CI/CD pipeline · monitoring · backup and recovery
</details>

---

# 🌟 Why Choose This System?

This project delivers a solid, inspectable foundation for organizations that need real-time face-attendance workflows without hiding the product state behind marketing language.

| Value | What exists today | Product direction |
|---|---|---|
| **AI powered** | InsightFace embeddings and cosine matching process live camera frames. | Add face quality, anomaly, and fraud intelligence. |
| **Real-time** | Background recognizers, camera status, MJPEG streams, and live dashboard queries. | Expand to multi-device and mobile synchronization. |
| **Modular** | Recognition, camera, time-management, enterprise query, NLP, and Flask layers are separated. | Evolve modules into broader school/company ERP services. |
| **Performance-minded** | Cached known embeddings, lazy model initialization, worker threads, cooldowns, and reconnect logic. | Add deployment observability and horizontal scaling. |
| **Business-ready foundation** | Student/teacher operations, attendance rules, exports, audit records, and dashboards are present. | Add authentication, notifications, payroll, and multi-organization control. |
| **Cloud-ready direction** | PostgreSQL is supported via environment configuration. | Docker, managed cloud, backups, CI/CD, and multi-tenant hosting are planned. |

The system is best suited today for teams that want a transparent, locally runnable face-attendance base and are prepared to complete production security, compliance, and deployment work for their environment.

---

## 📋 Requirements

### Software

- Python **3.14+** is the documented target in this repository.
- pip and a virtual environment tool.
- A local camera, USB camera, IP/RTSP stream, or supported video source for live recognition.
- SQLite (included with Python) or PostgreSQL for the database.
- Optional: pgAdmin for PostgreSQL administration.
- Optional: Ollama and a local model for non-rule-based assistant fallback.

### Python packages

The application requirements are maintained in [`requirements.txt`](requirements.txt):

```text
Flask
Flask-SQLAlchemy
SQLAlchemy
psycopg[binary]
opencv-python
numpy
Pillow
python-dotenv
requests
insightface
onnxruntime
```

Optional, not listed in the project requirements: `openpyxl` for `.xlsx` exports and `reportlab` for PDF exports.

---

## ▶️ How to Run

### Local SQLite quick start

```bash
git clone <your-repository-url>
cd kes
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Visit `http://localhost:5000`.

### PostgreSQL quick start

```bash
git clone <your-repository-url>
cd kes
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create the database in pgAdmin or with psql first.
export DATABASE_URL='postgresql://USER:PASSWORD@localhost:5432/faceid_db'
export FLASK_SECRET='replace-with-a-long-random-value'
python scripts/init_db.py
python app.py
```

### Useful verification commands

```bash
# Import-level dependency smoke test
python scripts/smoke_test.py

# Camera source normalization tests
pytest -q
```

---

## 🤝 Contributing

Contributions are welcome. Please keep changes scoped, testable, and truthful to the system’s current behavior.

1. Fork the repository and create a feature branch.
2. Create and activate a virtual environment; install dependencies.
3. Run the existing smoke test and pytest suite before making changes.
4. Add or update tests when behavior changes.
5. Keep API changes backward-compatible where practical; this project has two additive attendance/time-management paths.
6. Do not commit database files, production secrets, biometric images, generated model data, or personal data.
7. Open a pull request with a concise description, verification steps, and screenshots only when they reflect the actual UI.

```bash
git checkout -b feature/short-description
pytest -q
python scripts/smoke_test.py
git commit -m "feat: describe the change"
```

---

## 📄 License

**MIT License — intended.** A standalone `LICENSE` file is not currently present in the repository, so the legal license grant is **not implemented yet**. Add the approved MIT license text in a `LICENSE` file before distributing the project as MIT-licensed software.

---

## 👤 Author

**Krishna English School ERP / Face Attendance Management System**

Maintained as a school attendance and ERP foundation. For product ownership, commercial licensing, security disclosures, or deployment support, add the organization’s official contact channel and repository URL here before publication.

---

<p align="center">
  Built with Flask, OpenCV, InsightFace, and SQLAlchemy.<br>
  <sub>Use biometric attendance responsibly: obtain consent, secure face data, and follow applicable privacy law.</sub>
</p>

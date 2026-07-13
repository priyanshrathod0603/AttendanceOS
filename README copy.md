# Face Attendance System

A CCTV-driven face-recognition attendance system that watches a live camera,
identifies known students, and writes the result into PostgreSQL 17.

## Stack (Python 3.14 + macOS Apple Silicon)

| Layer        | Choice                                     |
|--------------|--------------------------------------------|
| Backend      | Flask 3.1 + Flask-SQLAlchemy 3.1          |
| Database     | PostgreSQL 17 (managed in pgAdmin 4)      |
| ORM          | SQLAlchemy 2.0 (with psycopg v3 driver)    |
| Face engine  | InsightFace (ONNX Runtime)                 |
| Video I/O    | OpenCV 4.13                                |
| SLM (chat)   | Rule-based NLP + optional Ollama fallback  |

> No `cmake`, no `dlib`, no system build tools required -- every wheel is
> prebuilt for `cp314-cp314-macosx_11_0_arm64`.

## 1. Create the database in pgAdmin 4

1. Open pgAdmin 4 and connect to your local PostgreSQL 17 server.
2. Right-click **Databases -> Create -> Database...**, name it `faceid_db`,
   or run the SQL script:

```sql
-- scripts/init_pgadmin.sql
CREATE DATABASE faceid_db;
```

3. In the project root, copy the example env file and edit the password:

```bash
cp .env.example .env
# then edit .env so DATABASE_URL points at faceid_db with your pgAdmin password
```

## 2. Set up the Python environment

```bash
cd "face id"
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

This installs cleanly on Python 3.14 + Apple Silicon.

## 3. Create tables

```bash
python scripts/init_db.py
```

## 4. Run the server

```bash
python app.py
```

Open http://localhost:5000.

## 5. Add students + face photos

* Use the **Students** form on the dashboard to add a row.
* Upload one clear front-facing JPG per student. The system encodes it
  with InsightFace and stores the 512-d embedding as JSONB in PostgreSQL.
* Optionally seed demo rows with `python scripts/seed_students.py`.

## 6. Plug in CCTV

Set `CAMERA_SOURCE` in `.env`:

| Source         | Value                                              |
|----------------|----------------------------------------------------|
| Built-in cam   | `0`                                                |
| USB cam        | `1`, `2`, ...                                      |
| IP / RTSP      | `rtsp://user:pass@192.168.1.10:554/stream`         |

You can also add cameras from the **Add Camera** form on the dashboard.

## 7. Natural-language chat

Visit http://localhost:5000/chat and ask:

- `Who is present today?`
- `How many students today?`
- `Who is absent today?`
- `Find Priyansh`
- `Attendance on 2026-06-29`
- `summary`

The default engine is fully offline. To enable the local SLM fallback:

```bash
# Install Ollama from https://ollama.com
ollama pull phi3:mini
USE_OLLAMA=true OLLAMA_MODEL=phi3:mini python app.py
```

## Project layout

```
face id/
  app.py                  Flask factory + routes
  config.py               Env-driven configuration
  database/
    db.py                 SQLAlchemy singleton
    models.py             Student, Camera, Attendance
  recognition/
    encoder.py            InsightFace embedding helpers
    recognizer.py         Background CCTV frame loop
  camera/
    stream.py             Multi-camera + MJPEG manager
  slm/
    nlp_engine.py         Rule-based NLP + Ollama fallback
  scripts/
    init_db.py            create tables
    seed_students.py      demo rows
    init_pgadmin.sql      CREATE DATABASE faceid_db;
    smoke_test.py         import-only sanity check
  static/                 UI assets + uploaded face photos
  templates/              Jinja2 templates
  requirements.txt
  .env.example
```

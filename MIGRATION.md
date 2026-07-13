# Migration Report -- Python 3.14, PostgreSQL 17, Apple Silicon

## What changed and why

### 1. `requirements.txt` rewritten

| Package           | Old pin           | New pin                                | Why                                                                                                    |
|-------------------|-------------------|----------------------------------------|--------------------------------------------------------------------------------------------------------|
| `Flask`           | `3.0.0`           | `>=3.0,<4.0` (resolved to 3.1.3)      | Latest stable Flask; supports Python 3.14.                                                              |
| `Flask-SQLAlchemy`| `3.1.1`           | `>=3.1,<4.0`                           | Already compatible; broadened to allow patch upgrades.                                                  |
| `SQLAlchemy`      | (transitive)      | `>=2.0.36,<3.0`                        | SQLAlchemy 2.0 is the supported line; explicit pin avoids surprise 1.x installs.                       |
| `psycopg2-binary` | `2.9.9`           | **dropped**                             | No maintained `cp314` wheel; replaced with psycopg v3 below.                                           |
| `psycopg[binary]` | (none)            | `>=3.2.3` (resolved to 3.3.4)          | Modern psycopg3 driver, ships prebuilt arm64 wheels for 3.14.                                           |
| `opencv-python`   | `4.8.1.78`        | `>=4.10.0.84` (resolved to 4.13.0.92)  | Official prebuilt arm64 wheels for Python 3.14; no Homebrew `opencv` needed.                           |
| `numpy`           | `>=1.26.0`        | `>=2.1.0` (resolved to 2.5.0)          | NumPy 1.x has no `cp314` wheels; 2.x is the actively supported line.                                   |
| `Pillow`          | `>=10.0.0`        | `>=11.0.0` (resolved to 12.2.0)        | Pillow 10 has no `cp314` wheels.                                                                       |
| `requests`        | `>=2.31.0`        | `>=2.32.3` (resolved to 2.34.2)        | Pulls urllib3 fix.                                                                                     |
| `python-dotenv`   | `>=1.0.0`         | `>=1.0.1` (resolved to 1.2.2)          | Patch bump for Python 3.14 compatibility.                                                              |
| `face-recognition`| `1.3.0`           | **dropped**                             | Depends on `dlib`, which has no `cp314` wheel and requires `cmake`. Replaced with InsightFace.          |
| `dlib`            | (transitive)      | **dropped**                             | Same reason as above.                                                                                  |
| `insightface`     | (none)            | `>=0.7.3` (resolved to 1.0.1)          | Modern, actively maintained face recognition toolkit; uses ONNX Runtime under the hood.                |
| `onnxruntime`     | (none)            | `>=1.19.0` (resolved to 1.27.0)        | Required by InsightFace; prebuilt arm64 wheels for 3.14.                                               |

The result: a single `pip install -r requirements.txt` completes without
any `cmake`/`brew install` step.

### 2. Face recognition pipeline swapped

`face_recognition` (dlib) -> `insightface` + `onnxruntime`.

* `recognition/encoder.py` -- exposes the same `encode_image(path)`,
  `encode_frame(frame)` and adds `detect_faces(frame)` returning
  `((top, right, bottom, left), embedding)` tuples. The largest face in
  the photo is selected so group photos encode the right person.
* `recognition/recognizer.py` -- matching now uses cosine similarity on
  L2-normalised InsightFace embeddings. InsightFace embeddings are 512-d
  (vs. dlib's 128-d). The DB column is JSONB so the shape change is free.
* Threshold semantics changed (lower is stricter -> higher is stricter),
  so `.env.example` ships with `FACE_MATCH_THRESHOLD=0.35`.

### 3. PostgreSQL driver swap

`psycopg2-binary` -> `psycopg[binary]` (psycopg v3).

* SQLAlchemy auto-detects psycopg3 from the `postgresql://` URL.
* `database/db.py` and the rest of the SQLAlchemy code is unchanged
  because psycopg3 is a transparent driver swap for the ORM.

### 4. PostgreSQL 17 compatibility

* Server defaults use `func.now()` with `db.DateTime(timezone=True)` so
  inserts always have a tz-aware value, regardless of driver defaults.
* The `encoding` column is still `JSONB`, available in PostgreSQL 17.
* `pool_pre_ping=True` and `pool_recycle=1800` added in `config.py` to
  play nicely with PostgreSQL 17's idle disconnects.
* `scripts/init_pgadmin.sql` now creates `faceid_db` to match the new
  `DATABASE_URL`.

### 5. Python 3.14 deprecations removed

* `datetime.utcnow()` -> `datetime.now(timezone.utc)` everywhere.
* `db.DateTime` -> `db.DateTime(timezone=True)` so the values round-trip
  through psycopg3 / PostgreSQL 17 without naive-vs-aware surprises.
* All `from __future__ import annotations` for forward-compat.

### 6. macOS Apple Silicon ergonomics

* `pip install -r requirements.txt` uses only prebuilt wheels; no
  Homebrew `cmake`, no manual `dlib` build, no extra system Python.
* InsightFace's `buffalo_l` model is downloaded into
  `~/.insightface/` on first run.

## Files changed

| File                                | Change                                                              |
|-------------------------------------|---------------------------------------------------------------------|
| `requirements.txt`                  | Bumped + dropped `dlib`/`face-recognition`/`psycopg2-binary`.        |
| `.env.example`                      | Renamed DB to `faceid_db`, swapped keys, switched threshold name.    |
| `config.py`                         | Modern env loading, `pool_pre_ping`, threshold renamed, bool parse. |
| `database/models.py`                | tz-aware datetimes, `func.now()` server default, no `utcnow`.       |
| `recognition/encoder.py`            | Rewritten on InsightFace + ONNX runtime.                             |
| `recognition/recognizer.py`         | Cosine-similarity matcher, modern type hints.                       |
| `camera/stream.py`                  | Type hints + docstrings only.                                       |
| `slm/nlp_engine.py`                 | `from __future__ import annotations`, modern typing.                |
| `app.py`                            | Cleaner route handlers, tz-aware `date.today()`.                    |
| `scripts/init_db.py`                | `__main__` guard, docstrings.                                       |
| `scripts/seed_students.py`          | `__main__` guard, docstrings.                                       |
| `scripts/init_pgadmin.sql`          | Now creates `faceid_db`.                                            |
| `scripts/smoke_test.py`             | New: import-only smoke test.                                        |
| `README.md`                         | Rewritten for the new stack + pgAdmin workflow.                     |
| `MIGRATION.md`                      | New: this file.                                                     |

## Commands cheatsheet

```bash
# 1. virtual env + deps
cd "face id"
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

# 2. database
#    (in pgAdmin 4 Query Tool)
#    CREATE DATABASE faceid_db;
python scripts/init_db.py

# 3. run
python app.py        # http://localhost:5000

# 4. sanity check (no DB needed)
python scripts/smoke_test.py
```

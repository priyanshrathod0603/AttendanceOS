"""Application configuration loaded from environment variables.

This module centralises every runtime setting so the rest of the codebase
never has to call ``os.getenv`` directly. Values come from ``.env`` (loaded
via python-dotenv) and fall back to sane development defaults.
"""
import os

from dotenv import load_dotenv

# Load .env from the project root (if present) before we read anything.
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _as_bool(value: str | None, default: bool = False) -> bool:
    """Parse common truthy strings into a proper bool."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _database_uri() -> str:
    """Build the SQLAlchemy URI.

    SQLAlchemy 2.x defaults to the psycopg2 dialect for ``postgresql://``
    URLs, but we ship psycopg v3. We rewrite the scheme to the explicit
    psycopg dialect so ``create_engine`` imports ``psycopg`` and never
    tries to import ``psycopg2``.
    """
    raw = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(BASE_DIR, 'krishna_erp.db')}",
    )
    if raw.startswith("postgresql://"):
        return "postgresql+psycopg://" + raw[len("postgresql://"):]
    if raw.startswith("postgres://"):
        return "postgresql+psycopg://" + raw[len("postgres://"):]
    return raw


class Config:
    """Flask + SQLAlchemy configuration."""

    # --- Flask ---
    SECRET_KEY: str = os.getenv("FLASK_SECRET", "dev-secret-change-me")

    # --- Database ---
    SQLALCHEMY_DATABASE_URI: str = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    # Works with SQLite and PostgreSQL. PostgreSQL deployments can still be
    # selected by setting DATABASE_URL without changing application code.
    SQLALCHEMY_ENGINE_OPTIONS: dict = {"pool_pre_ping": True, "pool_recycle": 1800}

    # --- Camera ---
    CAMERA_SOURCE: str = os.getenv("CAMERA_SOURCE", "0")
    ATTENDANCE_COOLDOWN_SECONDS: int = int(
        os.getenv("ATTENDANCE_COOLDOWN_SECONDS", "300")
    )

    # --- Face matching (InsightFace uses cosine similarity, 0..1) ---
    FACE_MATCH_THRESHOLD: float = float(os.getenv("FACE_MATCH_THRESHOLD", "0.35"))

    # --- Optional local SLM (Ollama) ---
    USE_OLLAMA: bool = _as_bool(os.getenv("USE_OLLAMA"), False)
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "phi3:mini")
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")

    KNOWN_FACES_DIR: str = os.path.join(BASE_DIR, "static", "known_faces")

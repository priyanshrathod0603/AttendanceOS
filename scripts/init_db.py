"""Create all tables in the PostgreSQL 17 database (run once).

Usage::

    source venv/bin/activate
    python scripts/init_db.py
"""
from __future__ import annotations

import os
import sys

# Allow ``python scripts/init_db.py`` from the project root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
from database.db import db  # noqa: E402


def main() -> None:
    with app.app_context():
        db.create_all()
        print("Tables created (or already existed).")


if __name__ == "__main__":
    main()

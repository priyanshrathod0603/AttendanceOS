"""Quick import-only smoke test.

Runs without PostgreSQL or a camera. Verifies that every module imports
cleanly under Python 3.14 with the upgraded dependency stack.
"""
from __future__ import annotations

import importlib
import os
import sys

# Allow ``python scripts/smoke_test.py`` to find project modules without
# requiring the user to export PYTHONPATH manually.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MODULES = [
    "config",
    "database.db",
    "database.models",
    "recognition.encoder",
    "recognition.recognizer",
    "camera.stream",
    "slm.nlp_engine",
]


def main() -> int:
    failures = 0
    for name in MODULES:
        try:
            importlib.import_module(name)
            print(f"  ok   {name}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  FAIL {name}: {exc}")
    if failures:
        print(f"\n{failures} module(s) failed to import.")
        return 1
    print("\nAll modules import cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

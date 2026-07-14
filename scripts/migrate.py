"""Run the safe, idempotent enterprise schema upgrade."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

if __name__ == "__main__":
    # Importing the application runs its idempotent create_all + compatibility
    # upgrade exactly once.
    _ = app
    print("Schema upgrade complete.")

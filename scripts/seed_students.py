"""Seed the database with demo students (and InsightFace encodings if photos exist)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
from database import db, Student  # noqa: E402
from recognition.encoder import encode_image  # noqa: E402

DEMO = [
    ("S001", "Aarav Sharma", "10", "A"),
    ("S002", "Diya Patel", "10", "A"),
    ("S003", "Vihaan Verma", "10", "B"),
    ("S004", "Ananya Iyer", "10", "B"),
    ("S005", "Priyansh Kumar", "10", "A"),
]


def main() -> None:
    with app.app_context():
        for roll, name, cls, sec in DEMO:
            s = Student.query.filter_by(roll_no=roll).first()
            if not s:
                s = Student(roll_no=roll, name=name, class_name=cls, section=sec)
                db.session.add(s)
                db.session.commit()
                print(f"Added {name}")

            photo_path = os.path.join("static", "known_faces", f"{roll}.jpg")
            if os.path.exists(photo_path) and not s.encoding:
                embedding = encode_image(photo_path)
                if embedding:
                    s.encoding = embedding
                    s.photo_path = f"known_faces/{roll}.jpg"
                    db.session.commit()
                    print(f"  encoded {roll}")
                else:
                    print(f"  no face found in {photo_path}")
            else:
                print(f"  no photo at {photo_path}; upload via dashboard")
        print("Done.")


if __name__ == "__main__":
    main()

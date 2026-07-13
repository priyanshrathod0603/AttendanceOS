"""SQLAlchemy ORM models for the face attendance system.

Design notes
------------
* ``Student.encoding`` stores the 512-d InsightFace embedding as JSONB so
  we can keep using the same schema regardless of which Postgres column
  type pgAdmin exposes. JSONB is available in PostgreSQL 17.
* ``Attendance.timestamp`` defaults to a timezone-aware ``now()`` at the
  database level as well, so inserts from background threads always have
  a value even if the Python side forgets to populate it.
* ``datetime.utcnow()`` is deprecated in Python 3.12+; we use
  ``datetime.now(timezone.utc)`` here and everywhere else.
* ``Teacher`` and ``UnknownFace`` were added so the new School ERP
  modules (Teachers, Reports) have a real storage target. The
  attendance table is unchanged.
"""
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from .db import db


def _utcnow() -> datetime:
    """Return a timezone-aware UTC ``datetime`` (replacement for ``utcnow``)."""
    return datetime.now(timezone.utc)


class Student(db.Model):
    """A student enrolled in the attendance system."""

    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    roll_no = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    class_name = db.Column(db.String(80), index=True)
    section = db.Column(db.String(40), index=True)
    mobile = db.Column(db.String(20))
    email = db.Column(db.String(120))
    photo_path = db.Column(db.String(255))
    # 512-d InsightFace embedding (list[float]). Stored as JSONB.
    encoding = db.Column(JSONB)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    attendance_records = db.relationship(
        "Attendance", backref="student", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "roll_no": self.roll_no,
            "name": self.name,
            "class_name": self.class_name,
            "section": self.section,
            "mobile": self.mobile,
            "email": self.email,
            "photo_path": self.photo_path,
            "has_encoding": self.encoding is not None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Camera(db.Model):
    """A camera (webcam index or RTSP URL)."""

    __tablename__ = "cameras"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    source = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(120))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "source": self.source,
            "location": self.location,
            "is_active": self.is_active,
        }


class Attendance(db.Model):
    """One attendance mark per student per day."""

    __tablename__ = "attendance"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("students.id"), nullable=False, index=True
    )
    camera_id = db.Column(db.Integer, db.ForeignKey("cameras.id"))
    timestamp = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    confidence = db.Column(db.Float)
    status = db.Column(db.String(20), default="present", nullable=False)

    camera = db.relationship("Camera")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "student_id": self.student_id,
            "student_name": self.student.name if self.student else None,
            "roll_no": self.student.roll_no if self.student else None,
            "class_name": self.student.class_name if self.student else None,
            "section": self.student.section if self.student else None,
            "camera_id": self.camera_id,
            "camera_name": self.camera.name if self.camera else None,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "confidence": self.confidence,
            "status": self.status,
        }


class Teacher(db.Model):
    """A teacher record. CRUD-only, no attendance logic yet."""

    __tablename__ = "teachers"

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(120))
    assigned_classes = db.Column(db.String(255))  # comma-separated, e.g. "5A,6B"
    mobile = db.Column(db.String(20))
    email = db.Column(db.String(120))
    photo_path = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "teacher_id": self.teacher_id,
            "name": self.name,
            "subject": self.subject,
            "assigned_classes": self.assigned_classes,
            "mobile": self.mobile,
            "email": self.email,
            "photo_path": self.photo_path,
            "is_active": self.is_active,
        }


class UnknownFace(db.Model):
    """A face that was detected but didn't match any known student.

    Used by the Reports module to surface unrecognised faces even though
    no attendance is recorded for them.
    """

    __tablename__ = "unknown_faces"

    id = db.Column(db.Integer, primary_key=True)
    camera_id = db.Column(db.Integer, db.ForeignKey("cameras.id"))
    timestamp = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    confidence = db.Column(db.Float)
    snapshot_path = db.Column(db.String(255))

    camera = db.relationship("Camera")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "camera_name": self.camera.name if self.camera else None,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "confidence": self.confidence,
            "snapshot_path": self.snapshot_path,
        }

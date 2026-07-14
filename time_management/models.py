"""SQLAlchemy models for the enterprise time-management module.

Every model here is additive — the existing ``attendance`` /
``unknown_faces`` tables are extended with new columns in
``database/models.py``; this file only declares brand-new tables.
"""
from __future__ import annotations

from datetime import date as _date
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)

from database.db import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AttendanceTimeRule(db.Model):
    """One configurable rule-set per scope (teacher / student).

    A single row is upserted per scope, so the table is small and reads
    are O(1). The model is permissive: every time field defaults to a
    sensible value so an admin who hasn't configured anything yet still
    gets a working system.
    """

    __tablename__ = "attendance_time_rules"

    id = Column(Integer, primary_key=True)
    scope = Column(String(20), unique=True, nullable=False, index=True)  # 'teacher' or 'student'

    # ---- core time windows ----
    office_start = Column(String(8), default="08:00", nullable=False)
    late_grace_time = Column(String(8), default="08:30", nullable=False)
    half_day_time = Column(String(8), default="09:30", nullable=False)
    absent_after_time = Column(String(8), default="11:00", nullable=False)
    office_end = Column(String(8), default="17:00", nullable=False)
    out_start = Column(String(8), default="16:00", nullable=False)
    overtime_start = Column(String(8), default="18:00", nullable=False)
    early_exit_time = Column(String(8), default="16:30", nullable=False)

    # ---- durations (in minutes) ----
    min_working_hours = Column(Integer, default=480, nullable=False)  # 8 hours
    max_break_minutes = Column(Integer, default=60, nullable=False)
    max_late_per_month = Column(Integer, default=3, nullable=False)

    # ---- weekly off (CSV of weekday numbers 0=Mon..6=Sun) ----
    # Python weekday numbering: Monday=0 ... Sunday=6. Sunday is the
    # conventional default weekly off.
    weekly_off = Column(String(40), default="6", nullable=False)

    # ---- feature toggles ----
    enable_in = Column(Boolean, default=True, nullable=False)
    enable_out = Column(Boolean, default=True, nullable=False)
    enable_working_hours = Column(Boolean, default=True, nullable=False)
    enable_overtime = Column(Boolean, default=True, nullable=False)
    enable_early_exit = Column(Boolean, default=True, nullable=False)
    enable_multi_entry = Column(Boolean, default=False, nullable=False)
    enable_unknown_alert = Column(Boolean, default=True, nullable=False)
    enable_notifications = Column(Boolean, default=False, nullable=False)
    enable_parent_notifications = Column(Boolean, default=False, nullable=False)
    enable_late_alert = Column(Boolean, default=True, nullable=False)
    enable_half_day = Column(Boolean, default=True, nullable=False)

    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "scope": self.scope,
            "office_start": self.office_start,
            "late_grace_time": self.late_grace_time,
            "half_day_time": self.half_day_time,
            "absent_after_time": self.absent_after_time,
            "office_end": self.office_end,
            "out_start": self.out_start,
            "overtime_start": self.overtime_start,
            "early_exit_time": self.early_exit_time,
            "min_working_hours": self.min_working_hours,
            "max_break_minutes": self.max_break_minutes,
            "max_late_per_month": self.max_late_per_month,
            "weekly_off": self.weekly_off,
            "enable_in": self.enable_in,
            "enable_out": self.enable_out,
            "enable_working_hours": self.enable_working_hours,
            "enable_overtime": self.enable_overtime,
            "enable_early_exit": self.enable_early_exit,
            "enable_multi_entry": self.enable_multi_entry,
            "enable_unknown_alert": self.enable_unknown_alert,
            "enable_notifications": self.enable_notifications,
            "enable_parent_notifications": self.enable_parent_notifications,
            "enable_late_alert": self.enable_late_alert,
            "enable_half_day": self.enable_half_day,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AttendanceSession(db.Model):
    """One row per student per day joining IN and OUT events.

    The recognizer still writes one row to ``attendance`` per detection.
    The time-management layer collapses those into a single daily
    session, computes derived fields (working hours, overtime, etc.) and
    links the underlying ``attendance`` rows back via ``session_id``.
    """

    __tablename__ = "attendance_session"

    id = Column(Integer, primary_key=True)
    student_id = Column(
        Integer, ForeignKey("students.id"), nullable=False, index=True
    )
    session_date = Column(Date, nullable=False, index=True)

    in_time = Column(DateTime(timezone=True))
    out_time = Column(DateTime(timezone=True))
    in_camera_id = Column(Integer, ForeignKey("cameras.id"))
    out_camera_id = Column(Integer, ForeignKey("cameras.id"))

    # 'present' | 'late' | 'half_day' | 'absent' | 'leave' | 'holiday' | 'early_exit' | 'overtime'
    status_detail = Column(String(20), default="present", nullable=False)
    manual_status = Column(String(20))  # when an admin overrides the computed status
    notes = Column(Text)

    is_late = Column(Boolean, default=False, nullable=False)
    is_half_day = Column(Boolean, default=False, nullable=False)
    is_early_exit = Column(Boolean, default=False, nullable=False)
    is_overtime = Column(Boolean, default=False, nullable=False)

    working_minutes = Column(Integer, default=0, nullable=False)
    overtime_minutes = Column(Integer, default=0, nullable=False)
    break_minutes = Column(Integer, default=0, nullable=False)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("student_id", "session_date", name="uq_session_student_date"),
        Index("ix_session_date", "session_date"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "student_id": self.student_id,
            "session_date": self.session_date.isoformat() if self.session_date else None,
            "in_time": self.in_time.isoformat() if self.in_time else None,
            "out_time": self.out_time.isoformat() if self.out_time else None,
            "in_camera_id": self.in_camera_id,
            "out_camera_id": self.out_camera_id,
            "status_detail": self.status_detail,
            "manual_status": self.manual_status,
            "notes": self.notes,
            "is_late": self.is_late,
            "is_half_day": self.is_half_day,
            "is_early_exit": self.is_early_exit,
            "is_overtime": self.is_overtime,
            "working_minutes": self.working_minutes,
            "overtime_minutes": self.overtime_minutes,
            "break_minutes": self.break_minutes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AttendanceHoliday(db.Model):
    """Holiday calendar with weekly off + national/school/emergency days."""

    __tablename__ = "attendance_holiday"

    id = Column(Integer, primary_key=True)
    scope = Column(String(20), default="all", nullable=False)  # 'teacher' | 'student' | 'all'
    holiday_date = Column(Date, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    kind = Column(String(20), default="school", nullable=False)  # 'national' | 'school' | 'emergency' | 'weekly_off'
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("holiday_date", "scope", name="uq_holiday_date_scope"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "scope": self.scope,
            "holiday_date": self.holiday_date.isoformat() if self.holiday_date else None,
            "name": self.name,
            "kind": self.kind,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AttendanceAuditLog(db.Model):
    """Audit trail for any admin-driven change to attendance or rules."""

    __tablename__ = "attendance_audit_log"

    id = Column(Integer, primary_key=True)
    entity_type = Column(String(40), nullable=False, index=True)  # 'attendance' | 'session' | 'rule' | 'holiday'
    entity_id = Column(Integer, nullable=False, index=True)
    field = Column(String(60), nullable=False)
    old_value = Column(Text)
    new_value = Column(Text)
    reason = Column(Text)
    edited_by = Column(String(80), default="admin", nullable=False)
    edited_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "field": self.field,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "edited_by": self.edited_by,
            "edited_at": self.edited_at.isoformat() if self.edited_at else None,
        }

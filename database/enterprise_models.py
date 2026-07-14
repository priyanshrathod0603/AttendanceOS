"""Additive, normalized models for enterprise attendance management."""
from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint, Index
from sqlalchemy.sql import func

from .db import db


class StudentAttendance(db.Model):
    __tablename__ = "student_attendance"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    attendance_date = db.Column(db.Date, nullable=False, index=True)
    in_time = db.Column(db.DateTime(timezone=True))
    out_time = db.Column(db.DateTime(timezone=True))
    working_minutes = db.Column(db.Integer, default=0, nullable=False)
    working_seconds = db.Column(db.Integer, default=0, nullable=False)
    break_minutes = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(24), default="present", nullable=False)
    is_late = db.Column(db.Boolean, default=False, nullable=False)
    is_early_exit = db.Column(db.Boolean, default=False, nullable=False)
    overtime_minutes = db.Column(db.Integer, default=0, nullable=False)
    camera_id = db.Column(db.Integer, db.ForeignKey("cameras.id"))
    confidence = db.Column(db.Float)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    student = db.relationship("Student")
    camera = db.relationship("Camera")
    __table_args__ = (UniqueConstraint("student_id", "attendance_date", name="uq_student_attendance_day"),)


class TeacherAttendance(db.Model):
    __tablename__ = "teacher_attendance"
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=False, index=True)
    attendance_date = db.Column(db.Date, nullable=False, index=True)
    in_time = db.Column(db.DateTime(timezone=True))
    out_time = db.Column(db.DateTime(timezone=True))
    working_minutes = db.Column(db.Integer, default=0, nullable=False)
    working_seconds = db.Column(db.Integer, default=0, nullable=False)
    break_minutes = db.Column(db.Integer, default=0, nullable=False)
    overtime_minutes = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(24), default="present", nullable=False)
    is_late = db.Column(db.Boolean, default=False, nullable=False)
    is_early_exit = db.Column(db.Boolean, default=False, nullable=False)
    camera_id = db.Column(db.Integer, db.ForeignKey("cameras.id"))
    confidence = db.Column(db.Float)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    teacher = db.relationship("Teacher")
    camera = db.relationship("Camera")
    __table_args__ = (UniqueConstraint("teacher_id", "attendance_date", name="uq_teacher_attendance_day"),)


class AttendanceEvent(db.Model):
    __tablename__ = "attendance_events"
    id = db.Column(db.Integer, primary_key=True)
    attendance_type = db.Column(db.String(12), nullable=False, index=True)  # student/teacher
    attendance_id = db.Column(db.Integer, nullable=False, index=True)
    event_type = db.Column(db.String(12), nullable=False)  # in/out/break_start/break_end
    event_time = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    camera_id = db.Column(db.Integer, db.ForeignKey("cameras.id"))
    confidence = db.Column(db.Float)
    camera = db.relationship("Camera")
    __table_args__ = (Index("ix_event_attendance", "attendance_type", "attendance_id"),)


class _TimeRuleBase:
    # IN and OUT boundaries are independent: a detection cannot become OUT
    # until out_detection_start, regardless of repeated camera detections.
    office_start = db.Column(db.String(5), default="08:00", nullable=False)
    in_end_time = db.Column(db.String(5), default="09:30", nullable=False)
    office_end = db.Column(db.String(5), default="17:00", nullable=False)
    late_time = db.Column(db.String(5), default="08:30", nullable=False)
    half_day_time = db.Column(db.String(5), default="09:30", nullable=False)
    absent_after = db.Column(db.String(5), default="11:00", nullable=False)
    out_detection_start = db.Column(db.String(5), default="16:00", nullable=False)
    early_exit_time = db.Column(db.String(5), default="16:30", nullable=False)
    overtime_start = db.Column(db.String(5), default="17:00", nullable=False)
    min_working_minutes = db.Column(db.Integer, default=480, nullable=False)
    overtime_enabled = db.Column(db.Boolean, default=True, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class TeacherTimeRule(db.Model, _TimeRuleBase):
    __tablename__ = "teacher_time_rules"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), default="Default", nullable=False, unique=True)


class StudentTimeRule(db.Model, _TimeRuleBase):
    __tablename__ = "student_time_rules"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), default="Default", nullable=False, unique=True)
    gate_close_time = db.Column(db.String(5), default="09:30", nullable=False)


class HolidayCalendar(db.Model):
    __tablename__ = "holiday_calendar"
    id = db.Column(db.Integer, primary_key=True)
    holiday_date = db.Column(db.Date, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    applies_to = db.Column(db.String(12), default="all", nullable=False)
    __table_args__ = (UniqueConstraint("holiday_date", "applies_to", name="uq_holiday_calendar_day"),)


class WeeklyOff(db.Model):
    __tablename__ = "weekly_off"
    id = db.Column(db.Integer, primary_key=True)
    applies_to = db.Column(db.String(12), nullable=False, index=True)
    weekday = db.Column(db.Integer, nullable=False)  # Monday=0
    __table_args__ = (UniqueConstraint("applies_to", "weekday", name="uq_weekly_off_scope_day"),)


class AttendanceSetting(db.Model):
    __tablename__ = "attendance_settings"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    enabled = db.Column(db.Boolean, default=False, nullable=False)


class AttendanceLog(db.Model):
    __tablename__ = "attendance_logs"
    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(40), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=False, index=True)
    field = db.Column(db.String(80), nullable=False)
    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text)
    edited_by = db.Column(db.String(80), default="admin", nullable=False)
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)


class AttendanceCorrection(db.Model):
    __tablename__ = "attendance_corrections"
    id = db.Column(db.Integer, primary_key=True)
    attendance_type = db.Column(db.String(12), nullable=False)
    attendance_id = db.Column(db.Integer, nullable=False, index=True)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(24))
    in_time = db.Column(db.DateTime(timezone=True))
    out_time = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)


class CameraSession(db.Model):
    __tablename__ = "camera_sessions"
    id = db.Column(db.Integer, primary_key=True)
    camera_id = db.Column(db.Integer, db.ForeignKey("cameras.id"), nullable=False, index=True)
    started_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at = db.Column(db.DateTime(timezone=True))
    camera = db.relationship("Camera")


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    channel = db.Column(db.String(20), nullable=False)
    recipient = db.Column(db.String(160))
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)

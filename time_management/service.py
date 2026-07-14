"""Time-management business logic.

The recognizer still does the heavy lifting of "face recognised → insert
an ``attendance`` row". After that row is committed, the recognizer
calls :func:`mark_event` and we decide whether the new row is an IN, an
OUT, or a duplicate that should be ignored.

All time math is performed against the *local* portion of the timestamp
so the configured office hours in the DB ("08:00", "17:00", ...) line
up with what the admin sees in the UI. The DB stores everything as
timezone-aware UTC; we render the local HH:MM in comparisons.
"""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError

from database.db import db
from database.models import Attendance

from .models import (
    AttendanceAuditLog,
    AttendanceHoliday,
    AttendanceSession,
    AttendanceTimeRule,
)


# --------------------------------------------------------------------- helpers
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


_HHMM = re.compile(r"^([0-1]?\d|2[0-3]):([0-5]\d)$")


def _parse_hhmm(value: str | None, default: str = "08:00") -> time:
    """Parse a ``HH:MM`` string to a :class:`time`. Falls back to default."""
    if not value or not isinstance(value, str):
        return _parse_hhmm(default, "08:00")
    m = _HHMM.match(value.strip())
    if not m:
        return _parse_hhmm(default, "08:00")
    return time(int(m.group(1)), int(m.group(2)))


def _time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _to_local(dt: datetime) -> datetime:
    """Convert a UTC-aware datetime to a naive local datetime (server tz)."""
    if dt is None:
        return None  # type: ignore[return-value]
    if dt.tzinfo is None:
        return dt
    return dt.astimezone().replace(tzinfo=None)


def _local_time_of(dt: datetime) -> time:
    return _to_local(dt).time()


# --------------------------------------------------------------------- rules
def get_active_rules(scope: str) -> AttendanceTimeRule:
    """Return the rule row for ``scope`` (creates a default if missing)."""
    if scope not in {"teacher", "student"}:
        scope = "student"
    rule = AttendanceTimeRule.query.filter_by(scope=scope).first()
    if rule is None:
        rule = AttendanceTimeRule(scope=scope)
        db.session.add(rule)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            rule = AttendanceTimeRule.query.filter_by(scope=scope).first()
    return rule


def ensure_default_rules() -> None:
    """Create default teacher + student rule rows on startup."""
    for scope in ("teacher", "student"):
        get_active_rules(scope)


# --------------------------------------------------------------------- audit
def audit(
    entity_type: str,
    entity_id: int,
    field: str,
    old_value,
    new_value,
    reason: str = "",
    edited_by: str = "admin",
) -> AttendanceAuditLog:
    """Write an audit-log row. Always commits."""
    log = AttendanceAuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        field=field,
        old_value=None if old_value is None else str(old_value),
        new_value=None if new_value is None else str(new_value),
        reason=reason or None,
        edited_by=edited_by,
    )
    db.session.add(log)
    db.session.commit()
    return log


# --------------------------------------------------------------------- formatting
def format_minutes(minutes: int | None) -> str:
    """Render minutes as ``Hh Mm`` (e.g. ``"8h 25m"``)."""
    if minutes is None or minutes < 0:
        return "0m"
    h, m = divmod(int(minutes), 60)
    if h and m:
        return f"{h}h {m}m"
    if h:
        return f"{h}h"
    return f"{m}m"


def format_hms(seconds: int | None) -> str:
    """Render seconds as ``HH:MM:SS``."""
    if seconds is None or seconds < 0:
        return "00:00:00"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


# --------------------------------------------------------------------- holiday
def is_holiday(d: date, scope: str = "all") -> bool:
    """True if the date is in the holiday calendar (including weekly off)."""
    # 1. Explicit holiday row
    holiday = AttendanceHoliday.query.filter(
        AttendanceHoliday.holiday_date == d,
        (AttendanceHoliday.scope == scope) | (AttendanceHoliday.scope == "all"),
    ).first()
    if holiday is not None:
        return True
    # 2. Weekly off (Sunday by default)
    rule = get_active_rules(scope if scope in {"teacher", "student"} else "student")
    weekly_off = [int(x) for x in (rule.weekly_off or "6").split(",") if x.strip().isdigit()]
    # Python: Monday=0, Sunday=6. Our UI labels say "Sun" = 6.
    if d.weekday() in weekly_off:
        return True
    return False


# --------------------------------------------------------------------- status
def compute_initial_status(ts: datetime, rules: AttendanceTimeRule) -> str:
    """Pick ``present`` / ``late`` / ``half_day`` for the first detection."""
    local = _local_time_of(ts)
    half_day = _parse_hhmm(rules.half_day_time, "09:30")
    late_grace = _parse_hhmm(rules.late_grace_time, "08:30")
    if rules.enable_half_day and local >= half_day:
        return "half_day"
    if local >= late_grace:
        return "late"
    return "present"


def compute_working_hours(session: AttendanceSession) -> None:
    if not session.in_time or not session.out_time:
        return
    delta = _to_local(session.out_time) - _to_local(session.in_time)
    session.working_minutes = max(int(delta.total_seconds() // 60), 0)


def compute_overtime(session: AttendanceSession, rules: AttendanceTimeRule) -> None:
    if not session.out_time:
        session.overtime_minutes = 0
        session.is_overtime = False
        return
    if not rules.enable_overtime:
        session.overtime_minutes = 0
        session.is_overtime = False
        return
    # The configurable overtime-start time is authoritative.  ``office_end``
    # remains the normal working-day boundary shown to administrators.
    office_end_min = _time_to_minutes(_parse_hhmm(rules.overtime_start or rules.office_end, "17:00"))
    out_min = _time_to_minutes(_local_time_of(session.out_time))
    diff = out_min - office_end_min
    if diff > 0:
        session.overtime_minutes = diff
        session.is_overtime = True
    else:
        session.overtime_minutes = 0
        session.is_overtime = False


def compute_early_exit(session: AttendanceSession, rules: AttendanceTimeRule) -> None:
    if not session.out_time or not rules.enable_early_exit:
        session.is_early_exit = False
        return
    early_min = _time_to_minutes(_parse_hhmm(rules.early_exit_time, "16:30"))
    out_min = _time_to_minutes(_local_time_of(session.out_time))
    session.is_early_exit = out_min < early_min


# --------------------------------------------------------------------- entry
def mark_event(
    student_id: int,
    camera_id: Optional[int],
    timestamp: datetime,
    confidence: float = 0.0,
    attendance_id: Optional[int] = None,
    scope: str = "student",
) -> dict:
    """Decide IN/OUT, update the session, and patch the attendance row.

    Returns a small dict summarising what happened. Failures here are
    caught and logged by the caller (recognizer) so the original
    attendance write is never blocked.
    """
    rules = get_active_rules(scope if scope in {"teacher", "student"} else "student")
    d = _to_local(timestamp).date()

    if is_holiday(d, scope=scope):
        # Record the event but don't create/update a session
        if attendance_id is not None:
            att = Attendance.query.get(attendance_id)
            if att is not None and not att.event_type:
                att.event_type = "in"
                db.session.commit()
        return {"event_type": "in", "holiday": True, "session_id": None}

    session = AttendanceSession.query.filter_by(
        student_id=student_id, session_date=d
    ).first()
    if session is None:
        session = AttendanceSession(student_id=student_id, session_date=d)
        db.session.add(session)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            session = AttendanceSession.query.filter_by(
                student_id=student_id, session_date=d
            ).first()

    out_window_start = _parse_hhmm(rules.out_start, "16:00")
    local_time = _local_time_of(timestamp)

    if session.in_time is None:
        if not rules.enable_in:
            return {"event_type": None, "reason": "in_disabled", "session_id": session.id}
        start_time = _parse_hhmm(rules.office_start, "08:00")
        absent_after = _parse_hhmm(rules.absent_after_time, "11:00")
        if local_time < start_time:
            return {"event_type": None, "reason": "before_in_window", "session_id": session.id}
        if local_time >= absent_after:
            session.status_detail = "absent"
            session.updated_at = _utcnow()
            db.session.commit()
            return {"event_type": None, "reason": "absent_after", "session_id": session.id,
                    "status_detail": "absent"}
        session.in_time = timestamp
        session.in_camera_id = camera_id
        session.status_detail = compute_initial_status(timestamp, rules)
        session.is_late = session.status_detail == "late"
        session.is_half_day = session.status_detail == "half_day"
        event_type = "in"
    elif session.out_time is None and local_time >= out_window_start:
        if not rules.enable_out:
            return {"event_type": None, "reason": "out_disabled", "session_id": session.id}
        session.out_time = timestamp
        session.out_camera_id = camera_id
        compute_working_hours(session)
        compute_overtime(session, rules)
        compute_early_exit(session, rules)
        if session.is_early_exit:
            session.status_detail = "early_exit"
        elif session.is_overtime:
            session.status_detail = "overtime"
        event_type = "out"
    else:
        # Duplicate detection: outside IN window but already has IN, or
        # before OUT window opens, or both IN and OUT already set.
        return {"event_type": None, "reason": "duplicate", "session_id": session.id}

    session.updated_at = _utcnow()
    db.session.commit()

    if attendance_id is not None:
        att = Attendance.query.get(attendance_id)
        if att is not None:
            att.event_type = event_type
            att.session_id = session.id
            db.session.commit()

    return {
        "event_type": event_type,
        "session_id": session.id,
        "status_detail": session.status_detail,
    }

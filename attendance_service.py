"""Single write path for live enterprise attendance recognition.

The recognizer calls :func:`record_recognition` once per matched face. This
service is the only writer to the normalised ``student_attendance`` /
``teacher_attendance`` tables and the ``attendance_events`` log; the legacy
``attendance`` table is left untouched.

Every derived field is recomputed from the configured time rules so the
dashboard, IN/OUT page, and reports can rely on the row's stored values
without re-deriving them.
"""
from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Optional

from database.db import db
from database.enterprise_models import (
    AttendanceEvent,
    StudentAttendance,
    StudentTimeRule,
    TeacherAttendance,
    TeacherTimeRule,
)


# --------------------------------------------------------------------- helpers
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite returns naive datetimes even for timezone-aware columns."""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _clock(value: Optional[str], default: str) -> time:
    try:
        h, m = (value or default).split(":", 1)
        return time(int(h), int(m))
    except (TypeError, ValueError):
        return _clock(default, default)


def _to_local_minutes(dt: datetime) -> int:
    """Return local HHMM as total minutes since 00:00, robust to naive datetimes."""
    if dt is None:
        return 0
    if dt.tzinfo is not None:
        dt = dt.astimezone()
    return dt.hour * 60 + dt.minute


def _diff_minutes(later: datetime, earlier: datetime) -> int:
    if not later or not earlier:
        return 0
    delta = _aware(later) - _aware(earlier)
    return max(int(delta.total_seconds() // 60), 0)


# --------------------------------------------------------------------- rules
def _rules_for(kind: str):
    model = StudentTimeRule if kind == "student" else TeacherTimeRule
    rules = model.query.first() or model()
    if rules.id is None:
        db.session.add(rules)
        db.session.flush()
    return rules


def _initial_status(now_clock: time, rules) -> tuple[str, bool, bool]:
    """Return ``(status, is_late, is_half_day)`` for a fresh IN event."""
    half_day_at = _clock(rules.half_day_time, "09:30")
    late_at = _clock(rules.late_time, "08:30")
    if now_clock >= half_day_at:
        return "half_day", False, True
    if now_clock >= late_at:
        return "late", True, False
    return "present", False, False


def _recompute_out_fields(row, rules, now: datetime) -> None:
    """Recompute every derived column on a row after IN or OUT changes."""
    # Working minutes
    if row.in_time and row.out_time:
        total = _diff_minutes(row.out_time, row.in_time)
        row.working_minutes = total
        row.working_seconds = total * 60
    else:
        row.working_minutes = 0
        row.working_seconds = 0

    # Break time is implicit; no separate break events are recorded yet.
    row.break_minutes = 0

    # A half-day is a completed session shorter than the configured minimum.
    # Keep this independent from the late flag: a person can be both late and
    # half-day, and the dashboard/report layer exposes both facts.
    if row.out_time:
        try:
            min_working = int(getattr(rules, "min_working_minutes", 480))
        except (TypeError, ValueError):
            min_working = 480
        is_half_day = row.working_minutes < min_working
    else:
        is_half_day = row.status == "half_day"

    # Early-exit: out before early_exit_time
    if row.out_time:
        early_at = _clock(rules.early_exit_time, "16:30")
        out_min = _to_local_minutes(row.out_time)
        early_min = early_at.hour * 60 + early_at.minute
        row.is_early_exit = out_min < early_min
    else:
        row.is_early_exit = False

    # Overtime: out after overtime_start (only when overtime enabled)
    overtime_enabled = bool(getattr(rules, "overtime_enabled", True))
    if row.out_time and overtime_enabled:
        ot_at = _clock(rules.overtime_start, "17:00")
        out_min = _to_local_minutes(row.out_time)
        ot_min = ot_at.hour * 60 + ot_at.minute
        diff = out_min - ot_min
        if diff > 0:
            row.overtime_minutes = diff
        else:
            row.overtime_minutes = 0
    else:
        row.overtime_minutes = 0

    # Final status: re-evaluate in priority order
    if row.out_time is None:
        # Still inside the school — keep IN-time derived status.
        if row.status in ("absent",):
            return
    if is_half_day:
        row.status = "half_day"
    elif row.is_early_exit:
        row.status = "early_exit"
    elif (row.overtime_minutes or 0) > 0:
        row.status = "overtime"
    elif row.is_late:
        row.status = "late"


# --------------------------------------------------------------------- public API
def record_recognition(
    person_type: str,
    person_id: int,
    camera_id: Optional[int],
    confidence: float,
    now: Optional[datetime] = None,
) -> dict:
    """Persist exactly one enterprise IN/OUT event.

    Parameters
    ----------
    person_type : str
        ``"student"`` or ``"teacher"``.
    person_id : int
        Database primary key of the matched person.
    camera_id : int | None
        Camera row that produced the detection.
    confidence : float
        Cosine similarity of the best match (0..1).
    now : datetime | None
        Override the current time. Used in tests; defaults to ``datetime.now(UTC)``.
    """
    if person_type not in {"student", "teacher"}:
        raise ValueError(f"unsupported person type: {person_type}")
    model, fk = (
        (StudentAttendance, "student_id")
        if person_type == "student"
        else (TeacherAttendance, "teacher_id")
    )
    now = _aware(now) or _now()
    rules = _rules_for(person_type)
    now_clock = now.astimezone().time().replace(tzinfo=None)

    row = model.query.filter_by(**{fk: person_id, "attendance_date": now.date()}).first()
    if row is None:
        # --- new day, no record yet -----------------------------------
        if now_clock < _clock(rules.office_start, "08:00"):
            print(f"[ATTENDANCE] rejected {person_type}={person_id}: before IN start")
            return {"action": "rejected", "reason": "before in start"}
        if now_clock >= _clock(rules.absent_after, "11:00"):
            row = model(
                **{
                    fk: person_id,
                    "attendance_date": now.date(),
                    "status": "absent",
                    "camera_id": camera_id,
                    "confidence": confidence,
                }
            )
            db.session.add(row)
            db.session.commit()
            print(f"[ATTENDANCE] rejected {person_type}={person_id}: absent-after threshold")
            return {"action": "rejected", "reason": "absent after", "attendance_id": row.id}

        status, is_late, is_half_day = _initial_status(now_clock, rules)
        row = model(
            **{
                fk: person_id,
                "attendance_date": now.date(),
                "in_time": now,
                "status": status,
                "is_late": is_late,
                "is_early_exit": False,
                "camera_id": camera_id,
                "confidence": confidence,
            }
        )
        db.session.add(row)
        db.session.flush()
        db.session.add(
            AttendanceEvent(
                attendance_type=person_type,
                attendance_id=row.id,
                event_type="in",
                event_time=now,
                camera_id=camera_id,
                confidence=confidence,
            )
        )
        _recompute_out_fields(row, rules, now)
        db.session.commit()
        print(
            f"[ATTENDANCE] inserted {person_type}={person_id} "
            f"attendance_id={row.id} event=in status={row.status} confidence={confidence:.3f}"
        )
        return {
            "action": "inserted",
            "event": "in",
            "attendance_id": row.id,
            "status": row.status,
        }

    if row.out_time is None:
        if row.in_time is None:
            print(
                f"[ATTENDANCE] rejected {person_type}={person_id}: "
                f"daily status is {row.status}; no IN exists"
            )
            return {"action": "rejected", "reason": "no in time", "attendance_id": row.id}
        if now_clock < _clock(rules.out_detection_start, "16:00"):
            print(
                f"[ATTENDANCE] ignored {person_type}={person_id}: "
                f"OUT window opens at {rules.out_detection_start}"
            )
            return {
                "action": "ignored",
                "reason": "before out detection start",
                "attendance_id": row.id,
            }
        row.out_time = now
        row.camera_id = camera_id
        row.confidence = confidence
        db.session.add(
            AttendanceEvent(
                attendance_type=person_type,
                attendance_id=row.id,
                event_type="out",
                event_time=now,
                camera_id=camera_id,
                confidence=confidence,
            )
        )
        _recompute_out_fields(row, rules, now)
        db.session.commit()
        print(
            f"[ATTENDANCE] updated {person_type}={person_id} "
            f"attendance_id={row.id} event=out status={row.status}"
        )
        return {
            "action": "updated",
            "event": "out",
            "attendance_id": row.id,
            "status": row.status,
        }

    print(f"[ATTENDANCE] rejected {person_type}={person_id}: daily IN and OUT already exist")
    return {"action": "rejected", "reason": "daily attendance complete", "attendance_id": row.id}

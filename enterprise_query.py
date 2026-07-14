"""Unified query layer for the enterprise attendance module.

The original codebase spread the same KPIs across three different endpoints
(``/api/stats``, ``/api/enterprise/dashboard``, ``/api/dashboard/summary``)
that computed overlapping metrics in subtly different ways. This module
replaces all of them with a single, well-tested calculator that powers the
Enterprise Dashboard, the IN/OUT page, and the Time Reports preview.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import re
from typing import Optional

from sqlalchemy import and_, func, or_

from database.db import db
from database.enterprise_models import (
    AttendanceEvent,
    HolidayCalendar,
    StudentAttendance,
    StudentTimeRule,
    TeacherAttendance,
    TeacherTimeRule,
    WeeklyOff,
)
from database.models import Attendance, Camera, Student, Teacher, UnknownFace


# --------------------------------------------------------------------- helpers
def _aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _to_local_time(dt: Optional[datetime]) -> Optional[time]:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone()
    return dt.time().replace(tzinfo=None)


def _avg_time_str(values: list[datetime]) -> Optional[str]:
    if not values:
        return None
    seconds = 0
    for v in values:
        if v is None:
            continue
        if v.tzinfo is not None:
            v = v.astimezone()
        seconds += v.hour * 3600 + v.minute * 60 + v.second
    avg = int(seconds / len(values))
    h, rem = divmod(avg, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _parse_hhmm(value: Optional[str], default: str) -> time:
    try:
        h, m = (value or default).split(":", 1)
        return time(int(h), int(m))
    except (TypeError, ValueError, AttributeError):
        try:
            h, m = default.split(":", 1)
            return time(int(h), int(m))
        except Exception:
            return time(8, 0)


def _to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _session_flags(row, rules) -> dict[str, bool]:
    """Return non-exclusive compliance flags for a completed session.

    ``status`` is intentionally a single display value, so it cannot safely
    represent facts such as "half day and early exit" at the same time.  All
    aggregate calculations use these rule-based flags instead.
    """
    min_working = int(getattr(rules, "min_working_minutes", 480) or 480)
    return {
        "present": row.in_time is not None,
        "late": bool(row.is_late) or row.status == "late",
        "half_day": bool(row.out_time and (row.working_minutes or 0) < min_working) or row.status == "half_day",
        "early_exit": bool(row.is_early_exit) or row.status == "early_exit",
        "overtime": bool((row.overtime_minutes or 0) > 0 or row.status == "overtime"),
    }


# --------------------------------------------------------------------- holidays
def is_holiday(d: date, scope: str = "all") -> bool:
    """True if the date falls on a configured holiday or weekly off."""
    if HolidayCalendar.query.filter(
        HolidayCalendar.holiday_date == d,
        or_(HolidayCalendar.applies_to == scope, HolidayCalendar.applies_to == "all"),
    ).first():
        return True
    # Weekly off: Sunday by default for school
    weekly = WeeklyOff.query.filter(
        or_(WeeklyOff.applies_to == scope, WeeklyOff.applies_to == "all")
    ).all()
    if not weekly:
        return d.weekday() == 6  # default Sunday off
    days = {w.weekday for w in weekly}
    return d.weekday() in days


# --------------------------------------------------------------------- sessions
def _student_attendance_query(d: date, class_name=None, section=None, department=None, designation=None):
    """Sessions for ``d`` plus the joins needed to filter by class/section."""
    q = StudentAttendance.query.filter(StudentAttendance.attendance_date == d)
    if class_name or section:
        q = q.join(Student, Student.id == StudentAttendance.student_id)
        if class_name:
            q = q.filter(Student.class_name == class_name)
        if section:
            q = q.filter(Student.section == section)
    return q


def _teacher_attendance_query(d: date, class_name=None, section=None, department=None, designation=None):
    q = TeacherAttendance.query.filter(TeacherAttendance.attendance_date == d)
    if department or designation:
        q = q.join(Teacher, Teacher.id == TeacherAttendance.teacher_id)
        if department:
            q = q.filter(Teacher.department == department)
        if designation:
            q = q.filter(Teacher.designation == designation)
    return q


# --------------------------------------------------------------------- summary
def compute_dashboard_summary(
    d: Optional[date] = None,
    class_name: Optional[str] = None,
    section: Optional[str] = None,
    department: Optional[str] = None,
    designation: Optional[str] = None,
) -> dict:
    """The single source of truth for the enterprise dashboard cards.

    Returns every KPI the dashboard, IN/OUT page, and reports preview
    render — so all three surfaces always agree.
    """
    target = d or _today_utc()
    rules_stu = StudentTimeRule.query.first()
    rules_tea = TeacherTimeRule.query.first()
    min_working = int(getattr(rules_stu, "min_working_minutes", 480) or 480)

    # Active population
    student_q = Student.query.filter_by(is_active=True)
    if class_name:
        student_q = student_q.filter_by(class_name=class_name)
    if section:
        student_q = student_q.filter_by(section=section)
    total_students = student_q.count()
    total_teachers = Teacher.query.filter_by(is_active=True).count()
    active_cams = Camera.query.filter_by(is_active=True).count()

    # Student sessions
    student_sessions = _student_attendance_query(target, class_name, section).all()
    teacher_sessions = _teacher_attendance_query(target, department=department, designation=designation).all()
    sessions = student_sessions + teacher_sessions

    flagged = [(s, _session_flags(s, rules_stu if s in student_sessions else rules_tea)) for s in sessions]
    present = sum(1 for _, flags in flagged if flags["present"])
    late = sum(1 for _, flags in flagged if flags["late"])
    half_day = sum(1 for _, flags in flagged if flags["half_day"])
    early_exit = sum(1 for _, flags in flagged if flags["early_exit"])
    overtime = sum(1 for _, flags in flagged if flags["overtime"])
    currently_inside = sum(1 for s in sessions if s.in_time is not None and s.out_time is None)
    currently_outside = sum(1 for s in sessions if s.in_time is not None and s.out_time is not None)
    # Absence is defined by a missing IN record, not merely a missing row.
    absent = max(total_students - sum(1 for s in student_sessions if s.in_time is not None), 0)

    unknown_today = UnknownFace.query.filter(func.date(UnknownFace.timestamp) == target).count()

    in_times = [s.in_time for s in sessions if s.in_time]
    out_times = [s.out_time for s in sessions if s.out_time]

    total_records = len(student_sessions) + len(teacher_sessions)
    avg_working = (
        int(sum(s.working_minutes or 0 for s in sessions) / max(len(sessions), 1))
        if sessions
        else 0
    )

    avg_in_time = _avg_time_str(in_times)
    avg_out_time = _avg_time_str(out_times)

    today_attendance_pct = (
        round((present / total_students) * 100, 1) if total_students else 0.0
    )

    return {
        "date": target.isoformat(),
        "is_holiday": is_holiday(target, "all"),
        # core counts
        "total_students": total_students,
        "total_teachers": total_teachers,
        "total_records": total_records,
        "present": present,
        "late": late,
        "half_day": half_day,
        "absent": absent,
        "early_exit": early_exit,
        "overtime": overtime,
        "currently_inside": currently_inside,
        "currently_outside": currently_outside,
        "unknown_faces": unknown_today,
        "active_cameras": active_cams,
        # times
        "average_in_time": avg_in_time,
        "average_out_time": avg_out_time,
        "average_working_minutes": avg_working,
        "min_working_minutes": min_working,
        # derived
        "today_attendance_pct": today_attendance_pct,
        "students_present": len(student_sessions),
        "teachers_present": len(teacher_sessions),
        "students_absent": absent,
        "teachers_absent": max(total_teachers - len(teacher_sessions), 0),
        "late_today": late,
        "today_entries": AttendanceEvent.query.filter(
            func.date(AttendanceEvent.event_time) == target,
            AttendanceEvent.event_type == "in",
        ).count(),
        "today_exits": AttendanceEvent.query.filter(
            func.date(AttendanceEvent.event_time) == target,
            AttendanceEvent.event_type == "out",
        ).count(),
        # filters echoed back so the UI can reflect them
        "class_name": class_name,
        "section": section,
        "department": department,
        "designation": designation,
    }


# --------------------------------------------------------------------- sessions list
def list_sessions(
    d: Optional[date] = None,
    kind: str = "student",
    class_name: Optional[str] = None,
    section: Optional[str] = None,
    department: Optional[str] = None,
    designation: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    event_type: Optional[str] = None,
    camera_id: Optional[int] = None,
    min_confidence: Optional[float] = None,
    max_confidence: Optional[float] = None,
    recognition_type: Optional[str] = None,
    limit: int = 1000,
) -> list[dict]:
    """Return a list of sessions as dicts ready for the IN/OUT table.

    ``status`` may be one of: ``present``, ``late``, ``half_day``,
    ``early_exit``, ``overtime``, ``absent``, ``inside``, ``outside``.
    ``event_type`` may be ``in`` or ``out`` (filters to sessions that
    have that event recorded).
    """
    target = d or _today_utc()
    rows: list[dict] = []
    if kind in ("all", "student"):
        q = _student_attendance_query(target, class_name, section, department, designation)
        if status:
            q = q.filter(StudentAttendance.status == status)
        if search:
            like = f"%{search.lower()}%"
            q = q.join(Student, Student.id == StudentAttendance.student_id).filter(
                or_(
                    func.lower(Student.roll_no).like(like),
                    func.lower(Student.name).like(like),
                )
            )
        for s in q.all():
            rows.append(_session_to_dict(s, "student"))
    if kind in ("all", "teacher"):
        q = _teacher_attendance_query(target, department=department, designation=designation)
        if status:
            q = q.filter(TeacherAttendance.status == status)
        if search:
            like = f"%{search.lower()}%"
            q = q.join(Teacher, Teacher.id == TeacherAttendance.teacher_id).filter(
                func.lower(Teacher.name).like(like)
            )
        for s in q.all():
            rows.append(_session_to_dict(s, "teacher"))
    # post filters
    out: list[dict] = []
    for r in rows:
        if event_type == "in" and not r.get("in_time"):
            continue
        if event_type == "out" and not r.get("out_time"):
            continue
        if event_type == "late" and not r.get("is_late"):
            continue
        if event_type == "half_day" and not r.get("is_half_day"):
            continue
        if event_type == "early_exit" and not r.get("is_early_exit"):
            continue
        if event_type == "overtime" and not r.get("overtime_minutes"):
            continue
        if camera_id and r.get("camera_id") != camera_id:
            continue
        if min_confidence is not None and (r.get("confidence") or 0) < min_confidence:
            continue
        if max_confidence is not None and (r.get("confidence") or 0) > max_confidence:
            continue
        if recognition_type and r.get("recognition_type") != recognition_type:
            continue
        out.append(r)
    return out[:limit]


def _session_to_dict(row, kind: str) -> dict:
    if kind == "student":
        person = row.student
        return {
            "id": row.id,
            "type": "student",
            "date": row.attendance_date.isoformat() if row.attendance_date else None,
            "person_id": person.id if person else None,
            "name": person.name if person else None,
            "roll_no": person.roll_no if person else None,
            "class_name": person.class_name if person else None,
            "section": person.section if person else None,
            "employee_id": None,
            "department": None,
            "designation": None,
            "in_time": row.in_time.isoformat() if row.in_time else None,
            "out_time": row.out_time.isoformat() if row.out_time else None,
            "working_minutes": row.working_minutes or 0,
            "break_minutes": row.break_minutes or 0,
            "overtime_minutes": row.overtime_minutes or 0,
            "is_late": bool(row.is_late),
            "is_half_day": _session_flags(row, StudentTimeRule.query.first() or StudentTimeRule())["half_day"],
            "is_early_exit": bool(row.is_early_exit),
            "status": row.status,
            "camera_id": row.camera_id,
            "camera": row.camera.name if row.camera else None,
            "confidence": row.confidence,
            "recognition_type": "face",
        }
    person = row.teacher
    return {
        "id": row.id,
        "type": "teacher",
        "date": row.attendance_date.isoformat() if row.attendance_date else None,
        "person_id": person.id if person else None,
        "name": person.name if person else None,
        "roll_no": None,
        "class_name": None,
        "section": None,
        "employee_id": person.teacher_id if person else None,
        "department": person.department if person else None,
        "designation": person.designation if person else None,
        "in_time": row.in_time.isoformat() if row.in_time else None,
        "out_time": row.out_time.isoformat() if row.out_time else None,
        "working_minutes": row.working_minutes or 0,
        "break_minutes": row.break_minutes or 0,
        "overtime_minutes": row.overtime_minutes or 0,
        "is_late": bool(row.is_late),
        "is_half_day": _session_flags(row, TeacherTimeRule.query.first() or TeacherTimeRule())["half_day"],
        "is_early_exit": bool(row.is_early_exit),
        "status": row.status,
        "camera_id": row.camera_id,
        "camera": row.camera.name if row.camera else None,
        "confidence": row.confidence,
        "recognition_type": "face",
    }


# --------------------------------------------------------------------- reports
def build_report(
    report_type: str,
    d: Optional[date] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
    class_name: Optional[str] = None,
    section: Optional[str] = None,
    department: Optional[str] = None,
    designation: Optional[str] = None,
    search: Optional[str] = None,
    person_type: Optional[str] = None,
) -> tuple[list[dict], list[str], str]:
    """Return ``(rows, headers, title)`` for a given report type.

    Every supported report (daily, weekly, monthly, late, half_day,
    working_hours, early_exit, overtime, summary, teacher, student,
    class, department) flows through this function so the preview and
    exported file always agree.
    """
    target = d or _today_utc()
    today = target
    if report_type == "daily":
        start = end = today
    elif report_type == "weekly":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
    elif report_type == "monthly":
        start = today.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end = start.replace(month=start.month + 1, day=1) - timedelta(days=1)
    elif report_type == "yearly":
        start = today.replace(month=1, day=1)
        end = today.replace(month=12, day=31)
    else:
        if not start:
            start = today - timedelta(days=30)
        if not end:
            end = today

    student_q = StudentAttendance.query.filter(
        StudentAttendance.attendance_date >= start,
        StudentAttendance.attendance_date <= end,
    )
    teacher_q = TeacherAttendance.query.filter(
        TeacherAttendance.attendance_date >= start,
        TeacherAttendance.attendance_date <= end,
    )
    if class_name or section or search:
        student_q = student_q.join(Student, Student.id == StudentAttendance.student_id)
        if class_name:
            student_q = student_q.filter(Student.class_name == class_name)
        if section:
            student_q = student_q.filter(Student.section == section)
        if search:
            like = f"%{search.lower()}%"
            student_q = student_q.filter(
                or_(
                    func.lower(Student.roll_no).like(like),
                    func.lower(Student.name).like(like),
                )
            )
    if department or designation:
        teacher_q = teacher_q.join(Teacher, Teacher.id == TeacherAttendance.teacher_id)
        if department:
            teacher_q = teacher_q.filter(Teacher.department == department)
        if designation:
            teacher_q = teacher_q.filter(Teacher.designation == designation)

    student_rows = student_q.all() if person_type in (None, "", "all", "student") else []
    teacher_rows = teacher_q.all() if person_type in (None, "", "all", "teacher") else []

    # Filter rows by report type
    def keep(row, is_student: bool) -> bool:
        if report_type in ("daily", "weekly", "monthly", "yearly", "teacher", "student",
                          "class", "department"):
            return True
        if report_type == "late":
            return bool(row.is_late) or row.status == "late"
        if report_type == "half_day":
            return row.status == "half_day" or (row.is_late and row.working_minutes and row.working_minutes < 240)
        if report_type == "early_exit":
            return bool(row.is_early_exit) or row.status == "early_exit"
        if report_type == "overtime":
            return (row.overtime_minutes or 0) > 0 or row.status == "overtime"
        if report_type == "working_hours":
            return row.out_time is not None
        return True

    student_rows = [r for r in student_rows if keep(r, True)]
    teacher_rows = [r for r in teacher_rows if keep(r, False)]

    headers = [
        "date", "type", "name", "roll_no", "employee_id",
        "class", "section", "department", "designation",
        "in_time", "out_time", "working_hours", "overtime",
        "status", "is_late", "is_early_exit", "is_overtime",
    ]
    rows: list[dict] = []
    for r in student_rows:
        person = r.student
        rows.append({
            "date": r.attendance_date.isoformat() if r.attendance_date else "",
            "type": "student",
            "name": person.name if person else "",
            "roll_no": person.roll_no if person else "",
            "employee_id": "",
            "class": person.class_name if person else "",
            "section": person.section if person else "",
            "department": "",
            "designation": "",
            "in_time": _fmt_time(r.in_time),
            "out_time": _fmt_time(r.out_time),
            "working_hours": _fmt_minutes(r.working_minutes or 0),
            "overtime": _fmt_minutes(r.overtime_minutes or 0),
            "status": r.status or "",
            "is_late": "Y" if r.is_late else "",
            "is_early_exit": "Y" if r.is_early_exit else "",
            "is_overtime": "Y" if (r.overtime_minutes or 0) > 0 else "",
        })
    for r in teacher_rows:
        person = r.teacher
        rows.append({
            "date": r.attendance_date.isoformat() if r.attendance_date else "",
            "type": "teacher",
            "name": person.name if person else "",
            "roll_no": "",
            "employee_id": person.teacher_id if person else "",
            "class": "",
            "section": "",
            "department": person.department if person else "",
            "designation": person.designation if person else "",
            "in_time": _fmt_time(r.in_time),
            "out_time": _fmt_time(r.out_time),
            "working_hours": _fmt_minutes(r.working_minutes or 0),
            "overtime": _fmt_minutes(r.overtime_minutes or 0),
            "status": r.status or "",
            "is_late": "Y" if r.is_late else "",
            "is_early_exit": "Y" if r.is_early_exit else "",
            "is_overtime": "Y" if (r.overtime_minutes or 0) > 0 else "",
        })
    if report_type == "summary":
        return _build_summary_report(rows, start, end), ["metric", "value"], f"Attendance Summary {start} to {end}"
    if report_type == "class":
        return _build_class_report(rows), ["class", "total", "present", "late", "half_day", "absent", "early_exit", "overtime"], "Class Attendance"
    if report_type == "department":
        return _build_dept_report(rows), ["department", "total", "present", "late", "half_day", "early_exit", "overtime"], "Department Attendance"
    title = f"{report_type.replace('_', ' ').title()} Report ({start} to {end})"
    return rows, headers, title


def _fmt_time(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    dt = _aware(dt)
    if dt.tzinfo is not None:
        dt = dt.astimezone()
    return dt.strftime("%H:%M:%S")


def _fmt_minutes(minutes: int) -> str:
    if not minutes:
        return "0m"
    h, m = divmod(int(minutes), 60)
    if h and m:
        return f"{h}h {m}m"
    if h:
        return f"{h}h"
    return f"{m}m"


def _build_summary_report(rows: list[dict], start: date, end: date) -> list[dict]:
    total = len(rows)
    present = sum(1 for r in rows if r["status"] in {"present", "late", "overtime", "early_exit", "half_day"})
    late = sum(1 for r in rows if r["is_late"] == "Y")
    half_day = sum(1 for r in rows if r["status"] == "half_day")
    early_exit = sum(1 for r in rows if r["is_early_exit"] == "Y")
    overtime = sum(1 for r in rows if r["is_overtime"] == "Y")
    total_working = sum(_parse_minutes(r["working_hours"]) for r in rows)
    total_ot = sum(_parse_minutes(r["overtime"]) for r in rows)
    return [
        {"metric": "Period", "value": f"{start} to {end}"},
        {"metric": "Total Records", "value": total},
        {"metric": "Present", "value": present},
        {"metric": "Late", "value": late},
        {"metric": "Half Day", "value": half_day},
        {"metric": "Early Exit", "value": early_exit},
        {"metric": "Overtime", "value": overtime},
        {"metric": "Total Working Hours", "value": _fmt_minutes(total_working)},
        {"metric": "Total Overtime", "value": _fmt_minutes(total_ot)},
    ]


def _parse_minutes(text: str) -> int:
    if not text:
        return 0
    value = str(text).strip().lower()
    hours = re.search(r"(\d+)\s*h", value)
    minutes = re.search(r"(\d+)\s*m", value)
    if hours or minutes:
        return (int(hours.group(1)) * 60 if hours else 0) + (int(minutes.group(1)) if minutes else 0)
    try:
        return int(value)
    except ValueError:
        return 0


def _build_class_report(rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for r in rows:
        if r["type"] != "student":
            continue
        key = r["class"] or "Unassigned"
        grouped.setdefault(key, []).append(r)
    out = []
    for cls, items in sorted(grouped.items()):
        out.append({
            "class": cls,
            "total": len(items),
            "present": sum(1 for r in items if r["status"] in {"present", "late", "overtime", "early_exit", "half_day"}),
            "late": sum(1 for r in items if r["is_late"] == "Y"),
            "half_day": sum(1 for r in items if r["status"] == "half_day"),
            "absent": 0,
            "early_exit": sum(1 for r in items if r["is_early_exit"] == "Y"),
            "overtime": sum(1 for r in items if r["is_overtime"] == "Y"),
        })
    return out


def _build_dept_report(rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for r in rows:
        if r["type"] != "teacher":
            continue
        key = r["department"] or "Unassigned"
        grouped.setdefault(key, []).append(r)
    out = []
    for dept, items in sorted(grouped.items()):
        out.append({
            "department": dept,
            "total": len(items),
            "present": sum(1 for r in items if r["status"] in {"present", "late", "overtime", "early_exit", "half_day"}),
            "late": sum(1 for r in items if r["is_late"] == "Y"),
            "half_day": sum(1 for r in items if r["status"] == "half_day"),
            "early_exit": sum(1 for r in items if r["is_early_exit"] == "Y"),
            "overtime": sum(1 for r in items if r["is_overtime"] == "Y"),
        })
    return out


# --------------------------------------------------------------------- trend / heatmap
def attendance_trend(days: int = 7, class_name=None, section=None) -> list[dict]:
    """Daily attendance percentage for the past ``days`` days."""
    out = []
    today = _today_utc()
    student_q = Student.query.filter_by(is_active=True)
    if class_name:
        student_q = student_q.filter_by(class_name=class_name)
    if section:
        student_q = student_q.filter_by(section=section)
    total_students = max(student_q.count(), 1)
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        q = StudentAttendance.query.filter(StudentAttendance.attendance_date == d)
        if class_name or section:
            q = q.join(Student, Student.id == StudentAttendance.student_id)
            if class_name:
                q = q.filter(Student.class_name == class_name)
            if section:
                q = q.filter(Student.section == section)
        sessions = q.all()
        present = sum(1 for s in sessions if s.status in {"present", "late", "overtime", "early_exit", "half_day"})
        late = sum(1 for s in sessions if s.is_late or s.status == "late")
        out.append({
            "date": d.isoformat(),
            "present": present,
            "late": late,
            "absent": max(total_students - present, 0),
            "pct": round((present / total_students) * 100, 1),
        })
    return out


def hourly_entries(d: Optional[date] = None) -> list[dict]:
    """Number of IN events grouped by hour-of-day (0..23)."""
    target = d or _today_utc()
    rows = AttendanceEvent.query.filter(
        func.date(AttendanceEvent.event_time) == target,
        AttendanceEvent.event_type == "in",
    ).all()
    buckets = [0] * 24
    for r in rows:
        dt = _aware(r.event_time)
        if dt.tzinfo is not None:
            dt = dt.astimezone()
        buckets[dt.hour] += 1
    return [{"hour": h, "count": buckets[h]} for h in range(24)]


def top_late_students(limit: int = 10, days: int = 30) -> list[dict]:
    today = _today_utc()
    start = today - timedelta(days=days)
    q = (
        db.session.query(
            StudentAttendance.student_id,
            func.count(StudentAttendance.id).label("late_count"),
        )
        .filter(
            StudentAttendance.attendance_date >= start,
            (StudentAttendance.is_late == True) | (StudentAttendance.status == "late"),
        )
        .group_by(StudentAttendance.student_id)
        .order_by(func.count(StudentAttendance.id).desc())
        .limit(limit)
        .all()
    )
    out = []
    for sid, count in q:
        student = Student.query.get(sid)
        if not student:
            continue
        out.append({
            "student_id": sid,
            "name": student.name,
            "roll_no": student.roll_no,
            "class_name": student.class_name,
            "section": student.section,
            "late_count": int(count),
        })
    return out


def top_overtime_teachers(limit: int = 10, days: int = 30) -> list[dict]:
    today = _today_utc()
    start = today - timedelta(days=days)
    q = (
        db.session.query(
            TeacherAttendance.teacher_id,
            func.coalesce(func.sum(TeacherAttendance.overtime_minutes), 0).label("ot"),
        )
        .filter(TeacherAttendance.attendance_date >= start)
        .group_by(TeacherAttendance.teacher_id)
        .order_by(func.sum(TeacherAttendance.overtime_minutes).desc())
        .limit(limit)
        .all()
    )
    out = []
    for tid, ot in q:
        teacher = Teacher.query.get(tid)
        if not teacher:
            continue
        out.append({
            "teacher_id": tid,
            "name": teacher.name,
            "employee_id": teacher.teacher_id,
            "department": teacher.department,
            "overtime_minutes": int(ot or 0),
        })
    return out


def top_early_exits(limit: int = 10, days: int = 30) -> list[dict]:
    today = _today_utc()
    start = today - timedelta(days=days)
    q = (
        db.session.query(StudentAttendance)
        .filter(
            StudentAttendance.attendance_date >= start,
            (StudentAttendance.is_early_exit == True) | (StudentAttendance.status == "early_exit"),
        )
        .order_by(StudentAttendance.attendance_date.desc())
        .limit(limit)
        .all()
    )
    out = []
    for s in q:
        person = s.student
        out.append({
            "name": person.name if person else None,
            "roll_no": person.roll_no if person else None,
            "class_name": person.class_name if person else None,
            "section": person.section if person else None,
            "date": s.attendance_date.isoformat() if s.attendance_date else None,
            "out_time": _fmt_time(s.out_time),
        })
    return out


def working_hours_distribution(days: int = 30) -> list[dict]:
    today = _today_utc()
    start = today - timedelta(days=days)
    rows = (
        db.session.query(StudentAttendance.working_minutes, StudentAttendance.is_late, StudentAttendance.status)
        .filter(
            StudentAttendance.attendance_date >= start,
            StudentAttendance.out_time.isnot(None),
        )
        .all()
    )
    buckets = {
        "< 4h": 0,
        "4-6h": 0,
        "6-8h": 0,
        "8-10h": 0,
        "10h+": 0,
    }
    for minutes, _is_late, _status in rows:
        m = minutes or 0
        if m < 240:
            buckets["< 4h"] += 1
        elif m < 360:
            buckets["4-6h"] += 1
        elif m < 480:
            buckets["6-8h"] += 1
        elif m < 600:
            buckets["8-10h"] += 1
        else:
            buckets["10h+"] += 1
    return [{"range": k, "count": v} for k, v in buckets.items()]


def camera_health() -> list[dict]:
    cams = Camera.query.all()
    out = []
    today = _today_utc()
    for c in cams:
        events = AttendanceEvent.query.filter(
            func.date(AttendanceEvent.event_time) == today,
            AttendanceEvent.camera_id == c.id,
        ).count()
        unknown = UnknownFace.query.filter(
            func.date(UnknownFace.timestamp) == today,
            UnknownFace.camera_id == c.id,
        ).count()
        out.append({
            "id": c.id,
            "name": c.name,
            "location": c.location,
            "is_active": c.is_active,
            "source": c.source,
            "events_today": events,
            "unknown_today": unknown,
        })
    return out


def recognition_stats(d: Optional[date] = None) -> dict:
    target = d or _today_utc()
    total = AttendanceEvent.query.filter(func.date(AttendanceEvent.event_time) == target).count()
    recognized = (
        db.session.query(func.count(AttendanceEvent.id))
        .filter(
            func.date(AttendanceEvent.event_time) == target,
            AttendanceEvent.confidence.isnot(None),
        )
        .scalar()
    ) or 0
    success = round((recognized / total) * 100, 1) if total else 0.0
    return {
        "total_recognitions": int(total),
        "successful": int(recognized),
        "success_rate": success,
        "unknown_faces": UnknownFace.query.filter(func.date(UnknownFace.timestamp) == target).count(),
    }


def activity_feed(limit: int = 30) -> list[dict]:
    rows = (
        AttendanceEvent.query
        .order_by(AttendanceEvent.event_time.desc())
        .limit(limit)
        .all()
    )
    out = []
    for r in rows:
        person_name = ""
        if r.attendance_type == "student":
            s = StudentAttendance.query.get(r.attendance_id)
            if s and s.student:
                person_name = f"{s.student.name} ({s.student.roll_no})"
        elif r.attendance_type == "teacher":
            t = TeacherAttendance.query.get(r.attendance_id)
            if t and t.teacher:
                person_name = f"{t.teacher.name} ({t.teacher.teacher_id})"
        out.append({
            "id": r.id,
            "type": r.attendance_type,
            "event_type": r.event_type,
            "event_time": r.event_time.isoformat() if r.event_time else None,
            "person": person_name,
            "camera": r.camera.name if r.camera else None,
            "confidence": r.confidence,
        })
    return out


def class_attendance_heatmap(days: int = 7) -> dict:
    """Return a 2D matrix ``{class: {date: pct}}`` for the heatmap."""
    today = _today_utc()
    classes = sorted({s.class_name for s in Student.query.filter(Student.class_name.isnot(None)).all()})
    if not classes:
        return {"classes": [], "dates": [], "matrix": {}}
    out_matrix: dict[str, dict[str, float]] = {}
    dates = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
    for cls in classes:
        out_matrix[cls] = {}
        total_for_class = Student.query.filter_by(is_active=True, class_name=cls).count() or 1
        for d_iso in dates:
            d = date.fromisoformat(d_iso)
            q = (
                db.session.query(StudentAttendance)
                .join(Student, Student.id == StudentAttendance.student_id)
                .filter(
                    StudentAttendance.attendance_date == d,
                    Student.class_name == cls,
                    StudentAttendance.status.in_(["present", "late", "overtime", "early_exit", "half_day"]),
                )
            )
            present = q.count()
            out_matrix[cls][d_iso] = round((present / total_for_class) * 100, 1)
    return {
        "classes": classes,
        "dates": dates,
        "matrix": out_matrix,
    }

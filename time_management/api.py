"""Flask blueprint with all enterprise time-management endpoints.

All endpoints are additive — they live under ``/api/`` and do not
modify the shape or behaviour of the existing endpoints in ``app.py``.

Permission stub
---------------
The optional ``X-User-Role`` header (``admin`` | ``teacher`` | ``student``)
controls who can mutate data. GET endpoints are open to everyone. When
the header is missing, the role is assumed to be ``admin`` so existing
admin sessions keep working.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from flask import Blueprint, Response, jsonify, request
from sqlalchemy import and_, func, or_

from database.db import db
from database.models import Attendance, Camera, Student, Teacher, UnknownFace

from .models import (
    AttendanceAuditLog,
    AttendanceHoliday,
    AttendanceSession,
    AttendanceTimeRule,
)
from .service import (
    audit,
    ensure_default_rules,
    format_hms,
    format_minutes,
    get_active_rules,
    is_holiday,
)

bp = Blueprint("time_mgmt", __name__, url_prefix="/api")


# --------------------------------------------------------------------- helpers
def _role() -> str:
    """Read the optional X-User-Role header (defaults to admin)."""
    return (request.headers.get("X-User-Role") or "admin").lower()


def _require_admin():
    if _role() != "admin":
        return jsonify({"error": "admin role required"}), 403
    return None


def _parse_date_arg(name: str) -> Optional[date]:
    raw = request.args.get(name)
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


_HHMM = re.compile(r"^([0-1]?\d|2[0-3]):[0-5]\d$")


def _as_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


# --------------------------------------------------------------------- rules
@bp.route("/time-rules/<scope>", methods=["GET"])
def get_rules(scope: str):
    if scope not in {"teacher", "student"}:
        return jsonify({"error": "scope must be 'teacher' or 'student'"}), 400
    rule = get_active_rules(scope)
    return jsonify(rule.to_dict())


@bp.route("/time-rules/<scope>", methods=["PUT"])
def put_rules(scope: str):
    if scope not in {"teacher", "student"}:
        return jsonify({"error": "scope must be 'teacher' or 'student'"}), 400
    denied = _require_admin()
    if denied:
        return denied
    rule = get_active_rules(scope)
    data = request.get_json(force=True) or {}
    field_names = [
        "office_start", "late_grace_time", "half_day_time", "absent_after_time",
        "office_end", "out_start", "overtime_start", "early_exit_time",
        "min_working_hours", "max_break_minutes", "max_late_per_month",
        "weekly_off", "enable_in", "enable_out", "enable_working_hours",
        "enable_overtime", "enable_early_exit", "enable_multi_entry",
        "enable_unknown_alert", "enable_notifications",
        "enable_parent_notifications", "enable_late_alert", "enable_half_day",
    ]
    reason = (data.get("reason") or "").strip()
    for key in field_names:
        if key in data:
            old = getattr(rule, key)
            new = data[key]
            if key in {"min_working_hours", "max_break_minutes", "max_late_per_month"}:
                try:
                    new = int(new)
                except (TypeError, ValueError):
                    return jsonify({"error": f"{key} must be an integer"}), 400
            elif key.startswith("enable_"):
                new = _as_bool(new)
            elif key in {"office_start", "late_grace_time", "half_day_time",
                         "absent_after_time", "office_end", "out_start",
                         "overtime_start", "early_exit_time"}:
                if not isinstance(new, str) or not _HHMM.match(new.strip()):
                    return jsonify({"error": f"{key} must be HH:MM (24-hour)"}), 400
                new = new.strip()
            setattr(rule, key, new)
            if old != new:
                audit("rule", rule.id, key, old, new, reason=reason)
    db.session.commit()
    return jsonify(rule.to_dict())


@bp.route("/time-rules/<scope>/reset", methods=["POST"])
def reset_rules(scope: str):
    if scope not in {"teacher", "student"}:
        return jsonify({"error": "scope must be 'teacher' or 'student'"}), 400
    denied = _require_admin()
    if denied:
        return denied
    rule = get_active_rules(scope)
    # Re-seed by deleting and letting get_active_rules recreate
    db.session.delete(rule)
    db.session.commit()
    rule = get_active_rules(scope)
    audit("rule", rule.id, "reset", "defaults", "defaults", reason="reset to defaults")
    return jsonify(rule.to_dict())


# --------------------------------------------------------------------- holidays
@bp.route("/holidays", methods=["GET", "POST"])
def holidays():
    if request.method == "GET":
        q = AttendanceHoliday.query.order_by(AttendanceHoliday.holiday_date.desc())
        scope = request.args.get("scope")
        if scope:
            q = q.filter(or_(AttendanceHoliday.scope == scope, AttendanceHoliday.scope == "all"))
        return jsonify([h.to_dict() for h in q.all()])
    denied = _require_admin()
    if denied:
        return denied
    data = request.get_json(force=True) or {}
    d_raw = data.get("holiday_date")
    name = (data.get("name") or "").strip()
    kind = (data.get("kind") or "school").strip()
    scope = (data.get("scope") or "all").strip()
    if not d_raw or not name:
        return jsonify({"error": "holiday_date and name are required"}), 400
    try:
        d = datetime.strptime(d_raw, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "holiday_date must be YYYY-MM-DD"}), 400
    h = AttendanceHoliday(holiday_date=d, name=name, kind=kind, scope=scope)
    db.session.add(h)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "a holiday for that date and scope already exists"}), 409
    audit("holiday", h.id, "create", None, f"{d.isoformat()}:{name}", reason="")
    return jsonify(h.to_dict()), 201


@bp.route("/holidays/<int:hid>", methods=["PUT", "DELETE"])
def holiday_detail(hid: int):
    denied = _require_admin()
    if denied:
        return denied
    h = AttendanceHoliday.query.get_or_404(hid)
    if request.method == "DELETE":
        audit("holiday", h.id, "delete", h.name, None, reason=request.args.get("reason", ""))
        db.session.delete(h)
        db.session.commit()
        return jsonify({"ok": True})
    data = request.get_json(force=True) or {}
    if "name" in data:
        old = h.name
        h.name = (data["name"] or "").strip() or h.name
        audit("holiday", h.id, "name", old, h.name, reason=data.get("reason", ""))
    if "kind" in data:
        old = h.kind
        h.kind = (data["kind"] or "school").strip()
        audit("holiday", h.id, "kind", old, h.kind, reason=data.get("reason", ""))
    if "holiday_date" in data:
        try:
            d = datetime.strptime(data["holiday_date"], "%Y-%m-%d").date()
            old = h.holiday_date
            h.holiday_date = d
            audit("holiday", h.id, "holiday_date", old, d, reason=data.get("reason", ""))
        except (TypeError, ValueError):
            return jsonify({"error": "holiday_date must be YYYY-MM-DD"}), 400
    if "scope" in data:
        h.scope = (data["scope"] or "all").strip()
    db.session.commit()
    return jsonify(h.to_dict())


# --------------------------------------------------------------------- sessions
@bp.route("/sessions", methods=["GET"])
def list_sessions():
    q = AttendanceSession.query
    d = _parse_date_arg("date")
    if d:
        q = q.filter(AttendanceSession.session_date == d)
    sd = _parse_date_arg("start")
    ed = _parse_date_arg("end")
    if sd:
        q = q.filter(AttendanceSession.session_date >= sd)
    if ed:
        q = q.filter(AttendanceSession.session_date <= ed)
    status = request.args.get("status")
    if status:
        q = q.filter(AttendanceSession.status_detail == status)
    class_name = request.args.get("class_name")
    section = request.args.get("section")
    if class_name or section:
        q = q.join(Student, Student.id == AttendanceSession.student_id)
        if class_name:
            q = q.filter(Student.class_name == class_name)
        if section:
            q = q.filter(Student.section == section)
    search = (request.args.get("q") or "").strip()
    if search:
        like = f"%{search.lower()}%"
        q = q.join(Student, Student.id == AttendanceSession.student_id).filter(
            or_(
                func.lower(Student.name).like(like),
                func.lower(Student.roll_no).like(like),
            )
        )
    rows = q.order_by(AttendanceSession.session_date.desc(), AttendanceSession.student_id).limit(1000).all()
    out = []
    for s in rows:
        d = s.to_dict()
        stu = Student.query.get(s.student_id)
        if stu:
            d["student_name"] = stu.name
            d["roll_no"] = stu.roll_no
            d["class_name"] = stu.class_name
            d["section"] = stu.section
        out.append(d)
    return jsonify(out)


@bp.route("/sessions/<int:sid>", methods=["GET"])
def session_detail(sid: int):
    s = AttendanceSession.query.get_or_404(sid)
    d = s.to_dict()
    stu = Student.query.get(s.student_id)
    if stu:
        d["student_name"] = stu.name
        d["roll_no"] = stu.roll_no
        d["class_name"] = stu.class_name
        d["section"] = stu.section
    return jsonify(d)


@bp.route("/sessions/<int:sid>", methods=["PUT"])
def session_edit(sid: int):
    denied = _require_admin()
    if denied:
        return denied
    s = AttendanceSession.query.get_or_404(sid)
    data = request.get_json(force=True) or {}
    reason = (data.get("reason") or "").strip()
    if "in_time" in data and data["in_time"]:
        try:
            new = _parse_iso(data["in_time"])
            audit("session", s.id, "in_time", s.in_time, new, reason=reason)
            s.in_time = new
        except (TypeError, ValueError):
            return jsonify({"error": "in_time must be ISO-8601"}), 400
    if "out_time" in data and data["out_time"]:
        try:
            new = _parse_iso(data["out_time"])
            audit("session", s.id, "out_time", s.out_time, new, reason=reason)
            s.out_time = new
        except (TypeError, ValueError):
            return jsonify({"error": "out_time must be ISO-8601"}), 400
    if "status_detail" in data:
        old = s.status_detail
        s.status_detail = (data["status_detail"] or "present").strip()
        s.manual_status = s.status_detail
        audit("session", s.id, "status_detail", old, s.status_detail, reason=reason)
    if "notes" in data:
        s.notes = data["notes"]
        audit("session", s.id, "notes", None, s.notes, reason=reason)
    db.session.commit()
    return jsonify(s.to_dict())


def _parse_iso(raw: str) -> datetime:
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


# --------------------------------------------------------------------- attendance extended
@bp.route("/attendance/extended", methods=["GET"])
def attendance_extended():
    """Same filter API as ``/api/attendance`` but joined to ``attendance_session``."""
    d = _parse_date_arg("date")
    class_name = request.args.get("class_name")
    section = request.args.get("section")
    search = (request.args.get("q") or "").strip()
    cid = request.args.get("camera_id", type=int)
    event_type = request.args.get("event_type")

    q = Attendance.query
    if d:
        q = q.filter(func.date(Attendance.timestamp) == d)
    if cid:
        q = q.filter(Attendance.camera_id == cid)
    if event_type in {"in", "out"}:
        q = q.filter(Attendance.event_type == event_type)
    if class_name or section or search:
        q = q.join(Student, Student.id == Attendance.student_id)
        if class_name:
            q = q.filter(Student.class_name == class_name)
        if section:
            q = q.filter(Student.section == section)
        if search:
            like = f"%{search.lower()}%"
            q = q.filter(or_(
                func.lower(Student.roll_no).like(like),
                func.lower(Student.name).like(like),
            ))

    rows = q.order_by(Attendance.timestamp.desc()).limit(2000).all()
    out = []
    for r in rows:
        d = r.to_dict()
        if r.session_id:
            sess = AttendanceSession.query.get(r.session_id)
            if sess:
                d["session_status"] = sess.status_detail
                d["working_minutes"] = sess.working_minutes
                d["overtime_minutes"] = sess.overtime_minutes
                d["is_late"] = sess.is_late
                d["is_half_day"] = sess.is_half_day
                d["is_early_exit"] = sess.is_early_exit
                d["is_overtime"] = sess.is_overtime
        out.append(d)
    return jsonify(out)


# --------------------------------------------------------------------- attendance edit (audit)
@bp.route("/attendance/<int:aid>/edit", methods=["POST"])
def attendance_edit_with_audit(aid: int):
    """Edit an attendance row, writing an audit log per changed field."""
    denied = _require_admin()
    if denied:
        return denied
    record = Attendance.query.get_or_404(aid)
    data = request.get_json(force=True) or {}
    reason = (data.get("reason") or "").strip()
    if "in_time" in data or "out_time" in data or "status_detail" in data:
        # When the caller sets in/out/status on a session, update the
        # session instead of the bare attendance row.
        sess_id = record.session_id
        if sess_id is None:
            from datetime import date as _date
            sess = AttendanceSession.query.filter_by(
                student_id=record.student_id, session_date=record.timestamp.date() if record.timestamp else _date.today()
            ).first()
            if sess is None:
                sess = AttendanceSession(
                    student_id=record.student_id,
                    session_date=record.timestamp.date() if record.timestamp else _date.today(),
                )
                db.session.add(sess)
                db.session.commit()
            sess_id = sess.id
            record.session_id = sess_id
        sess = AttendanceSession.query.get(sess_id)
        if "in_time" in data and data["in_time"]:
            try:
                new = _parse_iso(data["in_time"])
                audit("session", sess.id, "in_time", sess.in_time, new, reason=reason)
                sess.in_time = new
            except (TypeError, ValueError):
                return jsonify({"error": "in_time must be ISO-8601"}), 400
        if "out_time" in data and data["out_time"]:
            try:
                new = _parse_iso(data["out_time"])
                audit("session", sess.id, "out_time", sess.out_time, new, reason=reason)
                sess.out_time = new
            except (TypeError, ValueError):
                return jsonify({"error": "out_time must be ISO-8601"}), 400
        if "status_detail" in data:
            old = sess.status_detail
            sess.status_detail = (data["status_detail"] or "present").strip()
            sess.manual_status = sess.status_detail
            audit("session", sess.id, "status_detail", old, sess.status_detail, reason=reason)
        db.session.commit()
        return jsonify(sess.to_dict())
    # Direct attendance-row edits (mirror the legacy /api/attendance/<id> PUT)
    for key in ("status", "event_type", "edit_reason"):
        if key in data:
            old = getattr(record, key)
            new = data[key]
            setattr(record, key, new)
            audit("attendance", record.id, key, old, new, reason=reason)
    record.manual_edit = True
    db.session.commit()
    return jsonify(record.to_dict())


# --------------------------------------------------------------------- audit log
@bp.route("/audit-log", methods=["GET"])
def audit_log():
    q = AttendanceAuditLog.query.order_by(AttendanceAuditLog.edited_at.desc())
    entity = request.args.get("entity_type")
    if entity:
        q = q.filter(AttendanceAuditLog.entity_type == entity)
    eid = request.args.get("entity_id", type=int)
    if eid:
        q = q.filter(AttendanceAuditLog.entity_id == eid)
    return jsonify([r.to_dict() for r in q.limit(500).all()])


# --------------------------------------------------------------------- dashboard summary
def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


@bp.route("/dashboard/summary", methods=["GET"])
def dashboard_summary():
    d = _parse_date_arg("date") or _today_utc()
    class_name = request.args.get("class_name")
    section = request.args.get("section")

    student_q = Student.query.filter_by(is_active=True)
    if class_name:
        student_q = student_q.filter_by(class_name=class_name)
    if section:
        student_q = student_q.filter_by(section=section)
    total_students = student_q.count()

    sess_q = AttendanceSession.query.filter(AttendanceSession.session_date == d)
    if class_name or section:
        sess_q = sess_q.join(Student, Student.id == AttendanceSession.student_id)
        if class_name:
            sess_q = sess_q.filter(Student.class_name == class_name)
        if section:
            sess_q = sess_q.filter(Student.section == section)
    sessions_today = sess_q.all()
    sessions_with_student = {s.student_id: s for s in sessions_today}

    present = sum(1 for s in sessions_today if s.status_detail in {"present", "late", "overtime", "early_exit"})
    late = sum(1 for s in sessions_today if s.is_late or s.status_detail == "late")
    half_day = sum(1 for s in sessions_today if s.is_half_day or s.status_detail == "half_day")
    absent = max(total_students - len(sessions_today), 0)
    early_exit = sum(1 for s in sessions_today if s.is_early_exit or s.status_detail == "early_exit")
    overtime = sum(1 for s in sessions_today if s.is_overtime or s.status_detail == "overtime")
    currently_inside = sum(1 for s in sessions_today if s.in_time and not s.out_time)
    currently_outside = sum(1 for s in sessions_today if s.in_time and s.out_time)

    unknown_today = UnknownFace.query.filter(func.date(UnknownFace.timestamp) == d).count()
    active_cams = Camera.query.filter_by(is_active=True).count()

    in_times = [s.in_time for s in sessions_today if s.in_time]
    out_times = [s.out_time for s in sessions_today if s.out_time]
    avg_in = _avg_time(in_times)
    avg_out = _avg_time(out_times)

    return jsonify({
        "date": d.isoformat(),
        "total_students": total_students,
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
        "average_in_time": avg_in,
        "average_out_time": avg_out,
        "is_holiday": is_holiday(d, "all"),
    })


def _avg_time(values):
    if not values:
        return None
    def _seconds(v):
        # SQLite often returns naive datetimes; treat them as local.
        if v.tzinfo is not None:
            v = v.astimezone()
        return v.hour * 3600 + v.minute * 60 + v.second
    seconds = [_seconds(v) for v in values]
    avg = int(sum(seconds) / len(seconds))
    h, rem = divmod(avg, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# --------------------------------------------------------------------- reports
REPORT_TYPES = {
    "daily", "weekly", "monthly", "teacher", "student", "late", "half_day",
    "working_hours", "early_exit", "overtime", "holiday", "summary",
}


@bp.route("/reports/<rptype>", methods=["GET"])
def reports(rptype: str):
    if rptype not in REPORT_TYPES:
        return jsonify({"error": f"unknown report type '{rptype}'"}), 400
    fmt = (request.args.get("format") or "csv").lower()
    d = _parse_date_arg("date") or _today_utc()
    class_name = request.args.get("class_name")
    section = request.args.get("section")
    search = (request.args.get("q") or "").strip()

    if rptype == "summary":
        return _report_summary(d, class_name, section, fmt)
    if rptype == "holiday":
        return _report_holiday(d, class_name, fmt)
    return _report_session_based(rptype, d, class_name, section, search, fmt)


def _session_query(class_name, section, search):
    q = AttendanceSession.query
    if class_name or section or search:
        q = q.join(Student, Student.id == AttendanceSession.student_id)
        if class_name:
            q = q.filter(Student.class_name == class_name)
        if section:
            q = q.filter(Student.section == section)
        if search:
            like = f"%{search.lower()}%"
            q = q.filter(or_(
                func.lower(Student.roll_no).like(like),
                func.lower(Student.name).like(like),
            ))
    return q


def _report_session_based(rptype: str, d: date, class_name, section, search, fmt: str):
    if rptype == "daily":
        start = d
        end = d
    elif rptype == "weekly":
        start = d - timedelta(days=d.weekday())
        end = start + timedelta(days=6)
    elif rptype == "monthly":
        start = d.replace(day=1)
        # last day of month
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end = start.replace(month=start.month + 1, day=1) - timedelta(days=1)
    else:
        start = _parse_date_arg("start")
        end = _parse_date_arg("end")
        if not start:
            start = d - timedelta(days=30)
        if not end:
            end = d

    q = _session_query(class_name, section, search).filter(
        AttendanceSession.session_date >= start,
        AttendanceSession.session_date <= end,
    )
    sessions = q.all()

    if rptype in ("teacher", "student"):
        # Same as a generic session rollup
        sessions = sessions
    elif rptype == "late":
        sessions = [s for s in sessions if s.is_late or s.status_detail == "late"]
    elif rptype == "half_day":
        sessions = [s for s in sessions if s.is_half_day or s.status_detail == "half_day"]
    elif rptype == "working_hours":
        sessions = [s for s in sessions if s.out_time]
    elif rptype == "early_exit":
        sessions = [s for s in sessions if s.is_early_exit or s.status_detail == "early_exit"]
    elif rptype == "overtime":
        sessions = [s for s in sessions if s.is_overtime or s.status_detail == "overtime"]

    rows = []
    for s in sessions:
        stu = Student.query.get(s.student_id)
        rows.append({
            "date": s.session_date.isoformat() if s.session_date else "",
            "roll_no": stu.roll_no if stu else "",
            "name": stu.name if stu else "",
            "class": stu.class_name if stu else "",
            "section": stu.section if stu else "",
            "in_time": s.in_time.astimezone().strftime("%H:%M:%S") if s.in_time else "",
            "out_time": s.out_time.astimezone().strftime("%H:%M:%S") if s.out_time else "",
            "status": s.status_detail,
            "working_hours": format_minutes(s.working_minutes),
            "overtime": format_minutes(s.overtime_minutes),
            "is_late": "Y" if s.is_late else "",
            "is_half_day": "Y" if s.is_half_day else "",
            "is_early_exit": "Y" if s.is_early_exit else "",
            "is_overtime": "Y" if s.is_overtime else "",
        })

    headers = list(rows[0].keys()) if rows else [
        "date", "roll_no", "name", "class", "section",
        "in_time", "out_time", "status", "working_hours", "overtime",
        "is_late", "is_half_day", "is_early_exit", "is_overtime",
    ]
    title = f"{rptype.title()} Report ({start.isoformat()} to {end.isoformat()})"
    return _export(rows, headers, fmt, title, f"{rptype}_{start.isoformat()}_{end.isoformat()}")


def _report_summary(d: date, class_name, section, fmt: str):
    student_q = Student.query.filter_by(is_active=True)
    if class_name:
        student_q = student_q.filter_by(class_name=class_name)
    if section:
        student_q = student_q.filter_by(section=section)
    total_students = student_q.count()
    sess_q = _session_query(class_name, section, "").filter(AttendanceSession.session_date == d)
    sessions = sess_q.all()
    present = sum(1 for s in sessions if s.status_detail in {"present", "late", "overtime", "early_exit"})
    late = sum(1 for s in sessions if s.is_late or s.status_detail == "late")
    half_day = sum(1 for s in sessions if s.is_half_day or s.status_detail == "half_day")
    absent = max(total_students - len(sessions), 0)
    early_exit = sum(1 for s in sessions if s.is_early_exit or s.status_detail == "early_exit")
    overtime = sum(1 for s in sessions if s.is_overtime or s.status_detail == "overtime")
    total_working = sum(s.working_minutes for s in sessions)
    total_ot = sum(s.overtime_minutes for s in sessions)
    rows = [
        {"metric": "Total Students", "value": total_students},
        {"metric": "Present", "value": present},
        {"metric": "Late", "value": late},
        {"metric": "Half Day", "value": half_day},
        {"metric": "Absent", "value": absent},
        {"metric": "Early Exit", "value": early_exit},
        {"metric": "Overtime", "value": overtime},
        {"metric": "Total Working Hours", "value": format_minutes(total_working)},
        {"metric": "Total Overtime", "value": format_minutes(total_ot)},
        {"metric": "Holiday", "value": "Yes" if is_holiday(d, "all") else "No"},
    ]
    return _export(rows, ["metric", "value"], fmt, f"Attendance Summary {d.isoformat()}", f"summary_{d.isoformat()}")


def _report_holiday(d: date, class_name, fmt: str):
    rows_q = AttendanceHoliday.query.order_by(AttendanceHoliday.holiday_date.desc())
    if class_name:
        rows_q = rows_q.filter(or_(AttendanceHoliday.scope == class_name, AttendanceHoliday.scope == "all"))
    rows = [{"date": h.holiday_date.isoformat(), "name": h.name, "kind": h.kind, "scope": h.scope} for h in rows_q.all()]
    return _export(rows, ["date", "name", "kind", "scope"], fmt, "Holiday Calendar", "holidays")


def _export(rows, headers, fmt: str, title: str, filename: str):
    if fmt == "json":
        return jsonify({"title": title, "rows": rows, "headers": headers})
    if fmt in ("pdf", "excel"):
        return _export_pdf(rows, headers, title, filename)
    # CSV default
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for r in rows:
        w.writerow([r.get(h, "") for h in headers])
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}.csv"},
    )


def _export_pdf(rows, headers, title: str, filename: str):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as _cv
        from reportlab.lib.units import cm
    except Exception:
        # reportlab not installed; fall back to CSV
        return _export(rows, headers, "csv", title, filename)
    pdf_buf = io.BytesIO()
    c = _cv.Canvas(pdf_buf, pagesize=A4)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2 * cm, 28 * cm, title[:90])
    c.setFont("Helvetica", 9)
    y = 26 * cm
    # headers
    c.setFont("Helvetica-Bold", 9)
    col_w = 17 * cm / max(len(headers), 1)
    for i, h in enumerate(headers):
        c.drawString(2 * cm + i * col_w, y, str(h)[:18])
    y -= 0.6 * cm
    c.setFont("Helvetica", 9)
    for r in rows:
        if y < 2 * cm:
            c.showPage()
            y = 28 * cm
            c.setFont("Helvetica", 9)
        for i, h in enumerate(headers):
            c.drawString(2 * cm + i * col_w, y, str(r.get(h, ""))[:18])
        y -= 0.5 * cm
    c.save()
    return Response(
        pdf_buf.getvalue(),
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}.pdf"},
    )

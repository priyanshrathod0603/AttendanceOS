"""
Small Language Model (SLM) for natural-language attendance queries.

Hybrid approach:

1. Rule-based intent parser -- works fully offline, no GPU, no model file.
2. Optional Ollama fallback (``phi3:mini``, ``llama3.2:1b``, etc.) when
   ``USE_OLLAMA=true`` in ``.env`` and the Ollama daemon is running.

The rule layer answers common attendance questions deterministically
from the live PostgreSQL data; Ollama handles richer chat follow-ups.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Callable

from sqlalchemy import func

from database.db import db
from database.models import Attendance, Student


HELP_TEXT = (
    "Try asking things like:\n"
    "  - Who is present today?\n"
    "  - How many students are present today?\n"
    "  - Who is absent today?\n"
    "  - Find Priyansh\n"
    "  - Attendance on 2026-06-29\n"
    "  - Summary"
)


INTENTS: dict[str, list[str]] = {
    "attendance_today": [
        r"who(?:'s| is)?\s+present today",
        r"today'?s?\s+attendance",
        r"attendance today",
        r"present today",
    ],
    "attendance_count_today": [
        r"how many.*today",
        r"total.*present today",
        r"count.*today",
        r"how many.*present",
    ],
    "attendance_count_date": [
        r"how many.*on (\d{4}-\d{2}-\d{2})",
        r"attendance on (\d{4}-\d{2}-\d{2})",
        r"present on (\d{4}-\d{2}-\d{2})",
    ],
    "absentees_today": [
        r"who(?:'s| is)?\s+absent",
        r"absent today",
        r"missing today",
        r"not present today",
    ],
    "student_lookup": [
        r"find (?:student )?(\w+)",
        r"who is (\w+)",
        r"locate (\w+)",
    ],
    "summary": [r"summary", r"overview", r"stats", r"statistics"],
    "help": [r"^help$", r"what can you do"],
}


def detect_intent(text: str) -> tuple[str | None, re.Match | None]:
    """Return ``(intent_name, regex_match)`` or ``(None, None)``."""
    lowered = (text or "").lower().strip()
    for intent, patterns in INTENTS.items():
        for pattern in patterns:
            match = re.search(pattern, lowered)
            if match:
                return intent, match
    return None, None


def _class_filter(text: str) -> str | None:
    match = re.search(r"class\s*([\w\-]+)", text.lower())
    return match.group(1).upper() if match else None


def _handle_attendance_today(_text: str, _match: re.Match) -> str:
    rows = (
        db.session.query(Student, Attendance)
        .join(Attendance, Attendance.student_id == Student.id)
        .filter(func.date(Attendance.timestamp) == date.today())
        .order_by(Attendance.timestamp)
        .all()
    )
    if not rows:
        return "No attendance has been recorded today yet."
    names = ", ".join(f"{s.name} ({s.roll_no})" for s, _ in rows)
    return f"{len(rows)} student(s) marked present today: {names}."


def _handle_attendance_count_today(_text: str, _match: re.Match) -> str:
    n = (
        db.session.query(func.count(Attendance.id))
        .filter(func.date(Attendance.timestamp) == date.today())
        .scalar()
        or 0
    )
    return f"{n} student(s) are marked present today."


def _handle_attendance_count_date(_text: str, match: re.Match) -> str:
    try:
        d = datetime.strptime(match.group(1), "%Y-%m-%d").date()
    except ValueError:
        return "That date doesn't look right. Use YYYY-MM-DD."
    n = (
        db.session.query(func.count(Attendance.id))
        .filter(func.date(Attendance.timestamp) == d)
        .scalar()
        or 0
    )
    return f"{n} attendance record(s) found on {d.isoformat()}."


def _handle_absentees_today(text: str, _match: re.Match) -> str:
    present_ids = (
        db.session.query(Attendance.student_id)
        .filter(func.date(Attendance.timestamp) == date.today())
        .subquery()
    )
    cls = _class_filter(text)
    q = Student.query.filter(~Student.id.in_(present_ids))
    if cls:
        q = q.filter(Student.class_name == cls)
    rows = q.all()
    if not rows:
        return "Everyone is present today. No absentees."
    return f"{len(rows)} absent: " + ", ".join(
        f"{s.name} ({s.roll_no})" for s in rows
    )


def _handle_student_lookup(_text: str, match: re.Match) -> str:
    needle = match.group(1).lower()
    rows = Student.query.all()
    hits = [
        s
        for s in rows
        if needle in s.name.lower() or needle in (s.roll_no or "").lower()
    ]
    if not hits:
        return f"No student matched '{needle}'."
    return "Found: " + ", ".join(f"{s.name} ({s.roll_no})" for s in hits)


def _handle_summary(_text: str, _match: re.Match) -> str:
    total = Student.query.count()
    today_present = (
        db.session.query(func.count(Attendance.id))
        .filter(func.date(Attendance.timestamp) == date.today())
        .scalar()
        or 0
    )
    total_records = Attendance.query.count()
    return (
        f"Total students: {total}. "
        f"Present today: {today_present}. "
        f"Total attendance records: {total_records}."
    )


HANDLERS: dict[str, Callable[[str, re.Match], str]] = {
    "attendance_today": _handle_attendance_today,
    "attendance_count_today": _handle_attendance_count_today,
    "attendance_count_date": _handle_attendance_count_date,
    "absentees_today": _handle_absentees_today,
    "student_lookup": _handle_student_lookup,
    "summary": _handle_summary,
}


def _use_ollama() -> bool:
    try:
        from flask import current_app

        return bool(current_app.config.get("USE_OLLAMA", False))
    except Exception:  # noqa: BLE001
        return False


def _ollama_answer(question: str) -> str:
    try:
        import requests
        from flask import current_app

        model = current_app.config.get("OLLAMA_MODEL", "phi3:mini")
        url = current_app.config.get("OLLAMA_URL", "http://localhost:11434")
        rows = (
            db.session.query(
                Student.name, Student.roll_no, Attendance.timestamp
            )
            .join(
                Attendance,
                Attendance.student_id == Student.id,
                isouter=True,
            )
            .order_by(Attendance.timestamp.desc())
            .limit(20)
            .all()
        )
        ctx = "\n".join(
            f"- {r.name} ({r.roll_no}) @ {r.timestamp or 'no record'}" for r in rows
        )
        prompt = (
            "You are the assistant for a face-recognition attendance system. "
            "Use the context below to answer the user's question in one short "
            "sentence.\n\n"
            f"Context:\n{ctx}\n\nQuestion: {question}\nAnswer:"
        )
        res = requests.post(
            f"{url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=30,
        )
        if res.ok:
            return res.json().get("response", "").strip() or "No answer."
        return f"Ollama error: HTTP {res.status_code}"
    except Exception as exc:  # noqa: BLE001
        return f"SLM fallback unavailable: {exc}"


def answer(question: str) -> str:
    """Top-level SLM entry point used by the Flask ``/api/ask`` route."""
    question = (question or "").strip()
    if not question:
        return HELP_TEXT
    intent, match = detect_intent(question)
    if intent == "help":
        return HELP_TEXT
    if intent and intent in HANDLERS:
        return HANDLERS[intent](question, match)
    if _use_ollama():
        return _ollama_answer(question)
    return "I couldn't understand that. " + HELP_TEXT

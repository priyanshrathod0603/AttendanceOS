"""Enterprise IN/OUT Time Management module.

This package is purely additive to the existing face attendance system.
It wraps the recognizer's existing ``_mark_attendance`` flow with a thin
service layer that:

* Persists time rules per scope (teacher / student).
* Tracks one ``AttendanceSession`` row per student per day.
* Decides IN vs OUT based on admin-configured windows.
* Computes late, half-day, early-exit, overtime, working hours.
* Maintains a holiday calendar and an audit log.

No existing tables, APIs, or recognizer logic are modified.
"""
from __future__ import annotations

from .models import (
    AttendanceAuditLog,
    AttendanceHoliday,
    AttendanceSession,
    AttendanceTimeRule,
)
from .service import (
    audit,
    compute_early_exit,
    compute_initial_status,
    compute_overtime,
    compute_working_hours,
    ensure_default_rules,
    format_hms,
    format_minutes,
    get_active_rules,
    is_holiday,
    mark_event,
)

__all__ = [
    "AttendanceAuditLog",
    "AttendanceHoliday",
    "AttendanceSession",
    "AttendanceTimeRule",
    "audit",
    "compute_early_exit",
    "compute_initial_status",
    "compute_overtime",
    "compute_working_hours",
    "ensure_default_rules",
    "format_hms",
    "format_minutes",
    "get_active_rules",
    "is_holiday",
    "mark_event",
]

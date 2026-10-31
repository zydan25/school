"""Attendance business domain services."""
from apps.attendance.services.attendance_service import (
    approve_register,
    bulk_record_attendance,
    get_or_create_register,
    lock_register,
    request_reopen_register,
    review_reopen_request,
    submit_register,
)
from apps.attendance.services.calendar_service import (
    apply_central_template,
    generate_event_occurrences,
    is_school_day,
    seed_default_calendar,
)
from apps.attendance.services.excuse_service import (
    approve_early_departure,
    confirm_gate_exit,
    create_early_departure_request,
    create_excuse_request,
    review_excuse_request,
)
from apps.attendance.services.scoring_service import (
    calculate_student_attendance_score,
    recalculate_term_scores,
    sync_score_to_gradebook,
)

__all__ = [
    "get_or_create_register",
    "bulk_record_attendance",
    "submit_register",
    "approve_register",
    "lock_register",
    "request_reopen_register",
    "review_reopen_request",
    "seed_default_calendar",
    "is_school_day",
    "apply_central_template",
    "generate_event_occurrences",
    "create_excuse_request",
    "review_excuse_request",
    "create_early_departure_request",
    "approve_early_departure",
    "confirm_gate_exit",
    "calculate_student_attendance_score",
    "recalculate_term_scores",
    "sync_score_to_gradebook",
]

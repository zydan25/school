"""Transactional staff leave approval and annual allowance checks."""
from __future__ import annotations

import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.staff.models import LeaveRequest, StaffMember, Teacher


def _days_in_year(start: datetime.date, end: datetime.date, year: int) -> int:
    year_start = datetime.date(year, 1, 1)
    year_end = datetime.date(year, 12, 31)
    first = max(start, year_start)
    last = min(end, year_end)
    return max(0, (last - first).days + 1)


def review_leave_request(
    *,
    leave_request: LeaveRequest,
    reviewer,
    approve: bool,
    notes: str = "",
) -> LeaveRequest:
    """Approve/reject one leave request with employee locking and annual quotas."""
    with transaction.atomic():
        locked = LeaveRequest.objects.select_for_update().select_related(
            "leave_type", "teacher", "staff_member",
        ).get(pk=leave_request.pk)

        if locked.status != LeaveRequest.Status.PENDING:
            raise ValidationError("لا يمكن مراجعة طلب إجازة إلا إذا كان قيد المراجعة.")

        if locked.teacher_id:
            employee = Teacher.objects.select_for_update().get(pk=locked.teacher_id)
            employee_filter = {"teacher_id": employee.pk, "staff_member__isnull": True}
        else:
            employee = StaffMember.objects.select_for_update().get(pk=locked.staff_member_id)
            employee_filter = {"staff_member_id": employee.pk, "teacher__isnull": True}

        if employee.school_id != locked.school_id or employee.is_archived:
            raise ValidationError("ملف الموظف لم يعد صالحاً في المدرسة.")

        if approve:
            overlapping = LeaveRequest.objects.filter(
                school=locked.school,
                status=LeaveRequest.Status.APPROVED,
                is_archived=False,
                start_date__lte=locked.end_date,
                end_date__gte=locked.start_date,
                **employee_filter,
            ).exclude(pk=locked.pk)
            if overlapping.exists():
                raise ValidationError("تتداخل هذه الإجازة مع إجازة أخرى معتمدة للموظف.")

            existing = LeaveRequest.objects.filter(
                school=locked.school,
                leave_type=locked.leave_type,
                status=LeaveRequest.Status.APPROVED,
                is_archived=False,
                **employee_filter,
            ).exclude(pk=locked.pk)
            years = range(locked.start_date.year, locked.end_date.year + 1)
            for year in years:
                requested_days = _days_in_year(locked.start_date, locked.end_date, year)
                used_days = 0
                year_start = datetime.date(year, 1, 1)
                year_end = datetime.date(year, 12, 31)
                for other in existing.filter(
                    start_date__lte=year_end,
                    end_date__gte=year_start,
                ).only("start_date", "end_date"):
                    used_days += _days_in_year(other.start_date, other.end_date, year)
                if used_days + requested_days > locked.leave_type.days_allowed:
                    raise ValidationError(
                        f"يتجاوز الطلب رصيد نوع الإجازة ({locked.leave_type.name}) لعام {year}: "
                        f"المتاح {locked.leave_type.days_allowed} يوماً، والمستخدم {used_days} يوماً."
                    )
            locked.status = LeaveRequest.Status.APPROVED
            locked.approved_by = reviewer
            locked.approved_at = timezone.now()
        else:
            locked.status = LeaveRequest.Status.REJECTED
            locked.approved_by = None
            locked.approved_at = None

        locked.reviewed_by = reviewer
        locked.reviewed_at = timezone.now()
        locked.review_notes = (notes or "")[:500]
        locked.save(update_fields=[
            "status", "approved_by", "approved_at",
            "reviewed_by", "reviewed_at", "review_notes", "updated_at",
        ])
        return locked

"""Versioned timetable lifecycle and effective schedule selection."""
from __future__ import annotations

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from apps.timetable.models import ClassSchedule, TimetablePlan


def _scope_plans(*, school, academic_year, branch):
    return TimetablePlan.objects.filter(
        school=school, academic_year=academic_year, branch=branch, is_archived=False,
    )


@transaction.atomic
def copy_timetable_plan(*, school, academic_year, branch=None, source_plan=None, name=None, effective_from=None, academic_term=None, bell_schedule=None, created_by=None, notes=""):
    """Create a draft version from a plan or the pre-versioned timetable."""
    if academic_year.school_id != school.pk:
        raise ValidationError("السنة الدراسية لا تتبع المدرسة المحددة.")
    if branch is None and academic_year.branch_id:
        branch = academic_year.branch
    if branch and branch.school_id != school.pk:
        raise ValidationError("الفرع لا يتبع المدرسة المحددة.")
    if academic_year.branch_id and academic_year.branch_id != getattr(branch, "pk", None):
        raise ValidationError("الفرع لا يطابق فرع السنة الدراسية.")
    if source_plan is None:
        source_plan = _scope_plans(school=school, academic_year=academic_year, branch=branch).filter(
            status__in=[TimetablePlan.Status.PUBLISHED, TimetablePlan.Status.RETIRED],
        ).order_by("-effective_from", "-version").first()
    if source_plan and (source_plan.school_id != school.pk or source_plan.academic_year_id != academic_year.pk or source_plan.branch_id != getattr(branch, "pk", None)):
        raise ValidationError("النسخة المصدر يجب أن تتبع المدرسة والسنة والفرع المستهدف نفسه.")
    if source_plan:
        source_rows = ClassSchedule.objects.filter(timetable_plan=source_plan, is_archived=False).order_by("day_of_week", "period_number", "section_id")
        bell_schedule = bell_schedule or source_plan.bell_schedule
        academic_term = academic_term or source_plan.academic_term
    else:
        source_rows = ClassSchedule.objects.filter(
            school=school, academic_year=academic_year, timetable_plan__isnull=True,
            is_archived=False, branch=branch,
        ).order_by("day_of_week", "period_number", "section_id")
    version = (_scope_plans(school=school, academic_year=academic_year, branch=branch).aggregate(value=Max("version"))["value"] or 0) + 1
    plan = TimetablePlan.objects.create(
        school=school, branch=branch, academic_year=academic_year, academic_term=academic_term,
        bell_schedule=bell_schedule, based_on=source_plan,
        name=name or f"الجدول {academic_year.name} - نسخة {version}", version=version,
        status=TimetablePlan.Status.DRAFT, effective_from=effective_from or timezone.localdate(), notes=notes or "",
    )
    for row in source_rows:
        ClassSchedule.objects.create(
            school=school, branch=branch, timetable_plan=plan,
            bell_schedule=row.bell_schedule or bell_schedule, academic_year=academic_year,
            academic_term=academic_term or row.academic_term, section=row.section, subject=row.subject,
            teacher=row.teacher, classroom=row.classroom, day_of_week=row.day_of_week,
            period_number=row.period_number, start_time=row.start_time, end_time=row.end_time,
        )
    return plan


@transaction.atomic
def submit_timetable_plan(plan, *, submitted_by=None):
    locked = TimetablePlan.objects.select_for_update().get(pk=plan.pk)
    if locked.status != TimetablePlan.Status.DRAFT:
        raise ValidationError("لا يمكن إرسال نسخة الجدول إلا من حالة المسودة.")
    rows = list(locked.class_schedules.filter(is_archived=False))
    if not rows:
        raise ValidationError("لا يمكن إرسال نسخة جدول فارغة للمراجعة.")
    for row in rows:
        row.full_clean()
    locked.status = TimetablePlan.Status.IN_REVIEW
    locked.submitted_by = submitted_by
    locked.submitted_at = timezone.now()
    locked.is_current = False
    locked.save(update_fields=["status", "submitted_by", "submitted_at", "is_current", "updated_at"])
    return locked


@transaction.atomic
def approve_timetable_plan(plan, *, approved_by=None):
    locked = TimetablePlan.objects.select_for_update().get(pk=plan.pk)
    if locked.status != TimetablePlan.Status.IN_REVIEW:
        raise ValidationError("لا يمكن اعتماد نسخة الجدول إلا بعد تقديمها للمراجعة.")
    if not locked.class_schedules.filter(is_archived=False).exists():
        raise ValidationError("لا يمكن اعتماد نسخة جدول بلا حصص.")
    locked.status = TimetablePlan.Status.APPROVED
    locked.approved_by = approved_by
    locked.approved_at = timezone.now()
    locked.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    return locked


@transaction.atomic
def publish_timetable_plan(plan, *, published_by=None):
    locked = TimetablePlan.objects.select_for_update().get(pk=plan.pk)
    if locked.status != TimetablePlan.Status.APPROVED:
        raise ValidationError("لا يمكن نشر نسخة الجدول إلا بعد اعتمادها.")
    rows = list(locked.class_schedules.filter(is_archived=False))
    if not rows:
        raise ValidationError("لا يمكن نشر نسخة جدول فارغة.")
    for row in rows:
        row.full_clean()
    previous = _scope_plans(school=locked.school, academic_year=locked.academic_year, branch=locked.branch).select_for_update().filter(
        status=TimetablePlan.Status.PUBLISHED, is_current=True,
    ).exclude(pk=locked.pk).first()
    if previous:
        if locked.effective_from <= previous.effective_from:
            raise ValidationError("يجب أن يبدأ إصدار الجدول الجديد بعد بداية الإصدار المنشور الحالي.")
        previous.effective_to = locked.effective_from - timedelta(days=1)
        previous.status = TimetablePlan.Status.RETIRED
        previous.is_current = False
        previous.save(update_fields=["effective_to", "status", "is_current", "updated_at"])
    locked.status = TimetablePlan.Status.PUBLISHED
    locked.is_current = True
    locked.published_by = published_by
    locked.published_at = timezone.now()
    locked.save(update_fields=["status", "is_current", "published_by", "published_at", "updated_at"])
    return locked


def get_effective_class_schedules(*, school, on_date=None, branch=None, section_id=None):
    """Resolve the current published plan (branch override first), then legacy rows."""
    from apps.academics.models import Section
    from apps.tenants.models import Branch

    on_date = on_date or timezone.localdate()
    if branch is None and section_id:
        branch_id = Section.objects.filter(pk=section_id, school=school).values_list("branch_id", flat=True).first()
        if branch_id:
            branch = Branch.objects.filter(pk=branch_id, school=school, is_archived=False).first()
    applicable = TimetablePlan.objects.filter(
        school=school, is_archived=False,
        status__in=[TimetablePlan.Status.PUBLISHED, TimetablePlan.Status.RETIRED],
        effective_from__lte=on_date,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on_date))
    plan = None
    if branch:
        plan = applicable.filter(branch=branch).order_by("-effective_from", "-version").first()
    if plan is None:
        plan = applicable.filter(branch__isnull=True).order_by("-effective_from", "-version").first()
    if plan:
        rows = ClassSchedule.objects.filter(school=school, timetable_plan=plan, is_archived=False)
    else:
        legacy = ClassSchedule.objects.filter(school=school, timetable_plan__isnull=True, is_archived=False)
        if branch:
            branch_rows = legacy.filter(branch=branch)
            rows = branch_rows if branch_rows.exists() else legacy.filter(branch__isnull=True)
        else:
            rows = legacy.filter(branch__isnull=True)
    if section_id:
        rows = rows.filter(section_id=section_id)
    return rows.select_related("section", "subject", "teacher__user", "classroom", "bell_schedule").order_by("day_of_week", "period_number")
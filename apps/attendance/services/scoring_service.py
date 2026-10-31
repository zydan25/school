"""Attendance Scoring, Policy Deductions, and GradeBook Synchronization Service."""
from __future__ import annotations

from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from apps.academics.models import AcademicTerm, Subject
from apps.assessments.models import AssessmentType, GradeBook
from apps.attendance.models import (
    AttendanceScoreEntry,
    AttendanceScoringPolicy,
    AttendanceStatusType,
    StudentAttendanceRecord,
)
from apps.students.models import Student


def get_or_create_policy(
    school,
    academic_year,
    subject: Subject | None = None,
) -> AttendanceScoringPolicy:
    """استرجاع أو إنشاء سياسة احتساب درجات المواظبة المعتمدة."""
    # First search for subject-specific policy
    if subject:
        policy = AttendanceScoringPolicy.objects.filter(
            school=school,
            academic_year=academic_year,
            subject=subject,
            is_active=True,
            is_archived=False,
        ).first()
        if policy:
            return policy

    # General school policy
    policy = AttendanceScoringPolicy.objects.filter(
        school=school,
        academic_year=academic_year,
        subject__isnull=True,
        is_active=True,
        is_archived=False,
    ).first()

    if not policy:
        policy = AttendanceScoringPolicy.objects.create(
            school=school,
            academic_year=academic_year,
            subject=None,
            total_attendance_score=Decimal("10.00"),
            unexcused_absence_deduction=Decimal("1.00"),
            unexcused_late_deduction=Decimal("0.25"),
            excused_absence_deduction=Decimal("0.00"),
            min_score=Decimal("0.00"),
            is_active=True,
            notes="السياسة الافتراضية الموحدة للمواظبة والسلوك",
        )

    return policy


def calculate_student_attendance_score(
    school,
    student: Student,
    academic_term: AcademicTerm,
    subject: Subject | None = None,
) -> AttendanceScoreEntry:
    """احتساب درجة المواظبة الفعلية للطالب خلال الفصل الدراسي وتطبيق الخصومات."""
    policy = get_or_create_policy(school, academic_term.academic_year, subject)

    records = StudentAttendanceRecord.objects.filter(
        school=school,
        student=student,
        register__date__gte=academic_term.starts_on,
        register__date__lte=academic_term.ends_on,
        is_archived=False,
    )
    if subject:
        records = records.filter(register__schedule__subject=subject)

    unexcused_absences = records.filter(
        status_category=AttendanceStatusType.Category.ABSENT_UNEXCUSED
    ).count()

    excused_absences = records.filter(
        status_category=AttendanceStatusType.Category.ABSENT_EXCUSED
    ).count()

    late_count = records.filter(
        status_category=AttendanceStatusType.Category.LATE
    ).count()

    deduction = (
        (Decimal(unexcused_absences) * policy.unexcused_absence_deduction)
        + (Decimal(excused_absences) * policy.excused_absence_deduction)
        + (Decimal(late_count) * policy.unexcused_late_deduction)
    )

    final_score = max(policy.min_score, policy.total_attendance_score - deduction)

    with transaction.atomic():
        entry, _ = AttendanceScoreEntry.objects.update_or_create(
            school=school,
            student=student,
            academic_term=academic_term,
            subject=subject,
            defaults={
                "scoring_policy": policy,
                "raw_score": policy.total_attendance_score,
                "unexcused_absence_count": unexcused_absences,
                "excused_absence_count": excused_absences,
                "late_count": late_count,
                "deduction_total": deduction,
                "final_score": final_score,
                "calculated_at": timezone.now(),
            },
        )

    return entry


def recalculate_term_scores(
    school,
    academic_term: AcademicTerm,
    section=None,
    subject: Subject | None = None,
) -> list[AttendanceScoreEntry]:
    """إعادة احتساب درجات المواظبة جماعياً لجميع طلاب شعبة أو مدرسة معينة."""
    students = Student.objects.filter(school=school, status=Student.Status.ACTIVE, is_archived=False)
    if section:
        students = students.filter(section=section)

    entries = []
    for student in students:
        entry = calculate_student_attendance_score(school, student, academic_term, subject)
        entries.append(entry)
    return entries


def sync_score_to_gradebook(score_entry: AttendanceScoreEntry, teacher=None) -> GradeBook | None:
    """ترحيل درجة المواظبة إلى سجل الدرجات العام والشهادة الأكاديمية."""
    # Must have a subject to link to GradeBook, or pick the first subject
    subject = score_entry.subject
    if not subject:
        subject = Subject.objects.filter(school=score_entry.school, is_active=True).first()
        if not subject:
            return None

    assessment_type, _ = AssessmentType.objects.get_or_create(
        school=score_entry.school,
        code="ATTENDANCE",
        defaults={
            "name": "درجات المواظبة والحضور",
            "default_max_score": score_entry.raw_score,
            "weight_percentage": Decimal("10.00"),
        },
    )

    with transaction.atomic():
        gradebook, _ = GradeBook.objects.update_or_create(
            school=score_entry.school,
            student=score_entry.student,
            academic_term=score_entry.academic_term,
            subject=subject,
            assessment_type=assessment_type,
            defaults={
                "assessment_title": f"درجة المواظبة والحضور - {score_entry.academic_term.name}",
                "score": score_entry.final_score,
                "max_score": score_entry.raw_score,
                "teacher_feedback": f"غياب غير مبرر: {score_entry.unexcused_absence_count}، تأخر: {score_entry.late_count}، حسم: {score_entry.deduction_total}",
                "graded_by": teacher,
                "graded_at": timezone.now(),
                "is_published": True,
            },
        )
        score_entry.is_synced_to_gradebook = True
        score_entry.gradebook_entry = gradebook
        score_entry.save(update_fields=["is_synced_to_gradebook", "gradebook_entry", "updated_at"])

    return gradebook

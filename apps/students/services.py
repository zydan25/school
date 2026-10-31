from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.academics.models import AcademicYear, GradeLevel, Section
from apps.students.models import Student, StudentEnrollment


def promote_student(
    student: Student,
    next_academic_year: AcademicYear,
    next_grade_level: GradeLevel,
    next_section: Section | None = None,
    user=None,
    notes: str = "",
) -> tuple[Student, StudentEnrollment]:
    """
    ترفيع الطالب إلى العام الدراسي التالي والصف الأعلى، مع تحديث السجل التاريخي للقيد.
    """
    if next_academic_year.school_id != student.school_id:
        raise ValidationError("العام الدراسي الجديد لا يتبع مدرسة الطالب.")
    if next_grade_level.school_id != student.school_id:
        raise ValidationError("الصف الدراسي الجديد لا يتبع مدرسة الطالب.")
    if next_section:
        if next_section.school_id != student.school_id:
            raise ValidationError("الشعبة الجديدة لا تتبع مدرسة الطالب.")
        if next_section.grade_id != next_grade_level.pk:
            raise ValidationError("الشعبة المختارة لا تنتمي إلى الصف الدراسي المحدد.")

    with transaction.atomic():
        locked_student = Student.objects.select_for_update().get(pk=student.pk)

        # تحديث القيد السابق إن وجد
        prev_enrollment = StudentEnrollment.objects.filter(
            school=locked_student.school,
            student=locked_student,
            academic_year=locked_student.academic_year,
            is_archived=False,
        ).first()

        if prev_enrollment:
            prev_enrollment.status = StudentEnrollment.Status.PROMOTED
            prev_enrollment.final_result = StudentEnrollment.FinalResult.PASSED
            if notes:
                prev_enrollment.notes = f"{prev_enrollment.notes}\n{notes}".strip()
            prev_enrollment.save(update_fields=["status", "final_result", "notes", "updated_at"])

        # إنشاء قيد العام الجديد
        target_section = next_section or (
            Section.objects.filter(
                school=locked_student.school,
                grade=next_grade_level,
                is_archived=False,
            ).first()
        )
        if not target_section:
            raise ValidationError(f"لا توجد شعب دراسية متاحة في الصف {next_grade_level.name}.")

        new_enrollment, _ = StudentEnrollment.objects.update_or_create(
            school=locked_student.school,
            student=locked_student,
            academic_year=next_academic_year,
            is_archived=False,
            defaults={
                "grade_level": next_grade_level,
                "section": target_section,
                "enrollment_date": timezone.now().date(),
                "status": StudentEnrollment.Status.ENROLLED,
                "final_result": StudentEnrollment.FinalResult.PENDING,
                "notes": notes or f"تم الترفيع إلى {next_grade_level.name} للعام {next_academic_year.name}",
            },
        )

        locked_student.academic_year = next_academic_year
        locked_student.grade_level = next_grade_level
        locked_student.section = target_section
        locked_student.status = Student.Status.ACTIVE
        locked_student.save(update_fields=["academic_year", "grade_level", "section", "status", "updated_at"])

        return locked_student, new_enrollment


def retain_student(
    student: Student,
    next_academic_year: AcademicYear,
    section: Section | None = None,
    user=None,
    notes: str = "",
) -> tuple[Student, StudentEnrollment]:
    """
    إعادة السنة الدراسية للطالب (رسوب أو إعادة بطلب)، مع قيده في نفس الصف للعام الجديد.
    """
    if next_academic_year.school_id != student.school_id:
        raise ValidationError("العام الدراسي الجديد لا يتبع مدرسة الطالب.")
    if section and section.school_id != student.school_id:
        raise ValidationError("الشعبة المختارة لا تتبع مدرسة الطالب.")

    with transaction.atomic():
        locked_student = Student.objects.select_for_update().get(pk=student.pk)

        # تحديث القيد السابق إن وجد
        prev_enrollment = StudentEnrollment.objects.filter(
            school=locked_student.school,
            student=locked_student,
            academic_year=locked_student.academic_year,
            is_archived=False,
        ).first()

        if prev_enrollment:
            prev_enrollment.status = StudentEnrollment.Status.RETAINED
            prev_enrollment.final_result = StudentEnrollment.FinalResult.FAILED
            if notes:
                prev_enrollment.notes = f"{prev_enrollment.notes}\n{notes}".strip()
            prev_enrollment.save(update_fields=["status", "final_result", "notes", "updated_at"])

        target_section = section or locked_student.section
        new_enrollment, _ = StudentEnrollment.objects.update_or_create(
            school=locked_student.school,
            student=locked_student,
            academic_year=next_academic_year,
            is_archived=False,
            defaults={
                "grade_level": locked_student.grade_level,
                "section": target_section,
                "enrollment_date": timezone.now().date(),
                "status": StudentEnrollment.Status.ENROLLED,
                "final_result": StudentEnrollment.FinalResult.PENDING,
                "notes": notes or f"إعادة قيد في الصف {locked_student.grade_level.name} للعام {next_academic_year.name}",
            },
        )

        locked_student.academic_year = next_academic_year
        if section:
            locked_student.section = section
        locked_student.status = Student.Status.ACTIVE
        locked_student.save(update_fields=["academic_year", "section", "status", "updated_at"])

        return locked_student, new_enrollment


def graduate_student(
    student: Student,
    user=None,
    notes: str = "",
) -> Student:
    """
    تخريج الطالب وتحديث وضعه الأكاديمي وقيده الحالي كخريج.
    """
    with transaction.atomic():
        locked_student = Student.objects.select_for_update().get(pk=student.pk)

        current_enrollment = StudentEnrollment.objects.filter(
            school=locked_student.school,
            student=locked_student,
            academic_year=locked_student.academic_year,
            is_archived=False,
        ).first()

        if current_enrollment:
            current_enrollment.status = StudentEnrollment.Status.GRADUATED
            current_enrollment.final_result = StudentEnrollment.FinalResult.PASSED
            if notes:
                current_enrollment.notes = f"{current_enrollment.notes}\n{notes}".strip()
            current_enrollment.save(update_fields=["status", "final_result", "notes", "updated_at"])

        locked_student.status = Student.Status.GRADUATED
        locked_student.save(update_fields=["status", "updated_at"])
        return locked_student


def withdraw_student(
    student: Student,
    reason: str = "",
    user=None,
) -> Student:
    """
    توثيق انسحاب الطالب أو نقله خارج المدرسة وتحديث قيوده.
    """
    with transaction.atomic():
        locked_student = Student.objects.select_for_update().get(pk=student.pk)

        current_enrollment = StudentEnrollment.objects.filter(
            school=locked_student.school,
            student=locked_student,
            academic_year=locked_student.academic_year,
            is_archived=False,
        ).first()

        if current_enrollment:
            current_enrollment.status = StudentEnrollment.Status.WITHDRAWN
            if reason:
                current_enrollment.notes = f"{current_enrollment.notes}\nسبب الانسحاب: {reason}".strip()
            current_enrollment.save(update_fields=["status", "notes", "updated_at"])

        locked_student.status = Student.Status.WITHDRAWN
        locked_student.save(update_fields=["status", "updated_at"])
        return locked_student

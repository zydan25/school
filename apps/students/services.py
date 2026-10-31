from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import MembershipRole, SchoolMembership, SchoolRole, User
from apps.auditlog.services import record_event
from apps.academics.models import AcademicYear, GradeLevel, Section
from apps.students.models import Student, StudentEnrollment, StudentMovement


def record_student_movement(
    *,
    student: Student,
    movement_type: str,
    recorded_by=None,
    previous_academic_year=None,
    previous_grade_level=None,
    previous_section=None,
    next_academic_year=None,
    next_grade_level=None,
    next_section=None,
    reason: str = "",
    effective_date=None,
) -> StudentMovement:
    movement = StudentMovement.objects.create(
        school=student.school,
        branch=student.branch,
        student=student,
        movement_type=movement_type,
        previous_academic_year=previous_academic_year,
        previous_grade_level=previous_grade_level,
        previous_section=previous_section,
        next_academic_year=next_academic_year,
        next_grade_level=next_grade_level,
        next_section=next_section,
        reason=(reason or "")[:10000],
        effective_date=effective_date or timezone.localdate(),
        recorded_by=recorded_by,
    )
    record_event(
        action=f"student.{movement_type}",
        description=f"تسجيل حركة {movement.get_movement_type_display()} للطالب {student.get_full_name()}",
        actor=recorded_by,
        school=student.school,
        obj=movement,
        metadata={
            "student_id": str(student.pk),
            "previous_section_id": str(previous_section.pk) if previous_section else None,
            "next_section_id": str(next_section.pk) if next_section else None,
        },
    )
    return movement


@transaction.atomic
def link_student_account(*, student: Student, user: User, actor=None) -> Student:
    """Link a verified phone account to one student profile within a school."""
    locked_student = Student.objects.select_for_update().select_related(
        "school", "branch", "academic_year", "grade_level", "section",
    ).get(pk=student.pk, school=student.school, is_archived=False)
    locked_user = User.objects.select_for_update().get(pk=user.pk)

    if not locked_user.is_active or locked_user.status != User.Status.ACTIVE:
        raise ValidationError("لا يمكن ربط حساب غير نشط بملف طالب.")
    if locked_user.phone_verified_at is None:
        raise ValidationError("يجب توثيق رقم هاتف الحساب قبل ربطه بملف الطالب.")

    conflict = Student.objects.filter(
        school=locked_student.school,
        user=locked_user,
        is_archived=False,
    ).exclude(pk=locked_student.pk).exists()
    if conflict:
        raise ValidationError("الحساب مرتبط بالفعل بملف طالب آخر في المدرسة نفسها.")

    membership = SchoolMembership.objects.select_for_update().filter(
        user=locked_user, school=locked_student.school,
    ).first()
    now = timezone.now()
    if membership is not None:
        if (
            membership.status != SchoolMembership.Status.ACTIVE
            or (membership.expires_at is not None and membership.expires_at <= now)
        ):
            raise ValidationError("للحساب عضوية مدرسية موقوفة أو منتهية؛ لا يمكن تجاوز حالتها بربط الملف.")
    else:
        has_default = SchoolMembership.objects.filter(
            user=locked_user,
            status=SchoolMembership.Status.ACTIVE,
            is_default=True,
        ).exists()
        membership = SchoolMembership.objects.create(
            user=locked_user,
            school=locked_student.school,
            status=SchoolMembership.Status.ACTIVE,
            is_default=not has_default,
            joined_at=now,
        )

    student_role, _ = SchoolRole.objects.get_or_create(
        school=locked_student.school,
        code="student",
        defaults={
            "name": "طالب",
            "description": "وصول ذاتي محدود إلى الملف والخدمات المخصصة للطالب.",
            "is_system": True,
        },
    )
    if not student_role.is_active or student_role.is_archived:
        raise ValidationError("دور الطالب غير مفعل في هذه المدرسة.")
    MembershipRole.objects.get_or_create(
        membership=membership,
        role=student_role,
        defaults={"assigned_by": actor, "valid_from": timezone.localdate()},
    )

    if locked_student.user_id != locked_user.pk:
        locked_student.user = locked_user
        locked_student.save(update_fields=["user", "updated_at"])
        record_event(
            action="student.account_linked",
            description="ربط حساب موثق بملف طالب",
            actor=actor,
            school=locked_student.school,
            obj=locked_student,
            metadata={"user_id": str(locked_user.pk), "phone": locked_user.phone},
        )
    return locked_student


@transaction.atomic
def unlink_student_account(*, student: Student, actor=None) -> Student:
    locked_student = Student.objects.select_for_update().select_related("school").get(
        pk=student.pk, school=student.school, is_archived=False,
    )
    if locked_student.user_id is None:
        raise ValidationError("ملف الطالب غير مرتبط بحساب حالياً.")
    linked_user = locked_student.user
    locked_student.user = None
    locked_student.save(update_fields=["user", "updated_at"])

    membership = SchoolMembership.objects.filter(
        user=linked_user, school=locked_student.school,
    ).first()
    student_role = SchoolRole.objects.filter(
        school=locked_student.school, code="student",
    ).first()
    if membership and student_role:
        MembershipRole.objects.filter(
            membership=membership, role=student_role,
        ).delete()

    record_event(
        action="student.account_unlinked",
        description="فصل حساب المستخدم عن ملف الطالب دون حذف الحساب أو العضوية",
        actor=actor,
        school=locked_student.school,
        obj=locked_student,
        metadata={"user_id": str(linked_user.pk)},
    )
    return locked_student


def _validate_next_year(student, next_academic_year):
    if next_academic_year.school_id != student.school_id:
        raise ValidationError("العام الدراسي الجديد لا يتبع مدرسة الطالب.")
    if next_academic_year.is_archived or next_academic_year.status not in {
        AcademicYear.Status.PLANNING, AcademicYear.Status.ACTIVE,
    }:
        raise ValidationError("لا يمكن النقل إلى سنة دراسية مغلقة أو مؤرشفة.")
    if next_academic_year.starts_on <= student.academic_year.starts_on:
        raise ValidationError("يجب أن تكون السنة الدراسية المستهدفة لاحقة للسنة الحالية.")


def promote_student(
    student: Student,
    next_academic_year: AcademicYear,
    next_grade_level: GradeLevel,
    next_section: Section | None = None,
    user=None,
    notes: str = "",
) -> tuple[Student, StudentEnrollment]:
    """Promote a student and retain a permanent movement record."""
    _validate_next_year(student, next_academic_year)
    if next_grade_level.school_id != student.school_id or next_grade_level.is_archived or not next_grade_level.is_active:
        raise ValidationError("الصف الدراسي الجديد غير متاح في المدرسة.")
    if next_section:
        if next_section.school_id != student.school_id:
            raise ValidationError("الشعبة الجديدة لا تتبع مدرسة الطالب.")
        if next_section.is_archived or not next_section.is_active:
            raise ValidationError("الشعبة الجديدة غير نشطة.")
        if next_section.academic_year_id != next_academic_year.pk:
            raise ValidationError("الشعبة الجديدة لا تنتمي إلى العام الدراسي الجديد المحدد.")
        if next_section.grade_id != next_grade_level.pk:
            raise ValidationError("الشعبة المختارة لا تنتمي إلى الصف الدراسي المحدد.")

    with transaction.atomic():
        locked_student = Student.objects.select_for_update().select_related(
            "school", "branch", "academic_year", "grade_level", "section",
        ).get(pk=student.pk, school=student.school, is_archived=False)
        if locked_student.status != Student.Status.ACTIVE:
            raise ValidationError("لا يمكن ترفيع طالب غير نشط.")
        if StudentEnrollment.objects.filter(
            school=locked_student.school,
            student=locked_student,
            academic_year=next_academic_year,
            is_archived=False,
        ).exists():
            raise ValidationError("يوجد قيد سابق للطالب في السنة المستهدفة؛ راجع السجل قبل إعادة الترفيع.")

        previous_year = locked_student.academic_year
        previous_grade = locked_student.grade_level
        previous_section = locked_student.section
        prev_enrollment = StudentEnrollment.objects.filter(
            school=locked_student.school,
            student=locked_student,
            academic_year=previous_year,
            is_archived=False,
        ).first()

        if prev_enrollment:
            prev_enrollment.status = StudentEnrollment.Status.PROMOTED
            prev_enrollment.final_result = StudentEnrollment.FinalResult.PASSED
            if notes:
                prev_enrollment.notes = f"{prev_enrollment.notes}\n{notes}".strip()
            prev_enrollment.save(update_fields=["status", "final_result", "notes", "updated_at"])

        target_section = next_section or Section.objects.filter(
            school=locked_student.school,
            academic_year=next_academic_year,
            grade=next_grade_level,
            is_archived=False,
            is_active=True,
        ).order_by("name").first()
        if not target_section:
            raise ValidationError(
                f"لا توجد شعب دراسية متاحة في الصف {next_grade_level.name} للعام {next_academic_year.name}."
            )
        if target_section.is_full:
            raise ValidationError("الشعبة المستهدفة ممتلئة.")

        new_enrollment = StudentEnrollment.objects.create(
            school=locked_student.school,
            student=locked_student,
            academic_year=next_academic_year,
            grade_level=next_grade_level,
            section=target_section,
            enrollment_date=timezone.localdate(),
            status=StudentEnrollment.Status.ENROLLED,
            final_result=StudentEnrollment.FinalResult.PENDING,
            notes=notes or f"تم الترفيع إلى {next_grade_level.name} للعام {next_academic_year.name}",
        )

        locked_student.academic_year = next_academic_year
        locked_student.grade_level = next_grade_level
        locked_student.section = target_section
        locked_student.save(update_fields=["academic_year", "grade_level", "section", "updated_at"])
        record_student_movement(
            student=locked_student,
            movement_type=StudentMovement.MovementType.PROMOTED,
            recorded_by=user,
            previous_academic_year=previous_year,
            previous_grade_level=previous_grade,
            previous_section=previous_section,
            next_academic_year=next_academic_year,
            next_grade_level=next_grade_level,
            next_section=target_section,
            reason=notes,
        )
        return locked_student, new_enrollment


def retain_student(
    student: Student,
    next_academic_year: AcademicYear,
    section: Section | None = None,
    user=None,
    notes: str = "",
) -> tuple[Student, StudentEnrollment]:
    """Retain a student in the same grade for the next academic year."""
    _validate_next_year(student, next_academic_year)

    with transaction.atomic():
        locked_student = Student.objects.select_for_update().select_related(
            "school", "branch", "academic_year", "grade_level", "section",
        ).get(pk=student.pk, school=student.school, is_archived=False)
        if locked_student.status != Student.Status.ACTIVE:
            raise ValidationError("لا يمكن إعادة قيد طالب غير نشط.")
        if StudentEnrollment.objects.filter(
            school=locked_student.school,
            student=locked_student,
            academic_year=next_academic_year,
            is_archived=False,
        ).exists():
            raise ValidationError("يوجد قيد سابق للطالب في السنة المستهدفة؛ راجع السجل قبل إعادة القيد.")

        previous_year = locked_student.academic_year
        previous_grade = locked_student.grade_level
        previous_section = locked_student.section
        prev_enrollment = StudentEnrollment.objects.filter(
            school=locked_student.school,
            student=locked_student,
            academic_year=previous_year,
            is_archived=False,
        ).first()
        if prev_enrollment:
            prev_enrollment.status = StudentEnrollment.Status.RETAINED
            prev_enrollment.final_result = StudentEnrollment.FinalResult.FAILED
            if notes:
                prev_enrollment.notes = f"{prev_enrollment.notes}\n{notes}".strip()
            prev_enrollment.save(update_fields=["status", "final_result", "notes", "updated_at"])

        target_section = section or Section.objects.filter(
            school=locked_student.school,
            academic_year=next_academic_year,
            grade=locked_student.grade_level,
            is_archived=False,
            is_active=True,
        ).order_by("name").first()
        if not target_section:
            raise ValidationError(
                f"لا توجد شعب دراسية متاحة في الصف {locked_student.grade_level.name} للعام الدراسي {next_academic_year.name}."
            )
        if (
            target_section.school_id != locked_student.school_id
            or target_section.academic_year_id != next_academic_year.pk
            or target_section.grade_id != locked_student.grade_level_id
            or target_section.is_archived
            or not target_section.is_active
        ):
            raise ValidationError("الشعبة المختارة لا تتبع الصف والسنة الجديدين.")
        if target_section.is_full:
            raise ValidationError("الشعبة المستهدفة ممتلئة.")

        new_enrollment = StudentEnrollment.objects.create(
            school=locked_student.school,
            student=locked_student,
            academic_year=next_academic_year,
            grade_level=locked_student.grade_level,
            section=target_section,
            enrollment_date=timezone.localdate(),
            status=StudentEnrollment.Status.ENROLLED,
            final_result=StudentEnrollment.FinalResult.PENDING,
            notes=notes or f"إعادة قيد في الصف {locked_student.grade_level.name} للعام {next_academic_year.name}",
        )

        locked_student.academic_year = next_academic_year
        locked_student.section = target_section
        locked_student.save(update_fields=["academic_year", "section", "updated_at"])
        record_student_movement(
            student=locked_student,
            movement_type=StudentMovement.MovementType.RETAINED,
            recorded_by=user,
            previous_academic_year=previous_year,
            previous_grade_level=previous_grade,
            previous_section=previous_section,
            next_academic_year=next_academic_year,
            next_grade_level=locked_student.grade_level,
            next_section=target_section,
            reason=notes,
        )
        return locked_student, new_enrollment


def transfer_student(student: Student, target_section: Section, user=None, reason: str = "") -> Student:
    """Transfer a student to another section in the same active academic year."""
    with transaction.atomic():
        locked_student = Student.objects.select_for_update().select_related(
            "school", "branch", "academic_year", "grade_level", "section",
        ).get(pk=student.pk, school=student.school, is_archived=False)
        if locked_student.status != Student.Status.ACTIVE:
            raise ValidationError("لا يمكن نقل طالب غير نشط.")
        section = Section.objects.select_for_update().filter(
            pk=target_section.pk,
            school=locked_student.school,
            academic_year=locked_student.academic_year,
            is_archived=False,
            is_active=True,
        ).first()
        if section is None:
            raise ValidationError("الشعبة المستهدفة غير نشطة أو لا تتبع السنة الدراسية الحالية.")
        if section.grade_id != locked_student.grade_level_id:
            raise ValidationError("النقل الداخلي لا يغيّر الصف الدراسي؛ استخدم إجراء الترفيع أو إعادة القيد.")
        if section.pk == locked_student.section_id:
            raise ValidationError("الطالب مقيد بالفعل في الشعبة المحددة.")
        if section.is_full:
            raise ValidationError("الشعبة المستهدفة ممتلئة.")

        previous_year = locked_student.academic_year
        previous_grade = locked_student.grade_level
        previous_section = locked_student.section
        enrollment = StudentEnrollment.objects.select_for_update().filter(
            school=locked_student.school,
            student=locked_student,
            academic_year=locked_student.academic_year,
            is_archived=False,
        ).first()
        if enrollment is None:
            raise ValidationError("لا يوجد سجل قيد سنوي يمكن تحديثه؛ راجع ملف الطالب أولاً.")
        enrollment.section = section
        enrollment.notes = f"{enrollment.notes}\nنقل داخلي إلى {section.name}: {reason}".strip()
        enrollment.save(update_fields=["section", "notes", "updated_at"])
        locked_student.section = section
        locked_student.save(update_fields=["section", "updated_at"])
        record_student_movement(
            student=locked_student,
            movement_type=StudentMovement.MovementType.TRANSFERRED,
            recorded_by=user,
            previous_academic_year=previous_year,
            previous_grade_level=previous_grade,
            previous_section=previous_section,
            next_academic_year=locked_student.academic_year,
            next_grade_level=locked_student.grade_level,
            next_section=section,
            reason=reason,
        )
        return locked_student


def graduate_student(student: Student, user=None, notes: str = "") -> Student:
    """Graduate a student once and append the resulting movement."""
    with transaction.atomic():
        locked_student = Student.objects.select_for_update().select_related(
            "school", "branch", "academic_year", "grade_level", "section",
        ).get(pk=student.pk, school=student.school, is_archived=False)
        if locked_student.status != Student.Status.ACTIVE:
            raise ValidationError("لا يمكن تخريج طالب غير نشط أو سبق إنهاء قيده.")
        previous_year = locked_student.academic_year
        previous_grade = locked_student.grade_level
        previous_section = locked_student.section
        current_enrollment = StudentEnrollment.objects.filter(
            school=locked_student.school, student=locked_student,
            academic_year=previous_year, is_archived=False,
        ).first()
        if current_enrollment:
            current_enrollment.status = StudentEnrollment.Status.GRADUATED
            current_enrollment.final_result = StudentEnrollment.FinalResult.PASSED
            if notes:
                current_enrollment.notes = f"{current_enrollment.notes}\n{notes}".strip()
            current_enrollment.save(update_fields=["status", "final_result", "notes", "updated_at"])
        locked_student.status = Student.Status.GRADUATED
        locked_student.save(update_fields=["status", "updated_at"])
        record_student_movement(
            student=locked_student,
            movement_type=StudentMovement.MovementType.GRADUATED,
            recorded_by=user,
            previous_academic_year=previous_year,
            previous_grade_level=previous_grade,
            previous_section=previous_section,
            reason=notes,
        )
        return locked_student


def withdraw_student(student: Student, reason: str = "", user=None) -> Student:
    """Withdraw a student once and preserve their current placement in history."""
    with transaction.atomic():
        locked_student = Student.objects.select_for_update().select_related(
            "school", "branch", "academic_year", "grade_level", "section",
        ).get(pk=student.pk, school=student.school, is_archived=False)
        if locked_student.status != Student.Status.ACTIVE:
            raise ValidationError("لا يمكن سحب قيد طالب غير نشط أو سبق إنهاء قيده.")
        previous_year = locked_student.academic_year
        previous_grade = locked_student.grade_level
        previous_section = locked_student.section
        current_enrollment = StudentEnrollment.objects.filter(
            school=locked_student.school, student=locked_student,
            academic_year=previous_year, is_archived=False,
        ).first()
        if current_enrollment:
            current_enrollment.status = StudentEnrollment.Status.WITHDRAWN
            if reason:
                current_enrollment.notes = f"{current_enrollment.notes}\nسبب الانسحاب: {reason}".strip()
            current_enrollment.save(update_fields=["status", "notes", "updated_at"])
        locked_student.status = Student.Status.WITHDRAWN
        locked_student.save(update_fields=["status", "updated_at"])
        record_student_movement(
            student=locked_student,
            movement_type=StudentMovement.MovementType.WITHDRAWN,
            recorded_by=user,
            previous_academic_year=previous_year,
            previous_grade_level=previous_grade,
            previous_section=previous_section,
            reason=reason,
        )
        return locked_student

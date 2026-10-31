from __future__ import annotations

import csv
import io

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api_permissions import (
    STUDENT_AFFAIRS_ROLES,
    has_school_roles,
    require_school_role_or_permission,
    resolve_active_school,
)
from apps.accounts.services import is_platform_operator
from apps.academics.models import AcademicYear, GradeLevel, Section
from apps.students.api.serializers import (
    PromoteStudentSerializer,
    RetainStudentSerializer,
    StudentDetailSerializer,
    StudentListSerializer,
    StudentSafeListSerializer,
    StudentSafeDetailSerializer,
    StudentMovementSerializer,
    StudentTransferSerializer,
    StudentImportRowSerializer,
    WithdrawStudentSerializer,
)
from apps.students.models import Student, StudentMovement
from apps.accounts.models import User, normalize_phone
from apps.students.services import (
    graduate_student,
    link_student_account,
    promote_student,
    record_student_movement,
    retain_student,
    transfer_student,
    unlink_student_account,
    withdraw_student,
)


def _resolve_school(request):
    return resolve_active_school(request)


STUDENT_MANAGE_ROLES = STUDENT_AFFAIRS_ROLES | {
    "admin", "school-admin", "school_admin",
    "principal", "school-principal",
}
STUDENT_READ_ADMIN_ROLES = STUDENT_MANAGE_ROLES | {
    "registrar", "academic-coordinator", "academic_coordinator",
}


def _student_read_queryset(request, school):
    qs = Student.objects.filter(
        school=school, is_archived=False,
    ).select_related("grade_level", "section", "academic_year")
    if is_platform_operator(request.user) or has_school_roles(
        request.user, school, STUDENT_READ_ADMIN_ROLES,
    ):
        return qs

    scope = Q(pk__in=[])
    found_profile = False

    if has_school_roles(request.user, school, {"teacher"}):
        teacher = request.user.teacher_profiles.filter(
            school=school, is_archived=False, is_active_teaching=True,
        ).first()
        if teacher:
            section_ids = teacher.assignments.filter(
                school=school,
                is_archived=False,
                academic_year__status=AcademicYear.Status.ACTIVE,
            ).values_list("section_id", flat=True)
            if section_ids.exists():
                found_profile = True
                scope |= Q(section_id__in=section_ids)

    if has_school_roles(request.user, school, {"guardian"}):
        guardian = request.user.guardian_profiles.filter(
            school=school, is_archived=False,
        ).first()
        if guardian:
            found_profile = True
            scope |= Q(pk__in=guardian.children.filter(
                school=school, is_archived=False,
            ).values_list("pk", flat=True))

    if has_school_roles(request.user, school, {"student"}):
        found_profile = True
        scope |= Q(user=request.user)

    if not found_profile:
        raise PermissionDenied("لا تملك دوراً أو ملفاً يسمح بعرض سجلات الطلاب.")
    return qs.filter(scope).distinct()


class StudentListAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StudentListSerializer

    def get_school(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة أو لا تملك صلاحية الوصول.")
        return school

    def get_serializer_class(self):
        if self.request.method == "POST":
            return StudentDetailSerializer
        if (
            is_platform_operator(self.request.user)
            or has_school_roles(self.request.user, self.get_school(), STUDENT_READ_ADMIN_ROLES)
        ):
            return StudentListSerializer
        return StudentSafeListSerializer

    def get_queryset(self):
        school = self.get_school()
        qs = _student_read_queryset(self.request, school)
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search)
                | Q(middle_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(student_id_number__icontains=search)
            )
        grade_id = self.request.query_params.get("grade_level")
        if grade_id:
            qs = qs.filter(grade_level_id=grade_id)
        section_id = self.request.query_params.get("section")
        if section_id:
            qs = qs.filter(section_id=section_id)
        year_id = self.request.query_params.get("academic_year")
        if year_id:
            qs = qs.filter(academic_year_id=year_id)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs.order_by("first_name", "last_name")

    def perform_create(self, serializer):
        school = self.get_school()
        require_school_role_or_permission(
            self.request, school, STUDENT_MANAGE_ROLES,
            "students.add_student",
        )
        data = serializer.validated_data
        if data.get("status", Student.Status.ACTIVE) != Student.Status.ACTIVE:
            raise ValidationError(
                "ينشأ الطالب بحالة نشطة؛ استخدم إجراءات القيد المخصصة لتغيير الحالة."
            )

        year = get_object_or_404(
            AcademicYear, pk=data["academic_year"].pk, school=school,
            is_archived=False,
        )
        grade = get_object_or_404(
            GradeLevel, pk=data["grade_level"].pk, school=school,
            is_archived=False, is_active=True,
        )
        if year.status not in {
            AcademicYear.Status.PLANNING, AcademicYear.Status.ACTIVE,
        }:
            raise PermissionDenied(
                "لا يمكن تسجيل طالب في سنة دراسية مغلقة أو مؤرشفة."
            )

        with transaction.atomic():
            # Serialize capacity checks for concurrent registrations in this section.
            section = get_object_or_404(
                Section.objects.select_for_update(),
                pk=data["section"].pk, school=school,
                is_archived=False, is_active=True,
            )
            if section.grade_id != grade.pk or section.academic_year_id != year.pk:
                raise PermissionDenied(
                    "يجب أن تتبع الشعبة الصف والسنة الدراسية المحددين."
                )
            if section.is_full:
                raise ValidationError(
                    "الشعبة ممتلئة؛ افتح شعبة جديدة أو زِد سعتها قبل تسجيل الطالب."
                )

            student = Student(
                school=school,
                academic_year=year,
                grade_level=grade,
                section=section,
                student_id_number=data["student_id_number"].strip(),
                first_name=data["first_name"].strip(),
                middle_name=data.get("middle_name", "").strip(),
                last_name=data["last_name"].strip(),
                gender=data.get("gender", Student.Gender.MALE),
                national_id=data.get("national_id", ""),
                birth_date=data.get("birth_date"),
                enrollment_date=data.get("enrollment_date") or timezone.localdate(),
                status=Student.Status.ACTIVE,
            )
            student.full_clean()
            student.save()
            record_student_movement(
                student=student,
                movement_type=StudentMovement.MovementType.ADMITTED,
                recorded_by=self.request.user,
                next_academic_year=year,
                next_grade_level=grade,
                next_section=section,
                reason="تسجيل طالب جديد",
                effective_date=student.enrollment_date,
            )
            serializer.instance = student



class StudentDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StudentSafeDetailSerializer
    lookup_url_kwarg = "pk"

    def get_serializer_class(self):
        if has_school_roles(self.request.user, self.get_school(), STUDENT_READ_ADMIN_ROLES) or is_platform_operator(self.request.user):
            return StudentDetailSerializer
        return StudentSafeDetailSerializer

    def get_school(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        return school

    def get_queryset(self):
        return _student_read_queryset(self.request, self.get_school()).prefetch_related(
            "enrollment_history__academic_year",
            "enrollment_history__grade_level",
            "enrollment_history__section",
        )

    def perform_update(self, serializer):
        school = self.get_school()
        require_school_role_or_permission(
            self.request, school, STUDENT_MANAGE_ROLES,
            "students.change_student",
        )
        lifecycle_fields = {
            "academic_year", "grade_level", "section", "status",
            "enrollment_date",
        }
        changed_lifecycle_fields = []
        for field in lifecycle_fields:
            if field not in serializer.validated_data:
                continue
            new_value = serializer.validated_data[field]
            current_value = getattr(serializer.instance, field)
            old_value = getattr(current_value, "pk", current_value)
            new_value = getattr(new_value, "pk", new_value)
            if old_value != new_value:
                changed_lifecycle_fields.append(field)
        if changed_lifecycle_fields:
            raise ValidationError({
                "detail": (
                    "لا تغيّر الصف أو الشعبة أو السنة أو حالة القيد من تعديل الملف؛ "
                    "استخدم إجراءات الترفيع أو إعادة القيد أو التخرج أو الانسحاب."
                ),
                "fields": sorted(changed_lifecycle_fields),
            })
        serializer.save()

    def perform_destroy(self, instance):
        require_school_role_or_permission(
            self.request, self.get_school(), STUDENT_MANAGE_ROLES,
            "students.delete_student",
        )
        instance.archive(actor=self.request.user, reason="أرشفة الطالب عبر API")


class StudentPromoteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        require_school_role_or_permission(request, school, STUDENT_AFFAIRS_ROLES, "students.change_student")
        student = get_object_or_404(Student, pk=pk, school=school, is_archived=False)
        serializer = PromoteStudentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        next_year = get_object_or_404(AcademicYear, pk=data["next_academic_year_id"], school=school)
        next_grade = get_object_or_404(GradeLevel, pk=data["next_grade_level_id"], school=school)
        next_section = None
        if data.get("next_section_id"):
            next_section = get_object_or_404(Section, pk=data["next_section_id"], school=school)

        student, enrollment = promote_student(
            student=student,
            next_academic_year=next_year,
            next_grade_level=next_grade,
            next_section=next_section,
            user=request.user,
            notes=data.get("notes", ""),
        )
        return Response({
            "message": f"تم ترفيع الطالب {student} إلى {next_grade.name} بنجاح.",
            "student_id": str(student.pk),
            "academic_year": next_year.name,
            "grade_level": next_grade.name,
        }, status=status.HTTP_200_OK)


class StudentRetainAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        require_school_role_or_permission(request, school, STUDENT_AFFAIRS_ROLES, "students.change_student")
        student = get_object_or_404(Student, pk=pk, school=school, is_archived=False)
        serializer = RetainStudentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        next_year = get_object_or_404(AcademicYear, pk=data["next_academic_year_id"], school=school)
        section = None
        if data.get("section_id"):
            section = get_object_or_404(Section, pk=data["section_id"], school=school)

        student, enrollment = retain_student(
            student=student,
            next_academic_year=next_year,
            section=section,
            user=request.user,
            notes=data.get("notes", ""),
        )
        return Response({
            "message": f"تم إعادة قيد الطالب {student} للعام {next_year.name} بنجاح.",
            "student_id": str(student.pk),
            "academic_year": next_year.name,
        }, status=status.HTTP_200_OK)


class StudentGraduateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        require_school_role_or_permission(request, school, STUDENT_AFFAIRS_ROLES, "students.change_student")
        student = get_object_or_404(Student, pk=pk, school=school, is_archived=False)
        notes = request.data.get("notes", "")
        student = graduate_student(student=student, user=request.user, notes=notes)
        return Response({
            "message": f"تم تخريج الطالب {student} بنجاح.",
            "student_id": str(student.pk),
            "status": student.status,
        }, status=status.HTTP_200_OK)


class StudentWithdrawAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        require_school_role_or_permission(request, school, STUDENT_AFFAIRS_ROLES, "students.change_student")
        student = get_object_or_404(Student, pk=pk, school=school, is_archived=False)
        serializer = WithdrawStudentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get("reason", "")
        student = withdraw_student(student=student, reason=reason, user=request.user)
        return Response({
            "message": f"تم توثيق انسحاب الطالب {student} بنجاح.",
            "student_id": str(student.pk),
            "status": student.status,
        }, status=status.HTTP_200_OK)


class StudentAccountBindingAPIView(APIView):
    """Bind/unbind a verified phone account to exactly one student profile."""

    permission_classes = [IsAuthenticated]

    def get_student(self, request, pk):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        require_school_role_or_permission(
            request, school, STUDENT_MANAGE_ROLES, "students.change_student",
        )
        return get_object_or_404(
            Student.objects.select_related("school", "branch"),
            pk=pk, school=school, is_archived=False,
        )

    def post(self, request, pk):
        student = self.get_student(request, pk)
        phone = normalize_phone(request.data.get("phone") or "")
        if not phone:
            raise ValidationError({"phone": "أدخل رقم هاتف الحساب المراد ربطه."})
        user = User.objects.filter(phone=phone).first()
        if user is None:
            raise ValidationError({"phone": "لا يوجد حساب مسجل بهذا الرقم؛ أنشئ الحساب ووثق الهاتف أولاً."})
        linked = link_student_account(
            student=student, user=user, actor=request.user,
        )
        return Response({
            "message": "تم ربط الحساب بملف الطالب بنجاح.",
            "student_id": str(linked.pk),
            "user_id": str(user.pk),
            "phone": user.phone,
        }, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        student = self.get_student(request, pk)
        unlinked = unlink_student_account(student=student, actor=request.user)
        return Response({
            "message": "تم فصل الحساب عن ملف الطالب دون حذف الحساب أو سجلاته.",
            "student_id": str(unlinked.pk),
        }, status=status.HTTP_200_OK)


class StudentTransferAPIView(APIView):
    """Move a student between sections within the same school and academic year."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        require_school_role_or_permission(
            request, school, STUDENT_AFFAIRS_ROLES, "students.change_student",
        )
        student = get_object_or_404(
            Student.objects.select_related(
                "school", "branch", "academic_year", "grade_level", "section",
            ),
            pk=pk, school=school, is_archived=False,
        )
        serializer = StudentTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = get_object_or_404(
            Section,
            pk=serializer.validated_data["target_section_id"],
            school=school,
            is_archived=False,
            is_active=True,
        )
        student = transfer_student(
            student=student,
            target_section=target,
            user=request.user,
            reason=serializer.validated_data.get("reason", ""),
        )
        return Response({
            "message": f"تم نقل الطالب إلى الشعبة {student.section.name} بنجاح.",
            "student_id": str(student.pk),
            "academic_year_id": str(student.academic_year_id),
            "grade_level_id": str(student.grade_level_id),
            "section_id": str(student.section_id),
        })


class StudentMovementListAPIView(generics.ListAPIView):
    """Read-only chronological audit of student admission and lifecycle movements."""

    permission_classes = [IsAuthenticated]
    serializer_class = StudentMovementSerializer

    def get_queryset(self):
        school = _resolve_school(self.request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        require_school_role_or_permission(
            self.request, school, STUDENT_READ_ADMIN_ROLES,
            "students.view_student",
        )
        return StudentMovement.objects.filter(
            school=school,
            student_id=self.kwargs["pk"],
            student__is_archived=False,
            is_archived=False,
        ).select_related(
            "previous_academic_year", "previous_grade_level", "previous_section",
            "next_academic_year", "next_grade_level", "next_section", "recorded_by",
        ).order_by("-effective_date", "-created_at")


def _read_student_import_csv(request):
    upload = request.FILES.get("file")
    if upload is None:
        raise ValidationError({"file": "ارفق ملف CSV في الحقل file."})
    if upload.size > 2 * 1024 * 1024:
        raise ValidationError({"file": "الحد الأقصى لحجم ملف الاستيراد 2 ميجابايت."})
    try:
        content = upload.read().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError({"file": "يجب حفظ الملف بترميز UTF-8."}) from exc

    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise ValidationError({"file": "ملف CSV فارغ أو بلا عناوين أعمدة."})
    normalized_headers = {
        (header or "").strip().lower()
        for header in reader.fieldnames
    }
    required = {
        "student_id_number", "first_name", "last_name",
        "academic_year_id", "grade_level_id", "section_id",
    }
    missing = sorted(required - normalized_headers)
    if missing:
        raise ValidationError({
            "file": "الأعمدة الإلزامية مفقودة.",
            "missing_columns": missing,
        })

    rows = []
    for row_number, raw in enumerate(reader, start=2):
        if not raw or not any((value or "").strip() for value in raw.values()):
            continue
        normalized = {
            (key or "").strip().lower(): (value or "").strip()
            for key, value in raw.items() if key is not None
        }
        for optional_date in ("birth_date", "enrollment_date"):
            if not normalized.get(optional_date):
                normalized[optional_date] = None
        if not normalized.get("gender"):
            normalized["gender"] = Student.Gender.MALE
        rows.append((row_number, normalized))
        if len(rows) > 500:
            raise ValidationError({"file": "الحد الأقصى 500 طالب في عملية الاستيراد الواحدة."})
    if not rows:
        raise ValidationError({"file": "لا يحتوي الملف على سجلات طلاب."})
    return rows


def _validate_student_import_rows(rows, school):
    validated = []
    errors = []
    seen_ids = set()
    for row_number, raw in rows:
        serializer = StudentImportRowSerializer(
            data=raw, context={"school": school},
        )
        if not serializer.is_valid():
            errors.append({
                "row": row_number,
                "student_id_number": raw.get("student_id_number", ""),
                "errors": serializer.errors,
            })
            continue
        data = serializer.validated_data
        student_number = data["student_id_number"].strip()
        normalized = student_number.casefold()
        if normalized in seen_ids:
            errors.append({
                "row": row_number,
                "student_id_number": student_number,
                "errors": {"student_id_number": ["رقم الطالب مكرر داخل ملف الاستيراد."]},
            })
            continue
        seen_ids.add(normalized)
        validated.append((row_number, data))

    existing_query = Q(pk__in=[])
    for _row, data in validated:
        existing_query |= Q(student_id_number__iexact=data["student_id_number"])
    existing_ids = {
        value.casefold()
        for value in Student.objects.filter(
            school=school, is_archived=False,
        ).filter(existing_query).values_list("student_id_number", flat=True)
    } if validated else set()
    filtered = []
    for row_number, data in validated:
        if data["student_id_number"].casefold() in existing_ids:
            errors.append({
                "row": row_number,
                "student_id_number": data["student_id_number"],
                "errors": {"student_id_number": ["رقم الطالب مسجل مسبقاً في هذه المدرسة."]},
            })
        else:
            filtered.append((row_number, data))
    return filtered, errors


class StudentImportPreviewAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        require_school_role_or_permission(
            request, school, STUDENT_MANAGE_ROLES, "students.add_student",
        )
        rows = _read_student_import_csv(request)
        valid, errors = _validate_student_import_rows(rows, school)
        return Response({
            "total_rows": len(rows),
            "valid_rows": len(valid),
            "invalid_rows": len(errors),
            "errors": errors,
            "preview": [{
                "row": row_number,
                "student_id_number": data["student_id_number"],
                "full_name": " ".join(filter(None, [
                    data["first_name"], data.get("middle_name", ""), data["last_name"],
                ])),
                "academic_year": data["academic_year"].name,
                "grade_level": data["grade_level"].name,
                "section": data["section"].name,
            } for row_number, data in valid[:50]],
            "requires_confirmation": not errors,
        })


class StudentImportCommitAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        require_school_role_or_permission(
            request, school, STUDENT_MANAGE_ROLES, "students.add_student",
        )
        rows = _read_student_import_csv(request)
        valid, errors = _validate_student_import_rows(rows, school)
        if errors:
            return Response({
                "message": "لم يتم استيراد أي سجل؛ أصلح أخطاء الملف ثم أعد المعاينة.",
                "total_rows": len(rows),
                "valid_rows": len(valid),
                "invalid_rows": len(errors),
                "errors": errors,
                "imported": 0,
            }, status=status.HTTP_400_BAD_REQUEST)

        imported = []
        with transaction.atomic():
            section_ids = sorted({data["section"].pk for _row, data in valid}, key=str)
            locked_sections = {
                section.pk: section
                for section in Section.objects.select_for_update().filter(
                    school=school, pk__in=section_ids,
                    is_archived=False, is_active=True,
                ).order_by("pk")
            }
            if len(locked_sections) != len(section_ids):
                raise ValidationError("تغيرت بيانات إحدى الشعب؛ أعد معاينة الملف.")
            for row_number, data in valid:
                section = locked_sections[data["section"].pk]
                if section.is_full:
                    raise ValidationError({
                        "row": row_number,
                        "student_id_number": data["student_id_number"],
                        "detail": f"الشعبة {section.name} ممتلئة؛ لم يتم استيراد أي سجل.",
                    })
                student = Student(
                    school=school,
                    student_id_number=data["student_id_number"],
                    first_name=data["first_name"],
                    middle_name=data.get("middle_name", ""),
                    last_name=data["last_name"],
                    gender=data["gender"],
                    academic_year=data["academic_year"],
                    grade_level=data["grade_level"],
                    section=section,
                    enrollment_date=data.get("enrollment_date") or timezone.localdate(),
                    birth_date=data.get("birth_date"),
                    national_id=data.get("national_id", ""),
                    status=Student.Status.ACTIVE,
                )
                student.full_clean()
                student.save()
                record_student_movement(
                    student=student,
                    movement_type=StudentMovement.MovementType.ADMITTED,
                    recorded_by=request.user,
                    next_academic_year=student.academic_year,
                    next_grade_level=student.grade_level,
                    next_section=student.section,
                    reason="استيراد جماعي من ملف CSV",
                    effective_date=student.enrollment_date,
                )
                imported.append({
                    "id": str(student.pk),
                    "student_id_number": student.student_id_number,
                })
        return Response({
            "message": "اكتمل استيراد الطلاب بنجاح.",
            "imported": len(imported),
            "results": imported,
        }, status=status.HTTP_201_CREATED)


class StudentExportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = _resolve_school(request)
        if not school:
            raise PermissionDenied("لم يتم تحديد المدرسة.")
        require_school_role_or_permission(
            request, school, STUDENT_MANAGE_ROLES, "students.view_student",
        )
        qs = Student.objects.filter(
            school=school, is_archived=False,
        ).select_related("academic_year", "grade_level", "section").order_by(
            "student_id_number",
        )
        writer_buffer = io.StringIO()
        writer = csv.writer(writer_buffer)
        writer.writerow([
            "student_id_number", "first_name", "middle_name", "last_name",
            "gender", "academic_year_id", "grade_level_id", "section_id",
            "enrollment_date", "birth_date", "national_id",
            "academic_year", "grade_level", "section",
        ])
        for student in qs.iterator(chunk_size=500):
            writer.writerow([
                student.student_id_number, student.first_name, student.middle_name,
                student.last_name, student.gender, str(student.academic_year_id),
                str(student.grade_level_id), str(student.section_id),
                student.enrollment_date.isoformat() if student.enrollment_date else "",
                student.birth_date.isoformat() if student.birth_date else "",
                student.national_id, student.academic_year.name,
                student.grade_level.name, student.section.name,
            ])
        response = HttpResponse(
            "\ufeff" + writer_buffer.getvalue(),
            content_type="text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = 'attachment; filename="students-export.csv"'
        return response

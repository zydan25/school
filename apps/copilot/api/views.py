"""Views for Copilot endpoints."""
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api_permissions import has_school_roles, resolve_active_school
from apps.accounts.models import SchoolMembership
from apps.academics.models import GradeLevel, Subject
from apps.staff.models import Teacher, TeacherAssignment
from apps.tenants.models import School

from apps.copilot.api.serializers import (
    EssayGradingRequestSerializer,
    LessonPlanRequestSerializer,
    QuizGenerationRequestSerializer,
    StudentChatRequestSerializer,
)
from apps.copilot.models import AIChatSession
from apps.copilot.usage import AIUsageLimitExceeded, run_budgeted_ai_call
from apps.copilot.services.ai_student import (
    fetch_academic_grades,
    fetch_pending_homework,
    fetch_today_lessons,
    process_student_message,
)
from apps.copilot.services.ai_teacher import auto_grade_essay, generate_lesson_plan, generate_quiz
from apps.students.models import Guardian, Student


AI_TEACHER_ADMIN_ROLES = {
    "admin", "school-admin", "school_admin", "school-director",
    "school_director", "principal", "school-principal",
    "academic-coordinator", "academic_coordinator", "student-affairs",
    "student_affairs", "exam-controller", "exam_controller",
}
STUDENT_ADMIN_ROLES = AI_TEACHER_ADMIN_ROLES


def _resolve_school(request):
    school = resolve_active_school(request)
    if school is not None:
        return school
    if getattr(request, "school_context_error", None):
        raise PermissionDenied("اختيار المدرسة غير صالح أو لا تملك عضوية سارية فيها.")

    # Student and guardian app accounts can be verified through their explicit
    # school-owned profile links even when no staff-style membership exists.
    school_ids = set(Student.objects.filter(
        user=request.user, is_archived=False,
        school__status=School.Status.ACTIVE, school__is_archived=False,
    ).values_list("school_id", flat=True))
    school_ids.update(Guardian.objects.filter(
        user=request.user, is_archived=False,
        school__status=School.Status.ACTIVE, school__is_archived=False,
    ).values_list("school_id", flat=True))

    # Profile-linked legacy accounts may lack a membership row. If a membership
    # exists, however, it must still be active and unexpired.
    membership_rows = SchoolMembership.objects.filter(
        user=request.user, school_id__in=school_ids,
    ).values_list("school_id", "status", "expires_at")
    blocked_school_ids = {
        school_id for school_id, member_status, expires_at in membership_rows
        if member_status != SchoolMembership.Status.ACTIVE
        or (expires_at is not None and expires_at <= timezone.now())
    }
    school_ids.difference_update(blocked_school_ids)

    linked_schools = School.objects.filter(
        pk__in=school_ids, status=School.Status.ACTIVE, is_archived=False,
    )

    requested_id = request.headers.get("X-School-ID") or request.query_params.get("school_id")
    requested_code = request.headers.get("X-School-Code") or request.query_params.get("school_code")
    if requested_id:
        school = linked_schools.filter(pk=requested_id).first()
    elif requested_code:
        school = linked_schools.filter(code=requested_code.strip().upper()).first()
    else:
        school = linked_schools.first() if linked_schools.count() == 1 else None
    if school is None:
        raise PermissionDenied("حدد مدرسة مرتبطة بملفك النشط.")
    return school


def _require_teacher_access(request):
    school = _resolve_school(request)
    if has_school_roles(request.user, school, AI_TEACHER_ADMIN_ROLES):
        return school, None
    if not has_school_roles(request.user, school, {"teacher"}):
        raise PermissionDenied("هذه الخدمة مخصصة للمعلمين والإدارة الأكاديمية المخولة.")
    teacher = Teacher.objects.filter(
        school=school, user=request.user, is_archived=False,
        is_active_teaching=True,
    ).first()
    if teacher is None:
        raise PermissionDenied("لا يوجد ملف معلم نشط مرتبط بحسابك في المدرسة المحددة.")
    return school, teacher



def _validate_teacher_scope(*, school, teacher, subject_id=None, grade_level_id=None, student_id=None):
    """Require explicit, school-local teaching assignment context for teacher AI tools."""
    subject = None
    grade_level = None
    student = None
    if subject_id:
        subject = Subject.objects.filter(pk=subject_id, school=school, is_archived=False).first()
        if subject is None:
            raise NotFound("المادة المحددة غير موجودة في المدرسة النشطة.")
    if grade_level_id:
        grade_level = GradeLevel.objects.filter(pk=grade_level_id, school=school, is_archived=False).first()
        if grade_level is None:
            raise NotFound("الصف المحدد غير موجود في المدرسة النشطة.")
    if student_id:
        student = Student.objects.filter(pk=student_id, school=school, is_archived=False).select_related("section").first()
        if student is None:
            raise NotFound("ملف الطالب غير موجود في المدرسة النشطة.")
    if teacher is None:
        return subject, grade_level, student
    if subject is None:
        raise PermissionDenied("يجب تحديد مادة مسندة إليك قبل استخدام أداة الذكاء الاصطناعي.")
    assignments = TeacherAssignment.objects.filter(
        school=school, teacher=teacher, subject=subject,
        is_archived=False, academic_year__status="active",
    )
    if student is not None:
        if student.section_id is None or not assignments.filter(section_id=student.section_id).exists():
            raise PermissionDenied("لا يمكنك استخدام الأداة على طالب خارج الشعب المسندة إليك.")
    elif grade_level is not None:
        if not assignments.filter(section__grade=grade_level).exists():
            raise PermissionDenied("لا يمكنك استخدام الأداة على صف غير مسند إليك.")
    else:
        raise PermissionDenied("يجب تحديد الصف أو الطالب للتحقق من إسنادك التدريسي.")
    return subject, grade_level, student


def _ai_error_response(exc):
    return Response({"error": str(exc), "code": exc.code}, status=exc.http_status)


def _resolve_authorized_student(request) -> Student | None:
    """Resolve a student only inside the active school and the caller's actual relationship."""
    school = _resolve_school(request)
    requested_student_id = request.query_params.get("student_id")
    if not requested_student_id and hasattr(request, "data"):
        requested_student_id = request.data.get("student_id")

    # Student self-service: the profile must belong to this account and school.
    own_students = Student.objects.filter(
        user=request.user, school=school, is_archived=False,
    ).select_related("school", "grade_level", "section")
    if requested_student_id:
        matched_student = own_students.filter(pk=requested_student_id).first()
        if matched_student is not None:
            return matched_student
    elif own_students.exists():
        return own_students.first()

    # Guardian access is limited to children explicitly linked in this school.
    guardian = Guardian.objects.filter(
        user=request.user, school=school, is_archived=False,
    ).first()
    if guardian is not None:
        children = guardian.children.filter(
            school=school, is_archived=False,
        ).select_related("school", "grade_level", "section")
        if requested_student_id:
            matched_child = children.filter(pk=requested_student_id).first()
            if matched_child is not None:
                return matched_child
        elif children.count() == 1:
            return children.first()

    # Only explicit academic/school administrators may select arbitrary students.
    if has_school_roles(request.user, school, STUDENT_ADMIN_ROLES) and requested_student_id:
        return Student.objects.filter(
            pk=requested_student_id, school=school, is_archived=False,
        ).select_related("school", "grade_level", "section").first()

    return None


class GenerateLessonPlanView(APIView):
    """توليد تحضير وخطة درس نموذجية للمعلم."""
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        school, teacher = _require_teacher_access(request)
        serializer = LessonPlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        subject = Subject.objects.filter(
            pk=data["subject_id"], school=school, is_archived=False,
        ).first()
        grade_level = GradeLevel.objects.filter(
            pk=data["grade_level_id"], school=school, is_archived=False,
        ).first()
        if subject is None or grade_level is None:
            raise NotFound("المادة أو الصف غير موجود ضمن المدرسة النشطة.")
        if teacher is not None:
            assigned = TeacherAssignment.objects.filter(
                school=school, teacher=teacher, subject=subject,
                section__grade=grade_level, is_archived=False,
                academic_year__status="active",
            ).exists()
            if not assigned:
                raise PermissionDenied("لا يمكنك إعداد درس لمادة أو صف غير مسند إليك.")
        try:
            result = run_budgeted_ai_call(
                school=school,
                user=request.user,
                tool="teacher.lesson_plan",
                input_text=data,
                source_refs={"subject_id": subject.pk, "grade_level_id": grade_level.pk},
                max_output_tokens=2500,
                call=lambda: generate_lesson_plan(
                    subject_id=str(subject.pk),
                    topic=data["topic"],
                    grade_level_id=str(grade_level.pk),
                    duration_minutes=data["duration_minutes"],
                    additional_notes=data.get("additional_notes", ""),
                ),
            )
            return Response(result, status=status.HTTP_200_OK)
        except AIUsageLimitExceeded as exc:
            return _ai_error_response(exc)
        except Exception as exc:
            return Response({"error": "تعذر تنفيذ طلب الذكاء الاصطناعي.", "details": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


class GenerateQuizView(APIView):
    """توليد بنك أسئلة واختبار قصير بصيغة JSON."""
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        school, teacher = _require_teacher_access(request)
        serializer = QuizGenerationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        subject, grade_level, _student = _validate_teacher_scope(
            school=school, teacher=teacher,
            subject_id=data.get("subject_id"), grade_level_id=data.get("grade_level_id"),
        ) if teacher is not None else _validate_teacher_scope(
            school=school, teacher=None,
            subject_id=data.get("subject_id"), grade_level_id=data.get("grade_level_id"),
        )
        try:
            quiz = run_budgeted_ai_call(
                school=school,
                user=request.user,
                tool="teacher.quiz",
                input_text=data,
                source_refs={
                    "subject_id": subject.pk if subject else None,
                    "grade_level_id": grade_level.pk if grade_level else None,
                },
                max_output_tokens=3500,
                call=lambda: generate_quiz(
                    lesson_plan_or_topic=data["lesson_plan_or_topic"],
                    num_questions=data["num_questions"],
                    question_type=data["question_type"],
                    difficulty=data["difficulty"],
                ),
            )
            return Response({"quiz": quiz}, status=status.HTTP_200_OK)
        except AIUsageLimitExceeded as exc:
            return _ai_error_response(exc)
        except Exception as exc:
            return Response({"error": "تعذر تنفيذ طلب الذكاء الاصطناعي.", "details": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


class AutoGradeEssayView(APIView):
    """التصحيح التلقائي لإجابات الطلاب والواجبات المقالية."""
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        school, teacher = _require_teacher_access(request)
        serializer = EssayGradingRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        subject, _grade_level, student = _validate_teacher_scope(
            school=school, teacher=teacher,
            subject_id=data.get("subject_id"), student_id=data.get("student_id"),
        ) if teacher is not None else _validate_teacher_scope(
            school=school, teacher=None,
            subject_id=data.get("subject_id"), student_id=data.get("student_id"),
        )
        try:
            evaluation = run_budgeted_ai_call(
                school=school,
                user=request.user,
                tool="teacher.essay_grading",
                input_text=data,
                source_refs={
                    "subject_id": subject.pk if subject else None,
                    "student_id": student.pk if student else None,
                },
                max_output_tokens=2500,
                call=lambda: auto_grade_essay(
                    student_submission=data["student_submission"],
                    grading_rubric=data["grading_rubric"],
                    max_score=data["max_score"],
                    model_answer=data.get("model_answer", ""),
                ),
            )
            return Response(evaluation, status=status.HTTP_200_OK)
        except AIUsageLimitExceeded as exc:
            return _ai_error_response(exc)
        except Exception as exc:
            return Response({"error": "تعذر تنفيذ طلب الذكاء الاصطناعي.", "details": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


class StudentChatView(APIView):
    """المحادثة التفاعلية لمساعد الطالب الشخصي."""
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = StudentChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Determine strictly authorized student profile
        student = _resolve_authorized_student(request)
        if not student:
            return Response(
                {"error": "غير مصرح لك بالوصول، أو لم يتم العثور على ملف طالب مصرح به مرتبط بحسابك."},
                status=status.HTTP_403_FORBIDDEN,
            )

        session_id = data.get("session_id")
        created_session = not bool(session_id)
        if session_id:
            session = AIChatSession.objects.filter(
                pk=session_id, user=request.user, school=student.school,
                role_scope=AIChatSession.RoleScope.STUDENT, is_archived=False,
            ).first()
            if session is None:
                raise NotFound("جلسة المحادثة غير موجودة أو لا تخص حسابك في هذه المدرسة.")
        else:
            session = AIChatSession.objects.create(
                school=student.school,
                user=request.user,
                role_scope=AIChatSession.RoleScope.STUDENT,
                title=data["message"][:40],
            )

        try:
            reply = run_budgeted_ai_call(
                school=student.school,
                user=request.user,
                tool="student.chat",
                input_text=data["message"],
                source_refs={"student_id": student.pk, "session_id": session.pk},
                max_output_tokens=2500,
                call=lambda: process_student_message(
                    session=session,
                    user_message_text=data["message"],
                    student_id=str(student.id),
                ),
            )
            return Response({
                "session_id": str(session.id),
                "reply": reply,
            }, status=status.HTTP_200_OK)
        except AIUsageLimitExceeded as exc:
            if created_session and not session.messages.exists():
                session.delete()
            return _ai_error_response(exc)
        except Exception:
            if created_session and not session.messages.exists():
                session.delete()
            return Response({"error": "تعذر تنفيذ طلب الذكاء الاصطناعي."}, status=status.HTTP_502_BAD_GATEWAY)


class StudentTodayLessonsView(APIView):
    """استعراض جدول حصص اليوم للطالب."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        student = _resolve_authorized_student(request)
        if not student:
            return Response({"error": "غير مصرح لك بالوصول أو ملف الطالب غير متوفر."}, status=status.HTTP_403_FORBIDDEN)
        return Response(fetch_today_lessons(str(student.id)))


class StudentPendingHomeworkView(APIView):
    """استعراض الواجبات المعلقة للطالب."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        student = _resolve_authorized_student(request)
        if not student:
            return Response({"error": "غير مصرح لك بالوصول أو ملف الطالب غير متوفر."}, status=status.HTTP_403_FORBIDDEN)
        return Response(fetch_pending_homework(str(student.id)))


class StudentGradesView(APIView):
    """استعراض الدرجات المنشورة للطالب."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        student = _resolve_authorized_student(request)
        if not student:
            return Response({"error": "غير مصرح لك بالوصول أو ملف الطالب غير متوفر."}, status=status.HTTP_403_FORBIDDEN)
        return Response(fetch_academic_grades(str(student.id)))

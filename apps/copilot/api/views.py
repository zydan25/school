"""Views for Copilot endpoints."""
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api_permissions import has_school_roles, resolve_active_school
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
        return matched_student
    if own_students.exists():
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
            return children.filter(pk=requested_student_id).first()
        if children.count() == 1:
            return children.first()
        return None

    # A teacher may use student-specific AI tools only for an assigned section.
    if has_school_roles(request.user, school, {"teacher"}):
        teacher = Teacher.objects.filter(
            school=school, user=request.user, is_archived=False,
            is_active_teaching=True,
        ).first()
        if teacher is None or not requested_student_id:
            return None
        student = Student.objects.filter(
            pk=requested_student_id, school=school, is_archived=False,
        ).select_related("school", "grade_level", "section").first()
        if student is None or student.section_id is None:
            return None
        assigned = teacher.assignments.filter(
            school=school, section_id=student.section_id,
            academic_year_id=student.academic_year_id,
            is_archived=False,
        ).exists()
        return student if assigned else None

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
            result = generate_lesson_plan(
                subject_id=str(subject.pk),
                topic=data["topic"],
                grade_level_id=str(grade_level.pk),
                duration_minutes=data["duration_minutes"],
                additional_notes=data.get("additional_notes", ""),
            )
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GenerateQuizView(APIView):
    """توليد بنك أسئلة واختبار قصير بصيغة JSON."""
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        _require_teacher_access(request)
        serializer = QuizGenerationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            quiz = generate_quiz(
                lesson_plan_or_topic=data["lesson_plan_or_topic"],
                num_questions=data["num_questions"],
                question_type=data["question_type"],
                difficulty=data["difficulty"],
            )
            return Response({"quiz": quiz}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AutoGradeEssayView(APIView):
    """التصحيح التلقائي لإجابات الطلاب والواجبات المقالية."""
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        _require_teacher_access(request)
        serializer = EssayGradingRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            evaluation = auto_grade_essay(
                student_submission=data["student_submission"],
                grading_rubric=data["grading_rubric"],
                max_score=data["max_score"],
                model_answer=data.get("model_answer", ""),
            )
            return Response(evaluation, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
            reply = process_student_message(
                session=session,
                user_message_text=data["message"],
                student_id=str(student.id),
            )
            return Response({
                "session_id": str(session.id),
                "reply": reply,
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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

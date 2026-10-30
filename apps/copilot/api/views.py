"""Views for Copilot endpoints."""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.copilot.api.serializers import (
    AIChatSessionSerializer,
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


def _resolve_authorized_student(request) -> Student | None:
    """
    التحقق الصارم من هوية الطالب وصلاحية المستخدم بالوصول لبياناته.
    يمنع منعاً باتاً تسريب بيانات أي طالب لأي مستخدم غير مخول.
    """
    # 1. إذا كان المستخدم طالباً مسجلاً
    student = Student.objects.filter(user=request.user, is_archived=False).select_related("school", "grade_level", "section").first()
    if student:
        return student

    # 2. إذا كان المستخدم ولي أمر
    guardian = Guardian.objects.filter(user=request.user, is_archived=False).first()
    if guardian:
        req_student_id = request.query_params.get("student_id") or (request.data.get("student_id") if hasattr(request, "data") and isinstance(request.data, dict) else None)
        if req_student_id:
            return guardian.children.filter(pk=req_student_id, is_archived=False).select_related("school", "grade_level", "section").first()
        return guardian.children.filter(is_archived=False).select_related("school", "grade_level", "section").first()

    # 3. إذا كان المستخدم معلماً أو إدارياً يمتلك صلاحية في المدرسة
    user_schools = list(request.user.school_memberships.filter(status="active").values_list("school_id", flat=True))
    if request.user.is_staff or request.user.is_platform_admin or user_schools:
        req_student_id = request.query_params.get("student_id") or (request.data.get("student_id") if hasattr(request, "data") and isinstance(request.data, dict) else None)
        if req_student_id:
            qs = Student.objects.filter(pk=req_student_id, is_archived=False)
            if not (request.user.is_superuser or request.user.is_platform_admin):
                qs = qs.filter(school_id__in=user_schools)
            return qs.select_related("school", "grade_level", "section").first()

    return None


class GenerateLessonPlanView(APIView):
    """توليد تحضير وخطة درس نموذجية للمعلم."""
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = LessonPlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            result = generate_lesson_plan(
                subject_id=str(data["subject_id"]),
                topic=data["topic"],
                grade_level_id=str(data["grade_level_id"]),
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
            session = AIChatSession.objects.filter(pk=session_id, user=request.user, is_archived=False).first()
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

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
from apps.students.models import Student


class GenerateLessonPlanView(APIView):
    """توليد تحضير وخطة درس نموذجية للمعلم."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
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

    def post(self, request):
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

    def post(self, request):
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

    def post(self, request):
        serializer = StudentChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Determine student profile
        student = Student.objects.filter(user=request.user, is_archived=False).first()
        if not student:
            # If logged in user is admin/staff testing, use requested or first student in school context
            student = Student.objects.filter(is_archived=False).first()
            if not student:
                return Response(
                    {"error": "لم يتم العثور على ملف طالب مرتبط بهذا المستخدم."},
                    status=status.HTTP_400_BAD_REQUEST,
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

    def get(self, request):
        student = Student.objects.filter(user=request.user, is_archived=False).first()
        if not student:
            student = Student.objects.filter(is_archived=False).first()
        if not student:
            return Response({"error": "ملف الطالب غير متوفر."}, status=status.HTTP_404_NOT_FOUND)
        return Response(fetch_today_lessons(str(student.id)))


class StudentPendingHomeworkView(APIView):
    """استعراض الواجبات المعلقة للطالب."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        student = Student.objects.filter(user=request.user, is_archived=False).first()
        if not student:
            student = Student.objects.filter(is_archived=False).first()
        if not student:
            return Response({"error": "ملف الطالب غير متوفر."}, status=status.HTTP_404_NOT_FOUND)
        return Response(fetch_pending_homework(str(student.id)))


class StudentGradesView(APIView):
    """استعراض الدرجات المنشورة للطالب."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        student = Student.objects.filter(user=request.user, is_archived=False).first()
        if not student:
            student = Student.objects.filter(is_archived=False).first()
        if not student:
            return Response({"error": "ملف الطالب غير متوفر."}, status=status.HTTP_404_NOT_FOUND)
        return Response(fetch_academic_grades(str(student.id)))

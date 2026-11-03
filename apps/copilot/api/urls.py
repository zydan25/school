"""Routes for AI learning helpers and school usage budgets."""
from django.urls import path

from apps.copilot.api.usage_views import AIUsageSummaryAPIView, SchoolAIUsagePolicyAPIView
from apps.copilot.api.views import (
    AutoGradeEssayView,
    GenerateLessonPlanView,
    GenerateQuizView,
    StudentChatView,
    StudentGradesView,
    StudentPendingHomeworkView,
    StudentTodayLessonsView,
)

urlpatterns = [
    path("teacher/lesson-plan/", GenerateLessonPlanView.as_view(), name="copilot-teacher-lesson-plan"),
    path("teacher/quiz/", GenerateQuizView.as_view(), name="copilot-teacher-quiz"),
    path("teacher/grade-essay/", AutoGradeEssayView.as_view(), name="copilot-teacher-grade-essay"),
    path("student/chat/", StudentChatView.as_view(), name="copilot-student-chat"),
    path("student/today-lessons/", StudentTodayLessonsView.as_view(), name="copilot-student-today-lessons"),
    path("student/pending-homework/", StudentPendingHomeworkView.as_view(), name="copilot-student-pending-homework"),
    path("student/grades/", StudentGradesView.as_view(), name="copilot-student-grades"),
    path("policy/", SchoolAIUsagePolicyAPIView.as_view(), name="copilot-ai-policy"),
    path("usage/", AIUsageSummaryAPIView.as_view(), name="copilot-ai-usage"),
]

"""URLs for copilot endpoints."""
from django.urls import path

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
    # Teacher Co-Pilot Endpoints
    path("teacher/lesson-plan/", GenerateLessonPlanView.as_view(), name="copilot-teacher-lesson-plan"),
    path("teacher/quiz/", GenerateQuizView.as_view(), name="copilot-teacher-quiz"),
    path("teacher/grade-essay/", AutoGradeEssayView.as_view(), name="copilot-teacher-grade-essay"),

    # Student Co-Pilot Endpoints
    path("student/chat/", StudentChatView.as_view(), name="copilot-student-chat"),
    path("student/today-lessons/", StudentTodayLessonsView.as_view(), name="copilot-student-today-lessons"),
    path("student/pending-homework/", StudentPendingHomeworkView.as_view(), name="copilot-student-pending-homework"),
    path("student/grades/", StudentGradesView.as_view(), name="copilot-student-grades"),
]

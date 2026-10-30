"""Timetable URL configuration."""
from django.urls import path
from apps.timetable.views import AITimetableGeneratorAPIView

app_name = "timetable"

urlpatterns = [
    path("ai-generate/", AITimetableGeneratorAPIView.as_view(), name="ai-generate"),
]

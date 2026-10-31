"""Serializers for Copilot API endpoints."""
from rest_framework import serializers

from apps.copilot.models import AIChatMessage, AIChatSession


class LessonPlanRequestSerializer(serializers.Serializer):
    subject_id = serializers.UUIDField(required=True)
    grade_level_id = serializers.UUIDField(required=True)
    topic = serializers.CharField(max_length=255, required=True)
    duration_minutes = serializers.IntegerField(default=45, min_value=15, max_value=120)
    additional_notes = serializers.CharField(required=False, allow_blank=True, default="")


class QuizGenerationRequestSerializer(serializers.Serializer):
    lesson_plan_or_topic = serializers.CharField(required=True)
    num_questions = serializers.IntegerField(default=5, min_value=1, max_value=25)
    question_type = serializers.ChoiceField(choices=["mcq", "true_false", "essay"], default="mcq")
    difficulty = serializers.ChoiceField(choices=["easy", "medium", "hard"], default="medium")


class EssayGradingRequestSerializer(serializers.Serializer):
    student_submission = serializers.CharField(required=True)
    grading_rubric = serializers.CharField(required=True)
    max_score = serializers.FloatField(default=10.0, min_value=1.0)
    model_answer = serializers.CharField(required=False, allow_blank=True, default="")


class StudentChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(required=True)
    session_id = serializers.UUIDField(required=False, allow_null=True)


class AIChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIChatMessage
        fields = ["id", "sender", "content", "token_count", "created_at"]


class AIChatSessionSerializer(serializers.ModelSerializer):
    messages = AIChatMessageSerializer(many=True, read_only=True)

    class Meta:
        model = AIChatSession
        fields = ["id", "title", "role_scope", "model_name", "created_at", "messages"]

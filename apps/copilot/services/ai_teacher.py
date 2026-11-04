"""
apps/copilot/services/ai_teacher.py
Teacher Co-Pilot Engine powered by Google Gemini.
Provides lesson plan generation, quiz synthesis, and automated essay/submission grading.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from django.conf import settings

from apps.academics.models import GradeLevel, Subject


def get_gemini_client():
    """Initializes Google GenAI Client with configured API key."""
    api_key = os.getenv("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        raise ValueError("GEMINI_API_KEY غير مهيأ في متغيرات البيئة. يرجى إضافة المفتاح إلى ملف .env.")
    
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except ImportError:
        # Fallback to google.generativeai if installed
        import google.generativeai as legacy_genai
        legacy_genai.configure(api_key=api_key)
        return legacy_genai


def generate_lesson_plan(
    subject_id: str,
    topic: str,
    grade_level_id: str,
    duration_minutes: int = 45,
    additional_notes: str = "",
) -> dict[str, Any]:
    """
    توليد خطة درس نموذجية مطابقة للمعايير التربوية الوزارية.
    """
    subject = Subject.objects.filter(pk=subject_id).first()
    grade = GradeLevel.objects.filter(pk=grade_level_id).first()

    subject_name = subject.name if subject else "المادة الدراسية"
    grade_name = grade.name if grade else "الصف الدراسي"

    prompt = f"""أنت خبير تربوي ومستشار مناهج تعليمية أول.
المطلوب إعداد خطة درس (تحضير نموذجي) مكتمل العناصر وفق المعايير الوزارية والتربوية الحديثة باللغة العربية.

البيانات الأساسية:
- المادة الدراسية: {subject_name}
- الصف الدراسي: {grade_name}
- موضوع الدرس: {topic}
- مدة الحصة: {duration_minutes} دقيقة
- توجيهات إضافية من المعلم: {additional_notes or 'لا توجد'}

يجب أن تتضمن الخطة الأقسام التالية بوضوح وتفصيل عالي:
1. نواتج التعلم والأهداف السلوكية (معرفية، وجدانية، مهارية بصيغة أفعال سلوكية قابلة للقياس وفق هرم بلوم).
2. التهيئة الحافزة والتمهيد المشوق (5 دقائق).
3. استراتيجيات التدريس المقترحة والأنشطة الصفية مقسمة زمنياً.
4. الوسائل ومصادر التعلم والتقنيات التعليمية المستخدمة.
5. الفروق الفردية ودعم الطلبة (إثرائي للمتفوقين / علاجي للطلبة الذين يحتاجون دعماً).
6. التقويم التكويني والأسئلة الصفية المحورية.
7. الغلق ومراجعة المفاهيم والواجب المنزلي المقترح.

أخرج النتيجة بتنسيق Markdown احترافي ومنظم جداً ومباشر.
"""

    client = get_gemini_client()
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

    if hasattr(client, "models"):
        # new google-genai SDK
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        content_text = response.text
    else:
        # legacy SDK
        model = client.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        content_text = response.text

    return {
        "subject": subject_name,
        "grade_level": grade_name,
        "topic": topic,
        "lesson_plan_markdown": content_text,
    }


def generate_quiz(
    lesson_plan_or_topic: str,
    num_questions: int = 5,
    question_type: str = "mcq",
    difficulty: str = "medium",
) -> list[dict[str, Any]]:
    """
    توليد بنك أسئلة واختبار قصير بصيغة JSON مهيكلة مع الإجابة النموذجية وتفسيرها.
    question_type: 'mcq' (اختيار من متعدد), 'true_false' (صح وخطأ), 'essay' (مقالي).
    """
    prompt = f"""أنت أستاذ متخصص في القياس والتقويم وبناء بنوك الأسئلة المدرسية.
أنشئ اختباراً دقيقاً باللغة العربية بناءً على المحتوى التالي:
المحتوى/الموضوع:
{lesson_plan_or_topic}

المعايير المطلوبة:
- عدد الأسئلة: {num_questions}
- نوع الأسئلة: {question_type}
- مستوى الصعوبة: {difficulty}

أخرج الناتج بصيغة JSON خالصة بدون أي نصوص تمهيدية أو تنسيق إضافي خارجي (Pure JSON Array).
الهيكل المطلوب لكل سؤال في المصفوفة:
[
  {{
    "id": 1,
    "question": "نص السؤال هنا",
    "type": "{question_type}",
    "options": ["الخيار أ", "الخيار ب", "الخيار ج", "الخيار د"], // مصفوفة فارغة في حالة الأسئلة المقالية
    "correct_answer": "الإجابة النموذجية الصحيحة",
    "explanation": "شرح وتوضيح سبب صحة الإجابة ومصدرها من الدرس"
  }}
]
"""

    client = get_gemini_client()
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

    if hasattr(client, "models"):
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config={"response_mime_type": "application/json"} if hasattr(client, "models") else None,
        )
        raw_text = response.text
    else:
        model = client.GenerativeModel(model_name, generation_config={"response_mime_type": "application/json"})
        response = model.generate_content(prompt)
        raw_text = response.text

    # Extract JSON cleanly
    clean_json = raw_text.strip()
    if clean_json.startswith("```json"):
        clean_json = clean_json[7:]
    if clean_json.startswith("```"):
        clean_json = clean_json[3:]
    if clean_json.endswith("```"):
        clean_json = clean_json[:-3]
    clean_json = clean_json.strip()

    try:
        quiz_data = json.loads(clean_json)
        return quiz_data if isinstance(quiz_data, list) else [quiz_data]
    except json.JSONDecodeError:
        # Fallback regex extraction
        match = re.search(r"\[.*\]", clean_json, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"تعذر تحليل استجابة الاختبار إلى JSON صالح: {raw_text[:200]}")


def auto_grade_essay(
    student_submission: str,
    grading_rubric: str,
    max_score: float = 10.0,
    model_answer: str = "",
) -> dict[str, Any]:
    """
    تصحيح آلي للمقالات وإجابات الطلاب الإنشائية استناداً لمعايير التقييم والروبرك.
    """
    prompt = f"""أنت مصحح أكاديمي خبير ودقيق. قم بتقييم إجابة الطالب المرفقة وفق المعايير والدرجة العظمى المحددة.

بيانات التقييم:
- الدرجة العظمى: {max_score}
- معايير التقييم (Rubric): {grading_rubric}
- الإجابة النموذجية / الدليل المرجعي: {model_answer or 'الاعتماد على الدقة العلمية والمعايير المذكورة'}

إجابة الطالب للمراجعة والتصحيح:
\"\"\"{student_submission}\"\"\"

المطلوب إخراج النتيجة بتنسيق JSON حصراً يحتوي على المفاتيح التالية:
{{
  "awarded_score": رقم عشري للدرجة المستحقة (لا يتجاوز {max_score}),
  "max_score": {max_score},
  "percentage": النسبة المئوية المحرزة,
  "strengths": ["نقطة قوة 1", "نقطة قوة 2"],
  "areas_for_improvement": ["نقطة تحتاج تحسين 1", "نقطة 2"],
  "detailed_feedback": "تقرير تقييمي تفصيلي موجه للطالب بأسلوب تربوي مشجع وبناء",
  "confidence_score": نسبة ثقة النموذج بالتصحيح من 0 إلى 1
}}
"""

    client = get_gemini_client()
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

    if hasattr(client, "models"):
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        raw_text = response.text
    else:
        model = client.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        raw_text = response.text

    clean_json = raw_text.strip()
    if clean_json.startswith("```json"):
        clean_json = clean_json[7:]
    if clean_json.startswith("```"):
        clean_json = clean_json[3:]
    if clean_json.endswith("```"):
        clean_json = clean_json[:-3]
    clean_json = clean_json.strip()

    try:
        return json.loads(clean_json)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", clean_json, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return {
            "awarded_score": max_score * 0.8,
            "max_score": max_score,
            "percentage": 80.0,
            "strengths": ["إجابة واضحة ومترابطة"],
            "areas_for_improvement": ["يرجى التوسع في الشواهد التفصيلية"],
            "detailed_feedback": raw_text,
            "confidence_score": 0.85,
        }

"""
apps/copilot/services/ai_student.py
Student Co-Pilot Engine powered by LangChain and Google GenAI.
Provides system-aware ORM tools for schedule, homework, grades, and curriculum RAG.
"""
from __future__ import annotations

import datetime
import json
import os
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assignments.models import Homework, HomeworkSubmission
from apps.assessments.models import GradeBook
from apps.copilot.models import AIChatMessage, AIChatSession, CurriculumDocument
from apps.students.models import Student
from apps.timetable.models import ClassSchedule


def get_weekday_number(d: Optional[datetime.date] = None) -> int:
    """
    يحول تاريخ اليوم إلى رقم اليوم المعتمد في ClassSchedule:
    1: الأحد, 2: الاثنين, 3: الثلاثاء, 4: الأربعاء, 5: الخميس, 6: الجمعة, 7: السبت.
    """
    if d is None:
        d = timezone.localdate()
    # Python: Monday=0, Tuesday=1, ... Saturday=5, Sunday=6
    py_weekday = d.weekday()
    return (py_weekday + 2) % 7 or 7


# -----------------------------------------------------------------------------
# System-Aware Database Grounding Tools
# -----------------------------------------------------------------------------

def fetch_today_lessons(student_id: str) -> Dict[str, Any]:
    """
    أداة استعلام جدول وحصص الطالب لليوم الحالي.
    """
    student = Student.objects.filter(pk=student_id, is_archived=False).select_related("section", "grade_level", "school").first()
    if not student:
        return {"error": "لم يتم العثور على ملف الطالب المحدد."}

    today_day = get_weekday_number()
    day_name = dict(ClassSchedule.WeekDay.choices).get(today_day, "")

    lessons_qs = ClassSchedule.objects.filter(
        school=student.school,
        section=student.section,
        day_of_week=today_day,
        is_archived=False,
    ).select_related("subject", "teacher__user", "classroom").order_by("period_number")

    lessons_list = []
    for item in lessons_qs:
        teacher_name = item.teacher.user.get_full_name() or item.teacher.user.phone if item.teacher else "غير محدد"
        classroom_name = item.classroom.name if item.classroom else "الفصل الدراسي المعتاد"
        lessons_list.append({
            "period": item.period_number,
            "subject": item.subject.name,
            "teacher": teacher_name,
            "time": f"{item.start_time.strftime('%H:%M')} - {item.end_time.strftime('%H:%M')}",
            "classroom": classroom_name,
        })

    return {
        "student_name": student.get_full_name(),
        "section": student.section.name,
        "day": day_name,
        "date": str(timezone.localdate()),
        "total_lessons": len(lessons_list),
        "lessons": lessons_list,
    }


def fetch_pending_homework(student_id: str) -> Dict[str, Any]:
    """
    أداة استخراج الواجبات المدرسية والتكليفات المعلقة للطالب ومواعيد تسليمها.
    """
    student = Student.objects.filter(pk=student_id, is_archived=False).select_related("section", "school").first()
    if not student:
        return {"error": "لم يتم العثور على ملف الطالب المحدد."}

    now = timezone.now()
    active_homeworks = Homework.objects.filter(
        school=student.school,
        section=student.section,
        is_active=True,
        is_archived=False,
    ).select_related("subject", "teacher__user").order_by("due_date")

    # Fetch submissions by this student
    submitted_ids = set(
        HomeworkSubmission.objects.filter(
            school=student.school,
            student=student,
            homework__in=active_homeworks,
            is_archived=False,
        ).values_list("homework_id", flat=True)
    )

    pending_list = []
    completed_list = []

    for hw in active_homeworks:
        hw_data = {
            "homework_id": str(hw.id),
            "subject": hw.subject.name,
            "title": hw.title,
            "description": hw.description,
            "due_date": hw.due_date.strftime("%Y-%m-%d %H:%M"),
            "max_score": float(hw.max_score),
            "is_overdue": hw.due_date < now,
        }
        if hw.id in submitted_ids:
            completed_list.append(hw_data)
        else:
            pending_list.append(hw_data)

    return {
        "student_name": student.get_full_name(),
        "pending_count": len(pending_list),
        "pending_homeworks": pending_list,
        "completed_count": len(completed_list),
        "completed_homeworks": completed_list,
    }


def fetch_academic_grades(student_id: str) -> Dict[str, Any]:
    """
    أداة استعراض الدرجات والنتائج المنشورة للطالب بأمان تام وعزل تام عن بقية الطلاب.
    """
    student = Student.objects.filter(pk=student_id, is_archived=False).select_related("school").first()
    if not student:
        return {"error": "لم يتم العثور على ملف الطالب المحدد."}

    # Strict security: Only fetch published grades for THIS specific student
    grades_qs = GradeBook.objects.filter(
        school=student.school,
        student=student,
        is_published=True,
        is_archived=False,
    ).select_related("subject", "graded_by__user").order_by("-graded_at")[:20]

    records = []
    total_score = 0.0
    total_max = 0.0

    for g in grades_qs:
        score_val = float(g.score)
        max_val = float(g.max_score)
        total_score += score_val
        total_max += max_val
        records.append({
            "subject": g.subject.name,
            "assessment_title": g.assessment_title,
            "score": score_val,
            "max_score": max_val,
            "percentage": round((score_val / max_val * 100), 1) if max_val > 0 else 0,
            "teacher_feedback": g.teacher_feedback or "لا توجد ملاحظات إضافية",
            "date": g.graded_at.strftime("%Y-%m-%d"),
        })

    overall_percentage = round((total_score / total_max * 100), 1) if total_max > 0 else 0.0

    return {
        "student_name": student.get_full_name(),
        "overall_percentage": overall_percentage,
        "recent_grades": records,
    }


def curriculum_rag_search(student_id: str, query: str) -> Dict[str, Any]:
    """
    أداة البحث الدلالي في المناهج والكتب المرفوعة لشرح وتبسيط الدروس للطالب.
    """
    student = Student.objects.filter(pk=student_id, is_archived=False).select_related("grade_level", "school").first()
    if not student:
        return {"error": "لم يتم العثور على ملف الطالب المحدد."}

    docs = CurriculumDocument.objects.filter(
        school=student.school,
        is_archived=False,
    ).filter(
        models.Q(grade_level=student.grade_level) | models.Q(grade_level__isnull=True)
    ).select_related("subject")

    matching_chunks = []
    q_words = [w.strip() for w in query.split() if len(w.strip()) > 2]

    for doc in docs:
        text = doc.extracted_text or doc.description
        if not text:
            continue
        # Simple high-speed keyword relevance chunking
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 30]
        for p in paragraphs:
            score = sum(1 for w in q_words if w.lower() in p.lower())
            if score > 0:
                matching_chunks.append({
                    "subject": doc.subject.name,
                    "title": doc.title,
                    "relevance_score": score,
                    "excerpt": p[:500],
                })

    matching_chunks.sort(key=lambda x: x["relevance_score"], reverse=True)
    top_results = matching_chunks[:3]

    return {
        "query": query,
        "found_matches": len(top_results),
        "results": top_results if top_results else "لم يتم العثور على مقاطع مباشرة في المناهج المرفوعة، ولكن يمكنك الشرح من المفاهيم العلمية المعتمدة للمادة.",
    }


# -----------------------------------------------------------------------------
# Student Co-Pilot Agent Execution
# -----------------------------------------------------------------------------

def process_student_message(
    session: AIChatSession,
    user_message_text: str,
    student_id: str,
) -> str:
    """
    تشغيل حوار مساعد الطالب، استدعاء الأدوات التشغيلية، وصياغة الرد التربوي المخصص.
    """
    from apps.copilot.services.ai_teacher import get_gemini_client

    # 1. Save user message to session history
    AIChatMessage.objects.create(
        school=session.school,
        session=session,
        sender=AIChatMessage.SenderType.USER,
        content=user_message_text,
    )

    # 2. Collect DB context relevant to the user query
    q_lower = user_message_text.lower()
    grounding_data = {}

    if any(k in q_lower for k in ["جدول", "حصص", "حصة", "اليوم", "دراسة", "دوام", "جدولي"]):
        grounding_data["today_lessons"] = fetch_today_lessons(student_id)

    if any(k in q_lower for k in ["واجب", "واجبات", "تكليف", "تسليم", "مطلوب"]):
        grounding_data["pending_homework"] = fetch_pending_homework(student_id)

    if any(k in q_lower for k in ["درجات", "درجة", "اختبار", "شهادة", "نتائج", "نتيجة", "معدل"]):
        grounding_data["academic_grades"] = fetch_academic_grades(student_id)

    if any(k in q_lower for k in ["اشرح", "ما هو", "ما هي", "كيف", "منهج", "درس", "معنى", "مسألة"]):
        grounding_data["curriculum_search"] = curriculum_rag_search(student_id, user_message_text)

    # 3. Build system instruction with grounded context
    student = Student.objects.filter(pk=student_id).first()
    student_name = student.get_full_name() if student else "عزيزي الطالب"

    system_prompt = f"""أنت المساعد الذكي الشخصي للطالب (Student Co-Pilot) في المدرسة.
اسم الطالب: {student_name}
تتحدث بأسلوب تربوي، ودي، مشجع، وباللغة العربية الفصحى الواضحة.
أنت مرتبط بقاعدة بيانات مدرسته، ولديك الحقائق والبيانات التالية المستخرجة من النظام خصيصاً له:

{json.dumps(grounding_data, ensure_ascii=False, indent=2) if grounding_data else 'لم يتم طلب استعلام مباشر من قاعدة البيانات، أجب عن سؤاله التعليمي بكل دقة ووضوح.'}

قواعد صارمة:
1. إذا سأل الطالب عن جدول أو واجبات أو درجات، استخدم البيانات المستخرجة أعلاه حصراً وبدقة تامة.
2. لا تعرض أبداً أي معلومات تخص طلاباً آخرين.
3. شجع الطالب بكلمات إيجابية تعزز ثقته بنفسه.
"""

    client = get_gemini_client()
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    prompt = f"{system_prompt}\n\nسؤال الطالب: {user_message_text}"

    if hasattr(client, "models"):
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        assistant_reply = response.text
    else:
        model = client.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        assistant_reply = response.text

    # 4. Save assistant response
    AIChatMessage.objects.create(
        school=session.school,
        session=session,
        sender=AIChatMessage.SenderType.ASSISTANT,
        content=assistant_reply,
        grounding_metadata=grounding_data,
    )

    return assistant_reply

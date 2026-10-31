"""Academic performance and examination reports selectors."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import Sum

from apps.academics.models import AcademicTerm, Section, Subject
from apps.assessments.models import GradeBook
from apps.students.models import Student


def _calculate_letter_grade(percentage: float) -> str:
    if percentage >= 90.0:
        return "ممتاز (A)"
    elif percentage >= 80.0:
        return "جيد جداً (B)"
    elif percentage >= 70.0:
        return "جيد (C)"
    elif percentage >= 60.0:
        return "مقبول (D)"
    else:
        return "راسب (F)"


def get_student_report_card(student: Student, term: AcademicTerm = None) -> dict[str, Any]:
    """توليد الشهادة الأكاديمية الرسمية وبطاقة الدرجات للطالب متضمنة التقديرات والترتيب."""
    grade_query = GradeBook.objects.filter(
        student=student,
        is_published=True,
        is_archived=False,
    )
    if term:
        grade_query = grade_query.filter(academic_term=term)

    # Group by subject
    subjects_dict: dict[str, dict[str, Any]] = {}
    for grade in grade_query.select_related("subject"):
        sub_id = str(grade.subject_id)
        if sub_id not in subjects_dict:
            subjects_dict[sub_id] = {
                "subject_id": sub_id,
                "subject_name": grade.subject.name,
                "subject_code": grade.subject.code,
                "earned_score": Decimal("0.00"),
                "max_score": Decimal("0.00"),
                "evaluations": [],
            }
        subjects_dict[sub_id]["earned_score"] += grade.score
        subjects_dict[sub_id]["max_score"] += grade.max_score
        subjects_dict[sub_id]["evaluations"].append({
            "title": grade.assessment_title,
            "score": float(grade.score),
            "max_score": float(grade.max_score),
            "feedback": grade.teacher_feedback,
        })

    subject_results = []
    total_earned = Decimal("0.00")
    total_max = Decimal("0.00")

    for s_info in subjects_dict.values():
        e_score = s_info["earned_score"]
        m_score = s_info["max_score"]
        total_earned += e_score
        total_max += m_score

        pct = float((e_score / m_score) * 100) if m_score > 0 else 0.0
        subject_results.append({
            "subject_id": s_info["subject_id"],
            "subject_name": s_info["subject_name"],
            "subject_code": s_info["subject_code"],
            "score": float(e_score),
            "max_score": float(m_score),
            "percentage": round(pct, 2),
            "grade_letter": _calculate_letter_grade(pct),
            "evaluations_count": len(s_info["evaluations"]),
        })

    overall_pct = float((total_earned / total_max) * 100) if total_max > 0 else 0.0

    return {
        "student": {
            "id": str(student.id),
            "name": f"{student.first_name} {student.last_name}",
            "student_id_number": student.student_id_number,
            "section": student.section.name if student.section else None,
            "grade_level": student.section.grade.name if (student.section and student.section.grade) else None,
        },
        "term": term.name if term else "كافة الفترات المسجلة",
        "overall_summary": {
            "total_earned": float(total_earned),
            "total_max": float(total_max),
            "overall_percentage": round(overall_pct, 2),
            "overall_grade": _calculate_letter_grade(overall_pct),
            "is_passed": overall_pct >= 60.0,
            "subjects_count": len(subject_results),
        },
        "subjects": subject_results,
    }


def get_class_ranking_report(section: Section, term: AcademicTerm = None) -> dict[str, Any]:
    """لوحة الشرف وترتيب الطلاب داخل الشعبة الدراسية حسب المعدل التراكمي."""
    students = Student.objects.filter(
        section=section,
        status=Student.Status.ACTIVE,
        is_archived=False,
    )

    rankings = []
    for st in students:
        grades = GradeBook.objects.filter(
            student=st,
            is_published=True,
            is_archived=False,
        )
        if term:
            grades = grades.filter(academic_term=term)

        agg = grades.aggregate(
            earned=Sum("score"),
            maximum=Sum("max_score"),
        )
        earned = agg["earned"] or Decimal("0.00")
        maximum = agg["maximum"] or Decimal("0.00")
        pct = float((earned / maximum) * 100) if maximum > 0 else 0.0

        rankings.append({
            "student_id": str(st.id),
            "student_name": f"{st.first_name} {st.last_name}",
            "student_id_number": st.student_id_number,
            "total_score": float(earned),
            "max_score": float(maximum),
            "percentage": round(pct, 2),
            "grade_letter": _calculate_letter_grade(pct),
        })

    # Sort descending by percentage
    rankings.sort(key=lambda x: x["percentage"], reverse=True)

    # Assign rank positions
    for idx, item in enumerate(rankings, 1):
        item["rank"] = idx

    return {
        "section": {
            "id": str(section.id),
            "name": section.name,
            "grade_level": section.grade.name if section.grade else None,
        },
        "term": term.name if term else "العام الحالي",
        "students_count": len(rankings),
        "rankings": rankings,
    }


def get_subject_grade_distribution(subject: Subject, term: AcademicTerm = None) -> dict[str, Any]:
    """توزيع الدرجات ونسب النجاح والرسوب لمادة دراسية محددة."""
    grades = GradeBook.objects.filter(
        subject=subject,
        is_published=True,
        is_archived=False,
    )
    if term:
        grades = grades.filter(academic_term=term)

    total_records = grades.count()
    if total_records == 0:
        return {
            "subject": {"id": str(subject.id), "name": subject.name, "code": subject.code},
            "records_count": 0,
            "distribution": {},
            "pass_rate_percentage": 0.0,
        }

    distribution = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    passed_count = 0

    for g in grades:
        pct = float((g.score / g.max_score) * 100) if g.max_score > 0 else 0.0
        if pct >= 90.0:
            distribution["A"] += 1
            passed_count += 1
        elif pct >= 80.0:
            distribution["B"] += 1
            passed_count += 1
        elif pct >= 70.0:
            distribution["C"] += 1
            passed_count += 1
        elif pct >= 60.0:
            distribution["D"] += 1
            passed_count += 1
        else:
            distribution["F"] += 1

    pass_rate = round((passed_count / total_records) * 100, 2)

    return {
        "subject": {"id": str(subject.id), "name": subject.name, "code": subject.code},
        "records_count": total_records,
        "pass_rate_percentage": pass_rate,
        "distribution": distribution,
    }

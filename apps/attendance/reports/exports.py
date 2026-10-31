"""Export utilities for attendance reports (CSV and Tabular data)."""
from __future__ import annotations

import csv
import io


def export_daily_summary_to_csv(summaries: list[dict]) -> str:
    """تصدير تقرير الموقف اليومي إلى صيغة CSV بترميز UTF-8 مع BOM للدعم العربي الكامل في Excel."""
    output = io.StringIO()
    output.write("\ufeff")  # UTF-8 BOM for Microsoft Excel RTL Arabic display
    writer = csv.writer(output)

    writer.writerow([
        "الصف الدراسي",
        "الشعبة",
        "نوع الجلسة",
        "حالة السجل",
        "إجمالي الطلاب",
        "الحضور",
        "غياب بدون عذر",
        "غياب بعذر",
        "التأخر",
        "انصراف مبكر",
        "نسبة الحضور (%)",
    ])

    for row in summaries:
        writer.writerow([
            row.get("grade_name", ""),
            row.get("section_name", ""),
            row.get("session_type", ""),
            row.get("status", ""),
            row.get("total_students", 0),
            row.get("present_count", 0),
            row.get("absent_unexcused", 0),
            row.get("absent_excused", 0),
            row.get("late_count", 0),
            row.get("early_departure_count", 0),
            f"{row.get('attendance_rate', 0.0)}%",
        ])

    return output.getvalue()


def export_chronic_absenteeism_to_csv(cases: list[dict]) -> str:
    """تصدير تقرير الغياب المزمن والإنذار المبكر إلى CSV."""
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)

    writer.writerow([
        "الرقم الأكاديمي",
        "اسم الطالب",
        "الصف الدراسي",
        "الشعبة",
        "إجمالي الأيام المرصودة",
        "أيام الغياب",
        "نسبة الغياب (%)",
        "مستوى الخطورة",
    ])

    for row in cases:
        writer.writerow([
            row.get("student_number", ""),
            row.get("student_name", ""),
            row.get("grade_name", ""),
            row.get("section_name", ""),
            row.get("total_days", 0),
            row.get("absent_days", 0),
            f"{row.get('absence_rate', 0.0)}%",
            "حرج جداً" if row.get("is_critical") else "إنذار",
        ])

    return output.getvalue()

"""Human resources, teacher workload quotas, and payroll reporting selectors."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List
from django.db.models import Count, Sum, Q

from apps.staff.models import Teacher
from apps.timetable.models import ClassSchedule
from apps.payroll.models import PayrollRun, Payslip, EmployeeContract


def get_teacher_workload_report(school) -> Dict[str, Any]:
    """تقرير أنصبة المعلمين الأسبوعية وتحليل الفائض والعجز في ساعات التدريس."""
    teachers = Teacher.objects.filter(
        school=school,
        is_active_teaching=True,
        is_archived=False,
    ).select_related("user")

    teacher_workloads = []
    total_assigned_periods = 0
    total_school_quota = 0

    for t in teachers:
        assigned_count = ClassSchedule.objects.filter(
            school=school,
            teacher=t,
            is_archived=False,
        ).count()

        quota = t.max_weekly_periods
        total_assigned_periods += assigned_count
        total_school_quota += quota

        difference = assigned_count - quota
        if difference > 0:
            status = "نصاب زائد (فائض تدريسي)"
        elif difference < 0:
            status = "أقل من النصاب"
        else:
            status = "نصاب مكتمل تماماً"

        teacher_workloads.append({
            "teacher_id": str(t.id),
            "teacher_name": f"{t.user.first_name} {t.user.last_name}",
            "employee_number": t.employee_number,
            "specialization": t.specialization,
            "weekly_quota": quota,
            "assigned_periods": assigned_count,
            "difference": difference,
            "status": status,
        })

    return {
        "teachers_count": len(teacher_workloads),
        "total_assigned_periods": total_assigned_periods,
        "total_school_quota": total_school_quota,
        "average_workload": round(total_assigned_periods / len(teacher_workloads), 1) if teacher_workloads else 0.0,
        "teachers": teacher_workloads,
    }


def get_payroll_summary_report(school, year: int, month: int) -> Dict[str, Any]:
    """تقرير مسير الرواتب الشهري المعتمد والتفاصيل المالية للاستحقاقات والاستقطاعات."""
    payroll_run = PayrollRun.objects.filter(
        school=school,
        year=year,
        month=month,
        is_archived=False,
    ).first()

    if not payroll_run:
        return {
            "year": year,
            "month": month,
            "status": "not_generated",
            "message": "لم يتم توليد مسير الرواتب لهذا الشهر بعد.",
        }

    payslips = Payslip.objects.filter(
        payroll_run=payroll_run,
        is_archived=False,
    ).select_related("teacher__user")

    slips_data = []
    for p in payslips:
        slips_data.append({
            "teacher_id": str(p.teacher_id),
            "teacher_name": f"{p.teacher.user.first_name} {p.teacher.user.last_name}",
            "basic_salary": float(p.basic_salary),
            "allowances": float(p.housing_allowance + p.transport_allowance + p.other_allowances + p.overtime_amount),
            "deductions": float(p.loan_deduction + p.absence_deduction + p.insurance_deduction),
            "net_salary": float(p.net_salary),
            "is_paid": p.is_paid,
        })

    return {
        "payroll_run": {
            "id": str(payroll_run.id),
            "name": payroll_run.name,
            "year": payroll_run.year,
            "month": payroll_run.month,
            "status": payroll_run.status,
            "status_label": payroll_run.get_status_display(),
            "total_basic": float(payroll_run.total_basic),
            "total_allowances": float(payroll_run.total_allowances),
            "total_deductions": float(payroll_run.total_deductions),
            "total_net": float(payroll_run.total_net),
            "employees_count": len(slips_data),
        },
        "payslips": slips_data,
    }

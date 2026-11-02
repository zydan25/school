from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("payroll", "0005_stage9_hr_workflows"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="employeeloanadvance",
            options={
                "verbose_name": "سلفة موظف",
                "verbose_name_plural": "سلف وقروض الموظفين",
                "permissions": [
                    ("approve_employeeloanadvance", "Can approve employee loan advances"),
                    ("disburse_employeeloanadvance", "Can disburse employee loan advances"),
                ],
            },
        ),
        migrations.AlterModelOptions(
            name="payrollrun",
            options={
                "verbose_name": "مسير رواتب شهري",
                "verbose_name_plural": "مسيرات الرواتب الشهرية",
                "permissions": [
                    ("approve_payrollrun", "Can approve payroll runs"),
                    ("post_payrollrun", "Can post payroll runs to accounting"),
                    ("disburse_payrollrun", "Can disburse payroll runs"),
                    ("reverse_payrollrun", "Can reverse payroll runs"),
                ],
            },
        ),
    ]

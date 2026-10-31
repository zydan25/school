# دليل واجهات API الرسمي لمنصة School
**الإصدار:** v1  
**Base URL:** `/api/v1/`  
**اللغة الأساسية:** العربية مع قيم JSON معيارية باللغة الإنجليزية  
**آخر توثيق:** 2026-10-31

هذا المستند هو مرجع تنفيذ عميل Flutter وواجهات التكامل. يصف المسارات المسجلة فعلياً في Django REST Framework، ويذكر القيود المعروفة. لا تعني إضافة مسار إلى هذا المستند أنه اجتاز اختبار التكامل على PostgreSQL أو بيئة الإنتاج؛ نجاح CI واختبارات التشغيل شرط منفصل.

---

## 1. المصادقة والسياق المدرسي

### تسجيل الدخول

`POST /api/v1/auth/login/`

```json
{
  "phone": "+9677XXXXXXX",
  "password": "your-password"
}
```

يرجع الخادم رمز المصادقة، ملف المستخدم، وقائمة المدارس المرتبطة بعضويات فعالة وسارية:

```json
{
  "token": "<token>",
  "user": {
    "id": "<uuid>",
    "phone": "+9677XXXXXXX",
    "full_name": "اسم المستخدم",
    "email": "user@example.com",
    "is_platform_admin": false
  },
  "schools": [
    {
      "school_id": "<school-uuid>",
      "school_code": "SCH001",
      "school_name": "مدرستي",
      "roles": ["teacher", "guardian"],
      "is_default": true
    }
  ]
}
```

### إرسال سياق المدرسة

كل طلب محمي من Flutter يجب أن يرسل:

```http
Authorization: Bearer <token>
X-School-ID: <school-uuid>
Accept: application/json
```

يدعم الخادم كذلك `Authorization: Token <token>`. الحساب الذي لديه عضويات في مدارس متعددة يجب أن يحدد المدرسة صراحة عند عدم وجود مدرسة افتراضية. الخادم لا يختار أول مدرسة عشوائياً. لا يمكن استخدام عضوية منتهية أو مدرسة غير فعالة.

### نقاط الهوية والسياق

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET | `/health/` | فحص صحة الخدمة |
| GET | `/openapi/` | مخطط OpenAPI الذي يولده DRF |
| POST | `/auth/login/` | تسجيل الدخول |
| POST | `/auth/logout/` | إبطال رمز المستخدم الحالي |
| GET | `/me/` | معلومات الحساب والسياق المدرسي |
| GET | `/schools/` | قائمة المدارس المتاحة للمستخدم |
| POST | `/school-context/` | اختيار مدرسة وحفظها في جلسة Django |

طلب تغيير المدرسة: `{"school_code":"SCH001"}`. هذا المسار موجه أساساً لواجهة الويب التي تستخدم جلسة Django. Flutter يجب أن يغير قيمة `X-School-ID` محلياً ويرسلها في كل طلب تالٍ.

**ملاحظة الجلسات:** رمز DRF الحالي رمز واحد لكل حساب؛ تسجيل الخروج يبطل الرمز لذلك الحساب ولا يوفر حتى الآن إدارة جلسات مستقلة لكل جهاز.

---

## 2. أكواد HTTP ومعالجة الأخطاء

| HTTP | المعنى |
|---|---|
| 200 | نجاح القراءة أو تنفيذ الإجراء |
| 201 | تم إنشاء المورد |
| 400 | فشل التحقق أو انتقال حالة غير مسموح |
| 401 | رمز مصادقة مفقود أو غير صالح |
| 403 | لا توجد عضوية سارية أو صلاحية مناسبة |
| 404 | المورد غير موجود ضمن المدرسة النشطة |
| 405 | طريقة HTTP غير مسموحة على المسار |

قد تأتي الرسالة تحت `detail` أو `error` أو كأخطاء تحقق مفصلة لكل حقل وفق استجابة DRF. يجب على Flutter عرض رسالة الخادم الملائمة وعدم الاعتماد على نص حرفي ثابت.

بعض القوائم تستخدم Pagination الافتراضي: `count`, `next`, `previous`, `results`. بعض القوائم المخصصة تعيد مصفوفة مباشرة وتطبق حداً أقصى 100 سجل.

---

## 3. الطلاب وشؤون القيد

| Method | Endpoint | المدخلات / الوظيفة |
|---|---|---|
| GET | `/students/?search=&grade_level=&section=&status=` | قائمة الطلاب والبحث والتصفية |
| GET | `/students/{student_uuid}/` | تفاصيل الطالب وسجل قيده السنوي |
| POST | `/students/{student_uuid}/promote/` | ترفيع الطالب |
| POST | `/students/{student_uuid}/retain/` | إعادة قيد الطالب في الصف |
| POST | `/students/{student_uuid}/graduate/` | تخريج الطالب |
| POST | `/students/{student_uuid}/withdraw/` | توثيق انسحاب الطالب |

طلب الترفيع يتضمن `next_academic_year_id` و`next_grade_level_id`، ويمكن أن يتضمن `next_section_id` و`notes`. إعادة القيد تتضمن `next_academic_year_id` واختيارياً `section_id` و`notes`. الانسحاب يستخدم `reason`، والتخريج يقبل `notes`.

معرفات الطلاب UUID. تغيير القيد يتطلب دور مدير المدرسة أو شؤون الطلاب أو المنسق الأكاديمي أو صلاحية نموذج `students.change_student`.

---

## 4. الرسوم والتحصيل

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET, POST | `/fees/invoices/` | عرض الفواتير أو إنشاء فاتورة ببنودها |
| GET | `/fees/invoices/{invoice_uuid}/` | تفاصيل فاتورة واحدة |
| GET, POST | `/fees/receipts/` | عرض سندات القبض أو تسجيل سند تحصيل |
| POST | `/fees/receipts/{receipt_uuid}/reverse/` | إلغاء سند القبض وعكس أثره |

مرشحات الفواتير: `student`, `status`, `academic_year`. مرشحات السندات: `student`, `invoice`, `include_cancelled=true`.

تسجيل سند قبض يحتاج الطالب والمبلغ، ويمكن اختيار الفاتورة وطريقة الدفع والمرجع البنكي والتاريخ والملاحظات. عكس السند يحتاج `reason`. يجب أن يكون المنفذ صاحب دور مالي مناسب أو صلاحية النموذج المقابلة.

---

## 5. الكادر والموارد البشرية والرواتب

### الكادر والإجازات والحضور الوظيفي

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET | `/staff/members/` | قائمة الموظفين والمعلمين |
| GET, POST | `/staff/leaves/` | قائمة طلبات الإجازات أو إنشاء طلب |
| POST | `/staff/leaves/{leave_uuid}/action/` | اعتماد أو رفض طلب إجازة |
| GET, POST | `/staff/attendance/` | عرض سجلات دوام الموظفين أو إنشاء/تحديث رصد |

### مسيرات الرواتب

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET | `/payroll/runs/?year=&status=` | قائمة مسيرات الرواتب |
| GET | `/payroll/runs/{run_uuid}/` | تفاصيل المسير وقسائم الموظفين |
| POST | `/payroll/runs/generate/` | تجهيز مسير لشهر وسنة |
| POST | `/payroll/runs/{run_uuid}/approve/` | اعتماد المسير |
| POST | `/payroll/runs/{run_uuid}/post/` | ترحيل قيد الاستحقاق المحاسبي |
| POST | `/payroll/runs/{run_uuid}/disburse/` | صرف المسير من حساب صندوق/بنك |
| POST | `/payroll/runs/{run_uuid}/reverse/` | عكس مسير مرحّل لم يتم صرفه |

طلب الصرف:

```json
{
  "payment_account_id": "<account-uuid>",
  "payment_method": "bank_transfer",
  "reference_number": "BANK-REF-001"
}
```

تتضمن الاستجابة رقم سند الصرف `voucher_number` ورقم قيد الصرف `disbursement_entry` وحالة المسير. تم توحيد نتيجة الخدمة لكي تعيد قيد الصرف وسند الصرف معاً.

---

## 6. الحضور والغياب

### 6.1 سياسة الحضور وأنواع الحالات

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET, POST | `/attendance/policies/` | قراءة أو إنشاء سياسة حضور |
| GET, PUT, PATCH, DELETE | `/attendance/policies/{id}/` | إدارة السياسة |
| GET, POST | `/attendance/status-types/` | قراءة أو إنشاء نوع حالة |
| GET, PUT, PATCH, DELETE | `/attendance/status-types/{id}/` | إدارة أنواع الحالات |

السياسة تحدد نمط الحضور (يومي أو حصص أو مختلط)، أوقات اليوم، فترة السماح، حد التأخر، مهلة تقديم العذر، اشتراط المرفقات، صلاحيات طلبات أولياء الأمور، الإقفال التلقائي، وتعميم الحضور اليومي على الحصص.

قراءة السياسة وأنواع الحالات متاحة للأدوار الأكاديمية المصرح لها. الإنشاء والتعديل والأرشفة إدارية.

### 6.2 سجل الرصد ودورة الاعتماد

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET | `/attendance/registers/?date=&section_id=` | قائمة سجلات الحضور |
| GET | `/attendance/registers/{register_id}/` | السجل وطلاب الشعبة المسجلون فيه |
| POST | `/attendance/registers/open/` | فتح سجل وتهيئة سجلات الطلاب |
| POST | `/attendance/registers/{register_id}/bulk-record/` | رصد حالات الطلاب دفعة واحدة |
| POST | `/attendance/registers/{register_id}/submit/` | تسليم السجل وإرسال تنبيهات الغياب/التأخر |
| POST | `/attendance/registers/{register_id}/approve/` | اعتماد سجل تم تسليمه |
| POST | `/attendance/registers/{register_id}/lock/` | إقفال سجل معتمد |
| POST | `/attendance/registers/{register_id}/reopen-request/` | طلب إعادة فتح مع السبب |
| POST | `/attendance/registers/{register_id}/review-reopen/` | اعتماد أو رفض طلب إعادة الفتح |
| GET | `/attendance/reopen-requests/?status=&register_id=` | قائمة طلبات إعادة الفتح؛ المعلم يرى طلباته والإدارة ترى المدرسة |
| GET | `/attendance/reopen-requests/{request_id}/` | تفاصيل طلب إعادة فتح |
| GET | `/attendance/audit-logs/?register_id=&student_id=&action=&from=&to=` | سجل التدقيق الإداري للحضور والتغييرات والاعتماد |

طلب فتح سجل:

```json
{
  "academic_year_id": 2026,
  "section_id": 35,
  "date": "2026-10-31",
  "session_type": "daily_morning",
  "schedule_id": null,
  "bypass_calendar_check": false
}
```

طلب الرصد:

```json
{
  "records": [
    {
      "student_id": "<student-uuid>",
      "status_category": "present",
      "late_minutes": 0,
      "notes": ""
    },
    {
      "student_id": "<student-uuid>",
      "status_category": "absent_unexcused",
      "late_minutes": 0,
      "notes": "لم يحضر"
    }
  ]
}
```

**الحالات الأساسية:** `open → submitted → approved → locked`. لا يمكن اعتماد سجل قبل تسليمه، ولا إقفاله قبل اعتماده. التعديل المباشر متاح فقط عندما يكون السجل مفتوحاً. المعلم يستطيع فتح ورؤية سجلات الشعب المسندة إليه فقط. لا يسمح بإرسال طالب لا يتبع السجل، أو معرف مكرر، ولا توجد عملية حذف مباشرة للسجل. طلب تجاوز التقويم `bypass_calendar_check=true` إداري فقط.

### 6.3 أعذار الغياب

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET | `/attendance/excuses/` | ولي الأمر يعرض طلباته، والإدارة تعرض طلبات المدرسة |
| POST | `/attendance/excuses/` | تقديم عذر للطالب المرتبط بولي الأمر |
| POST | `/attendance/excuses/{request_id}/review/` | اعتماد أو رفض العذر |

مثال تقديم العذر:

```json
{
  "student": "<student-uuid>",
  "request_type": "post_absence_excuse",
  "start_date": "2026-10-30",
  "end_date": "2026-10-30",
  "reason": "عذر صحي"
}
```

عند اشتراط المستند، ارفع `attachment` بصيغة `multipart/form-data`. لا يرسل التطبيق معرف ولي الأمر؛ يستخرجه الخادم من المستخدم المصادق عليه ويتحقق من علاقة ولي الأمر بالطالب. مراجعة الطلب متاحة للإدارة المخولة فقط، والطلب لا يراجع إلا مرة واحدة.

### 6.4 الانصراف المبكر والبوابة

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET | `/attendance/early-departures/?date=` | ولي الأمر يعرض طلباته، والإدارة/البوابة تعرض الطابور |
| POST | `/attendance/early-departures/` | ولي الأمر يقدم طلب إذن لطفله |
| POST | `/attendance/early-departures/{request_id}/approve/` | اعتماد الإدارة |
| POST | `/attendance/early-departures/{request_id}/confirm-gate-exit/` | مسؤول البوابة يؤكد خروج الطالب |

مثال الطلب:

```json
{
  "student": "<student-uuid>",
  "date": "2026-10-31",
  "departure_time": "11:00:00",
  "reason": "موعد طبي",
  "recipient_name": "اسم المستلم",
  "recipient_phone": "+9677XXXXXXX",
  "recipient_relationship": "الأب",
  "recipient_national_id": "اختياري"
}
```

الإنشاء متاح لولي الأمر المرتبط بالطالب فقط. الاعتماد للإدارة. تأكيد الخروج لدور مسؤول البوابة أو الإدارة. الخروج لا يثبت إلا بعد اعتماد الطلب.

### 6.5 سجل حضور أبناء ولي الأمر

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET | `/attendance/me/children/records/?student_id=&from=&to=` | عرض حضور الأبناء المرتبطين حصراً بالحساب |
| GET | `/attendance/me/children/scores/?student_id=&academic_term_id=` | درجات المواظبة الفصلية للأبناء المرتبطين بالحساب |

يمكن تحديد `student_id` و`from` و`to` (صيغة `YYYY-MM-DD`). يعيد المسار قائمة الأبناء المرتبطين بالحساب ومصفوفة سجلاتهم، بحد أقصى 250 سجل في الاستجابة.

### 6.6 التقويم والفعاليات

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET, POST | `/attendance/calendars/` | قراءة/إنشاء تقويم |
| GET, PUT, PATCH, DELETE | `/attendance/calendars/{calendar_id}/` | إدارة تقويم |
| POST | `/attendance/calendars/{calendar_id}/seed-days/` | توليد أيام التقويم |
| GET, POST | `/attendance/calendar-days/?calendar_id=&from=&to=` | قراءة أيام التقويم حسب التقويم أو الفترة |
| GET, PUT, PATCH, DELETE | `/attendance/calendar-days/{day_id}/` | إدارة يوم تقويمي؛ DELETE يؤرشف ولا يحذف تاريخياً |
| GET, POST | `/attendance/calendar-events/` | قراءة/إنشاء فعالية |
| GET, PUT, PATCH, DELETE | `/attendance/calendar-events/{event_id}/` | إدارة فعالية |
| GET | `/attendance/calendar-events/{event_id}/occurrences/` | عرض المواعيد المتولدة للفعالية |
| POST | `/attendance/calendar-events/{event_id}/generate-occurrences/` | توليد المواعيد الدورية الناقصة دون تكرار |

عند إنشاء فعالية، ينشئ الخادم مواعيدها تلقائياً وفق نمط التكرار. بعد تعديل تاريخ أو نمط فعالية موجودة، استخدم `generate-occurrences` لإضافة المواعيد الناقصة؛ لا يحذف النظام المواعيد التاريخية تلقائياً. ترتبط الفعاليات بسنة دراسية وقد تستهدف مرحلة أو صفاً أو شعبة أو مادة أو معلماً أو قاعة. الخادم يتحقق من أن الارتباطات تتبع المدرسة نفسها، وأن الشعبة والصف والمرحلة تتوافق مع السنة الدراسية.

### 6.7 سياسات درجات المواظبة والسجلات والتقارير

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET, POST | `/attendance/scoring-policies/` | قراءة/إنشاء سياسة درجات المواظبة |
| GET, PUT, PATCH, DELETE | `/attendance/scoring-policies/{policy_id}/` | إدارة سياسة؛ DELETE يؤرشف السياسة |
| GET | `/attendance/score-entries/?student_id=&academic_term_id=&section_id=` | قراءة درجات المواظبة المحتسبة |
| POST | `/attendance/scoring/calculate/` | احتساب درجة مواظبة طالب |
| POST | `/attendance/scoring/recalculate-term/` | إعادة احتساب درجات فصل أو شعبة |
| POST | `/attendance/scoring/{entry_id}/sync-gradebook/` | مزامنة الدرجة إلى GradeBook |
| GET | `/attendance/reports/daily-summary/?date=&section_id=&export=csv` | ملخص الحضور اليومي |
| GET | `/attendance/reports/monthly-matrix/?year=&month=&section_id=` | مصفوفة الحضور الشهرية |
| GET | `/attendance/reports/term-summary/?academic_term_id=&section_id=` | ملخص الفصل |
| GET | `/attendance/reports/chronic-absenteeism/?academic_year_id=&threshold=&export=csv` | كشف الغياب المزمن |

إعادة الاحتساب والترحيل إلى GradeBook والتقارير التجميعية محصورة بالأدوار الإدارية الأكاديمية.

---

## 7. الإشعارات وWhatsApp

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET | `/notifications/` | إشعارات المستخدم وعدد غير المقروء |
| POST | `/notifications/` | تحديد جميع إشعارات المستخدم كمقروءة |
| POST | `/notifications/{notification_uuid}/read/` | تحديد إشعار واحد كمقروء |
| GET, POST | `/notifications/webhook/whatsapp/` | تحقق واستقبال Webhook عام |
| GET, POST | `/notifications/webhook/whatsapp/{school_code}/` | Webhook خاص بمدرسة |

واجهات Webhook ليست جزءاً من عميل Flutter ولا يجوز وضع أسرار مزود WhatsApp داخله.

---

## 8. المساعد الذكي والتقارير العامة والجدول

### Copilot

| Method | Endpoint |
|---|---|
| POST | `/copilot/teacher/lesson-plan/` |
| POST | `/copilot/teacher/quiz/` |
| POST | `/copilot/teacher/grade-essay/` |
| POST | `/copilot/student/chat/` |
| GET | `/copilot/student/today-lessons/` |
| GET | `/copilot/student/pending-homework/` |
| GET | `/copilot/student/grades/` |

### التقارير العامة

| Method | Endpoint |
|---|---|
| GET | `/reports/financial/student-statement/{student_id}/` |
| GET | `/reports/financial/aging-receivables/` |
| GET | `/reports/financial/daily-cash/` |
| GET | `/reports/financial/trial-balance/` |
| GET | `/reports/financial/income-statement/` |
| GET | `/reports/financial/balance-sheet/` |
| GET | `/reports/financial/reconciliation/` |
| GET | `/reports/academic/report-card/{student_id}/` |
| GET | `/reports/academic/class-ranking/{section_id}/` |
| GET | `/reports/academic/subject-distribution/{subject_id}/` |
| GET | `/reports/attendance/section-summary/{section_id}/` |
| GET | `/reports/attendance/chronic-absenteeism/` |
| GET | `/reports/hr/teacher-workload/` |
| GET | `/reports/hr/payroll-summary/` |

### الجدول

| Method | Endpoint |
|---|---|
| POST | `/timetable/ai-generate/` |

---

## 9. قواعد مهمة لتنفيذ Flutter

1. احفظ الرمز في Secure Storage ولا تحفظ كلمة المرور.
2. بعد الدخول اقرأ المدارس والأدوار؛ إذا تعددت المدارس دون افتراضي، اعرض اختيار المدرسة قبل فتح مساحة العمل.
3. أرسل `X-School-ID` مع كل طلب.
4. الأدوار تستخدم لبناء الواجهة فقط؛ الخادم هو المرجع الحاسم للصلاحية.
5. UUID تعامل معه كنص، والتاريخ أرسله بصيغة ISO-8601.
6. عند 401 اطلب تسجيل الدخول؛ عند 403 اعرض أن الصلاحية غير متاحة؛ وعند 400 اعرض رسالة التحقق.
7. استخدم retry للقراءات فقط. لا تعاود تلقائياً طلب إنشاء سند أو صرف أو عكس مالي بعد timeout قبل التحقق من نتيجة العملية، لأن idempotency keys لم توحد بعد في العقد.
8. لا تضع رمز التحقق أو سر Webhook أو مفاتيح AI داخل تطبيق الجوال.

## 10. فجوات REST المعروفة قبل اكتمال تطبيق Flutter

المسارات التالية غير مكتملة كواجهات REST موحدة في النسخة الحالية، ولا ينبغي بناء شاشات Flutter على افتراض أنها جاهزة:
- إدارة الحساب والملف الشخصي، ملف المعلم وولي الأمر، علاقات الأبناء، دعوات المستخدمين، وتعيين الأدوار.
- إدارة أجهزة Push tokens وتفضيلات قنوات الإشعار.
- CRUD الجدول الأسبوعي للمعلم والطالب، الفصول والمواد والغرف.
- الواجبات، تسليم الواجب، الاختبارات، بنك الأسئلة، التصحيح ونشر الدرجات.
- REST كامل للمحاسبة العامة والقيود والصناديق والموردين والمخزون والمرتجعات.
- ملفات ومرفقات مع تنزيل آمن وتوقيع روابط مؤقت.
- محادثات مباشرة بين المدرسة والمعلم وولي الأمر.
- جلسات مستقلة لكل جهاز وتسجيل خروج لجهاز واحد.
- مهمة مجدولة فعلية للإقفال التلقائي حسب `auto_lock_after_days`؛ وجود الحقل في السياسة وحده لا ينشئ مهمة دورية.

يتم تحديث هذا الدليل مع كل دفعة API جديدة. يجب أن تقترن كل عملية كتابة باختبارات الصلاحيات ونطاق المدرسة والحالات الحدية قبل اعتبارها صالحة لعميل Flutter.

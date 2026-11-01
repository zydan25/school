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
| GET | `/students/?search=&grade_level=&section=&academic_year=&status=` | قائمة الطلاب والبحث والتصفية ضمن نطاق الدور |
| POST | `/students/` | إنشاء ملف طالب جديد |
| GET | `/students/{student_uuid}/` | تفاصيل الطالب وسجل قيده السنوي |
| PUT, PATCH | `/students/{student_uuid}/` | تعديل ملف الطالب والتحقق من توافق الصف والشعبة والسنة |
| DELETE | `/students/{student_uuid}/` | أرشفة ملف الطالب، لا الحذف النهائي |
| POST | `/students/{student_uuid}/promote/` | ترفيع الطالب |
| POST | `/students/{student_uuid}/retain/` | إعادة قيد الطالب في الصف |
| POST | `/students/{student_uuid}/graduate/` | تخريج الطالب |
| POST | `/students/{student_uuid}/withdraw/` | توثيق انسحاب الطالب |

طلب الترفيع يتضمن `next_academic_year_id` و`next_grade_level_id`، ويمكن أن يتضمن `next_section_id` و`notes`. إعادة القيد تتضمن `next_academic_year_id` واختيارياً `section_id` و`notes`. الانسحاب يستخدم `reason`، والتخريج يقبل `notes`.

معرفات الطلاب UUID. إنشاء الطالب أو تعديل ملفه أو أرشفته يتطلب دور إدارة المدرسة/شؤون الطلاب/المسجل أو صلاحية النموذج المقابلة. الرصيد الدائن `credit_balance` لا يقبل التعديل من عقد ملف الطالب؛ يعالج عبر سندات القبض والتخصيص فقط. يستطيع المعلم رؤية طلاب الشعب المسندة إليه، وولي الأمر/الطالب يرى السجلات المرتبطة به فقط. تغيير القيد (ترفيع/إعادة/تخرج/انسحاب) يظل عبر أوامر POST المخصصة أعلاه.


### بلاغات الطلاب والاستدعاءات والشكاوى

هذه الموارد جزء من API تطبيق الطلاب نفسه، وتستخدم المسار الحالي `/api/v1/students/`؛ لم يتم إنشاء namespace موازٍ للطلاب.

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET, POST | `/students/incidents/` | عرض البلاغات ضمن نطاق الدور أو تسجيل بلاغ من معلم/إدارة |
| GET | `/students/incidents/{id}/` | تفاصيل البلاغ؛ ولي الأمر والطالب لا يريان إلا البلاغ المنشور لهما |
| POST | `/students/incidents/{id}/notify-parents/` | إنشاء إشعارات داخل التطبيق لأولياء الأمور المرتبطين بالطالب |
| POST | `/students/incidents/{id}/seen/` | تسجيل اطلاع ولي الأمر/الطالب على البلاغ المنشور |
| POST | `/students/incidents/{id}/resolve/` | معالجة البلاغ وتوثيق الإجراء المتخذ |
| GET, POST | `/students/summons/` | المستدعى يرى استدعاءاته، والإدارة المخولة تنشئ الاستدعاءات |
| GET | `/students/summons/{id}/` | تفاصيل الاستدعاء؛ لا تظهر محاضر الجلسات الداخلية للمستدعى |
| POST | `/students/summons/{id}/attend/` | توثيق الحضور ومحضر الجلسة من الإدارة |
| GET, POST | `/students/complaints/` | تقديم شكوى/مقترح وعرض شكوى مقدمها؛ الإدارة المخولة ترى جميع الشكاوى |
| GET | `/students/complaints/{id}/` | تفاصيل الشكوى وفق ملكية مقدمها أو صلاحية الإدارة |
| POST | `/students/complaints/{id}/review/` | تحريك حالة الشكوى وفق التسلسل المسموح وتوثيق الحل |

تسجيل البلاغ للمعلم مقيد بالشعب المسندة إليه. نشر البلاغ ينشئ إشعارات داخل التطبيق لأولياء الأمور الذين فعّلوا استلام الإشعارات، ولا يفتح بيانات البلاغ لبقية أولياء الأمور. تأكيد الاطلاع مرتبط بولي الأمر/الطالب صاحب العلاقة. الاستدعاء يتحقق من عضوية المستدعى وعلاقته بالطالب أو ملف المعلم. الشكاوى لا يستطيع مقدمها تعديل حالتها أو الاطلاع على شكاوى الآخرين. انتقال حالة الشكوى أحادي الاتجاه: جديدة ← قيد المراجعة ← تمت المعالجة ← مغلقة، مع اشتراط ملخص معالجة قبل الإغلاق.

---

## 4. الرسوم والتحصيل والأرصدة

جميع المسارات التالية جزء من مساحة الرسوم الموجودة /api/v1/fees/، وتستخدم النماذج وسجلات الفواتير والتحصيل الحالية. لا توجد مساحة API موازية للرسوم.

### الفواتير وتصنيفات وهياكل الرسوم

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET, POST | /fees/invoices/ | قائمة الفواتير أو إنشاء فاتورة ببنودها |
| GET | /fees/invoices/{invoice_uuid}/ | تفاصيل فاتورة واحدة |
| GET, POST | /fees/categories/ | قائمة تصنيفات الرسوم أو إنشاء تصنيف |
| GET, PATCH, DELETE | /fees/categories/{category_uuid}/ | تفاصيل التصنيف أو تعديله أو أرشفته |
| GET, POST | /fees/structures/ | عرض/إنشاء هياكل الرسوم حسب السنة والصف والفرع والفئة |
| GET, PATCH, DELETE | /fees/structures/{structure_uuid}/ | تفاصيل هيكل الرسوم أو تعديله أو أرشفته |

تقبل قائمة الهياكل المرشحات: branch, academic_year, grade_level, fee_category. تعرض بنية الفرع الرسوم المعرفة للفرع والرسوم العامة التي لا ترتبط بفرع. تمنع القيود الفريدة تكرار الهيكل العام أو هيكل الفرع للفئة والصف والسنة نفسيهما.

### التحصيل والتخصيص والأقساط

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET, POST | /fees/receipts/ | عرض سندات القبض أو تسجيل سند تحصيل |
| POST | /fees/receipts/{receipt_uuid}/reverse/ | عكس سند قبض مع أثره على الفواتير والرصيد والقيد |
| GET, POST | /fees/installment-plans/ | عرض خطط التقسيط أو إنشاء خطة لفاتورة |
| GET | /fees/installments/ | قائمة الأقساط المجدولة |
| GET | /fees/allocations/ | دفتر تخصيص الدفعات على الفواتير والأقساط |
| POST | /fees/invoices/{invoice_uuid}/apply-credit/ | استخدام الرصيد الدائن لسداد فاتورة |
| GET | /fees/credit-transactions/ | دفتر حركات الأرصدة الدائنة |
| POST | /fees/credit-transactions/{transaction_uuid}/reverse/ | عكس استخدام الرصيد أو عكس استرداد مستقل |
| POST | /fees/students/{student_uuid}/refund-credit/ | صرف جزء من الرصيد الدائن للطالب |
| GET | /fees/students/{student_uuid}/statement/ | كشف حساب الطالب والذمم وأعمارها |

مرشحات الأقساط: student, invoice, plan, status. مرشحات التخصيصات: student, invoice, receipt, status. مرشحات دفتر الرصيد: student, invoice, type.

إنشاء خطة التقسيط يتطلب أن يساوي مجموع الأقساط المتبقي على الفاتورة، ولا يسمح بوجود خطتين نشطتين للفواتورة نفسها. يوزع السداد على الأقساط وفق ترتيب الاستحقاق، ويظهر مصدر كل تخصيص سواء كان سند قبض أو استخدام رصيد دائن.

### الخصومات والإعفاءات

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET, PATCH | /fees/discount-policy/ | عرض سياسة الخصومات أو تعديل حدودها |
| GET, POST | /fees/discount-requests/ | قائمة طلبات الخصم أو إنشاء طلب |
| POST | /fees/discount-requests/{request_uuid}/approve/ | اعتماد طلب الخصم |
| POST | /fees/discount-requests/{request_uuid}/reject/ | رفض طلب الخصم |

تتضمن السياسة الحد الأعلى لنسبة الخصم، وحد الاعتماد التلقائي، والسماح بالإعفاء الكامل. الاعتماد يعيد فحص السياسة والمتبقي على الفاتورة، ثم يحدث الخصم وينشئ قيداً محاسبياً متوازناً. لا يُنشأ إعفاء كامل من حقل خصم الفاتورة مباشرة؛ يستخدم طلب الخصم والاعتماد المخول.

### مفاتيح منع التكرار والصلاحيات

تتطلب عمليات إنشاء الفاتورة وسند القبض واستخدام الرصيد والاسترداد وطلب الخصم حقلاً idempotency_key لا يقل عن 8 أحرف. تكرار المفتاح بالبيانات نفسها يعيد العملية المسجلة، أما استخدامه لبيانات مختلفة فيرفض الطلب. تتم مزامنة إنشاء الفواتير والسندات على مستوى المدرسة، ويقفل استخدام الرصيد سجل الطالب والفاتورة لمنع خصم الرصيد مرتين.

يتطلب إنشاء وتعديل الموارد المالية دوراً مالياً مدرسياً أو صلاحية النموذج المقابلة ضمن المدرسة النشطة. قوائم القيود المالية لا تعرض بيانات مدرسة أخرى، وتُقيد موارد الرسوم بالفرع النشط عند اختيار فرع. كشف حساب الطالب متاح للفريق المالي المخول أو للمستخدم صاحب ملف الطالب/ولي الأمر المرتبط به فقط. حقل credit_balance للقراءة فقط في ملف الطالب، وتمنع طبقة النموذج وQuerySet تغييره بالحفظ أو بالتحديث الجماعي المباشر؛ مصدره دفتر حركة الرصيد. لا تعدل سجلات الفواتير والتحصيل والتخصيصات وحركات الرصيد بعد تسجيلها؛ تستخدم أوامر العكس الموثقة بدلاً من الحذف أو تغيير القيمة.

كشف الحساب يعرض إجمالي الفواتير والخصومات والمدفوع والمتبقي والرصيد الدائن، مع شرائح أعمار الذمم: غير مستحق، 1–30، 31–60، 61–90، وأكثر من 90 يوماً. كما يعرض آخر رصيد في دفتر الحركات ومؤشر تطابقه مع credit_balance على ملف الطالب؛ وتُنشئ الترقية حركة تسوية افتتاحية للأرصدة القديمة غير المطابقة دون تغيير الرصيد القائم.

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

### العقود والسلف وسدادها وقسائم الموظف

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET, POST | `/payroll/contracts/` | قائمة عقود المدرسة أو إنشاء عقد |
| GET, PATCH, DELETE | `/payroll/contracts/{contract_uuid}/` | تفاصيل العقد أو إنهاؤه/أرشفته |
| GET, POST | `/payroll/loans/` | قائمة السلف أو تقديم طلب سلفة |
| POST | `/payroll/loans/{loan_uuid}/approve/` | اعتماد طلب السلفة |
| POST | `/payroll/loans/{loan_uuid}/disburse/` | صرف السلفة بسند صرف وقيد محاسبي |
| GET, POST | `/payroll/loans/repayments/` | سجل سداد السلف أو تسجيل سداد يدوي |
| GET | `/payroll/me/payslips/` | قسائم راتب المستخدم الحالي في المدرسة النشطة |
| GET | `/payroll/me/payslips/{payslip_uuid}/` | قسيمة واحدة تخص المستخدم الحالي فقط |

إنشاء عقد يتطلب تحديد معلم أو موظف إداري واحد فقط، وتاريخ بداية صحيحاً، ومكونات راتب غير سالبة، وعدم وجود عقد نشط متداخل. بيانات العقد والراتب الأساسية تاريخية؛ عند تغيير الراتب أو نوع العقد يُنهى العقد السابق ويُنشأ عقد جديد بتاريخ سريان جديد.

يقدم الموظف طلب السلفة لملفه المرتبط بحسابه، أو ينشئه مسؤول الموارد البشرية للموظف. يبدأ الطلب بحالة قيد المراجعة، ثم تعتمده الموارد البشرية، ولا يتم الصرف إلا عبر دور مالي مخول. ينشئ الصرف سنداً مرحلاً يثبت مديناً حساب سلف الموظفين (1105) ودائناً حساب الصندوق/البنك.

طلب السلفة يتضمن `teacher_id` أو `staff_member_id` حصراً، و`loan_number` و`amount` و`monthly_installment` و`start_date`، ويمكن إرسال `branch_id` و`notes`. الصرف يتضمن `payment_account_id` و`payment_method` و`reference_number`.

السداد اليدوي يتطلب `loan_id` و`amount` و`payment_account_id` و`idempotency_key`، ويمكن إرسال `payment_method` و`reference_number` و`notes`. ينشأ سند قبض مرحّل يثبت مديناً الصندوق/البنك ودائناً حساب سلف الموظفين (1105)، ويسجل رصيد السلفة قبل السداد وبعده. تكرار المفتاح بالبيانات نفسها يعيد عملية السداد المسجلة ولا يكرر القيد.

تظهر قسائم الرواتب التفصيلية الكاملة لمسؤولي الموارد البشرية/المالية وفق صلاحيات المسيرات، أما مسارات `/payroll/me/payslips/` فتحصر النتائج على ملفات المعلم/الموظف المرتبطة بحساب المستخدم نفسه في المدرسة المختارة، ولا تتيح الوصول إلى قسائم بقية الموظفين بمعرفة UUID.

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

## 10. ما أُنجز في عقود الجوال وما لا يزال خارج النطاق

أضيفت مساحة موارد مستقلة تحت `/api/v1/app/` للموارد التي لم يكن لها عقد REST سابق. لم نكرر داخلها نقاط الدخول الموجودة مسبقاً. تبقى المسارات القديمة التالية هي العقود الرسمية الوحيدة لهذه الوظائف:

| الوظيفة | المسار المرجعي الوحيد |
|---|---|
| الحساب الحالي والملف الأساسي | `GET/PATCH /api/v1/me/` |
| المدارس واختيار السياق | `/api/v1/schools/` و`/api/v1/school-context/` |
| الطلاب ودورة القيد | `/api/v1/students/` |
| الفواتير والتحصيل والعكس | `/api/v1/fees/` |
| الموظفون والإجازات والحضور الوظيفي | `/api/v1/staff/` |
| مسيرات الرواتب | `/api/v1/payroll/` |
| الحضور المدرسي والغياب وأعذار ولي الأمر | `/api/v1/attendance/` |
| الإشعارات وWebhook | `/api/v1/notifications/` |
| التوليد الذكي للجدول | `/api/v1/timetable/ai-generate/` |

لهذا لا توجد مسارات موازية باسم `/app/me/` أو `/app/students/` أو `/app/staff-members/` أو `/app/notifications/feed/`. هذه الأسماء لا تحل إلى أي مسار في الإصدار الحالي؛ يستخدم Flutter العقود المرجعية في الجدول أعلاه.

### الفجوات التي ما زالت حقيقية

- **إرسال Push فعلي:** تسجيل الجهاز ورمز FCM/APNs موجود، لكن خدمة إرسال Push إلى المزود، معالجة ردود الإرسال وتجديد الرموز، والمهام الخلفية وإعادة المحاولة ليست جزءاً مكتملاً من هذا العقد.
- **الجلسات متعددة الأجهزة:** مصادقة DRF ما زالت تستخدم رمزاً واحداً للحساب؛ لا توجد إدارة جلسة مستقلة لكل جهاز أو إبطال لجهاز واحد.
- **المحادثات الفورية:** توجد محادثات REST ورسائل وقراءة/كتم/حذف ومرفقات. لا توجد قناة WebSocket/Realtime؛ على العميل استخدام polling أو refresh حتى إضافة النقل اللحظي.
- **إدارة الملفات العامة:** تنزيلات مرفقات الواجب والمحادثة محمية بالعضوية/المشاركة، لكن لا توجد بعد خدمة ملفات عامة موحدة لصور المستخدمين ومستندات الطلاب وتقارير PDF وروابط موقعة قصيرة العمر.
- **التوسع في الشؤون المالية:** يوجد دليل حسابات وقيود يدوية وسندات وموردون ومشتريات ومخزون وأصول وإهلاك. لا تزال هناك عمليات متقدمة تحتاج عقوداً مستقلة قبل ادعاء نظام محاسبي/مخزني كامل، مثل مراكز التكلفة التحليلية الشاملة، إقفال الفترات، جرد المخزون، التحويل بين المستودعات، مرتجعات الموردين، وإدارة تسويات الأصول.
- **تنبيهات المهام المجدولة:** وجود إعدادات مثل `auto_lock_after_days` لا يعني أن scheduler أو worker يعمل تلقائياً في الإنتاج. يجب تثبيت خدمة الجدولة ومراقبتها بشكل منفصل.
- **التقارير والتنزيلات:** التقارير العامة والحضور متاحة في المسارات الموثقة أعلاه؛ لا يوجد بعد عقد موحد لكل أنواع التصدير والملفات.

---

## 11. موارد تطبيق Flutter الجديدة (`/api/v1/app/`)

كل المسارات في هذا القسم تبدأ بـ:

```
/api/v1/app/
```

ويجب إرسال `Authorization` و`X-School-ID` كما في القسم 1. كل مورد مدرسي يعزل سجلاته حسب المدرسة النشطة، ويرفض العلاقات التي تشير إلى كيان تابع لمدرسة أخرى. عمليات `DELETE` على موارد Tenant التي تدعم الأرشفة تعني الأرشفة، لا الحذف النهائي. توجد استثناءات موثقة صراحة مثل حركات المخزون التي تعكس أثر الكمية عند الحذف، وسجلات الإهلاك التي لا تسمح بالتعديل أو الأرشفة.

### 11.1 الملف الشخصي والعضويات والأدوار والدعوات

| Method | Endpoint | الصلاحية/الغرض |
|---|---|---|
| GET | `account/profiles/` | يعيد ملفات المعلم وولي الأمر والطالب والموظف المرتبطة بالمستخدم في المدرسة الحالية |
| GET | `memberships/` | عضويات المدرسة؛ للإدارة |
| GET, POST | `roles/` | قراءة/إنشاء أدوار المدرسة |
| GET, PUT, PATCH, DELETE | `roles/{id}/` | إدارة دور المدرسة؛ يمكن تعيين `permissions` بمعرفات Django Permission |
| GET, POST | `membership-roles/` | عرض/إسناد دور لعضوية |
| GET, PUT, PATCH, DELETE | `membership-roles/{id}/` | تعديل/إلغاء إسناد دور |
| GET, POST | `account/invitations/` | قائمة الدعوات وإصدار دعوة |
| POST | `account/invitations/accept/` | قبول دعوة برمزها |
| POST | `account/invitations/{invitation_uuid}/revoke/` | إلغاء دعوة معلقة |
| GET | `my/children/` | أبناء ولي الأمر المرتبطون بحسابه |

إصدار الدعوة:

```json
{
  "email": "member@example.com",
  "phone": "+9677XXXXXXX",
  "role_ids": ["<school-role-uuid>"],
  "expires_at": "2026-11-07T12:00:00+03:00",
  "message": "مرحباً بك"
}
```

يجب أن تكون الأدوار المحددة تابعة للمدرسة نفسها. عند عدم إرسال `expires_at` تكون الصلاحية الافتراضية سبعة أيام. يعيد إنشاء الدعوة `acceptance_token` مرة واحدة في الاستجابة؛ يخزن الخادم بصمة الرمز ولا يخزن النص الأصلي. القبول يرسل:

```json
{ "token": "<acceptance-token>" }
```

يشترط القبول مطابقة البريد، توثيق البريد، أن تكون المدرسة فعالة، وأن تكون الدعوة معلقة وغير منتهية. يجب أن يرسل رمز الدعوة للمدعو عبر قناة آمنة خارج سجل التطبيق العام.

### 11.2 ملفات أولياء الأمور والعلاقات الأسرية

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET, POST | `guardians/` | قراءة ملفات أولياء الأمور وإنشاء ملف ولي أمر |
| GET, PUT, PATCH, DELETE | `guardians/{id}/` | تفاصيل/تعديل/أرشفة ملف ولي الأمر |
| GET, POST | `guardian-relations/` | ربط طالب بولي أمر |
| GET, PUT, PATCH, DELETE | `guardian-relations/{id}/` | إدارة العلاقة وصلاحيات الاستلام والإشعارات |

إنشاء ملف ولي أمر يرسل `user_id` وحقول العلاقة مثل `relationship_type` و`national_id` و`emergency_phone`. المستخدم المرتبط يجب أن يمتلك عضوية مدرسة نشطة سارية. يمكن للإدارة إدارة جميع العلاقات؛ ولي الأمر يرى ملفه وأبناءه فقط.

علاقة ولي الأمر بالطالب تحتوي:
- `is_primary`: هل هو ولي الأمر الأساسي للمراسلات.
- `receives_notifications`: هل يستلم الإشعارات الأكاديمية والمالية.
- `can_pickup`: هل يملك صلاحية استلام الطالب والانصراف.

### 11.3 البنية الأكاديمية والإعدادات المدرسية

الموارد التالية تدعم عمليات CRUD القياسية: `GET` للقائمة، `POST` للإنشاء، `GET` للتفاصيل، `PUT/PATCH` للتعديل، و`DELETE` للأرشفة عندما يدعم الموديل الأرشفة.

| المورد | Endpoint |
|---|---|
| السنوات الدراسية | `academic-years/` |
| الفصول الدراسية | `academic-terms/` |
| المراحل | `stages/` |
| الصفوف | `grades/` |
| القاعات | `classrooms/` |
| الشعب | `sections/` |
| المواد | `subjects/` |
| تعريف الفترات الزمنية | `period-definitions/` |
| أيام الدوام | `working-days/` |

مرشحات مدعومة في القوائم:
- `grades/?stage_id={uuid}`
- `sections/?academic_year_id={uuid}&grade_id={uuid}`
- موارد التوقيت التي تستقبل `schedule_id` أو `academic_year_id` أو `section_id` موضحة في قسم الجدول أدناه.

تحقق النماذج والعقود من تواريخ السنة والفصل، وانتماء الصف للمرحلة، وانتماء الشعبة للصف والسنة، والطاقة الاستيعابية للشعبة.

### 11.4 المعلمون والموارد البشرية

| Method | Endpoint | ملاحظات |
|---|---|---|
| GET, POST | `teachers/` | ملفات المعلمين؛ الإنشاء يربط مستخدماً لديه عضوية مدرسية |
| GET, PUT, PATCH, DELETE | `teachers/{id}/` | إدارة ملف المعلم |
| GET, POST | `teacher-assignments/` | إسناد مادة/شعبة/سنة للمعلم |
| GET, PUT, PATCH, DELETE | `teacher-assignments/{id}/` | إدارة الإسناد |
| GET, POST | `departments/` | أقسام المدرسة |
| GET, PUT, PATCH, DELETE | `departments/{id}/` | إدارة الأقسام |
| GET, POST | `work-shifts/` | ورديات الدوام |
| GET, PUT, PATCH, DELETE | `work-shifts/{id}/` | إدارة الورديات |
| GET, POST | `leave-types/` | أنواع الإجازات |
| GET, PUT, PATCH, DELETE | `leave-types/{id}/` | إدارة أنواع الإجازات |

إدارة ملفات المعلمين والإسنادات والأقسام والورديات وأنواع الإجازات تتطلب دوراً إدارياً/أكاديمياً أو صلاحية نموذج مناسبة. الطلبات الشخصية للإجازة والحضور الوظيفي تبقى في `/api/v1/staff/leaves/` و`/api/v1/staff/attendance/` حتى لا ينشأ مسار ثانٍ للعملية نفسها.

### 11.5 الواجبات وتسليمات الطلاب

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET, POST | `homework/` | قائمة/إنشاء واجب |
| GET, PUT, PATCH, DELETE | `homework/{id}/` | تفاصيل/تعديل/أرشفة واجب |
| GET | `homework-submissions/` | عرض التسليمات حسب الصلاحية |
| POST | `homework-submissions/submit/` | إرسال محاولة واجب جديدة |
| POST | `homework-submissions/{submission_uuid}/request-resubmission/` | طلب المعلم إعادة التسليم مع السبب |
| POST | `homework-submissions/{submission_uuid}/grade/` | تصحيح آخر محاولة |
| GET | `homework-submissions/{submission_uuid}/attachment/` | تنزيل أحدث مرفق بأمان |
| GET | `homework-submissions/{submission_uuid}/attempts/{attempt_uuid}/attachment/` | تنزيل مرفق محاولة تاريخية |

إنشاء الواجب يتضمن `subject`, `section`, `title`, `description`, `due_date` ويمكن تحديد `max_score`. يستطيع المعلم إنشاء أو تعديل واجب فقط ضمن مادة وشعبة وسنة دراسية مسندة إليه. يستطيع المسؤول تحديد `teacher_id` نشط عند الإنشاء.

تسليم الطالب يستخدم JSON أو `multipart/form-data`:
- `homework_id` (مطلوب).
- `submission_text` (اختياري).
- `attachment` (اختياري).

الأنواع المسموحة: PDF وPNG وJPG/JPEG وDOC/DOCX، والحد الأقصى 15 ميجابايت. كل تسليم يحفظ كـ«محاولة» مستقلة برقم ووقت ومرفق خاص به؛ لا تستبدل المحاولة الجديدة السابقة. لا يسمح بإعادة التسليم إلا بعد أن يطلب المعلم ذلك من سجل التسليم ويكتب سبباً واضحاً، وبعدها يستطيع الطالب إرسال المحاولة التالية. إذا صحح المعلم التسليم فلا يقبل النظام محاولة إضافية مباشرة. يحفظ سجل التدقيق من طلب إعادة التسليم والتسليم والتصحيح.

### 11.6 التدريس والتقييم والاختبارات والنتائج

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET, POST | `assessment-types/` | أنواع التقييم وأوزانها |
| GET, POST | `gradebook/` | قائمة دفتر الدرجات/إنشاء مسودة درجة |
| GET, PUT, PATCH, DELETE | `gradebook/{id}/` | إدارة مسودة الدرجة ضمن الإسناد |
| POST | `gradebook/{id}/submit-for-approval/` | إرسال الدرجة للمراجعة |
| POST | `gradebook/{id}/approve/` | اعتماد الدرجة إدارياً |
| POST | `gradebook/{id}/publish/` | نشر الدرجة المعتمدة أو إخفاؤها بسبب |
| POST | `gradebook/{id}/reopen/` | إعادة فتح الدرجة للتصحيح بسبب موثق |
| GET | `gradebook/weighted-summary/?subject_id=&academic_term_id=` | ملخص الدرجة الموزونة للطالب |
| GET, POST | `question-bank/` | بنك الأسئلة للمعلمين والإدارة |
| GET, PUT, PATCH, DELETE | `question-bank/{id}/` | إدارة سؤال |
| GET, POST | `online-exams/` | قائمة/إنشاء اختبار كمسودة |
| GET, PUT, PATCH, DELETE | `online-exams/{id}/` | إدارة اختبار غير منشور ولم تبدأ محاولاته |
| POST | `online-exams/{id}/publish/` | نشر الاختبار أو إلغاء نشره بسبب |
| GET | `online-exams/{id}/paper/` | ورقة الاختبار للطالب خلال الفترة المسموحة |
| POST | `online-exams/{id}/start/` | بدء محاولة أو استئناف المحاولة نفسها |
| POST | `online-exams/{id}/submit/` | تسليم الإجابات |
| GET | `online-exams/{id}/report/` | تقرير أعداد البدء والتسليم والتصحيح والنشر |
| GET | `exam-submissions/` | محاولات الاختبارات حسب صلاحية الدور |
| POST | `exam-submissions/{id}/grade/` | التصحيح اليدوي بعد التسليم |
| POST | `exam-submissions/{id}/publish/` | نشر النتيجة أو إخفاؤها بسبب |
| POST | `exam-submissions/{id}/reopen/` | إعادة فتح محاولة مصححة بسبب موثق |
| GET, POST | `exam-committees/` | لجان الاختبارات |
| GET, PUT, PATCH, DELETE | `exam-committees/{id}/` | إدارة اللجان |
| GET, POST, PUT, PATCH, DELETE | `exam-committee-proctors/` | إسناد المراقبين للجان؛ المعلم يرى تكليفاته فقط |
| GET, POST | `exam-seatings/` | أرقام الجلوس وتوزيع اللجان |
| GET, PUT, PATCH, DELETE | `exam-seatings/{id}/` | إدارة أرقام الجلوس |

**سير اعتماد الدرجة:** تبدأ كل درجة جديدة كمسودة غير منشورة. يرسلها المعلم للمراجعة، ثم يعتمدها صاحب الصلاحية الأكاديمية، وبعد ذلك ينشرها. لا يستطيع الطالب أو ولي الأمر رؤية السجل قبل النشر. لا يمكن تعديل درجة معتمدة أو منشورة مباشرة؛ يجب إعادة فتحها مع سبب، ويُسجل كل انتقال في سجل التدقيق. مجموع أوزان أنواع التقييم النشطة في المدرسة لا يتجاوز 100 بالمئة، ويحسب `weighted-summary` متوسط كل نوع ثم يطبق وزنه على الأنواع المنشورة ذات الدرجات.

**دورة الاختبار:** ينشأ الاختبار كمسودة ولا يظهر للطلاب حتى نشره بصلاحية أكاديمية. يشترط أن تتبع المادة والصف والشعبة والفصل الدراسي المدرسة والسنة نفسها، وأن لا يتجاوز مجموع درجات الأسئلة الدرجة العظمى. بعد بدء أول محاولة لا يمكن تعديل محتوى الاختبار أو أسئلته؛ ينشأ اختبار جديد عند الحاجة إلى تغيير جوهري. بدء الاختبار يسجل وقت الخادم والمهلة النهائية، والاستئناف يعيد نفس المحاولة والمهلة ولا يبدأ المؤقت من الصفر. لا يقبل التسليم بعد انتهاء المهلة.

**حماية الإجابات والنتائج:** مسار `paper` لا يعيد `correct_answer` أو شرح الحل. تصحيح الأسئلة الموضوعية يجري على الخادم، ويقتصر التصحيح اليدوي على مجموع درجات الأسئلة القصيرة والمقالية. يحجب الخادم درجات المحاولة وملاحظات التصحيح عن الطالب وولي الأمر حتى ينشر مسؤول مخول النتيجة. يمكن إخفاء النتيجة المنشورة أو إعادة فتحها للتصحيح فقط بسبب موثق. لا يعيد API رقم السر الخاص بالكنترول `secret_code` للطالب.

**اللجان والمراقبون:** يدعم سجل اللجنة رئيساً، وتكليف عدة مراقبين مع تحديد دور كل مراقب. تقتصر قوائم المعلمين على اللجان المسندة إليهم، وتقتصر قائمة الطالب على رقم جلوسه. تقارير الاختبارات تعرض أعداد المستهدفين والبدء والتسليم والمحاولات الجارية والدرجات المنشورة دون كشف إجابات بقية الطلاب.

### 11.7 الجدول الأسبوعي وسجل تنفيذ الدروس

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET, POST | `bell-schedules/` | قوالب مواعيد اليوم والحصص |
| GET, PUT, PATCH, DELETE | `bell-schedules/{id}/` | إدارة القوالب |
| GET, POST | `period-templates/` | الفترات الزمنية للقالب |
| GET, PUT, PATCH, DELETE | `period-templates/{id}/` | إدارة الفترات |
| GET, POST | `class-schedules/` | جدول الحصص الأسبوعي |
| GET, PUT, PATCH, DELETE | `class-schedules/{id}/` | إدارة الحصص |
| GET, POST | `lesson-logs/` | توثيق تنفيذ الدرس |
| GET, PUT, PATCH, DELETE | `lesson-logs/{id}/` | إدارة سجل الدرس |
| GET | `my/timetable/?profile_type=teacher` | جدول المعلم |
| GET | `my/timetable/?profile_type=student` | جدول الطالب |
| GET | `my/timetable/?profile_type=guardian` | جداول أبناء ولي الأمر |
| GET | `my/timetable/?profile_type=school&section_id={uuid}` | جدول شعبة للإدارة |

مرشحات: `period-templates/?schedule_id=`, `class-schedules/?academic_year_id=&section_id=&teacher_id=&day_of_week=`, `lesson-logs/?date=&section_id=`. إذا كان الحساب يحمل أكثر من ملف (مثلاً معلم وولي أمر)، يجب إرسال `profile_type` لاختيار مساحة الجدول؛ وإذا تعددت الملفات ولم يحدد النوع يعيد الخادم خطأ تحقق يبين الأنواع المتاحة. لا تكرر واجهة التوليد الذكي هنا؛ مسار التوليد الرسمي موجود في `/api/v1/timetable/ai-generate/`.

### 11.8 المحاسبة والقيود والسندات

| Method | Endpoint | الوظيفة |
|---|---|---|
| CRUD | `fiscal-years/` | السنوات المالية |
| CRUD | `fiscal-periods/` | الفترات المالية |
| CRUD | `accounts/` | دليل الحسابات |
| CRUD | `cost-centers/` | مراكز التكلفة |
| CRUD | `expense-categories/` | تصنيفات المصروفات |
| GET, POST | `journal-entries/` | قائمة/إنشاء قيد يومية |
| GET, PUT, PATCH | `journal-entries/{id}/` | قراءة/تعديل المسودة |
| POST | `journal-entries/{id}/post/` | ترحيل القيد |
| POST | `journal-entries/{id}/reverse/` | إنشاء قيد عكسي بسبب محدد |
| GET, POST | `payment-vouchers/` | قائمة/إنشاء سند صرف |
| POST | `payment-vouchers/{id}/post/` | ترحيل سند الصرف |
| GET, POST | `receipt-vouchers/` | قائمة/إنشاء سند قبض عام |
| POST | `receipt-vouchers/{id}/post/` | ترحيل سند القبض العام |

إنشاء قيد يومية يدوي:

```json
{
  "fiscal_period_id": "<fiscal-period-uuid>",
  "date": "2026-10-31",
  "description": "قيد مصروفات تشغيلية",
  "lines": [
    {"account_id": "<expense-account-uuid>", "debit": "2500.00", "credit": "0.00"},
    {"account_id": "<cash-account-uuid>", "debit": "0.00", "credit": "2500.00"}
  ]
}
```

يجب وجود سطرين على الأقل، حساب تفصيلي صالح من المدرسة نفسها، وألا يكون أي سطر مديناً ودائناً معاً. مجموع المدين يجب أن يساوي مجموع الدائن. تعديل قيد مسودة عبر `PUT/PATCH` يقبل `description` و`date` و`fiscal_period_id`، ويمكن إرسال `lines` لاستبدال جميع الأسطر دفعة واحدة؛ يجب أن تبقى متوازنة بالكامل. إذا لم ترسل `lines` تبقى الأسطر الحالية كما هي. رقم القيد لا يتغير بعد الإنشاء. لا يسمح بتعديل القيد بعد الترحيل؛ التصحيح يتم بقيد عكسي فقط. قيود الصرف والقبض تنشئ رأس قيد وأسطره تلقائياً وتبقى مسودة حتى إجراء `post`.

### 11.9 الموردون والمستودعات والمشتريات والأصول

| Method | Endpoint | الوظيفة |
|---|---|---|
| CRUD | `suppliers/` | الموردون |
| CRUD | `warehouses/` | المستودعات |
| CRUD | `inventory-items/` | دليل الأصناف |
| CRUD | `stock-movements/` | حركات المخزون |
| CRUD | `purchase-orders/` | أوامر الشراء |
| POST | `purchase-orders/{id}/approve/` | اعتماد أمر شراء بعد إضافة بند على الأقل |
| POST | `purchase-orders/{id}/receive/` | استلام بنود الأمر وتوليد حركات توريد |
| CRUD | `purchase-order-items/` | بنود أوامر الشراء |
| CRUD | `vendor-invoices/` | فواتير الموردين |
| POST | `vendor-invoices/{id}/approve/` | اعتماد فاتورة مورد |
| POST | `vendor-invoices/{id}/post/` | ترحيل استحقاق المورد |
| POST | `vendor-invoices/{id}/record-payment/` | تسجيل سداد جزئي/كامل بعد ترحيل الفاتورة مع مفتاح منع تكرار |
| CRUD | `asset-categories/` | تصنيفات الأصول |
| CRUD | `fixed-assets/` | الأصول الثابتة |
| GET, POST | `asset-depreciations/` | سجل إهلاك الأصل |
| GET | `asset-depreciations/{id}/` | تفاصيل قيد الإهلاك |

مرشحات:
- `inventory-items/?warehouse_id=&low_stock=true`.
- `stock-movements/?item_id=&movement_type=`.
- `purchase-order-items/?purchase_order_id=`.

الرصيد المخزني يتغير من خلال `stock-movements` أو استلام أمر شراء فقط؛ لا يُسمح لعميل Flutter بتعديل `current_stock` مباشرة. حذف حركة مخزون ينفذ عكساً كمياً ذرياً وفق قواعد نموذج الحركة. بنود أمر الشراء تعدل فقط بينما الأمر مسودة ويعاد احتساب إجماليه تلقائياً. لا يمكن اعتماد أمر شراء فارغ أو استلامه قبل الاعتماد. لا يمكن سداد فاتورة مورد لم يرحّل استحقاقها محاسبياً.

قيود الإهلاك تاريخية: لا تقبل التعديل أو الحذف عبر API، ويجب إنشاء قيد تسوية منفصل لمعالجة الخطأ.

### 11.10 أجهزة الإشعارات وتفضيلات المستخدم

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET, POST | `devices/` | عرض/تسجيل جهاز المستخدم الحالي |
| POST | `devices/{id}/deactivate/` | تعطيل الجهاز |
| POST | `devices/{id}/heartbeat/` | تحديث النشاط وإعادة تفعيل الجهاز |
| GET, POST | `notification-preferences/` | قراءة/إنشاء تفضيل إشعار |
| PATCH | `notification-preferences/{id}/` | تغيير حالة تفضيل |

تسجيل الجهاز يرسل `device_id`, `platform` (`android`, `ios`, `web`), `push_token`, واختيارياً `app_version` و`device_name`. الرمز الفريد لا يمكن ربطه بحسابين. هذه الموارد تسجل بيانات الجهاز وتفضيلاته؛ لا تعني أن مزود Push الفعلي أو مهمة الإرسال جاهزة.

### 11.11 المحادثات والرسائل والمرفقات

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET, POST | `conversations/` | قائمة محادثات المستخدم/إنشاء محادثة |
| GET | `conversations/{id}/` | تفاصيل المحادثة والمشاركين وعدد غير المقروء |
| GET, POST | `conversations/{id}/messages/` | قراءة/إرسال الرسائل |
| POST | `conversations/{id}/read/` | تحديث آخر قراءة |
| POST | `conversations/{id}/mute/` | كتم/إلغاء كتم المحادثة |
| POST | `conversations/{id}/close/` | إغلاق المحادثة إدارياً |
| PATCH, DELETE | `conversations/{conversation_id}/messages/{message_id}/` | تعديل رسالة المرسل أو حذفها من العرض |
| GET | `conversation-messages/{message_id}/attachment/` | تنزيل مرفق رسالة لمشارك في المحادثة |

إنشاء المحادثة:

```json
{
  "subject": "متابعة الطالب",
  "conversation_type": "student",
  "student_id": "<student-uuid>",
  "participant_ids": ["<user-uuid>", "<another-user-uuid>"]
}
```

كل مشارك يجب أن يمتلك عضوية فعالة وسارية بالمدرسة. عند ربط المحادثة بطالب يجب أن يتبع الطالب المدرسة نفسها؛ ولي الأمر لا يستطيع بدء محادثة عن طالب غير مرتبط به. إرسال رسالة يقبل نصاً أو ملفاً، مع دعم الرد على رسالة عبر `reply_to_id`. المرفقات المسموحة: PDF/صور/DOC/DOCX/XLS/XLSX/TXT، والحد الأقصى 15 ميجابايت. رابط المرفق لا يعاد في JSON؛ يستخدم مسار التنزيل الذي يتحقق من عضوية المشارك. حذف الرسالة حذف منطقي ويخفي نصها وبيانات مرفقها من الاستجابة.

### 11.12 عقد عام لقوائم الموارد

أغلب ViewSets في هذا القسم تستخدم عمليات CRUD القياسية الموضحة بجانب كل مورد. المسارات المخصصة الواردة بلفظ POST هي أوامر سير عمل وليست إنشاء سجلات عادية. لا تستخدم `PUT/PATCH` لتجاوز حالة المورد؛ الخادم يرفض تعديل القيود المرحلة، أو فواتير المورد المعتمدة، أو أوامر الشراء المعتمدة، أو سجلات الإهلاك التاريخية.

عند تعدد أدوار المستخدم (مثلاً معلم وولي أمر)، يظل سياق المدرسة واحداً لكن يجب أن تعرض الواجهة أوضاع العمل التي تسمح بها ملفات المستخدم. الصلاحيات الفعلية والنطاق النهائي دائماً يتحقق منهما الخادم؛ إخفاء زر في Flutter ليس حاجزاً أمنياً.

---

## 12. حالة التحقق والإصدار

هذا الدليل يصف الملفات والمسارات الموجودة في المستودع. لا تعتبر أي دفعة جاهزة للإنتاج قبل تحقق CI على آخر commit، بما في ذلك:
1. Ruff lint للملفات الجديدة والمعدلة.
2. `python manage.py check`.
3. `python manage.py makemigrations --check --dry-run`.
4. الاختبارات على SQLite وPostgreSQL.
5. تجربة تدفقات التسجيل/الأدوار/الطلاب/الواجبات/الاختبارات/المحاسبة/المخزون/المحادثات على بيئة staging ببيانات اصطناعية.

لا تُسجل الخادم أو بيئة الإنتاج كمجربة من خلال CI فقط. يجب أن تضاف اختبارات تكامل خاصة لكل عملية مالية ومخزنية قبل إطلاق التطبيق.

---

## 17. خدمات المدرسة المساندة

هذه الوظائف لا تملك وحدة API خاصة بها في النسخة السابقة. أضيفت الآن داخل التطبيق المالك `apps/school_services/api/`، ولم يتم استبدال أو تعديل عقود التطبيقات التي كانت تملك API مستقلاً. جميع المسارات التالية تبدأ بـ `/api/v1/school-services/` وتتطلب المصادقة ورأس `X-School-ID` عند وجود أكثر من مدرسة للحساب.

### النقل المدرسي

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET, POST | `/bus-routes/` | عرض خطوط السير وإنشاء خط؛ السائق يرى الخطوط المسندة إليه فقط |
| GET, PUT, PATCH, DELETE | `/bus-routes/{id}/` | تفاصيل وتعديل أو أرشفة خط السير |
| GET, POST | `/bus-subscriptions/` | عرض اشتراكات النقل وإنشاء اشتراك |
| GET, PUT, PATCH, DELETE | `/bus-subscriptions/{id}/` | تفاصيل الاشتراك وتعديله أو أرشفته |

ولي الأمر والطالب يريان اشتراكات أبنائهم/ملفاتهم المرتبطة فقط. إدارة خطوط السير والاشتراكات محصورة بإدارة النقل والإدارة المخولة.

### المكتبة والإعارة

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET, POST | `/library/books/` | دليل الكتب وإضافة كتاب |
| GET, PUT, PATCH, DELETE | `/library/books/{id}/` | تفاصيل الكتاب وتحديثه أو أرشفته |
| GET, POST | `/library/loans/` | عرض الإعارات وإنشاء إعارة |
| POST | `/library/loans/{id}/return/` | تسجيل إرجاع نسخة وتحديث الرصيد المتاح مرة واحدة |

المستعير وولي أمره يريان سجلاتهم المرتبطة فقط. إدارة الكتب والإعارات وإجراء الإرجاع لأمين المكتبة أو الإدارة المخولة. حالة الإعارة وتاريخ الإرجاع لا يقبلان التعديل المباشر.

### التسويات وتوزيع الكتب وأوامر الصرف

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET, POST | `/bus-settlements/` | عرض التسويات أو إنشاء تسوية مسودة |
| POST | `/bus-settlements/{id}/calculate/` | احتساب العدد والمستحقات بحسب عقد خط السير |
| POST | `/bus-settlements/{id}/approve/` | اعتماد التسوية وإنشاء/ربط سند الصرف وفق خدمة النموذج |
| GET, POST | `/book-distributions/` | عرض أو تجهيز سجل تسليم كتاب لطالب |
| POST | `/book-distributions/{id}/deliver/` | التسليم الفعلي مع خصم المخزون وإنشاء فاتورة الرسوم عند الحاجة |
| POST | `/book-distributions/{id}/return/` | استرجاع الكتاب وعكس أثر المخزون والرسوم وفق قيود النموذج |
| GET, POST | `/book-requisitions/` | عرض أو إنشاء أمر صرف كتب في حالة مسودة مع البنود |
| POST | `/book-requisitions/{id}/items/` | إضافة بنود للمسودة قبل رفعها |
| POST | `/book-requisitions/{id}/submit/` | رفع الطلب للاعتماد |
| POST | `/book-requisitions/{id}/approve/` | اعتماد الكميات المطلوبة أو تعديلها ضمن سقف الكمية المطلوبة |
| POST | `/book-requisitions/{id}/reject/` | رفض الطلب مع سبب اختياري |
| POST | `/book-requisitions/{id}/fulfill/` | صرف البنود من المخزون مع تسجيل حركة صرف لكل صنف |

بيانات صرف أمر التوريد تتضمن مصفوفة `items`، وكل عنصر يحمل `requisition_item_id` و`inventory_item_id` و`quantity`. يسمح بالصرف الجزئي ولا تتحول الحالة إلى مكتمل حتى تصرف جميع الكميات المعتمدة. لا يقبل صرف صنف من مدرسة أخرى أو كمية تتجاوز المتبقي المعتمد.

### العيادة المدرسية

| Method | Endpoint | الوظيفة |
|---|---|---|
| GET, POST | `/clinic/health-profiles/` | قراءة أو إنشاء ملف صحي لطالب |
| GET, PUT, PATCH | `/clinic/health-profiles/{id}/` | تعديل الملف الصحي |
| GET, POST | `/clinic/visits/` | عرض زيارات العيادة وتسجيل زيارة |
| GET, PUT, PATCH | `/clinic/visits/{id}/` | مراجعة وتحديث بيانات الزيارة |

الملفات الصحية والتشخيصات بيانات شديدة الحساسية؛ لذلك لا تعرض هذه الواجهات إلا لدور العيادة/الممرض/الطبيب والإدارة المخولة، ولا تكشف الملف الصحي أو التشخيصات لواجهة ولي الأمر عبر هذا العقد. جميع الموارد مقيدة بالمدرسة النشطة.

**ضوابط مهمة:** لا توجد واجهات حذف فعلي للسجلات الطبية أو أوامر الصرف. تنتقل حالات الإعارة والتسليم والتسويات وأوامر الصرف عبر عمليات POST المخصصة، وليس بتغيير حقل الحالة مباشرة. يظل تطبيق قواعد المخزون والفواتير والسندات والقيود داخل خدمات ونماذج التطبيق المالكة.


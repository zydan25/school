# لوحات العمل المتصلة

تقرأ لوحة كل دور من API المدرسة الفعلي:
- ولي الأمر: app/my/children/ و app/my/timetable/?profile_type=guardian.
- الطالب: students/ و app/my/timetable/?profile_type=student.
- المعلم: app/teacher-assignments/ و students/ و app/my/timetable/?profile_type=teacher.
- الموظف: app/account/profiles/ (بيانات ملفه المصرح بها).
- الإدارة: تتحقق من دور الإدارة الموجود في بيانات عضوية المدرسة، ولا تعرض أرقاماً غير مطلوبة من الخادم.

لا تستخدم هذه الوحدة بيانات Preview. أسماء الطلاب والشعب والجدول تأتي من API. عند غياب بيانات، تعرض الحالة الفارغة بدلاً من ملء الشاشة بمعلومات تجريبية.

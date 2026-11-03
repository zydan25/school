# تقرير مواءمة تطبيق مدرستي مع خادم main

**التاريخ:** 3 نوفمبر 2026  
**المستودع:** `zydan25/school`  
**فرع التطبيق:** `feature/mobile-madrasati-android`  
**مرجع الخادم الذي تم اعتماده:** `main` — `55b90e0d5cc09f5a2c7f94a9a7695cf93732211a`  
**Commit مزامنة main إلى فرع التطبيق:** `e07040d0258c069c492a391c33227854c01412b9`

## ما تم اعتماده

تم دمج `main` إلى فرع تطبيق مستقل مشتق من `feature/mobile-expo-foundation`. لم يتم دفع أي تعديل إلى `main` ولم يتم تغيير كود الخادم. المقارنة بعد المزامنة: فرع التطبيق متقدم عن main فقط ولا توجد commits مفقودة منه وقت التحقق (`ahead 93 / behind 0`).

تمت مراجعة ملفات المسارات الفعلية في `apps/api/urls.py` و`apps/api/views.py` و`apps/api/v1/urls.py` و`apps/api/v1/views.py` وملفات API الحضور والإشعارات، مع دليل `docs/api/README_AR.md` على نفس مرجع main.

## مطابقة المسارات في التطبيق

| الوظيفة | المسارات المعتمدة |
|---|---|
| تسجيل الدخول والجلسات | `auth/login/`, `auth/logout/`, `auth/sessions/refresh/`, `schools/`, `me/` |
| الملفات والدور | `app/account/profiles/`, `app/my/children/`, `app/teacher-assignments/` |
| الدراسة والواجبات | `app/homework/`, `app/homework-submissions/`, `app/gradebook/` |
| الاختبارات | `app/online-exams/` مع `paper/start/submit` |
| كشف الرسوم | `fees/students/{student_id}/statement/` |
| الإشعارات | `notifications/`, `app/notification-preferences/` |
| المحادثات | `app/conversations/` مع `messages/read/mute/close` |

تسجيل الدخول الحالي يرسل `X-Device-ID` و`device_id` و`device_name`، ويعتمد `access_token` و`session_id` و`expires_at` من الخادم، ويخزن الجلسة في SecureStore، ويستخدم refresh route الجديد. لا تُحفظ كلمة المرور في التخزين المحلي.

## تحديثات الحضور المضافة

- جلب أنواع الحالات النشطة من `attendance/status-types/`.
- فتح سجل الشعبة المسندة عبر `attendance/registers/open/` مع التحقق من السنة والشعبة.
- حفظ سجلات الطلاب دفعة واحدة عبر `bulk-record/` ثم تسليمها عبر `submit/`.
- الإدارة تعتمد السجلات المرسلة عبر `approve/` ثم تقفل السجلات المعتمدة عبر `lock/`.
- المعلم يرسل طلب إعادة فتح سجل مقفل مع السبب عبر `reopen-request/`.
- الإدارة ترى الطلبات المعلقة في `attendance/reopen-requests/?status=pending` ثم توافق أو ترفض عبر `review-reopen/` مع ملاحظات المراجعة.
- صلاحية كل عملية تبقى للخادم؛ التطبيق لا يتجاوز role map ولا يحرر السجل بعد إقفاله محلياً.
- سجل الحضور ودرجات المواظبة للأبناء وطلبات الأعذار تستعمل مساراتها الحالية في main.

## صلاحيات Android والاتصال

- الاسم المعروض: `مدرستي`.
- Android applicationId: `com.zydan25.madrasati`.
- scheme: `madrasati`.
- الصلاحيات المضافة صراحة: `INTERNET` و`ACCESS_NETWORK_STATE`.
- cleartext traffic معطل؛ الاتصال المهيأ هو HTTPS.
- الجلسة تحفظ في Android Keystore عبر SecureStore.
- لم نطلب صلاحيات الكاميرا أو الموقع أو القراءة العامة للملفات لأنها ليست لازمة للرحلات الموجودة حالياً.
- لم نعلن أن Push يعمل: وجود API تسجيل الأجهزة ومكتبة Expo Notifications لا يثبت إعداد FCM/APNs ولا إكمال الإرسال الفعلي.

## ما لا يزال غير مكتمل في واجهات الهاتف

1. إرسال واستقبال مرفقات المحادثات والرد على رسالة وتعديلها وحذفها وتنزيل المرفقات؛ الخادم يدعم المسارات، واجهة الهاتف الحالية نصية.
2. واجهة الانصراف المبكر/بوابة الخروج، وسياسات التقويم والفعاليات، وعرض سجل التدقيق وتقارير الحضور؛ لها APIs في main ولم تدمج كشاشات بعد.
3. إدارة الاختبارات للمعلم والإدارة؛ واجهة الاختبارات الحالية للطالب.
4. مرفقات عذر الغياب من واجهة ولي الأمر؛ العقد يدعم multipart عند الحاجة.
5. تسجيل Push الفعلي وطلب إذن الإشعارات وربط مزود Android وإثبات وصول الإشعار؛ لا تُعد جاهزة الآن.
6. لا توجد واجهة حضور ذاتي للطالب في العقد الذي تم فحصه.

## نتائج التحقق

- GitHub Mobile CI: تم تثبيت الحزم، فحص توافق Expo، TypeScript، وتصدير Android JS bundle بنجاح على فرع مدرستي.
- Android APK workflow: تم تثبيت الحزم، TypeScript، توليد مشروع Android الأصلي، وفحص Manifest للصلاحيات والسياسة الآمنة. نتيجة تجميع APK تظل مرتبطة بتشغيل GitHub Actions، ولا يعتبر APK مبنياً حتى ينجح `assembleDebug` ويرفع Artifact.
- لم ينفذ تسجيل دخول بحسابات المدرسة الحقيقية أو اختبار على هاتف مادي في هذا التغيير.
- عنوان API المضمن: `https://school.alattab.site/api/v1` من `mobile/.env.example`. مطابقة ملفات التطبيق للعقد لا تعني أن الخادم المنشور على هذا العنوان قد نُشر عليه commit main نفسه؛ يلزم التحقق من النشر والصحة التشغيلية قبل تجربة حسابات فعلية.

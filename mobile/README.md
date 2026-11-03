# School Mobile

عميل الهاتف الموحد لمنصة School باستخدام Expo + React Native + TypeScript.

## المتطلبات
- Node.js 22.13 أو أحدث.
- npm.
- Android Studio أو جهاز Android للاختبار.
- حساب Expo/EAS عند البدء بالبناء السحابي والنشر.

## التجهيز المحلي

من داخل مجلد mobile:

~~~bash
npm install
cp .env.example .env
npx expo install --check
npm run typecheck
npx expo start
~~~

لتشغيل Expo على Android:

~~~bash
npm run android
~~~

لإنشاء Development Build بعد ربط حساب EAS:

~~~bash
npx eas-cli login
npx eas-cli init
npx eas-cli build --profile development --platform android
~~~

تثبت إصدارات Expo SDK في package.json. عند إضافة أي حزمة Native تابعة لـ Expo استخدم npx expo install اسم-الحزمة حتى يختار الإصدار المتوافق مع SDK 58، ثم نفذ npx expo install --check.

## المكتبات الأساسية
Expo Router، React Native Paper، Lucide React Native، TanStack Query، Zustand، React Hook Form، Zod، Expo SecureStore، Expo Notifications، Expo SQLite، Expo Font، Expo Localization، EAS Build وEAS Update.

## حالة التطبيق الحالية
المسار الرئيسي يعرض معرض تصميم تفاعلياً لواجهات الطالب وولي الأمر والمعلم. يستطيع المستخدم تبديل الدور، اختيار ابن أو شعبة، ومعاينة حالات عدم وجود الأبناء أو الإسنادات. جميع البيانات في المعرض تجريبية ولا تتصل بالخادم، ولا تمثل بعد تسجيل دخول حقيقياً.

## الوثائق
- معمارية الهاتف: ../docs/mobile/00-القرار-المعماري.md
- مواصفات الشاشات: ../docs/mobile/01-مواصفات-الشاشات.md
- النظام البصري: ../docs/mobile/02-نظام-التصميم-والمرجع-البصري.md
- عقد التكامل: ../docs/mobile/03-عقد-التكامل.md
- معرض التصميم: src/features/design-preview/README.md

## ضوابط
- لا تضع أسراراً أو ملفات .env في المستودع.
- لا تحفظ access token في AsyncStorage أو Zustand؛ استخدم SecureStore.
- لا تدمج تغييرات الهاتف في main إلا عبر مراجعة وطلب دمج.
- لا تنفذ عمليات مالية أو اعتماداً محلياً دون قبول الخادم.

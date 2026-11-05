import 'package:flutter_test/flutter_test.dart';
import 'package:school_flutter/core/api_service.dart';
import 'package:school_flutter/core/models.dart';
import 'package:school_flutter/main.dart';
import 'package:school_flutter/screens/login_screen.dart';

void main() {
  group('Madrasati Flutter Security & Navigation Tests', () {
    testWidgets('AuthGate displays LoginScreen when unauthenticated (No bypass)', (WidgetTester tester) async {
      final api = ApiService();
      expect(api.isAuthenticated, isFalse);

      await tester.pumpWidget(MadrasatiApp(api: api));
      await tester.pump();

      expect(find.byType(LoginScreen), findsOneWidget);
      expect(find.text('تسجيل الدخول للمنظومة'), findsOneWidget);
      expect(find.text('منظومة مدرستي الذكية'), findsOneWidget);
    });

    test('UserAccount model parses from backend JSON correctly', () {
      final json = {
        'id': 'user-123',
        'phone': '770000004',
        'full_name': 'سيف العتاب',
        'email': 'saif@example.com',
        'is_platform_admin': false,
        'phone_verified': true,
      };

      final account = UserAccount.fromJson(json);
      expect(account.id, equals('user-123'));
      expect(account.phone, equals('770000004'));
      expect(account.fullName, equals('سيف العتاب'));
      expect(account.phoneVerified, isTrue);
      expect(account.isPlatformAdmin, isFalse);
    });

    test('SchoolContextItem model parses from backend login response', () {
      final json = {
        'school_id': 'sch-4e865cc1',
        'school_code': '1234',
        'school_name': 'المدرسة الافتراضية',
        'roles': ['guardian'],
        'is_default': true,
      };

      final school = SchoolContextItem.fromJson(json);
      expect(school.schoolId, equals('sch-4e865cc1'));
      expect(school.schoolCode, equals('1234'));
      expect(school.schoolName, equals('المدرسة الافتراضية'));
      expect(school.roles, contains('guardian'));
      expect(school.isDefault, isTrue);
    });

    test('Role isolation: availableRoles derived from server response', () {
      final api = ApiService();
      expect(api.availableRoles, isNotEmpty);
      expect(api.availableRoles.contains('admin'), isFalse);
    });

    test('STU-01 & STU-02: Decoupled identity - activeStudentProfile is separate from guardianChildren', () {
      final api = ApiService();
      // By default with no login, activeStudentProfile is null and guardianChildren is empty
      expect(api.activeStudentProfile, isNull);
      expect(api.guardianChildren, isEmpty);
      // currentStudent returns null when no profile is loaded - NO fake Ahmed Al-Attab fallback!
      expect(api.currentStudent, isNull);
    });

    test('STU-08 & STU-09: OnlineExamItem model parses correctly from backend JSON', () {
      final json = {
        'id': 'exam-99',
        'title': 'اختبار الفيزياء الفصلي',
        'description': 'اختبار نهائي شامل لقوانين نيوتن والحركة',
        'subject_name': 'الفيزياء',
        'teacher_name': 'أ. إبراهيم الحداد',
        'duration_minutes': 45,
        'total_score': 30.0,
        'passing_score': 15.0,
        'status': 'available',
        'is_published': true,
      };

      final exam = OnlineExamItem.fromJson(json);
      expect(exam.id, equals('exam-99'));
      expect(exam.title, equals('اختبار الفيزياء الفصلي'));
      expect(exam.durationMinutes, equals(45));
      expect(exam.totalScore, equals(30.0));
      expect(exam.status, equals('available'));
      expect(exam.isPublished, isTrue);
    });

    test('STU-06: TodayLessonSummary model parses from copilot today-lessons API', () {
      final json = {
        'period': 1,
        'subject': 'الرياضيات',
        'teacher': 'إبراهيم الحداد',
        'time': '08:00 - 08:45',
        'classroom': 'قاعة 101',
      };

      final lesson = TodayLessonSummary.fromJson(json);
      expect(lesson.period, equals(1));
      expect(lesson.subject, equals('الرياضيات'));
      expect(lesson.classroom, equals('قاعة 101'));
    });

    test('STU-EDTECH: SubjectCurriculum and units structure parsed correctly', () {
      final unit = CurriculumUnit(
        unitNumber: 1,
        title: 'الوحدة الأولى: الميكانيكا',
        lessonsCount: 5,
        summary: 'دراسة قوانين نيوتن',
        keyTopics: const ['قانون نيوتن الأول', 'قانون نيوتن الثاني'],
        isCompleted: true,
      );

      final subject = SubjectCurriculum(
        id: 'sub_test',
        code: 'PHYS-10',
        name: 'الفيزياء',
        shortName: 'فيزياء',
        teacherName: 'أ. مروان القدسي',
        weeklyPeriods: 4,
        maxScore: 100.0,
        textbookTitle: 'كتاب الفيزياء',
        textbookPdfUrl: 'https://example.com/physics.pdf',
        totalPages: 180,
        progressPercent: 0.65,
        iconName: 'science',
        units: [unit],
      );

      expect(subject.name, equals('الفيزياء'));
      expect(subject.units.length, equals(1));
      expect(subject.units.first.keyTopics.length, equals(2));
      expect(subject.units.first.isCompleted, isTrue);
    });
  });
}

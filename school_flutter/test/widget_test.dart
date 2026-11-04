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
  });
}

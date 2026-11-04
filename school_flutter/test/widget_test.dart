import 'package:flutter_test/flutter_test.dart';
import 'package:school_flutter/core/api_service.dart';
import 'package:school_flutter/main.dart';

void main() {
  testWidgets('App renders correctly', (WidgetTester tester) async {
    final api = ApiService();
    await tester.pumpWidget(MadrasatiApp(api: api));
    expect(find.byType(MadrasatiApp), findsOneWidget);
  });
}

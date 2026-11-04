import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'core/api_service.dart';
import 'core/theme.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final api = ApiService();
  await api.initSession();
  runApp(MadrasatiApp(api: api));
}

class MadrasatiApp extends StatelessWidget {
  final ApiService api;
  const MadrasatiApp({super.key, required this.api});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'مدرستي - المنظومة الذكية',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.theme,
      locale: const Locale('ar', 'YE'),
      supportedLocales: const [
        Locale('ar', 'YE'),
        Locale('ar', ''),
        Locale('en', ''),
      ],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: Directionality(
        textDirection: TextDirection.rtl,
        child: AuthGate(api: api),
      ),
    );
  }
}

class AuthGate extends StatelessWidget {
  final ApiService api;
  const AuthGate({super.key, required this.api});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: api,
      builder: (context, _) {
        if (!api.isInitialized) {
          return const Scaffold(
            backgroundColor: AppTheme.background,
            body: Center(
              child: CircularProgressIndicator(
                color: AppTheme.accent,
                strokeWidth: 3,
              ),
            ),
          );
        }

        if (!api.isAuthenticated) {
          return LoginScreen(api: api);
        }

        return HomeScreen(api: api);
      },
    );
  }
}

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  // Vibrant, Lively & Modern Fintech Educational Palette
  static const Color primary = Color(0xFF1E293B); // Deep Slate
  static const Color primaryNavy = Color(0xFF0F172A);
  static const Color accent = Color(0xFF0284C7); // Vibrant Sky Blue
  static const Color jaibRed = Color(0xFFE11D48); // Jaib Vibrant Crimson/Rose
  static const Color rose = Color(0xFFF43F5E); // Vibrant Rose
  static const Color emerald = Color(0xFF10B981); // Vibrant Emerald Green
  static const Color amber = Color(0xFFF59E0B); // Vibrant Gold
  static const Color purple = Color(0xFF8B5CF6); // Vibrant Violet
  static const Color cyan = Color(0xFF06B6D4); // Vibrant Cyan
  static const Color indigo = Color(0xFF6366F1); // Modern Indigo

  // Tokens exact from user screenshot
  static const Color screenshotBlue = Color(0xFF0284C7);
  static const Color screenshotLightBlue = Color(0xFFE0F2FE);
  static const Color screenshotPurple = Color(0xFF7C3AED);
  static const Color screenshotOrange = Color(0xFFEA580C);
  static const Color screenshotGreen = Color(0xFF15803D);
  static const Color screenshotFieldBorder = Color(0xFF0EA5E9);

  static const Color background = Color(0xFFF8FAFC); // Clean crisp backdrop
  static const Color cardSurface = Colors.white;
  static const Color textMain = Color(0xFF0F172A);
  static const Color textMuted = Color(0xFF64748B);
  static const Color borderLight = Color(0xFFE2E8F0);

  // Vibrant Card Gradients
  static const LinearGradient cardGradientBlue = LinearGradient(
    colors: [Color(0xFF0284C7), Color(0xFF1D4ED8)],
    begin: Alignment.topRight,
    end: Alignment.bottomLeft,
  );

  static const LinearGradient cardGradientPurple = LinearGradient(
    colors: [Color(0xFF7C3AED), Color(0xFF4F46E5)],
    begin: Alignment.topRight,
    end: Alignment.bottomLeft,
  );

  static const LinearGradient cardGradientEmerald = LinearGradient(
    colors: [Color(0xFF059669), Color(0xFF0D9488)],
    begin: Alignment.topRight,
    end: Alignment.bottomLeft,
  );

  static const LinearGradient cardGradientTeal = LinearGradient(
    colors: [Color(0xFF0D9488), Color(0xFF0284C7)],
    begin: Alignment.topRight,
    end: Alignment.bottomLeft,
  );

  static const LinearGradient cardGradientSunset = LinearGradient(
    colors: [Color(0xFFF59E0B), Color(0xFFEA580C)],
    begin: Alignment.topRight,
    end: Alignment.bottomLeft,
  );

  static const LinearGradient cardGradientJaib = LinearGradient(
    colors: [Color(0xFFE11D48), Color(0xFFBE123C)],
    begin: Alignment.topRight,
    end: Alignment.bottomLeft,
  );

  static const LinearGradient cardGradientAmber = LinearGradient(
    colors: [Color(0xFFD97706), Color(0xFFEA580C)],
    begin: Alignment.topRight,
    end: Alignment.bottomLeft,
  );

  // Card shadows
  static List<BoxShadow> softShadow = [
    BoxShadow(
      color: const Color(0xFF0F172A).withValues(alpha: 0.04),
      blurRadius: 10,
      offset: const Offset(0, 2),
    ),
  ];

  static List<BoxShadow> cardShadow = [
    BoxShadow(
      color: const Color(0xFF0284C7).withValues(alpha: 0.10),
      blurRadius: 14,
      offset: const Offset(0, 4),
    ),
  ];

  static List<BoxShadow> glowShadow(Color color) => [
    BoxShadow(
      color: color.withValues(alpha: 0.20),
      blurRadius: 12,
      offset: const Offset(0, 3),
    ),
  ];

  static ThemeData get theme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      fontFamily: GoogleFonts.cairo().fontFamily,
      colorScheme: ColorScheme.fromSeed(
        seedColor: screenshotBlue,
        primary: screenshotBlue,
        secondary: screenshotGreen,
        surface: cardSurface,
      ),
      scaffoldBackgroundColor: background,
      appBarTheme: AppBarTheme(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        titleTextStyle: TextStyle(
          color: textMain,
          fontSize: 16,
          fontWeight: FontWeight.w800,
          fontFamily: GoogleFonts.cairo().fontFamily,
        ),
        iconTheme: const IconThemeData(color: textMain, size: 20),
      ),
    );
  }
}

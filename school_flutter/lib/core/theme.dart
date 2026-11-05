import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  // Neumorphic Light & Modern Clean Tokens per user specification
  static const Color primary = Color(0xFF1E60FF); // Modern Vibrant Royal Blue
  static const Color primaryNavy = Color(0xFF1A1D1F); // Clean Dark Charcoal
  static const Color primaryPurple = Color(0xFF6C5CE7); // Modern Clean Violet
  static const Color accent = Color(0xFF1E60FF); // Vibrant Blue
  static const Color jaibRed = Color(0xFFE11D48);
  static const Color rose = Color(0xFFF43F5E);
  static const Color emerald = Color(0xFF10B981);
  static const Color amber = Color(0xFFF59E0B);
  static const Color purple = Color(0xFF6C5CE7);
  static const Color cyan = Color(0xFF06B6D4);
  static const Color indigo = Color(0xFF6366F1);

  // Tokens exact from user specification
  static const Color screenshotBlue = Color(0xFF1E60FF);
  static const Color screenshotLightBlue = Color(0xFFEFF6FF);
  static const Color screenshotPurple = Color(0xFF6C5CE7);
  static const Color screenshotOrange = Color(0xFFEA580C);
  static const Color screenshotGreen = Color(0xFF10B981);
  static const Color screenshotFieldBorder = Color(0xFF3B82F6);

  static const Color background = Colors.white; // Pure white as user requested
  static const Color cardSurface = Colors.white;
  static const Color textMain = Color(0xFF111111); // Clean dark ink (Altakhfid style)
  static const Color textMuted = Color(0xFF777777); // Balanced muted slate (Altakhfid style)
  static const Color borderLight = Color(0xFFE7E7E7);

  // Vibrant Card Gradients
  static const LinearGradient cardGradientBlue = LinearGradient(
    colors: [Color(0xFF1E60FF), Color(0xFF3B82F6)],
    begin: Alignment.topRight,
    end: Alignment.bottomLeft,
  );

  static const LinearGradient cardGradientPurple = LinearGradient(
    colors: [Color(0xFF6C5CE7), Color(0xFF8B5CF6)],
    begin: Alignment.topRight,
    end: Alignment.bottomLeft,
  );

  static const LinearGradient cardGradientEmerald = LinearGradient(
    colors: [Color(0xFF059669), Color(0xFF10B981)],
    begin: Alignment.topRight,
    end: Alignment.bottomLeft,
  );

  static const LinearGradient cardGradientTeal = LinearGradient(
    colors: [Color(0xFF0D9488), Color(0xFF1E60FF)],
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

  // Neumorphic-Light Shadows matching rule 2:
  // boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 15, offset: Offset(0, 5))]
  static List<BoxShadow> softShadow = [
    BoxShadow(
      color: Colors.black.withValues(alpha: 0.04),
      blurRadius: 15,
      offset: const Offset(0, 5),
    ),
  ];

  static List<BoxShadow> cardShadow = [
    BoxShadow(
      color: const Color(0xFF1E60FF).withValues(alpha: 0.08),
      blurRadius: 15,
      offset: const Offset(0, 5),
    ),
  ];

  static List<BoxShadow> glowShadow(Color color) => [
    BoxShadow(
      color: color.withValues(alpha: 0.18),
      blurRadius: 14,
      offset: const Offset(0, 4),
    ),
  ];

  static BoxDecoration neumorphicDecoration({
    Color color = Colors.white,
    double radius = 18.0,
    Border? border,
  }) {
    return BoxDecoration(
      color: color,
      borderRadius: BorderRadius.circular(radius),
      border: border,
      boxShadow: softShadow,
    );
  }

  static ThemeData get theme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      fontFamily: GoogleFonts.cairo().fontFamily,
      colorScheme: ColorScheme.fromSeed(
        seedColor: primary,
        primary: primary,
        secondary: emerald,
        surface: cardSurface,
      ),
      scaffoldBackgroundColor: Colors.white,
      appBarTheme: AppBarTheme(
        backgroundColor: Colors.white,
        elevation: 0,
        centerTitle: true,
        titleTextStyle: TextStyle(
          color: textMain,
          fontSize: 15,
          fontWeight: FontWeight.w800,
          fontFamily: GoogleFonts.cairo().fontFamily,
        ),
        iconTheme: const IconThemeData(color: textMain, size: 20),
      ),
    );
  }
}

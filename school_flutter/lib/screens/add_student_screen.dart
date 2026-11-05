import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/api_service.dart';
import '../core/theme.dart';

class AddStudentScreen extends StatefulWidget {
  final ApiService api;
  const AddStudentScreen({super.key, required this.api});

  @override
  State<AddStudentScreen> createState() => _AddStudentScreenState();
}

class _AddStudentScreenState extends State<AddStudentScreen> {
  final _schoolCodeController = TextEditingController(text: '1234');
  final _studentCodeController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _obscurePassword = true;
  bool _isSubmitting = false;

  @override
  void dispose() {
    _schoolCodeController.dispose();
    _studentCodeController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _handleAddStudent() async {
    final code = _studentCodeController.text.trim();
    if (code.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Ø§Ù„Ø±Ø¬Ø§Ø¡ Ø¥Ø¯Ø®Ø§Ù„ ÙƒÙˆØ¯ Ø§Ù„Ø·Ø§Ù„Ø¨ Ø£ÙˆÙ„Ø§Ù‹', style: GoogleFonts.tajawal(fontSize: 13, fontWeight: FontWeight.bold)),
          backgroundColor: const Color(0xFFE11D48),
        ),
      );
      return;
    }

    setState(() => _isSubmitting = true);

    final result = await widget.api.linkStudent(
      schoolCode: _schoolCodeController.text.trim(),
      studentCode: code,
      password: _passwordController.text.trim(),
    );

    if (!mounted) return;
    setState(() => _isSubmitting = false);

    if (result['success'] == true) {
      _studentCodeController.clear();
      _passwordController.clear();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            result['message'] ?? 'ØªÙ… Ø§Ù„ØªØ­Ù‚Ù‚ Ù…Ù† Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ø·Ø§Ù„Ø¨ ÙÙŠ Ø§Ù„Ø®Ø§Ø¯Ù… ÙˆØ±Ø¨Ø·Ù‡ Ø¨Ù†Ø¬Ø§Ø­!',
            style: GoogleFonts.tajawal(fontSize: 13, fontWeight: FontWeight.bold),
          ),
          backgroundColor: const Color(0xFF15803D),
          duration: const Duration(seconds: 3),
        ),
      );
      Navigator.pop(context, true);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(result['message'] ?? 'ÙØ´Ù„ Ø§Ù„ØªØ­Ù‚Ù‚ Ù…Ù† ÙƒÙˆØ¯ Ø§Ù„Ø·Ø§Ù„Ø¨ ÙÙŠ Ø§Ù„Ø®Ø§Ø¯Ù…', style: GoogleFonts.tajawal(fontSize: 13)),
          backgroundColor: const Color(0xFFE11D48),
        ),
      );
    }
  }

  void _simulateQrScan() {
    setState(() {
      _schoolCodeController.text = '1234';
      _studentCodeController.text = 'STD-2026-009';
      _passwordController.text = 'School@123456';
    });
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('ØªÙ… Ù…Ø³Ø­ ÙƒÙˆØ¯ QR ÙˆÙ‚Ø±Ø§Ø¡Ø© Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ø·Ø§Ù„Ø¨ Ø¨Ù†Ø¬Ø§Ø­!', style: GoogleFonts.tajawal()),
        backgroundColor: const Color(0xFF7C3AED),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final currentSchool = widget.api.activeSchoolName.isNotEmpty
        ? widget.api.activeSchoolName
        : 'Ø§Ù„Ù…Ø¯Ø±Ø³Ø© Ø§Ù„Ø§ÙØªØ±Ø§Ø¶ÙŠØ©';
    final currentCode = widget.api.activeSchoolCode.isNotEmpty
        ? widget.api.activeSchoolCode
        : '1234';

    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        centerTitle: true,
        title: Text(
          'Ø¥Ø¶Ø§ÙØ© ÙˆØ±Ø¨Ø· Ø·Ø§Ù„Ø¨ Ø¬Ø¯ÙŠØ¯',
          style: GoogleFonts.tajawal(fontSize: 16, fontWeight: FontWeight.w900, color: const Color(0xFF0F172A)),
        ),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18, color: Color(0xFF0F172A)),
          onPressed: () => Navigator.pop(context),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.qr_code_scanner_rounded, size: 22, color: Color(0xFF0F172A)),
            onPressed: _simulateQrScan,
            tooltip: 'Ù…Ø³Ø­ ÙƒÙˆØ¯ QR',
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        physics: const BouncingScrollPhysics(),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Card 1: "Ø§Ù„Ù…Ø¯Ø±Ø³Ø©"
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: const Color(0xFFE2E8F0)),
                boxShadow: AppTheme.softShadow,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: const Color(0xFF0284C7).withValues(alpha: 0.1),
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(Icons.account_balance_rounded, color: Color(0xFF0284C7), size: 20),
                      ),
                      const SizedBox(width: 10),
                      Text(
                        'Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ù…Ø¯Ø±Ø³Ø© Ø§Ù„Ù…Ø¹ØªÙ…Ø¯Ø©',
                        style: GoogleFonts.tajawal(fontSize: 14, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF8FAFC),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: const Color(0xFFCBD5E1)),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(currentSchool, style: GoogleFonts.tajawal(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A))),
                            Text('ÙƒÙˆØ¯ Ø§Ù„Ù…Ø¯Ø±Ø³Ø©: $currentCode', style: GoogleFonts.tajawal(fontSize: 11, color: const Color(0xFF64748B))),
                          ],
                        ),
                        const Icon(Icons.verified_rounded, color: Color(0xFF15803D), size: 20),
                      ],
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 16),

            // Card 2: "Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ø·Ø§Ù„Ø¨ Ù„Ù„Ø¯Ø®ÙˆÙ„"
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: const Color(0xFFE2E8F0)),
                boxShadow: AppTheme.softShadow,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(8),
                            decoration: BoxDecoration(
                              color: const Color(0xFF15803D).withValues(alpha: 0.1),
                              shape: BoxShape.circle,
                            ),
                            child: const Icon(Icons.badge_rounded, color: Color(0xFF15803D), size: 20),
                          ),
                          const SizedBox(width: 10),
                          Text(
                            'ÙƒÙˆØ¯ ÙˆÙƒÙ„Ù…Ø© Ù…Ø±ÙˆØ± Ø§Ù„Ø·Ø§Ù„Ø¨',
                            style: GoogleFonts.tajawal(fontSize: 14, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                          ),
                        ],
                      ),
                      TextButton.icon(
                        onPressed: _simulateQrScan,
                        icon: const Icon(Icons.qr_code_scanner_rounded, size: 16),
                        label: Text('Ù…Ø³Ø­ QR', style: GoogleFonts.tajawal(fontSize: 11, fontWeight: FontWeight.bold)),
                        style: TextButton.styleFrom(
                          foregroundColor: const Color(0xFF0284C7),
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 14),

                  // Input 1: ÙƒÙˆØ¯ Ø§Ù„Ø·Ø§Ù„Ø¨
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: const Color(0xFFCBD5E1)),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.person_outline_rounded, color: Color(0xFF475569), size: 22),
                        const SizedBox(width: 10),
                        Expanded(
                          child: TextField(
                            controller: _studentCodeController,
                            textAlign: TextAlign.right,
                            style: GoogleFonts.tajawal(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                            decoration: InputDecoration(
                              hintText: 'ÙƒÙˆØ¯ Ø§Ù„Ø·Ø§Ù„Ø¨ (Ù…Ø«Ø§Ù„: STD-2026-009)',
                              hintStyle: GoogleFonts.tajawal(fontSize: 13, color: const Color(0xFF94A3B8)),
                              border: InputBorder.none,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 12),

                  // Input 2: ÙƒÙ„Ù…Ø© Ø§Ù„Ù…Ø±ÙˆØ±
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: const Color(0xFFCBD5E1)),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.lock_outline_rounded, color: Color(0xFF475569), size: 22),
                        const SizedBox(width: 10),
                        Expanded(
                          child: TextField(
                            controller: _passwordController,
                            obscureText: _obscurePassword,
                            textAlign: TextAlign.right,
                            style: GoogleFonts.tajawal(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                            decoration: InputDecoration(
                              hintText: 'ÙƒÙ„Ù…Ø© Ù…Ø±ÙˆØ± Ø§Ù„Ø·Ø§Ù„Ø¨',
                              hintStyle: GoogleFonts.tajawal(fontSize: 13, color: const Color(0xFF94A3B8)),
                              border: InputBorder.none,
                            ),
                          ),
                        ),
                        IconButton(
                          icon: Icon(
                            _obscurePassword ? Icons.visibility_off_outlined : Icons.visibility_outlined,
                            size: 18,
                            color: const Color(0xFF94A3B8),
                          ),
                          onPressed: () => setState(() => _obscurePassword = !_obscurePassword),
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 18),

                  // Submit Button
                  SizedBox(
                    width: double.infinity,
                    height: 48,
                    child: ElevatedButton(
                      onPressed: _isSubmitting ? null : _handleAddStudent,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF15803D),
                        foregroundColor: Colors.white,
                        elevation: 0,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      child: _isSubmitting
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                            )
                          : Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                const Icon(Icons.person_add_alt_1_rounded, size: 20),
                                const SizedBox(width: 8),
                                Text(
                                  '+ Ø¥Ø¶Ø§ÙØ© ÙˆØ±Ø¨Ø· Ø§Ù„Ø·Ø§Ù„Ø¨ Ø§Ù„Ø¢Ù†',
                                  style: GoogleFonts.tajawal(fontSize: 15, fontWeight: FontWeight.bold),
                                ),
                              ],
                            ),
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 16),

            // Security strip
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFEFF6FF),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFBFDBFE)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.verified_user_rounded, color: Color(0xFF0284C7), size: 20),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Ù†Ø¸Ø§Ù… Ø£Ù…Ø§Ù† Ø§Ù„Ø­Ø³Ø§Ø¨ Ø§Ù„Ù…Ø¯Ø±Ø³ÙŠ: ÙŠØªÙ… ØªÙˆØ«ÙŠÙ‚ Ø¬Ù‡Ø§Ø²Ùƒ ÙˆØ§Ø¹ØªÙ…Ø§Ø¯Ù‡ ÙÙˆØ±ÙŠØ§Ù‹ Ù„Ù„ÙˆØµÙˆÙ„ Ø§Ù„Ø¢Ù…Ù† Ù„Ø­Ø³Ø§Ø¨ Ø§Ù„Ø·Ø§Ù„Ø¨.',
                      style: GoogleFonts.tajawal(fontSize: 11, color: const Color(0xFF0284C7), fontWeight: FontWeight.bold),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}


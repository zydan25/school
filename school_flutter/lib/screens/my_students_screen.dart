import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/api_service.dart';
import '../core/theme.dart';
import 'add_student_screen.dart';

class MyStudentsScreen extends StatefulWidget {
  final ApiService api;
  const MyStudentsScreen({super.key, required this.api});

  @override
  State<MyStudentsScreen> createState() => _MyStudentsScreenState();
}

class _MyStudentsScreenState extends State<MyStudentsScreen> {
  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.api,
      builder: (context, _) {
        final students = widget.api.students;
        final selectedIndex = widget.api.selectedStudentIndex;

        return Scaffold(
          backgroundColor: const Color(0xFFF8FAFC),
          appBar: AppBar(
            backgroundColor: Colors.white,
            elevation: 0,
            centerTitle: true,
            title: Text(
              'Ø·Ù„Ø§Ø¨ÙŠ ÙˆØ§Ù„Ø­Ø³Ø§Ø¨Ø§Øª Ø§Ù„Ù…Ø¶Ø§ÙØ©',
              style: GoogleFonts.cairo(fontSize: 16, fontWeight: FontWeight.w900, color: const Color(0xFF0F172A)),
            ),
            leading: IconButton(
              icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18, color: Color(0xFF0F172A)),
              onPressed: () => Navigator.pop(context),
            ),
            actions: [
              IconButton(
                icon: const Icon(Icons.person_add_rounded, size: 22, color: Color(0xFF0284C7)),
                tooltip: 'Ø¥Ø¶Ø§ÙØ© Ø·Ø§Ù„Ø¨ Ø¬Ø¯ÙŠØ¯',
                onPressed: () async {
                  final added = await Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => AddStudentScreen(api: widget.api)),
                  );
                  if (added == true && mounted) {
                    setState(() {});
                  }
                },
              ),
            ],
          ),
          body: ListView(
            padding: const EdgeInsets.all(16),
            physics: const BouncingScrollPhysics(),
            children: [
              // 1. Prominent Add Student Banner
              InkWell(
                onTap: () async {
                  final added = await Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => AddStudentScreen(api: widget.api)),
                  );
                  if (added == true && mounted) {
                    setState(() {});
                  }
                },
                borderRadius: BorderRadius.circular(16),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFFEFF6FF), Color(0xFFDBEAFE)],
                      begin: Alignment.centerRight,
                      end: Alignment.centerLeft,
                    ),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: const Color(0xFFBFDBFE)),
                    boxShadow: [
                      BoxShadow(
                        color: const Color(0xFF0284C7).withValues(alpha: 0.08),
                        blurRadius: 10,
                        offset: const Offset(0, 3),
                      ),
                    ],
                  ),
                  child: Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: const BoxDecoration(
                          color: Color(0xFF0284C7),
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(Icons.person_add_alt_1_rounded, color: Colors.white, size: 20),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '+ Ø¥Ø¶Ø§ÙØ© ÙˆØ±Ø¨Ø· Ø·Ø§Ù„Ø¨ Ø¬Ø¯ÙŠØ¯',
                              style: GoogleFonts.cairo(fontSize: 14, fontWeight: FontWeight.bold, color: const Color(0xFF0369A1)),
                            ),
                            Text(
                              'Ø£Ø¯Ø®Ù„ ÙƒÙˆØ¯ Ø§Ù„Ø·Ø§Ù„Ø¨ ÙˆÙƒÙ„Ù…Ø© Ø§Ù„Ù…Ø±ÙˆØ± Ù„Ø±Ø¨Ø· Ø­Ø³Ø§Ø¨Ù‡ Ø¨Ø§Ù„Ù…ØªØ§Ø¨Ø¹Ø©',
                              style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF0284C7)),
                            ),
                          ],
                        ),
                      ),
                      const Icon(Icons.arrow_forward_ios_rounded, size: 14, color: Color(0xFF0284C7)),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 20),

              // 2. Section Header
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Ù‚Ø§Ø¦Ù…Ø© Ø§Ù„Ø·Ù„Ø§Ø¨ Ø§Ù„Ù…Ø±ØªØ¨Ø·ÙŠÙ† (${students.length})',
                    style: GoogleFonts.cairo(fontSize: 14, fontWeight: FontWeight.w900, color: const Color(0xFF0F172A)),
                  ),
                  Text(
                    'Ø§Ù†Ù‚Ø± Ø¹Ù„Ù‰ Ø§Ù„Ø·Ø§Ù„Ø¨ Ù„Ù„Ø§Ù†ØªÙ‚Ø§Ù„ ÙÙˆØ±Ø§Ù‹ Ù„Ù„Ø±Ø¦ÙŠØ³ÙŠØ© â‡¦',
                    style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF64748B), fontWeight: FontWeight.w600),
                  ),
                ],
              ),

              const SizedBox(height: 12),

              // 3. High-End Interactive Student Cards
              ...students.asMap().entries.map((entry) {
                final index = entry.key;
                final student = entry.value;
                final isSelected = selectedIndex == index;

                return Material(
                  color: Colors.transparent,
                  child: InkWell(
                    onTap: () {
                      widget.api.selectStudent(index);
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text(
                            'ØªÙ… ØªÙØ¹ÙŠÙ„ Ø§Ù„Ø·Ø§Ù„Ø¨: ${student.fullName} ÙˆØ§Ù„Ø§Ù†ØªÙ‚Ø§Ù„ Ù„Ù„Ø±Ø¦ÙŠØ³ÙŠØ© âœ“',
                            style: GoogleFonts.cairo(fontWeight: FontWeight.bold),
                          ),
                          backgroundColor: const Color(0xFF15803D),
                          duration: const Duration(seconds: 2),
                        ),
                      );
                      Navigator.pop(context, student);
                    },
                    borderRadius: BorderRadius.circular(16),
                    child: Container(
                      margin: const EdgeInsets.only(bottom: 12),
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(
                          color: isSelected ? const Color(0xFF0284C7) : const Color(0xFFE2E8F0),
                          width: isSelected ? 2.0 : 1.0,
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: isSelected ? const Color(0xFF0284C7).withValues(alpha: 0.12) : Colors.black.withValues(alpha: 0.03),
                            blurRadius: 10,
                            offset: const Offset(0, 3),
                          ),
                        ],
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Stack(
                                clipBehavior: Clip.none,
                                children: [
                                  ClipRRect(
                                    borderRadius: BorderRadius.circular(14),
                                    child: Image.network(
                                      student.avatarUrl,
                                      width: 48,
                                      height: 48,
                                      fit: BoxFit.cover,
                                      errorBuilder: (_, __, ___) => Container(
                                        width: 48,
                                        height: 48,
                                        color: const Color(0xFF0284C7).withValues(alpha: 0.1),
                                        child: const Icon(Icons.school, color: Color(0xFF0284C7)),
                                      ),
                                    ),
                                  ),
                                  if (isSelected)
                                    Positioned(
                                      bottom: -2,
                                      right: -2,
                                      child: Container(
                                        width: 14,
                                        height: 14,
                                        decoration: BoxDecoration(
                                          color: const Color(0xFF15803D),
                                          shape: BoxShape.circle,
                                          border: Border.all(color: Colors.white, width: 2),
                                        ),
                                      ),
                                    ),
                                ],
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Row(
                                      children: [
                                        Flexible(
                                          child: Text(
                                            student.fullName,
                                            maxLines: 1,
                                            overflow: TextOverflow.ellipsis,
                                            style: GoogleFonts.cairo(
                                              fontSize: 14.5,
                                              fontWeight: FontWeight.w900,
                                              color: const Color(0xFF0F172A),
                                            ),
                                          ),
                                        ),
                                        if (isSelected) ...[
                                          const SizedBox(width: 6),
                                          Container(
                                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1.5),
                                            decoration: BoxDecoration(
                                              color: const Color(0xFFDCFCE7),
                                              borderRadius: BorderRadius.circular(6),
                                              border: Border.all(color: const Color(0xFF86EFAC)),
                                            ),
                                            child: Text(
                                              'Ø§Ù„Ù†Ø´Ø· Ø­Ø§Ù„ÙŠØ§Ù‹',
                                              style: GoogleFonts.cairo(fontSize: 9.5, fontWeight: FontWeight.bold, color: const Color(0xFF15803D)),
                                            ),
                                          ),
                                        ],
                                      ],
                                    ),
                                    Text(
                                      '${student.grade} â€¢ ${student.section} â€¢ ÙƒÙˆØ¯ ${student.studentNumber}',
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF64748B), fontWeight: FontWeight.w600),
                                    ),
                                  ],
                                ),
                              ),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                decoration: BoxDecoration(
                                  color: isSelected ? const Color(0xFF0284C7) : const Color(0xFFF1F5F9),
                                  borderRadius: BorderRadius.circular(10),
                                ),
                                child: Text(
                                  isSelected ? 'Ù…Ø­Ø¯Ø¯ âœ“' : 'ØªÙØ¹ÙŠÙ„',
                                  style: GoogleFonts.cairo(
                                    fontSize: 11,
                                    fontWeight: FontWeight.bold,
                                    color: isSelected ? Colors.white : const Color(0xFF475569),
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 10),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                            decoration: BoxDecoration(
                              color: const Color(0xFFF8FAFC),
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text('Ù†Ø³Ø¨Ø© Ø§Ù„Ø­Ø¶ÙˆØ±: ${student.attendanceRate}%', style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF15803D), fontWeight: FontWeight.bold)),
                                Text('Ø§Ù„Ù…Ø¹Ø¯Ù„: ${student.gpa}%', style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF0284C7), fontWeight: FontWeight.bold)),
                                Text('ØªØ¨Ø¯ÙŠÙ„ Ù„Ù„Ø±Ø¦ÙŠØ³ÙŠØ© â‡¦', style: GoogleFonts.cairo(fontSize: 10, color: const Color(0xFF0284C7), fontWeight: FontWeight.bold)),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                );
              }),

              const SizedBox(height: 16),

              // 4. Linked Devices & Security Card
              Container(
                padding: const EdgeInsets.all(16),
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
                            color: const Color(0xFF15803D).withValues(alpha: 0.1),
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(Icons.phonelink_lock_rounded, color: Color(0xFF15803D), size: 18),
                        ),
                        const SizedBox(width: 10),
                        Text(
                          'Ø§Ù„Ø£Ø¬Ù‡Ø²Ø© Ø§Ù„Ù…Ø¹ØªÙ…Ø¯Ø© ÙˆØ§Ù„Ù…ÙˆØ«Ù‚Ø©',
                          style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF0FDF4),
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: const Color(0xFFBBF7D0)),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.check_circle_rounded, color: Color(0xFF15803D), size: 16),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              'Ø¬Ù‡Ø§Ø²Ùƒ Ø§Ù„Ø­Ø§Ù„ÙŠ (Android Client) Ù…Ø¤ÙƒØ¯ ÙˆÙ…Ø¹ØªÙ…Ø¯ Ø±Ø³Ù…ÙŠØ§Ù‹.',
                              style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF166534), fontWeight: FontWeight.bold),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}


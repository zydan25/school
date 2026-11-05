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
              'طلابي والحسابات المضافة',
              style: GoogleFonts.cairo(fontSize: 16, fontWeight: FontWeight.w900, color: const Color(0xFF0F172A)),
            ),
            leading: IconButton(
              icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18, color: Color(0xFF0F172A)),
              onPressed: () => Navigator.pop(context),
            ),
            actions: [
              IconButton(
                icon: const Icon(Icons.person_add_rounded, size: 22, color: Color(0xFF0284C7)),
                tooltip: 'إضافة طالب جديد',
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
                              '+ إضافة وربط طالب جديد',
                              style: GoogleFonts.cairo(fontSize: 14, fontWeight: FontWeight.bold, color: const Color(0xFF0369A1)),
                            ),
                            Text(
                              'أدخل كود الطالب وكلمة المرور لربط حسابه بالمتابعة',
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
                    'قائمة الطلاب المرتبطين (${students.length})',
                    style: GoogleFonts.cairo(fontSize: 14, fontWeight: FontWeight.w900, color: const Color(0xFF0F172A)),
                  ),
                  Text(
                    'انقر على الطالب للانتقال فوراً للرئيسية ⇦',
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
                            'تم تفعيل الطالب: ${student.fullName} والانتقال للرئيسية ✓',
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
                                              'النشط حالياً',
                                              style: GoogleFonts.cairo(fontSize: 9.5, fontWeight: FontWeight.bold, color: const Color(0xFF15803D)),
                                            ),
                                          ),
                                        ],
                                      ],
                                    ),
                                    Text(
                                      '${student.grade} • ${student.section} • كود ${student.studentNumber}',
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
                                  isSelected ? 'محدد ✓' : 'تفعيل',
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
                                Text('نسبة الحضور: ${student.attendanceRate}%', style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF15803D), fontWeight: FontWeight.bold)),
                                Text('المعدل: ${student.gpa}%', style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF0284C7), fontWeight: FontWeight.bold)),
                                Text('تبديل للرئيسية ⇦', style: GoogleFonts.cairo(fontSize: 10, color: const Color(0xFF0284C7), fontWeight: FontWeight.bold)),
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
                          'الأجهزة المعتمدة والموثقة',
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
                              'جهازك الحالي (Android Client) مؤكد ومعتمد رسمياً.',
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

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/api_service.dart';
import '../core/models.dart';
import '../core/theme.dart';
import 'homework_screen.dart';
import 'grades_screen.dart';
import 'timetable_screen.dart';
import 'attendance_screen.dart';
import 'finance_screen.dart';
import 'chat_screen.dart';
import 'notices_screen.dart';
import 'services_screen.dart';
import 'login_screen.dart';
import 'manage_students_screen.dart';
import 'subjects_screen.dart';
import 'teacher_dashboard_screen.dart';

class HomeScreen extends StatefulWidget {
  final ApiService api;
  const HomeScreen({super.key, required this.api});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late PageController _pageController;

  @override
  void initState() {
    super.initState();
    _pageController = PageController(
      initialPage: widget.api.selectedStudentIndex,
      viewportFraction: 0.90,
    );
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.api,
      builder: (context, _) {
        final currentStudent = widget.api.currentStudent;

        return Scaffold(
          backgroundColor: const Color(0xFFF8FAFC),
          floatingActionButton: FloatingActionButton.extended(
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => ChatScreen(api: widget.api)),
            ),
            backgroundColor: const Color(0xFF0F172A),
            elevation: 4,
            icon: const Icon(Icons.auto_awesome_rounded, color: Colors.amber, size: 20),
            label: Text(
              'المساعد الذكي (Gemini 3.5)',
              style: GoogleFonts.cairo(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold),
            ),
          ),
          body: SafeArea(
            child: CustomScrollView(
              physics: const BouncingScrollPhysics(),
              slivers: [
                // 1. Sleek Top Header Bar with QR scanner and Settings (matching screenshot)
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(16, 12, 16, 6),
                    child: _buildHeader(context),
                  ),
                ),

                // 2. Student Cards Carousel (NO "بطاقة الطالب النشط" text as requested)
                SliverToBoxAdapter(
                  child: Column(
                    children: [
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 4),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              'الأبناء المسجلون (${widget.api.selectedStudentIndex + 1}/${widget.api.students.length})',
                              style: GoogleFonts.cairo(
                                fontSize: 12,
                                fontWeight: FontWeight.bold,
                                color: const Color(0xFF334155),
                              ),
                            ),
                            InkWell(
                              onTap: () => Navigator.push(
                                context,
                                MaterialPageRoute(builder: (_) => ManageStudentsScreen(api: widget.api)),
                              ),
                              child: Row(
                                children: [
                                  const Icon(Icons.person_add_alt_1_rounded, size: 14, color: AppTheme.screenshotBlue),
                                  const SizedBox(width: 4),
                                  Text(
                                    '+ إضافة طالب',
                                    style: GoogleFonts.cairo(
                                      fontSize: 11,
                                      fontWeight: FontWeight.bold,
                                      color: AppTheme.screenshotBlue,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 4),
                      SizedBox(
                        height: 154, // Clear white card height
                        child: PageView.builder(
                          controller: _pageController,
                          itemCount: widget.api.students.length,
                          onPageChanged: (index) {
                            widget.api.selectStudent(index);
                          },
                          itemBuilder: (context, index) {
                            final student = widget.api.students[index];
                            final isSelected = widget.api.selectedStudentIndex == index;
                            return _buildCompactStudentCard(student, isSelected, index);
                          },
                        ),
                      ),
                      const SizedBox(height: 6),
                      // Carousel Indicator Dots
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: List.generate(
                          widget.api.students.length,
                          (index) => AnimatedContainer(
                            duration: const Duration(milliseconds: 250),
                            margin: const EdgeInsets.symmetric(horizontal: 3),
                            width: widget.api.selectedStudentIndex == index ? 16 : 5,
                            height: 4,
                            decoration: BoxDecoration(
                              color: widget.api.selectedStudentIndex == index
                                  ? AppTheme.screenshotBlue
                                  : const Color(0xFFCBD5E1),
                              borderRadius: BorderRadius.circular(4),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),

                const SliverToBoxAdapter(child: SizedBox(height: 10)),

                // 3. Compact Next Period Notice Strip
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: _buildCompactNoticeStrip(),
                  ),
                ),

                const SliverToBoxAdapter(child: SizedBox(height: 14)),

                // 4. Section Title
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 18),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'القوائم والخدمات المدرسية',
                          style: GoogleFonts.cairo(
                            fontSize: 14,
                            fontWeight: FontWeight.bold,
                            color: const Color(0xFF0F172A),
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: AppTheme.screenshotBlue.withValues(alpha: 0.08),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            currentStudent.fullName,
                            style: GoogleFonts.cairo(
                              fontSize: 11,
                              fontWeight: FontWeight.bold,
                              color: AppTheme.screenshotBlue,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),

                const SliverToBoxAdapter(child: SizedBox(height: 8)),

                // 5. 3-Column Compact Grid (All services + Manage Students & Teacher Dashboard)
                SliverPadding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  sliver: SliverGrid(
                    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 3,
                      mainAxisSpacing: 10,
                      crossAxisSpacing: 10,
                      childAspectRatio: 0.95, // Compact proportional cards
                    ),
                    delegate: SliverChildListDelegate([
                      _buildGridServiceCard(
                        title: 'المواد والمناهج',
                        icon: Icons.menu_book_rounded,
                        bgColor: const Color(0xFFEFF6FF), // Soft Blue
                        iconColor: const Color(0xFF2563EB),
                        badgeText: 'PDF 📚',
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => SubjectsScreen(api: widget.api))),
                      ),
                      _buildGridServiceCard(
                        title: 'الواجبات',
                        icon: Icons.menu_book_rounded,
                        bgColor: const Color(0xFFEFF6FF), // Soft Blue
                        iconColor: const Color(0xFF2563EB),
                        badgeCount: 1,
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => HomeworkScreen(api: widget.api))),
                      ),
                      _buildGridServiceCard(
                        title: 'النتائج والدرجات',
                        icon: Icons.workspace_premium_rounded,
                        bgColor: const Color(0xFFECFDF5), // Soft Emerald
                        iconColor: const Color(0xFF059669),
                        badgeText: '95%',
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => GradesScreen(api: widget.api))),
                      ),
                      _buildGridServiceCard(
                        title: 'جدول الحصص',
                        icon: Icons.calendar_month_rounded,
                        bgColor: const Color(0xFFF5F3FF), // Soft Purple
                        iconColor: const Color(0xFF7C3AED),
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => TimetableScreen(api: widget.api))),
                      ),
                      _buildGridServiceCard(
                        title: 'سجل الحضور',
                        icon: Icons.check_circle_outline_rounded,
                        bgColor: const Color(0xFFF0FDF4), // Soft Mint
                        iconColor: const Color(0xFF16A34A),
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => AttendanceScreen(api: widget.api))),
                      ),
                      _buildGridServiceCard(
                        title: 'الرسوم والأقساط',
                        icon: Icons.account_balance_wallet_rounded,
                        bgColor: const Color(0xFFFFFBEB), // Soft Amber
                        iconColor: const Color(0xFFD97706),
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => FinanceScreen(api: widget.api))),
                      ),
                      _buildGridServiceCard(
                        title: 'المحادثات والذكاء',
                        icon: Icons.forum_rounded,
                        bgColor: const Color(0xFFFDF2F8), // Soft Pink
                        iconColor: const Color(0xFFDB2777),
                        badgeText: 'AI 💬',
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => ChatScreen(api: widget.api))),
                      ),
                      // NEW: إدارة الطلاب والأجهزة (Matching user screenshot)
                      _buildGridServiceCard(
                        title: 'إدارة الطلاب والأجهزة',
                        icon: Icons.school_rounded,
                        bgColor: const Color(0xFFE0F2FE), // Screenshot light blue
                        iconColor: AppTheme.screenshotBlue,
                        badgeText: 'مؤكد ✅',
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => ManageStudentsScreen(api: widget.api))),
                      ),
                      // NEW: لوحة المعلم (Teacher Grade Sheet & Homework Submissions)
                      _buildGridServiceCard(
                        title: 'لوحة المعلم',
                        icon: Icons.assignment_turned_in_rounded,
                        bgColor: const Color(0xFFF0FDF4),
                        iconColor: AppTheme.screenshotGreen,
                        badgeText: 'رصد 📝',
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => TeacherDashboardScreen(api: widget.api))),
                      ),
                      _buildGridServiceCard(
                        title: 'التعاميم والأخبار',
                        icon: Icons.campaign_rounded,
                        bgColor: const Color(0xFFFFF7ED), // Soft Orange
                        iconColor: const Color(0xFFEA580C),
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => NoticesScreen(api: widget.api))),
                      ),
                      _buildGridServiceCard(
                        title: 'الخدمات المدرسية',
                        icon: Icons.directions_bus_filled_rounded,
                        bgColor: const Color(0xFFF0F9FF), // Soft Sky
                        iconColor: const Color(0xFF0284C7),
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => ServicesScreen(api: widget.api))),
                      ),
                      _buildGridServiceCard(
                        title: 'تبديل الحساب',
                        icon: Icons.switch_account_rounded,
                        bgColor: const Color(0xFFF1F5F9), // Soft Slate
                        iconColor: const Color(0xFF475569),
                        onTap: () => Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => LoginScreen(api: widget.api))),
                      ),
                    ]),
                  ),
                ),

                const SliverToBoxAdapter(child: SizedBox(height: 24)),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        // 1. RIGHT SIDE in RTL: School circular badge + User Name + Role + School Code
        Row(
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: const BoxDecoration(
                color: AppTheme.screenshotLightBlue,
                shape: BoxShape.circle,
              ),
              child: const Center(
                child: Icon(
                  Icons.school_rounded,
                  color: AppTheme.screenshotBlue,
                  size: 24,
                ),
              ),
            ),
            const SizedBox(width: 10),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      widget.api.currentUserName,
                      style: GoogleFonts.cairo(
                        fontSize: 15,
                        fontWeight: FontWeight.w900,
                        color: const Color(0xFF0F172A),
                      ),
                    ),
                    const SizedBox(width: 8),
                    InkWell(
                      onTap: () => _showRoleSwitcherDialog(context),
                      borderRadius: BorderRadius.circular(6),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: AppTheme.screenshotGreen.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text(
                              widget.api.currentRole == 'guardian'
                                  ? 'ولي أمر'
                                  : (widget.api.currentRole == 'student' ? 'طالب' : 'معلم'),
                              style: GoogleFonts.cairo(
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                                color: AppTheme.screenshotGreen,
                              ),
                            ),
                            const SizedBox(width: 2),
                            const Icon(Icons.arrow_drop_down_rounded, size: 14, color: AppTheme.screenshotGreen),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
                Text(
                  'المدرسة الافتراضية (كود: 1234)',
                  style: GoogleFonts.cairo(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: const Color(0xFF64748B),
                  ),
                ),
              ],
            ),
          ],
        ),

        // 2. LEFT SIDE in RTL: Action Icons (QR / Add Student, Switch Workspace, Notifications)
        Row(
          children: [
            IconButton(
              icon: const Icon(Icons.qr_code_scanner_rounded, size: 22, color: Color(0xFF0F172A)),
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => ManageStudentsScreen(api: widget.api)),
              ),
              tooltip: 'إضافة ومسح QR',
            ),
            IconButton(
              icon: const Icon(Icons.swap_horiz_rounded, size: 24, color: Color(0xFF0F172A)),
              onPressed: () => _showRoleSwitcherDialog(context),
              tooltip: 'تبديل مساحة العمل',
            ),
            IconButton(
              icon: const Icon(Icons.notifications_none_rounded, size: 22, color: Color(0xFF0F172A)),
              onPressed: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text('لا توجد إشعارات جديدة الآن', style: GoogleFonts.cairo(fontSize: 13)),
                  ),
                );
              },
              tooltip: 'الإشعارات',
            ),
          ],
        ),
      ],
    );
  }

  void _showRoleSwitcherDialog(BuildContext context) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(24))),
      builder: (ctx) => Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'اختر مساحة العمل والدور',
                  style: GoogleFonts.cairo(fontSize: 16, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(color: const Color(0xFFE0F2FE), borderRadius: BorderRadius.circular(6)),
                  child: Text('المدرسة الافتراضية', style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold, color: AppTheme.screenshotBlue)),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text('يمكنك التبديل الفوري بين جميع اللوحات المعتمدة للمدرسة:', style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF64748B))),
            const SizedBox(height: 16),
            _buildWorkspaceTile(
              title: 'لوحة الطالب (بوابة الدروس والواجبات)',
              subtitle: 'استعراض الحصص، حل الواجبات، كشف الدرجات، ومساعد الذكاء',
              icon: Icons.school_rounded,
              color: AppTheme.screenshotBlue,
              onTap: () {
                Navigator.pop(ctx);
              },
            ),
            const SizedBox(height: 8),
            _buildWorkspaceTile(
              title: 'لوحة المعلم (رصد الدرجات وتحضير الحصص)',
              subtitle: 'رصد الاختبارات، تصحيح دفاتر الكشكول، تحضير الطلاب، ودفتر الدروس',
              icon: Icons.assignment_turned_in_rounded,
              color: AppTheme.screenshotGreen,
              onTap: () {
                Navigator.pop(ctx);
                Navigator.push(context, MaterialPageRoute(builder: (_) => TeacherDashboardScreen(api: widget.api)));
              },
            ),
            const SizedBox(height: 8),
            _buildWorkspaceTile(
              title: 'لوحة ولي الأمر (إدارة الأبناء والأجهزة)',
              subtitle: 'ربط الطلاب بكود المدرسة وإدارة الأجهزة المؤكدة',
              icon: Icons.family_restroom_rounded,
              color: AppTheme.screenshotPurple,
              onTap: () {
                Navigator.pop(ctx);
                Navigator.push(context, MaterialPageRoute(builder: (_) => ManageStudentsScreen(api: widget.api)));
              },
            ),
            const SizedBox(height: 8),
            _buildWorkspaceTile(
              title: 'لوحة الإدارة والمناهج الدراسية',
              subtitle: 'إضافة واعتماد المناهج، الشعب، والمقررات الرسمية',
              icon: Icons.admin_panel_settings_rounded,
              color: const Color(0xFF0284C7),
              onTap: () {
                Navigator.pop(ctx);
                Navigator.push(context, MaterialPageRoute(builder: (_) => SubjectsScreen(api: widget.api)));
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildWorkspaceTile({
    required String title,
    required String subtitle,
    required IconData icon,
    required Color color,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: const Color(0xFFE2E8F0)),
        ),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(color: color.withValues(alpha: 0.12), shape: BoxShape.circle),
              child: Icon(icon, color: color, size: 22),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A))),
                  Text(subtitle, style: GoogleFonts.cairo(fontSize: 10, color: const Color(0xFF64748B))),
                ],
              ),
            ),
            const Icon(Icons.arrow_forward_ios_rounded, size: 14, color: Color(0xFF94A3B8)),
          ],
        ),
      ),
    );
  }

  Widget _buildCompactStudentCard(StudentProfile student, bool isSelected, int index) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      margin: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isSelected ? AppTheme.screenshotBlue : const Color(0xFFE2E8F0),
          width: isSelected ? 2.0 : 1.2,
        ),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF0F172A).withValues(alpha: isSelected ? 0.08 : 0.04),
            blurRadius: 10,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          // Row 1: Student Avatar + Full Name + Grade & Status Pill
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  CircleAvatar(
                    radius: 18,
                    backgroundColor: AppTheme.screenshotLightBlue,
                    child: Text(
                      student.fullName.isNotEmpty ? student.fullName.substring(0, 1) : 'ط',
                      style: GoogleFonts.cairo(
                        color: AppTheme.screenshotBlue,
                        fontWeight: FontWeight.w900,
                        fontSize: 14,
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        student.fullName,
                        style: GoogleFonts.cairo(
                          color: const Color(0xFF0F172A),
                          fontWeight: FontWeight.w900,
                          fontSize: 15,
                        ),
                      ),
                      Text(
                        '${student.grade} - ${student.section}',
                        style: GoogleFonts.cairo(
                          color: const Color(0xFF64748B),
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                decoration: BoxDecoration(
                  color: isSelected ? const Color(0xFFDCFCE7) : const Color(0xFFF1F5F9),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(
                    color: isSelected ? const Color(0xFF86EFAC) : const Color(0xFFE2E8F0),
                  ),
                ),
                child: Text(
                  isSelected ? 'الحالي ✓' : 'تحديد',
                  style: GoogleFonts.cairo(
                    color: isSelected ? const Color(0xFF15803D) : const Color(0xFF475569),
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),

          // Row 2: Student Code + RFID Icon
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  const Icon(Icons.badge_outlined, color: Color(0xFF64748B), size: 16),
                  const SizedBox(width: 6),
                  Text(
                    'رقم القيد: ${student.studentNumber}',
                    style: GoogleFonts.cairo(
                      color: const Color(0xFF334155),
                      fontSize: 12,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0.3,
                    ),
                  ),
                ],
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: const Color(0xFFEFF6FF),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  'مقيد ونشط',
                  style: GoogleFonts.cairo(
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                    color: AppTheme.screenshotBlue,
                  ),
                ),
              ),
            ],
          ),

          // Row 3: Compact Inline Light Metrics
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
            decoration: BoxDecoration(
              color: const Color(0xFFF8FAFC),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: const Color(0xFFE2E8F0)),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                _buildCompactStat('الحضور', '${student.attendanceRate.toInt()}%', const Color(0xFF16A34A)),
                _buildCompactStat('المعدل', '${student.gpa}%', const Color(0xFF7C3AED)),
                _buildCompactStat('المرحلة', student.stage.replaceAll('المرحلة ', ''), const Color(0xFF0284C7)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCompactStat(String label, String value, Color valueColor) {
    return Row(
      children: [
        Text(
          '$label: ',
          style: GoogleFonts.cairo(color: const Color(0xFF64748B), fontSize: 11, fontWeight: FontWeight.bold),
        ),
        Text(
          value,
          style: GoogleFonts.cairo(
            color: valueColor,
            fontWeight: FontWeight.w900,
            fontSize: 11,
          ),
        ),
      ],
    );
  }

  Widget _buildCompactNoticeStrip() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFE2E8F0)),
        boxShadow: AppTheme.softShadow,
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: AppTheme.screenshotBlue.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Icon(Icons.timer_outlined, color: AppTheme.screenshotBlue, size: 16),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              'الحصة القادمة: الرياضيات (08:00 ص - قاعة 101)',
              style: GoogleFonts.cairo(
                fontSize: 11,
                fontWeight: FontWeight.bold,
                color: const Color(0xFF0F172A),
              ),
            ),
          ),
          Text(
            'أ. إبراهيم الحداد',
            style: GoogleFonts.cairo(fontSize: 10, color: const Color(0xFF64748B)),
          ),
        ],
      ),
    );
  }

  Widget _buildGridServiceCard({
    required String title,
    required IconData icon,
    required Color bgColor,
    required Color iconColor,
    String? badgeText,
    int? badgeCount,
    required VoidCallback onTap,
  }) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        splashColor: iconColor.withValues(alpha: 0.1),
        child: Ink(
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 8),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: const Color(0xFFE2E8F0)),
            boxShadow: AppTheme.softShadow,
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Stack(
                clipBehavior: Clip.none,
                children: [
                  Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(
                      color: bgColor,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(icon, color: iconColor, size: 20),
                  ),
                  if (badgeCount != null)
                    Positioned(
                      top: -4,
                      right: -4,
                      child: Container(
                        padding: const EdgeInsets.all(4),
                        decoration: const BoxDecoration(
                          color: AppTheme.rose,
                          shape: BoxShape.circle,
                        ),
                        child: Text(
                          '$badgeCount',
                          style: GoogleFonts.cairo(
                            color: Colors.white,
                            fontSize: 8,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    )
                  else if (badgeText != null)
                    Positioned(
                      top: -4,
                      right: -4,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                        decoration: BoxDecoration(
                          color: AppTheme.screenshotGreen,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          badgeText,
                          style: GoogleFonts.cairo(
                            color: Colors.white,
                            fontSize: 8,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 6),
              Text(
                title,
                textAlign: TextAlign.center,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: GoogleFonts.cairo(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  color: const Color(0xFF0F172A),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

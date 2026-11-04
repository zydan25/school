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
      viewportFraction: 0.92,
    );
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  Color _getRoleColor(String role) {
    switch (role) {
      case 'student':
        return const Color(0xFF0284C7); // Student Blue
      case 'guardian':
        return const Color(0xFF7C3AED); // Guardian Purple
      case 'teacher':
        return const Color(0xFF0D9488); // Teacher Teal
      case 'admin':
        return const Color(0xFF0F172A); // Admin Deep Navy
      case 'staff':
        return const Color(0xFFD97706); // Staff Amber
      default:
        return AppTheme.accent;
    }
  }

  String _getRoleLabel(String role) {
    switch (role) {
      case 'student':
        return 'مساحة الطالب';
      case 'guardian':
        return 'مساحة ولي الأمر';
      case 'teacher':
        return 'مساحة المعلم';
      case 'admin':
        return 'مساحة الإدارة';
      case 'staff':
        return 'مساحة الموظف';
      default:
        return 'مساحة العمل';
    }
  }

  void _showRoleSwitcherDialog() {
    final available = widget.api.availableRoles;
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      backgroundColor: Colors.white,
      builder: (ctx) {
        return Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'تبديل مساحة العمل الرسمية',
                    style: GoogleFonts.cairo(fontSize: 16, fontWeight: FontWeight.w800, color: AppTheme.textMain),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close_rounded, size: 20),
                    onPressed: () => Navigator.pop(ctx),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              Text(
                'المساحات المعتمدة لملف حسابك في ${widget.api.activeSchoolName}:',
                style: GoogleFonts.cairo(fontSize: 12, color: AppTheme.textMuted),
              ),
              const SizedBox(height: 16),
              ...available.map((role) {
                final isSelected = widget.api.currentRole == role;
                final color = _getRoleColor(role);
                return Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: InkWell(
                    onTap: () {
                      widget.api.switchRole(role);
                      Navigator.pop(ctx);
                    },
                    borderRadius: BorderRadius.circular(14),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      decoration: BoxDecoration(
                        color: isSelected ? color.withValues(alpha: 0.1) : const Color(0xFFF8FAFC),
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(
                          color: isSelected ? color : AppTheme.borderLight,
                          width: isSelected ? 1.5 : 1,
                        ),
                      ),
                      child: Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(8),
                            decoration: BoxDecoration(
                              color: color.withValues(alpha: 0.15),
                              shape: BoxShape.circle,
                            ),
                            child: Icon(
                              role == 'guardian'
                                  ? Icons.family_restroom_rounded
                                  : role == 'student'
                                      ? Icons.school_rounded
                                      : role == 'teacher'
                                          ? Icons.cast_for_education_rounded
                                          : Icons.admin_panel_settings_rounded,
                              color: color,
                              size: 18,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  _getRoleLabel(role),
                                  style: GoogleFonts.cairo(
                                    fontSize: 13,
                                    fontWeight: FontWeight.bold,
                                    color: isSelected ? color : AppTheme.textMain,
                                  ),
                                ),
                                Text(
                                  role == 'guardian'
                                      ? 'متابعة الأبناء، الرسوم، الحضور، والتواصل'
                                      : role == 'student'
                                          ? 'المواد، الواجبات، الدرجات، والمساعد الذكي'
                                          : role == 'teacher'
                                              ? 'رصد الدرجات، تصحيح الواجبات، والتحضير'
                                              : 'إدارة المدرسة والطلاب والمعلمين',
                                  style: GoogleFonts.cairo(fontSize: 11, color: AppTheme.textMuted),
                                ),
                              ],
                            ),
                          ),
                          if (isSelected)
                            Icon(Icons.check_circle_rounded, color: color, size: 20),
                        ],
                      ),
                    ),
                  ),
                );
              }),
            ],
          ),
        );
      },
    );
  }

  void _showLogoutDialog() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        title: Text(
          'تسجيل الخروج',
          style: GoogleFonts.cairo(fontSize: 16, fontWeight: FontWeight.bold),
        ),
        content: Text(
          'هل تريد بالتأكيد تسجيل الخروج من منظومة مدرستي؟',
          style: GoogleFonts.cairo(fontSize: 13),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('إلغاء', style: GoogleFonts.cairo(color: AppTheme.textMuted)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.rose,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            onPressed: () {
              Navigator.pop(ctx);
              widget.api.logout();
            },
            child: Text('خروج', style: GoogleFonts.cairo(fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.api,
      builder: (context, _) {
        final role = widget.api.currentRole;
        final roleColor = _getRoleColor(role);

        return Scaffold(
          backgroundColor: AppTheme.background,
          floatingActionButton: (role == 'student' || role == 'guardian')
              ? FloatingActionButton.extended(
                  onPressed: () => Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => ChatScreen(api: widget.api)),
                  ),
                  backgroundColor: const Color(0xFF0F172A),
                  elevation: 4,
                  icon: const Icon(Icons.auto_awesome_rounded, color: Colors.amber, size: 20),
                  label: Text(
                    'المساعد الذكي (Gemini)',
                    style: GoogleFonts.cairo(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold),
                  ),
                )
              : null,
          body: SafeArea(
            child: CustomScrollView(
              physics: const BouncingScrollPhysics(),
              slivers: [
                // 1. Top Header Bar with School Context & Role Badge
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
                    child: _buildHeaderBar(context, role, roleColor),
                  ),
                ),

                // 2. Dynamic Body depending on Active Role
                if (role == 'guardian') ..._buildGuardianDashboard(context)
                else if (role == 'student') ..._buildStudentDashboard(context)
                else if (role == 'teacher') ..._buildTeacherDashboard(context)
                else ..._buildAdminDashboard(context),

                const SliverToBoxAdapter(child: SizedBox(height: 80)),
              ],
            ),
          ),
        );
      },
    );
  }

  // ---------------------------------------------------------------------------
  // Header Bar with Role Switcher & School Context
  // ---------------------------------------------------------------------------
  Widget _buildHeaderBar(BuildContext context, String role, Color roleColor) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppTheme.borderLight),
        boxShadow: AppTheme.softShadow,
      ),
      child: Row(
        children: [
          // User Avatar / Role Crest
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: roleColor.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: roleColor.withValues(alpha: 0.3)),
            ),
            child: Center(
              child: Icon(
                role == 'guardian'
                    ? Icons.family_restroom_rounded
                    : role == 'student'
                        ? Icons.school_rounded
                        : role == 'teacher'
                            ? Icons.cast_for_education_rounded
                            : Icons.admin_panel_settings_rounded,
                color: roleColor,
                size: 22,
              ),
            ),
          ),
          const SizedBox(width: 12),

          // User info and School name
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Flexible(
                      child: Text(
                        widget.api.currentUserName,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: GoogleFonts.cairo(
                          fontSize: 14,
                          fontWeight: FontWeight.w800,
                          color: AppTheme.textMain,
                        ),
                      ),
                    ),
                    const SizedBox(width: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: roleColor.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: roleColor.withValues(alpha: 0.4)),
                      ),
                      child: Text(
                        _getRoleLabel(role),
                        style: GoogleFonts.cairo(
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                          color: roleColor,
                        ),
                      ),
                    ),
                  ],
                ),
                Text(
                  '${widget.api.activeSchoolName} • كود ${widget.api.activeSchoolCode}',
                  style: GoogleFonts.cairo(
                    fontSize: 11,
                    color: AppTheme.textMuted,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),

          // Role Switcher Button
          IconButton(
            onPressed: _showRoleSwitcherDialog,
            tooltip: 'تبديل مساحة العمل',
            icon: Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: const Color(0xFFF1F5F9),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.swap_horiz_rounded, color: AppTheme.textMain, size: 20),
            ),
          ),

          // Logout Button
          IconButton(
            onPressed: _showLogoutDialog,
            tooltip: 'تسجيل الخروج',
            icon: Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: AppTheme.rose.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.logout_rounded, color: AppTheme.rose, size: 18),
            ),
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // 1. GUARDIAN DASHBOARD
  // ---------------------------------------------------------------------------
  List<Widget> _buildGuardianDashboard(BuildContext context) {
    final children = widget.api.students;
    final activeStudent = widget.api.currentStudent;

    return [
      // Children Selector Carousel
      SliverToBoxAdapter(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 10, 20, 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'الأبناء المسجلون (${children.length})',
                    style: GoogleFonts.cairo(
                      fontSize: 13,
                      fontWeight: FontWeight.w800,
                      color: AppTheme.textMain,
                    ),
                  ),
                  InkWell(
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(builder: (_) => ManageStudentsScreen(api: widget.api)),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.person_add_alt_1_rounded, size: 16, color: Color(0xFF7C3AED)),
                        const SizedBox(width: 4),
                        Text(
                          'إضافة طالب جديد',
                          style: GoogleFonts.cairo(
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                            color: const Color(0xFF7C3AED),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),

            if (children.isEmpty)
              Container(
                margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: AppTheme.borderLight),
                ),
                child: Center(
                  child: Column(
                    children: [
                      const Icon(Icons.school_outlined, size: 40, color: AppTheme.textMuted),
                      const SizedBox(height: 8),
                      Text(
                        'لا يوجد طلاب مرتبطون بحسابك حالياً',
                        style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'انقر على إضافة طالب جديد واستخدم كود الطالب وكلمة المرور لربطه.',
                        style: GoogleFonts.cairo(fontSize: 11, color: AppTheme.textMuted),
                      ),
                    ],
                  ),
                ),
              )
            else
              SizedBox(
                height: 185,
                child: PageView.builder(
                  controller: _pageController,
                  itemCount: children.length,
                  onPageChanged: (idx) => widget.api.selectStudent(idx),
                  itemBuilder: (context, idx) {
                    final student = children[idx];
                    final isSelected = idx == widget.api.selectedStudentIndex;
                    return _buildChildCard(student, isSelected);
                  },
                ),
              ),
          ],
        ),
      ),

      // Guardian Services Section Title
      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 18, 20, 10),
          child: Text(
            'خدمات متابعة الطالب (${activeStudent.fullName.split(' ').first})',
            style: GoogleFonts.cairo(
              fontSize: 14,
              fontWeight: FontWeight.w800,
              color: AppTheme.textMain,
            ),
          ),
        ),
      ),

      // Guardian Services Grid
      SliverPadding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        sliver: SliverGrid(
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 2,
            mainAxisSpacing: 12,
            crossAxisSpacing: 12,
            childAspectRatio: 1.45,
          ),
          delegate: SliverChildListDelegate([
            _buildServiceTile(
              title: 'إدارة الطلاب والأجهزة',
              subtitle: 'ربط الأبناء واعتماد الأجهزة',
              icon: Icons.qr_code_scanner_rounded,
              color: const Color(0xFF7C3AED),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => ManageStudentsScreen(api: widget.api)),
              ),
            ),
            _buildServiceTile(
              title: 'الرسوم والمصروفات',
              subtitle: 'كشف الحساب وسندات السداد',
              icon: Icons.account_balance_wallet_rounded,
              color: const Color(0xFFE11D48),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => FinanceScreen(api: widget.api)),
              ),
            ),
            _buildServiceTile(
              title: 'سجل الحضور والأعذار',
              subtitle: 'نسبة المواظبة وتقديم العذر',
              icon: Icons.event_available_rounded,
              color: const Color(0xFF0D9488),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => AttendanceScreen(api: widget.api)),
              ),
            ),
            _buildServiceTile(
              title: 'جدول الحصص الأسبوعي',
              subtitle: 'الحصص والقاعات والمعلمون',
              icon: Icons.calendar_month_rounded,
              color: const Color(0xFF0284C7),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => TimetableScreen(api: widget.api)),
              ),
            ),
            _buildServiceTile(
              title: 'متابعة الواجبات',
              subtitle: 'الواجبات والتسليمات المدرسية',
              icon: Icons.assignment_rounded,
              color: const Color(0xFFD97706),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => HomeworkScreen(api: widget.api)),
              ),
            ),
            _buildServiceTile(
              title: 'كشف الدرجات والشهادة',
              subtitle: 'النتائج الفصلية وتقييم المواد',
              icon: Icons.military_tech_rounded,
              color: const Color(0xFF15803D),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => GradesScreen(api: widget.api)),
              ),
            ),
            _buildServiceTile(
              title: 'المحادثات والتعاميم',
              subtitle: 'التواصل مع إدارة المدرسة والمدرسين',
              icon: Icons.forum_rounded,
              color: const Color(0xFF4F46E5),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => NoticesScreen(api: widget.api)),
              ),
            ),
            _buildServiceTile(
              title: 'النقل والخدمات',
              subtitle: 'حافلات المدرسة والمكتبة',
              icon: Icons.directions_bus_rounded,
              color: const Color(0xFF64748B),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => ServicesScreen(api: widget.api)),
              ),
            ),
          ]),
        ),
      ),
    ];
  }

  Widget _buildChildCard(StudentProfile student, bool isSelected) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: isSelected ? const Color(0xFF7C3AED) : AppTheme.borderLight,
          width: isSelected ? 2 : 1,
        ),
        boxShadow: isSelected
            ? [
                BoxShadow(
                  color: const Color(0xFF7C3AED).withValues(alpha: 0.15),
                  blurRadius: 14,
                  offset: const Offset(0, 4),
                ),
              ]
            : AppTheme.softShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(14),
                child: Image.network(
                  student.avatarUrl,
                  width: 52,
                  height: 52,
                  fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) => Container(
                    width: 52,
                    height: 52,
                    color: const Color(0xFF7C3AED).withValues(alpha: 0.1),
                    child: const Icon(Icons.person, color: Color(0xFF7C3AED)),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      student.fullName,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: GoogleFonts.cairo(
                        fontSize: 15,
                        fontWeight: FontWeight.w900,
                        color: AppTheme.textMain,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '${student.grade} • ${student.section}',
                      style: GoogleFonts.cairo(
                        fontSize: 12,
                        color: AppTheme.textMuted,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: const Color(0xFF7C3AED).withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  student.studentNumber,
                  style: GoogleFonts.cairo(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    color: const Color(0xFF7C3AED),
                  ),
                ),
              ),
            ],
          ),
          const Spacer(),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: const Color(0xFFF8FAFC),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppTheme.borderLight),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _buildCardMetric('نسبة الحضور', '${student.attendanceRate}%', const Color(0xFF15803D)),
                Container(width: 1, height: 20, color: AppTheme.borderLight),
                _buildCardMetric('المعدل التراكمي', '${student.gpa}%', const Color(0xFF0284C7)),
                Container(width: 1, height: 20, color: AppTheme.borderLight),
                _buildCardMetric('الحالة الأكاديمية', 'منتظم', const Color(0xFF7C3AED)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCardMetric(String label, String val, Color valColor) {
    return Column(
      children: [
        Text(label, style: GoogleFonts.cairo(fontSize: 10, color: AppTheme.textMuted)),
        Text(val, style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.w800, color: valColor)),
      ],
    );
  }

  // ---------------------------------------------------------------------------
  // 2. STUDENT DASHBOARD
  // ---------------------------------------------------------------------------
  List<Widget> _buildStudentDashboard(BuildContext context) {
    final student = widget.api.currentStudent;

    return [
      // Student Identity Card
      SliverToBoxAdapter(
        child: Container(
          margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [Color(0xFF0284C7), Color(0xFF1E3A8A)],
              begin: Alignment.topRight,
              end: Alignment.bottomLeft,
            ),
            borderRadius: BorderRadius.circular(22),
            boxShadow: [
              BoxShadow(
                color: const Color(0xFF0284C7).withValues(alpha: 0.3),
                blurRadius: 16,
                offset: const Offset(0, 6),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(14),
                    child: Image.network(
                      student.avatarUrl,
                      width: 54,
                      height: 54,
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => Container(
                        width: 54,
                        height: 54,
                        color: Colors.white24,
                        child: const Icon(Icons.school, color: Colors.white),
                      ),
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          student.fullName,
                          style: GoogleFonts.cairo(
                            fontSize: 17,
                            fontWeight: FontWeight.w900,
                            color: Colors.white,
                          ),
                        ),
                        Text(
                          '${student.grade} • ${student.section}',
                          style: GoogleFonts.cairo(
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                            color: Colors.white70,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: Colors.white.withValues(alpha: 0.3)),
                    ),
                    child: Text(
                      student.studentNumber,
                      style: GoogleFonts.cairo(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: Colors.white.withValues(alpha: 0.2)),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.schedule_rounded, color: Colors.amber, size: 16),
                        const SizedBox(width: 8),
                        Text(
                          'الحصة القادمة: الفيزياء (08:00 ص)',
                          style: GoogleFonts.cairo(fontSize: 12, color: Colors.white, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                    Text(
                      'معمل 101',
                      style: GoogleFonts.cairo(fontSize: 11, color: Colors.white70),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),

      // Student Services Title
      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 10),
          child: Text(
            'خدمات الطالب الأكاديمية والذكاء الاصطناعي',
            style: GoogleFonts.cairo(
              fontSize: 14,
              fontWeight: FontWeight.w800,
              color: AppTheme.textMain,
            ),
          ),
        ),
      ),

      // Student Services Grid
      SliverPadding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        sliver: SliverGrid(
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 2,
            mainAxisSpacing: 12,
            crossAxisSpacing: 12,
            childAspectRatio: 1.45,
          ),
          delegate: SliverChildListDelegate([
            _buildServiceTile(
              title: 'جدول الحصص اليومي',
              subtitle: 'أوقات الحصص والقاعات',
              icon: Icons.calendar_month_rounded,
              color: const Color(0xFF0284C7),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => TimetableScreen(api: widget.api)),
              ),
            ),
            _buildServiceTile(
              title: 'واجباتي المدرسية',
              subtitle: 'حل الواجبات ورفع صورة الكشكول',
              icon: Icons.assignment_rounded,
              color: const Color(0xFFD97706),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => HomeworkScreen(api: widget.api)),
              ),
            ),
            _buildServiceTile(
              title: 'درجاتي وكشف النتائج',
              subtitle: 'الدرجات الشهرية والمعدل',
              icon: Icons.military_tech_rounded,
              color: const Color(0xFF15803D),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => GradesScreen(api: widget.api)),
              ),
            ),
            _buildServiceTile(
              title: 'المناهج والكتب المقررة',
              subtitle: 'تحميل كتب PDF والوحدات',
              icon: Icons.menu_book_rounded,
              color: const Color(0xFF7C3AED),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => SubjectsScreen(api: widget.api)),
              ),
            ),
            _buildServiceTile(
              title: 'المساعد الذكي (Gemini)',
              subtitle: 'شرح الدروس وحل المسائل',
              icon: Icons.auto_awesome_rounded,
              color: const Color(0xFF0F172A),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => ChatScreen(api: widget.api)),
              ),
            ),
            _buildServiceTile(
              title: 'سجل حضوري وغيابي',
              subtitle: 'متابعة نسبة الحضور والأعذار',
              icon: Icons.event_available_rounded,
              color: const Color(0xFF0D9488),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => AttendanceScreen(api: widget.api)),
              ),
            ),
          ]),
        ),
      ),
    ];
  }

  // ---------------------------------------------------------------------------
  // 3. TEACHER DASHBOARD
  // ---------------------------------------------------------------------------
  List<Widget> _buildTeacherDashboard(BuildContext context) {
    return [
      SliverToBoxAdapter(
        child: Container(
          margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [Color(0xFF0D9488), Color(0xFF0F172A)],
              begin: Alignment.topRight,
              end: Alignment.bottomLeft,
            ),
            borderRadius: BorderRadius.circular(22),
            boxShadow: [
              BoxShadow(
                color: const Color(0xFF0D9488).withValues(alpha: 0.3),
                blurRadius: 16,
                offset: const Offset(0, 6),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 52,
                    height: 52,
                    decoration: BoxDecoration(
                      color: Colors.white24,
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: const Icon(Icons.cast_for_education_rounded, color: Colors.white, size: 28),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          widget.api.currentUserName,
                          style: GoogleFonts.cairo(
                            fontSize: 16,
                            fontWeight: FontWeight.w900,
                            color: Colors.white,
                          ),
                        ),
                        Text(
                          'معلم الرياضيات والفيزياء • الشعبة المسندة: أول ثانوي (أ)',
                          style: GoogleFonts.cairo(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            color: Colors.white70,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: () => Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => TeacherDashboardScreen(api: widget.api)),
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.white,
                    foregroundColor: const Color(0xFF0D9488),
                    elevation: 0,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                  icon: const Icon(Icons.dashboard_rounded, size: 18),
                  label: Text(
                    'فتح لوحة تحكم المعلم المتكاملة',
                    style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),

      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 10),
          child: Text(
            'محاور لوحة المعلم السريعة',
            style: GoogleFonts.cairo(
              fontSize: 14,
              fontWeight: FontWeight.w800,
              color: AppTheme.textMain,
            ),
          ),
        ),
      ),

      SliverPadding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        sliver: SliverGrid(
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 2,
            mainAxisSpacing: 12,
            crossAxisSpacing: 12,
            childAspectRatio: 1.45,
          ),
          delegate: SliverChildListDelegate([
            _buildServiceTile(
              title: 'رصد درجات الطلاب',
              subtitle: 'الدرجات الشهرية والمشاركة والاختبارات',
              icon: Icons.grade_rounded,
              color: const Color(0xFF0D9488),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => TeacherDashboardScreen(api: widget.api, initialTab: 0)),
              ),
            ),
            _buildServiceTile(
              title: 'تصحيح الواجبات',
              subtitle: 'مراجعة صور الكشكول والتقييم',
              icon: Icons.rate_review_rounded,
              color: const Color(0xFF7C3AED),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => TeacherDashboardScreen(api: widget.api, initialTab: 1)),
              ),
            ),
            _buildServiceTile(
              title: 'دفتر الدروس والتحضير',
              subtitle: 'تسجيل الحضور والخطة اليومية',
              icon: Icons.edit_calendar_rounded,
              color: const Color(0xFF0284C7),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => TeacherDashboardScreen(api: widget.api, initialTab: 2)),
              ),
            ),
            _buildServiceTile(
              title: 'المساعد التربوي للذكاء',
              subtitle: 'توليد خطط دروس واختبارات ذكية',
              icon: Icons.psychology_rounded,
              color: const Color(0xFFD97706),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => TeacherDashboardScreen(api: widget.api, initialTab: 3)),
              ),
            ),
          ]),
        ),
      ),
    ];
  }

  // ---------------------------------------------------------------------------
  // 4. ADMIN DASHBOARD
  // ---------------------------------------------------------------------------
  List<Widget> _buildAdminDashboard(BuildContext context) {
    return [
      SliverToBoxAdapter(
        child: Container(
          margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [Color(0xFF0F172A), Color(0xFF334155)],
              begin: Alignment.topRight,
              end: Alignment.bottomLeft,
            ),
            borderRadius: BorderRadius.circular(22),
            boxShadow: [
              BoxShadow(
                color: const Color(0xFF0F172A).withValues(alpha: 0.3),
                blurRadius: 16,
                offset: const Offset(0, 6),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 52,
                    height: 52,
                    decoration: BoxDecoration(
                      color: Colors.white24,
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: const Icon(Icons.admin_panel_settings_rounded, color: Colors.white, size: 28),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          widget.api.currentUserName,
                          style: GoogleFonts.cairo(
                            fontSize: 16,
                            fontWeight: FontWeight.w900,
                            color: Colors.white,
                          ),
                        ),
                        Text(
                          'إدارة المدرسة • ${widget.api.activeSchoolName}',
                          style: GoogleFonts.cairo(
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                            color: Colors.white70,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(child: _buildAdminMetricCard('الطلاب', '248', Icons.school_rounded)),
                  const SizedBox(width: 8),
                  Expanded(child: _buildAdminMetricCard('المعلمون', '18', Icons.badge_rounded)),
                  const SizedBox(width: 8),
                  Expanded(child: _buildAdminMetricCard('الشعب', '8', Icons.meeting_room_rounded)),
                  const SizedBox(width: 8),
                  Expanded(child: _buildAdminMetricCard('المواظبة', '97.2%', Icons.check_circle_rounded)),
                ],
              ),
            ],
          ),
        ),
      ),

      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 10),
          child: Text(
            'أدوات الإدارة والرقابة المدرسية',
            style: GoogleFonts.cairo(
              fontSize: 14,
              fontWeight: FontWeight.w800,
              color: AppTheme.textMain,
            ),
          ),
        ),
      ),

      SliverPadding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        sliver: SliverGrid(
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 2,
            mainAxisSpacing: 12,
            crossAxisSpacing: 12,
            childAspectRatio: 1.45,
          ),
          delegate: SliverChildListDelegate([
            _buildServiceTile(
              title: 'دليل الطلاب وقيد القبول',
              subtitle: 'سجلات الطلاب والشعب والترحيل',
              icon: Icons.people_alt_rounded,
              color: const Color(0xFF0F172A),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => ManageStudentsScreen(api: widget.api)),
              ),
            ),
            _buildServiceTile(
              title: 'المناهج والمقررات',
              subtitle: 'المواد والوحدات والكتب الرسمية',
              icon: Icons.menu_book_rounded,
              color: const Color(0xFF0284C7),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => SubjectsScreen(api: widget.api)),
              ),
            ),
            _buildServiceTile(
              title: 'الإدارة المالية والتحصيل',
              subtitle: 'إيرادات الرسوم وسندات القبض',
              icon: Icons.receipt_long_rounded,
              color: const Color(0xFFE11D48),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => FinanceScreen(api: widget.api)),
              ),
            ),
            _buildServiceTile(
              title: 'التعاميم المدرسية المعتمدة',
              subtitle: 'إصدار الأخبار والإشعارات الرسمية',
              icon: Icons.campaign_rounded,
              color: const Color(0xFFD97706),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => NoticesScreen(api: widget.api)),
              ),
            ),
          ]),
        ),
      ),
    ];
  }

  Widget _buildAdminMetricCard(String label, String value, IconData icon) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 4),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(
        children: [
          Icon(icon, size: 16, color: Colors.amber),
          const SizedBox(height: 2),
          Text(value, style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.w800, color: Colors.white)),
          Text(label, style: GoogleFonts.cairo(fontSize: 10, color: Colors.white70)),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Reusable Service Tile
  // ---------------------------------------------------------------------------
  Widget _buildServiceTile({
    required String title,
    required String subtitle,
    required IconData icon,
    required Color color,
    required VoidCallback onTap,
  }) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppTheme.borderLight),
            boxShadow: AppTheme.softShadow,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Center(child: Icon(icon, color: color, size: 20)),
              ),
              const SizedBox(height: 8),
              Text(
                title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: GoogleFonts.cairo(
                  fontSize: 12,
                  fontWeight: FontWeight.w800,
                  color: AppTheme.textMain,
                ),
              ),
              Text(
                subtitle,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: GoogleFonts.cairo(
                  fontSize: 10,
                  color: AppTheme.textMuted,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

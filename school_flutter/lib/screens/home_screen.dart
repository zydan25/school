import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../core/api_service.dart';
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
import 'online_exams_screen.dart';
import 'settings_screen.dart';

class HomeScreen extends StatefulWidget {
  final ApiService api;
  const HomeScreen({super.key, required this.api});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _gridColumns = 3; // Default 3 columns (Jaib fintech style from screenshot)
  int _selectedBottomNavIndex = 0;

  @override
  void initState() {
    super.initState();
    _loadGridTheme();
  }

  Future<void> _loadGridTheme() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final cols = prefs.getInt('home_grid_columns');
      if (cols != null && (cols == 2 || cols == 3)) {
        if (mounted) setState(() => _gridColumns = cols);
      }
    } catch (_) {}
  }

  String _getTimeGreeting() {
    final hour = DateTime.now().hour;
    if (hour < 12) {
      return 'صباح الخير';
    } else if (hour < 17) {
      return 'مساء الخير';
    } else {
      return 'مساء النور';
    }
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
          backgroundColor: const Color(0xFFF8FAFC),
          floatingActionButtonLocation: FloatingActionButtonLocation.centerDocked,
          floatingActionButton: Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(
              color: const Color(0xFF0F172A),
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFF0F172A).withValues(alpha: 0.35),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Material(
              color: Colors.transparent,
              child: InkWell(
                onTap: () => Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => ChatScreen(api: widget.api)),
                ),
                customBorder: const CircleBorder(),
                child: const Center(
                  child: Icon(Icons.keyboard_arrow_up_rounded, color: Colors.white, size: 30),
                ),
              ),
            ),
          ),
          bottomNavigationBar: _buildJaibBottomBar(context, role),
          body: SafeArea(
            child: CustomScrollView(
              physics: const BouncingScrollPhysics(),
              slivers: [
                // 1. Top Header Bar (Jaib style: Greeting + Name + Action Icons)
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
  // Header Bar with Role Switcher, Student Pill & 3-Dots Options Menu
  // ---------------------------------------------------------------------------
  Widget _buildHeaderBar(BuildContext context, String role, Color roleColor) {
    final firstName = widget.api.currentUserName.isNotEmpty
        ? widget.api.currentUserName.split(' ').first
        : 'مرحباً';
    final activeStudent = widget.api.currentStudent;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFFE2E8F0)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.03),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          // Greeting & User Name (Right side in RTL)
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  _getTimeGreeting(),
                  style: GoogleFonts.cairo(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: const Color(0xFF64748B),
                  ),
                ),
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Flexible(
                      child: Text(
                        firstName,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: GoogleFonts.cairo(
                          fontSize: 18,
                          fontWeight: FontWeight.w900,
                          color: const Color(0xFF0F172A),
                        ),
                      ),
                    ),
                    const SizedBox(width: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                      decoration: BoxDecoration(
                        color: roleColor.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: roleColor.withValues(alpha: 0.3)),
                      ),
                      child: Text(
                        _getRoleLabel(role),
                        style: GoogleFonts.cairo(
                          fontSize: 9.5,
                          fontWeight: FontWeight.bold,
                          color: roleColor,
                        ),
                      ),
                    ),
                  ],
                ),
                if (activeStudent != null && (role == 'guardian' || role == 'student')) ...[
                  const SizedBox(height: 3),
                  InkWell(
                    onTap: () async {
                      await Navigator.push(
                        context,
                        MaterialPageRoute(builder: (_) => ManageStudentsScreen(api: widget.api, initialTab: 1)),
                      );
                    },
                    borderRadius: BorderRadius.circular(6),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.school_rounded, size: 12, color: Color(0xFF0284C7)),
                        const SizedBox(width: 4),
                        Flexible(
                          child: Text(
                            'الطالب: ${activeStudent.fullName.split(' ').first} (${activeStudent.grade}) ⇄ تبديل',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: GoogleFonts.cairo(
                              fontSize: 10.5,
                              fontWeight: FontWeight.bold,
                              color: const Color(0xFF0284C7),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),

          // Clean Top Action Buttons (Left side in RTL)
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Notification Bell with Red Unread Dot
              Stack(
                clipBehavior: Clip.none,
                children: [
                  _buildHeaderIconButton(
                    icon: Icons.notifications_none_rounded,
                    color: const Color(0xFF0F172A),
                    tooltip: 'التعاميم والإشعارات',
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(builder: (_) => NoticesScreen(api: widget.api)),
                    ),
                  ),
                  Positioned(
                    top: 6,
                    left: 6,
                    child: Container(
                      width: 8,
                      height: 8,
                      decoration: const BoxDecoration(
                        color: Color(0xFFE11D48),
                        shape: BoxShape.circle,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(width: 8),

              // Role Switcher Button
              _buildHeaderIconButton(
                icon: Icons.swap_horiz_rounded,
                color: const Color(0xFF475569),
                tooltip: 'تبديل مساحة العمل',
                onTap: _showRoleSwitcherDialog,
              ),
              const SizedBox(width: 8),

              // 3-Dots Menu Button (منيو ثلاث نقاط)
              _buildHeaderIconButton(
                icon: Icons.more_vert,
                color: const Color(0xFF0F172A),
                tooltip: 'الخيارات ومساحات العمل',
                onTap: () => _showOptionsMenuDialog(context),
              ),
            ],
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // 3-Dots Options Menu Modal (منيو ثلاث نقاط)
  // ---------------------------------------------------------------------------
  void _showOptionsMenuDialog(BuildContext context) {
    final availableRoles = widget.api.availableRoles;
    final currentRole = widget.api.currentRole;
    final activeStudent = widget.api.currentStudent;

    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      backgroundColor: Colors.white,
      builder: (ctx) {
        return Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(6),
                        decoration: BoxDecoration(
                          color: const Color(0xFF0F172A).withValues(alpha: 0.1),
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(Icons.apps_rounded, color: Color(0xFF0F172A), size: 20),
                      ),
                      const SizedBox(width: 10),
                      Text(
                        'خيارات ومساحات العمل',
                        style: GoogleFonts.cairo(fontSize: 16, fontWeight: FontWeight.w900, color: const Color(0xFF0F172A)),
                      ),
                    ],
                  ),
                  IconButton(
                    icon: const Icon(Icons.close_rounded, size: 20),
                    onPressed: () => Navigator.pop(ctx),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              Text(
                'الوصول السريع إلى المساحات والطلاب والإعدادات المعتمدة بحسابك:',
                style: GoogleFonts.cairo(fontSize: 11.5, color: const Color(0xFF64748B)),
              ),
              const SizedBox(height: 14),

              // 1. Switch Student Option
              _buildMenuActionTile(
                title: 'تبديل الطالب النشط',
                subtitle: activeStudent != null
                    ? 'الحالي: ${activeStudent.fullName} (${activeStudent.grade})'
                    : 'اختيار وتفعيل أحد الأبناء المسجلين',
                icon: Icons.school_rounded,
                color: const Color(0xFF0284C7),
                onTap: () async {
                  Navigator.pop(ctx);
                  await Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => ManageStudentsScreen(api: widget.api, initialTab: 1)),
                  );
                },
              ),

              // 2. View My Students Option
              _buildMenuActionTile(
                title: 'عرض طلابي (الأبناء المسجلون)',
                subtitle: '${widget.api.students.length} طلاب مسجلون - ربط وإدارة الأجهزة',
                icon: Icons.people_alt_rounded,
                color: const Color(0xFF7C3AED),
                onTap: () async {
                  Navigator.pop(ctx);
                  await Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => ManageStudentsScreen(api: widget.api, initialTab: 1)),
                  );
                },
              ),

              // 3. Teacher Workspace Option (if available)
              if (availableRoles.contains('teacher'))
                _buildMenuActionTile(
                  title: 'الانتقال إلى مساحة المعلم',
                  subtitle: 'رصد درجات الطلاب وتصحيح الواجبات ودفتر التحضير',
                  icon: Icons.cast_for_education_rounded,
                  color: const Color(0xFF0D9488),
                  isSelected: currentRole == 'teacher',
                  onTap: () {
                    widget.api.switchRole('teacher');
                    Navigator.pop(ctx);
                  },
                ),

              // 4. Admin / Supervisor Workspace Option (if available)
              if (availableRoles.contains('admin') || availableRoles.contains('staff'))
                _buildMenuActionTile(
                  title: 'الانتقال إلى مساحة الإدارة والمشرف',
                  subtitle: 'إدارة المدرسة وقيد القبول والتقارير العامة',
                  icon: Icons.admin_panel_settings_rounded,
                  color: const Color(0xFF0F172A),
                  isSelected: currentRole == 'admin' || currentRole == 'staff',
                  onTap: () {
                    widget.api.switchRole(availableRoles.contains('admin') ? 'admin' : 'staff');
                    Navigator.pop(ctx);
                  },
                ),

              // 5. Guardian Workspace Option (if available)
              if (availableRoles.contains('guardian'))
                _buildMenuActionTile(
                  title: 'الانتقال إلى مساحة ولي الأمر',
                  subtitle: 'متابعة الأبناء، الرسوم وسندات السداد، والحضور',
                  icon: Icons.family_restroom_rounded,
                  color: const Color(0xFF7C3AED),
                  isSelected: currentRole == 'guardian',
                  onTap: () {
                    widget.api.switchRole('guardian');
                    Navigator.pop(ctx);
                  },
                ),

              // 6. Settings Option
              _buildMenuActionTile(
                title: 'الإعدادات وتخصيص الواجهة',
                subtitle: 'نمط البطائق، الأمان ورمز PIN، الإشعارات، الحساب',
                icon: Icons.settings_rounded,
                color: const Color(0xFF475569),
                onTap: () async {
                  Navigator.pop(ctx);
                  await Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => SettingsScreen(api: widget.api)),
                  );
                  _loadGridTheme();
                },
              ),

              // 7. Logout Option
              _buildMenuActionTile(
                title: 'تسجيل الخروج',
                subtitle: 'تسجيل الخروج الآمن من المنظومة',
                icon: Icons.logout_rounded,
                color: const Color(0xFFE11D48),
                onTap: () {
                  Navigator.pop(ctx);
                  _showLogoutDialog();
                },
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildMenuActionTile({
    required String title,
    required String subtitle,
    required IconData icon,
    required Color color,
    required VoidCallback onTap,
    bool isSelected = false,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: isSelected ? color.withValues(alpha: 0.1) : const Color(0xFFF8FAFC),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: isSelected ? color : const Color(0xFFE2E8F0),
              width: isSelected ? 1.5 : 1,
            ),
          ),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: color, size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: GoogleFonts.cairo(
                        fontSize: 13,
                        fontWeight: FontWeight.bold,
                        color: isSelected ? color : const Color(0xFF0F172A),
                      ),
                    ),
                    Text(
                      subtitle,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: GoogleFonts.cairo(fontSize: 10.5, color: const Color(0xFF64748B)),
                    ),
                  ],
                ),
              ),
              if (isSelected)
                Icon(Icons.check_circle_rounded, color: color, size: 18)
              else
                const Icon(Icons.arrow_forward_ios_rounded, size: 14, color: Color(0xFF94A3B8)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeaderIconButton({
    required IconData icon,
    required Color color,
    required String tooltip,
    required VoidCallback onTap,
  }) {
    return Tooltip(
      message: tooltip,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          width: 38,
          height: 38,
          decoration: BoxDecoration(
            color: const Color(0xFFF8FAFC),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: const Color(0xFFE2E8F0)),
          ),
          child: Center(
            child: Icon(icon, color: color, size: 20),
          ),
        ),
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
      // Compact Active Student Bar
      if (activeStudent != null)
        SliverToBoxAdapter(
          child: Container(
            margin: const EdgeInsets.fromLTRB(16, 6, 16, 6),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: const Color(0xFFE2E8F0)),
              boxShadow: AppTheme.softShadow,
            ),
            child: Row(
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: Image.network(
                    activeStudent.avatarUrl,
                    width: 44,
                    height: 44,
                    fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => Container(
                      width: 44,
                      height: 44,
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
                        'متابعة الطالب: ${activeStudent.fullName}',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                      ),
                      Text(
                        '${activeStudent.grade} • ${activeStudent.section} • حضور ${activeStudent.attendanceRate}% • معدل ${activeStudent.gpa}%',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: GoogleFonts.cairo(fontSize: 10.5, color: const Color(0xFF64748B), fontWeight: FontWeight.w600),
                      ),
                    ],
                  ),
                ),
                ElevatedButton(
                  onPressed: () async {
                    await Navigator.push(
                      context,
                      MaterialPageRoute(builder: (_) => ManageStudentsScreen(api: widget.api, initialTab: 1)),
                    );
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFFEFF6FF),
                    foregroundColor: const Color(0xFF0284C7),
                    elevation: 0,
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  child: Text(
                    'تبديل (${children.length})',
                    style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
          ),
        ),

      // Announcement / Promo Banner
      SliverToBoxAdapter(
        child: _buildPromoBanner(context, 'guardian'),
      ),

      // Guardian Services Section Title
      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 14, 20, 10),
          child: Text(
            activeStudent != null
                ? 'خدمات متابعة الطالب (${activeStudent.fullName.split(' ').first})'
                : 'خدمات متابعة الطالب',
            style: GoogleFonts.cairo(
              fontSize: 15,
              fontWeight: FontWeight.w900,
              color: const Color(0xFF0F172A),
            ),
          ),
        ),
      ),

      // Guardian Services Grid (3x3 = 9 items in 3-column mode)
      SliverPadding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        sliver: SliverGrid(
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: _gridColumns,
            mainAxisSpacing: _gridColumns == 3 ? 10 : 12,
            crossAxisSpacing: _gridColumns == 3 ? 10 : 12,
            childAspectRatio: _gridColumns == 3 ? 0.95 : 1.45,
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
              title: 'الاختبارات الإلكترونية',
              subtitle: 'أوراق الاختبار والمؤقت والنتائج',
              icon: Icons.quiz_rounded,
              color: const Color(0xFF6366F1),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => OnlineExamsScreen(api: widget.api)),
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

      // Recent Activity / Operations Section matching Jaib screenshot
      _buildRecentActivitiesSection(context, 'guardian'),
    ];
  }

  // ---------------------------------------------------------------------------
  // 2. STUDENT DASHBOARD
  // ---------------------------------------------------------------------------
  List<Widget> _buildStudentDashboard(BuildContext context) {
    final student = widget.api.currentStudent;

    if (student == null) {
      return [
        SliverToBoxAdapter(
          child: Container(
            margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 20),
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: const Color(0xFFE2E8F0)),
              boxShadow: AppTheme.softShadow,
            ),
            child: Column(
              children: [
                Container(
                  width: 64,
                  height: 64,
                  decoration: const BoxDecoration(
                    color: AppTheme.screenshotLightBlue,
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.school_rounded, color: AppTheme.screenshotBlue, size: 32),
                ),
                const SizedBox(height: 14),
                Text(
                  'لا يوجد ملف طالب نشط مرتبط بحسابك في ${widget.api.activeSchoolName}',
                  textAlign: TextAlign.center,
                  style: GoogleFonts.cairo(fontSize: 15, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                ),
                const SizedBox(height: 8),
                Text(
                  'يمكنك ربط كود الطالب أو التبديل إلى مدرسة أخرى أو مساحة عمل أخرى.',
                  textAlign: TextAlign.center,
                  style: GoogleFonts.cairo(fontSize: 12, color: const Color(0xFF64748B)),
                ),
                const SizedBox(height: 16),
                ElevatedButton.icon(
                  onPressed: () => Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => ManageStudentsScreen(api: widget.api)),
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.screenshotBlue,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  icon: const Icon(Icons.person_add_alt_1_rounded, size: 18),
                  label: Text('إضافة وربط كود الطالب', style: GoogleFonts.cairo(fontWeight: FontWeight.bold)),
                ),
              ],
            ),
          ),
        ),
      ];
    }

    final todayLessons = widget.api.studentTodayLessons;
    final hasLessons = todayLessons.isNotEmpty;
    final nextLesson = hasLessons ? todayLessons.first : null;

    return [
      // Compact Next Lesson Strip (Clean, Light Jaib Style)
      if (nextLesson != null)
        SliverToBoxAdapter(
          child: Container(
            margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: const Color(0xFFE2E8F0)),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.03),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Row(
              children: [
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    color: const Color(0xFFEFF6FF),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Center(
                    child: Icon(Icons.schedule_rounded, color: Color(0xFF0284C7), size: 20),
                  ),
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
                              'الحصة القادمة: ${nextLesson.subject}',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: GoogleFonts.cairo(
                                fontSize: 12.5,
                                fontWeight: FontWeight.w800,
                                color: const Color(0xFF0F172A),
                              ),
                            ),
                          ),
                          const SizedBox(width: 6),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1.5),
                            decoration: BoxDecoration(
                              color: const Color(0xFF0284C7).withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(
                              'الحصة ${nextLesson.period}',
                              style: GoogleFonts.cairo(
                                fontSize: 9.5,
                                fontWeight: FontWeight.bold,
                                color: const Color(0xFF0284C7),
                              ),
                            ),
                          ),
                        ],
                      ),
                      Text(
                        '${nextLesson.time} • ${nextLesson.classroom}',
                        style: GoogleFonts.cairo(
                          fontSize: 10.5,
                          fontWeight: FontWeight.w600,
                          color: const Color(0xFF64748B),
                        ),
                      ),
                    ],
                  ),
                ),
                TextButton(
                  onPressed: () => Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => TimetableScreen(api: widget.api)),
                  ),
                  style: TextButton.styleFrom(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    backgroundColor: const Color(0xFFF1F5F9),
                    foregroundColor: const Color(0xFF0F172A),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  child: Text(
                    'الجدول',
                    style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
          ),
        ),

      // Announcement / Promo Banner
      SliverToBoxAdapter(
        child: _buildPromoBanner(context, 'student'),
      ),

      // Student Services Title
      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 14, 20, 10),
          child: Text(
            'الخدمات الأكاديمية والذكاء الاصطناعي',
            style: GoogleFonts.cairo(
              fontSize: 15,
              fontWeight: FontWeight.w900,
              color: const Color(0xFF0F172A),
            ),
          ),
        ),
      ),

      // Student Services Grid (3x3 = 9 items in 3-column mode)
      SliverPadding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        sliver: SliverGrid(
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: _gridColumns,
            mainAxisSpacing: _gridColumns == 3 ? 10 : 12,
            crossAxisSpacing: _gridColumns == 3 ? 10 : 12,
            childAspectRatio: _gridColumns == 3 ? 0.95 : 1.45,
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
              title: 'الاختبارات الإلكترونية',
              subtitle: 'أوراق الاختبار والمؤقت والنتائج',
              icon: Icons.quiz_rounded,
              color: const Color(0xFF6366F1),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => OnlineExamsScreen(api: widget.api)),
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
              title: 'الرسوم والخدمات',
              subtitle: 'كشف الحساب وسندات السداد',
              icon: Icons.account_balance_wallet_rounded,
              color: const Color(0xFFE11D48),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => FinanceScreen(api: widget.api)),
              ),
            ),
          ]),
        ),
      ),

      // Recent Activity / Operations Section matching Jaib screenshot
      _buildRecentActivitiesSection(context, 'student'),
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

      // Announcement / Promo Banner
      SliverToBoxAdapter(
        child: _buildPromoBanner(context, 'teacher'),
      ),

      // Teacher Services Title
      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 14, 20, 10),
          child: Text(
            'محاور لوحة المعلم السريعة',
            style: GoogleFonts.cairo(
              fontSize: 15,
              fontWeight: FontWeight.w900,
              color: const Color(0xFF0F172A),
            ),
          ),
        ),
      ),

      // Teacher Services Grid (3x2 = 6 items)
      SliverPadding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        sliver: SliverGrid(
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: _gridColumns,
            mainAxisSpacing: _gridColumns == 3 ? 10 : 12,
            crossAxisSpacing: _gridColumns == 3 ? 10 : 12,
            childAspectRatio: _gridColumns == 3 ? 0.95 : 1.45,
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
            _buildServiceTile(
              title: 'جدول الحصص اليومي',
              subtitle: 'أوقات الحصص والمجموعات والقاعات',
              icon: Icons.calendar_month_rounded,
              color: const Color(0xFF0284C7),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => TimetableScreen(api: widget.api)),
              ),
            ),
            _buildServiceTile(
              title: 'سجل حضور الحصة',
              subtitle: 'تسجيل الحاضرين والغائبين مباشرة',
              icon: Icons.event_available_rounded,
              color: const Color(0xFF15803D),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => AttendanceScreen(api: widget.api)),
              ),
            ),
          ]),
        ),
      ),

      // Recent Operations Section
      _buildRecentActivitiesSection(context, 'teacher'),
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

      // Announcement / Promo Banner
      SliverToBoxAdapter(
        child: _buildPromoBanner(context, 'admin'),
      ),

      // Admin Services Title
      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 14, 20, 10),
          child: Text(
            'أدوات الإدارة والرقابة المدرسية',
            style: GoogleFonts.cairo(
              fontSize: 15,
              fontWeight: FontWeight.w900,
              color: const Color(0xFF0F172A),
            ),
          ),
        ),
      ),

      // Admin Services Grid (3x2 = 6 items)
      SliverPadding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        sliver: SliverGrid(
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: _gridColumns,
            mainAxisSpacing: _gridColumns == 3 ? 10 : 12,
            crossAxisSpacing: _gridColumns == 3 ? 10 : 12,
            childAspectRatio: _gridColumns == 3 ? 0.95 : 1.45,
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
            _buildServiceTile(
              title: 'جدول الحصص المدرسي العام',
              subtitle: 'إدارة وتوزيع الحصص الأسبوعية',
              icon: Icons.calendar_month_rounded,
              color: const Color(0xFF0D9488),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => TimetableScreen(api: widget.api)),
              ),
            ),
            _buildServiceTile(
              title: 'تقارير الحضور والمواظبة',
              subtitle: 'سجلات الغياب ونسب التزام المدرسة',
              icon: Icons.event_available_rounded,
              color: const Color(0xFF7C3AED),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => AttendanceScreen(api: widget.api)),
              ),
            ),
          ]),
        ),
      ),

      // Recent Operations Section
      _buildRecentActivitiesSection(context, 'admin'),
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
  // Reusable Service Tile (Supporting both 3-column Jaib Fintech & 2-column detailed)
  // ---------------------------------------------------------------------------
  Widget _buildServiceTile({
    required String title,
    required String subtitle,
    required IconData icon,
    required Color color,
    required VoidCallback onTap,
  }) {
    if (_gridColumns == 3) {
      // 3-Column Jaib Fintech Style matching media_1793863825724_547dd324.jpg
      return Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 8),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: const Color(0xFFF1F5F9)),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.035),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Container(
                  width: 42,
                  height: 42,
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.09),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: color.withValues(alpha: 0.2)),
                  ),
                  child: Center(
                    child: Icon(icon, color: color, size: 21),
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  title,
                  textAlign: TextAlign.center,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.cairo(
                    fontSize: 11.0,
                    fontWeight: FontWeight.w800,
                    color: const Color(0xFF0F172A),
                    height: 1.2,
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    }

    // 2-Column Detailed Mode
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

  // ---------------------------------------------------------------------------
  // Promo / Notice Banner matching Jaib Screenshot
  // ---------------------------------------------------------------------------
  Widget _buildPromoBanner(BuildContext context, String role) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFFFFF1F2), Color(0xFFFEE2E2), Color(0xFFFFFFFF)],
          begin: Alignment.centerRight,
          end: Alignment.centerLeft,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFFECDD3)),
      ),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: const Color(0xFFE11D48).withValues(alpha: 0.12),
              shape: BoxShape.circle,
            ),
            child: const Center(
              child: Icon(Icons.auto_awesome_rounded, color: Color(0xFFE11D48), size: 24),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'المساعد الذكي لمدرستي (Gemini AI)',
                  style: GoogleFonts.cairo(
                    fontSize: 12,
                    fontWeight: FontWeight.w900,
                    color: const Color(0xFF9F1239),
                  ),
                ),
                Text(
                  'شرح فوري للمناهج وحل المسائل وتلخيص الدروس مباشرة',
                  style: GoogleFonts.cairo(
                    fontSize: 10.5,
                    fontWeight: FontWeight.w600,
                    color: const Color(0xFF475569),
                  ),
                ),
              ],
            ),
          ),
          TextButton(
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => ChatScreen(api: widget.api)),
            ),
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              backgroundColor: const Color(0xFFE11D48),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            child: Text(
              'اسأل الآن',
              style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold),
            ),
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Recent Activities / Operations Section matching "العمليات" in Screenshot
  // ---------------------------------------------------------------------------
  Widget _buildRecentActivitiesSection(BuildContext context, String role) {
    return SliverToBoxAdapter(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 20, 16, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'العمليات والأنشطة الحديثة',
                  style: GoogleFonts.cairo(
                    fontSize: 15,
                    fontWeight: FontWeight.w900,
                    color: const Color(0xFF0F172A),
                  ),
                ),
                TextButton(
                  onPressed: () {
                    if (role == 'student') {
                      Navigator.push(context, MaterialPageRoute(builder: (_) => GradesScreen(api: widget.api)));
                    } else if (role == 'guardian') {
                      Navigator.push(context, MaterialPageRoute(builder: (_) => FinanceScreen(api: widget.api)));
                    } else {
                      Navigator.push(context, MaterialPageRoute(builder: (_) => TeacherDashboardScreen(api: widget.api)));
                    }
                  },
                  child: Text(
                    'عرض الكل',
                    style: GoogleFonts.cairo(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      color: const Color(0xFFE11D48),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: const Color(0xFFE2E8F0)),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.03),
                    blurRadius: 10,
                    offset: const Offset(0, 3),
                  ),
                ],
              ),
              child: role == 'guardian'
                  ? _buildRecentActivityRow(
                      title: 'سداد قسط مدرسي معتمد',
                      timestamp: '05/11/2026 (09:30)',
                      value: '-50,000 ريال يمني',
                      valueColor: const Color(0xFFE11D48),
                      icon: Icons.account_balance_wallet_rounded,
                      iconBg: const Color(0xFFFFF1F2),
                      iconColor: const Color(0xFFE11D48),
                    )
                  : role == 'student'
                      ? _buildRecentActivityRow(
                          title: 'تسجيل حضور اليوم الدراسي',
                          timestamp: '05/11/2026 (07:45)',
                          value: 'حاضر في الموعد ✓',
                          valueColor: const Color(0xFF15803D),
                          icon: Icons.event_available_rounded,
                          iconBg: const Color(0xFFDCFCE7),
                          iconColor: const Color(0xFF15803D),
                        )
                      : _buildRecentActivityRow(
                          title: 'رصد درجات اختبار الشهر',
                          timestamp: '05/11/2026 (10:15)',
                          value: '24 طالباً مكتمل',
                          valueColor: const Color(0xFF0D9488),
                          icon: Icons.grade_rounded,
                          iconBg: const Color(0xFFCCFBF1),
                          iconColor: const Color(0xFF0D9488),
                        ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRecentActivityRow({
    required String title,
    required String timestamp,
    required String value,
    required Color valueColor,
    required IconData icon,
    required Color iconBg,
    required Color iconColor,
  }) {
    return Row(
      children: [
        Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: iconBg,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Center(child: Icon(icon, color: iconColor, size: 22)),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: GoogleFonts.cairo(
                  fontSize: 13,
                  fontWeight: FontWeight.w800,
                  color: const Color(0xFF0F172A),
                ),
              ),
              Text(
                timestamp,
                style: GoogleFonts.cairo(
                  fontSize: 11,
                  color: const Color(0xFF94A3B8),
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
        Text(
          value,
          style: GoogleFonts.cairo(
            fontSize: 13,
            fontWeight: FontWeight.w900,
            color: valueColor,
          ),
        ),
      ],
    );
  }

  // ---------------------------------------------------------------------------
  // Jaib Fintech Style Bottom Navigation Bar with Notched Elevation
  // ---------------------------------------------------------------------------
  Widget _buildJaibBottomBar(BuildContext context, String role) {
    return BottomAppBar(
      shape: const CircularNotchedRectangle(),
      notchMargin: 8,
      color: Colors.white,
      elevation: 10,
      height: 64,
      padding: EdgeInsets.zero,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: [
          _buildBottomNavItem(
            icon: Icons.home_rounded,
            label: 'الرئيسية',
            isSelected: _selectedBottomNavIndex == 0,
            onTap: () => setState(() => _selectedBottomNavIndex = 0),
          ),
          _buildBottomNavItem(
            icon: Icons.widgets_outlined,
            label: 'الخدمات',
            isSelected: _selectedBottomNavIndex == 1,
            onTap: () {
              setState(() => _selectedBottomNavIndex = 1);
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => ServicesScreen(api: widget.api)),
              ).then((_) {
                if (mounted) setState(() => _selectedBottomNavIndex = 0);
              });
            },
          ),
          const SizedBox(width: 44), // Space for centered notched FAB
          _buildBottomNavItem(
            icon: Icons.assessment_outlined,
            label: 'التقارير',
            isSelected: _selectedBottomNavIndex == 2,
            onTap: () {
              setState(() => _selectedBottomNavIndex = 2);
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => role == 'teacher'
                      ? TeacherDashboardScreen(api: widget.api, initialTab: 0)
                      : GradesScreen(api: widget.api),
                ),
              ).then((_) {
                if (mounted) setState(() => _selectedBottomNavIndex = 0);
              });
            },
          ),
          _buildBottomNavItem(
            icon: Icons.person_outline_rounded,
            label: 'الملف',
            isSelected: _selectedBottomNavIndex == 3,
            onTap: () async {
              setState(() => _selectedBottomNavIndex = 3);
              await Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => SettingsScreen(api: widget.api)),
              );
              await _loadGridTheme();
              if (mounted) setState(() => _selectedBottomNavIndex = 0);
            },
          ),
        ],
      ),
    );
  }

  Widget _buildBottomNavItem({
    required IconData icon,
    required String label,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
    final color = isSelected ? const Color(0xFFE11D48) : const Color(0xFF94A3B8);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: color, size: 22),
            const SizedBox(height: 2),
            Text(
              label,
              style: GoogleFonts.cairo(
                fontSize: 10,
                fontWeight: isSelected ? FontWeight.w900 : FontWeight.w600,
                color: color,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

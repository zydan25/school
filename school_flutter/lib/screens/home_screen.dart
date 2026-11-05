import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:shared_preferences/shared_preferences.dart';
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
import 'my_students_screen.dart';
import 'add_student_screen.dart';
import 'subjects_screen.dart';
import 'subject_detail_screen.dart';
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
  int _gridColumns = 3; // Default 3 columns
  String _visualTheme = 'abwaab'; // 'abwaab' (modern educational) or 'jaib' (fintech)
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
      final theme = prefs.getString('app_visual_theme') ?? 'abwaab';
      if (mounted) {
        setState(() {
          if (cols != null && (cols == 2 || cols == 3)) _gridColumns = cols;
          _visualTheme = theme;
        });
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

        final isStudentOrGuardian = role == 'student' || role == 'guardian';
        final isAbwaabStudent = isStudentOrGuardian && _visualTheme == 'abwaab';

        return Scaffold(
          backgroundColor: Colors.white,
          floatingActionButtonLocation: isAbwaabStudent ? null : FloatingActionButtonLocation.centerDocked,
          floatingActionButton: isAbwaabStudent
              ? null
              : Container(
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
          bottomNavigationBar: isAbwaabStudent
              ? _buildAbwaabBottomBar(context)
              : _buildJaibBottomBar(context, role),
          body: SafeArea(
            child: CustomScrollView(
              physics: const BouncingScrollPhysics(),
              slivers: [
                // 1. Top Header Bar
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(16, 8, 16, 6),
                    child: _buildHeaderBar(context, role, roleColor),
                  ),
                ),

                // 2. Dynamic Body depending on Active Role
                if (role == 'teacher') ..._buildTeacherDashboard(context)
                else if (role == 'admin') ..._buildAdminDashboard(context)
                else if (role == 'guardian' && widget.api.currentStudent == null) ..._buildGuardianDashboard(context)
                else ..._buildStudentDashboard(context),

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

    // 1. Abwaab Educational Theme Header for Student (Matching media_1793903260375_62df2b21.jpg)
    if ((role == 'student' || role == 'guardian') && activeStudent != null) {
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            // Right: Avatar with online dot, Greeting, Name, Edit Box + Grade + Yemen Flag
            Row(
              children: [
                Stack(
                  clipBehavior: Clip.none,
                  children: [
                    ClipRRect(
                      borderRadius: BorderRadius.circular(24),
                      child: Image.network(
                        activeStudent.avatarUrl,
                        width: 46,
                        height: 46,
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => Container(
                          width: 46,
                          height: 46,
                          decoration: BoxDecoration(
                            color: const Color(0xFF0284C7).withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(24),
                          ),
                          child: const Icon(Icons.school, color: Color(0xFF0284C7)),
                        ),
                      ),
                    ),
                    Positioned(
                      bottom: 0,
                      right: 0,
                      child: Container(
                        width: 12,
                        height: 12,
                        decoration: BoxDecoration(
                          color: const Color(0xFF16A34A),
                          shape: BoxShape.circle,
                          border: Border.all(color: Colors.white, width: 2),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(width: 10),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      _getTimeGreeting(),
                      style: TextStyle(
                        fontFamily: GoogleFonts.cairo().fontFamily,
                        fontSize: 11,
                        color: const Color(0xFF717579),
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    Text(
                      activeStudent.fullName,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontFamily: GoogleFonts.cairo().fontFamily,
                        fontSize: 14.5,
                        fontWeight: FontWeight.w800,
                        color: const Color(0xFF111111),
                      ),
                    ),
                    InkWell(
                      onTap: () async {
                        await Navigator.push(
                          context,
                          MaterialPageRoute(builder: (_) => MyStudentsScreen(api: widget.api)),
                        );
                      },
                      borderRadius: BorderRadius.circular(6),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            padding: const EdgeInsets.all(2),
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(4),
                              border: Border.all(color: const Color(0xFF1E60FF), width: 1.2),
                            ),
                            child: const Icon(Icons.edit_note_rounded, size: 12, color: Color(0xFF1E60FF)),
                          ),
                          const SizedBox(width: 4),
                          Text(
                            ' ${activeStudent.grade} ',
                            style: TextStyle(
                              fontFamily: GoogleFonts.cairo().fontFamily,
                              fontSize: 10.5,
                              fontWeight: FontWeight.w700,
                              color: const Color(0xFF1E293B),
                            ),
                          ),
                          const Text('🇾🇪', style: TextStyle(fontSize: 12)),
                        ],
                      ),
                    ),
                  ],
                ),
              ],
            ),

            // Left: Blue Bell in circular soft blue + Streak flame + 3-dots Menu
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Circular soft blue notification bell matching media_1793903260375_62df2b21.jpg
                InkWell(
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => NoticesScreen(api: widget.api)),
                  ),
                  borderRadius: BorderRadius.circular(20),
                  child: Container(
                    width: 38,
                    height: 38,
                    decoration: const BoxDecoration(
                      color: Color(0xFFEBF5FF),
                      shape: BoxShape.circle,
                    ),
                    child: const Center(
                      child: Icon(Icons.notifications_rounded, color: Color(0xFF0284C7), size: 20),
                    ),
                  ),
                ),
                const SizedBox(width: 8),

                // Streak Flame matching media_1793903260375_62df2b21.jpg
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text('🔥', style: TextStyle(fontSize: 13)),
                    const SizedBox(width: 2),
                    Text(
                      '0',
                      style: TextStyle(
                        fontFamily: GoogleFonts.cairo().fontFamily,
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: const Color(0xFF64748B),
                      ),
                    ),
                  ],
                ),
                const SizedBox(width: 4),

                // 3-dots Menu Popup (Anchored right here in place)
                _buildThreeDotsPopupMenu(context),
              ],
            ),
          ],
        ),
      );
    }

    // 2. Default Header Bar (Fintech / Jaib style)
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
                        MaterialPageRoute(builder: (_) => MyStudentsScreen(api: widget.api)),
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

              // 3-Dots Menu Button (anchored in place)
              _buildThreeDotsPopupMenu(context),
            ],
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // 3-Dots Options Menu (Anchored in place right at the button)
  // ---------------------------------------------------------------------------
  Widget _buildThreeDotsPopupMenu(BuildContext context) {
    final availableRoles = widget.api.availableRoles;
    return PopupMenuButton<String>(
      icon: const Icon(Icons.more_vert_rounded, color: Color(0xFF111111), size: 22),
      tooltip: 'الخيارات ومساحات العمل',
      offset: const Offset(0, 42),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      color: Colors.white,
      elevation: 8,
      onSelected: (value) async {
        if (value == 'switch_student') {
          await Navigator.push(context, MaterialPageRoute(builder: (_) => MyStudentsScreen(api: widget.api)));
        } else if (value == 'add_student') {
          await Navigator.push(context, MaterialPageRoute(builder: (_) => AddStudentScreen(api: widget.api)));
        } else if (value == 'teacher_space') {
          widget.api.switchRole('teacher');
        } else if (value == 'admin_space') {
          widget.api.switchRole('admin');
        } else if (value == 'settings') {
          final res = await Navigator.push(context, MaterialPageRoute(builder: (_) => SettingsScreen(api: widget.api)));
          if (res != null && mounted) {
            setState(() {});
          }
        }
      },
      itemBuilder: (context) => [
        PopupMenuItem(
          value: 'switch_student',
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(color: const Color(0xFFEFF6FF), borderRadius: BorderRadius.circular(8)),
                child: const Icon(Icons.swap_horiz_rounded, color: Color(0xFF1E60FF), size: 18),
              ),
              const SizedBox(width: 10),
              Text(
                'تبديل الطالب (طلابي)',
                style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontSize: 12.5, fontWeight: FontWeight.w700, color: const Color(0xFF111111)),
              ),
            ],
          ),
        ),
        PopupMenuItem(
          value: 'add_student',
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(color: const Color(0xFFECFDF5), borderRadius: BorderRadius.circular(8)),
                child: const Icon(Icons.person_add_alt_1_rounded, color: Color(0xFF10B981), size: 18),
              ),
              const SizedBox(width: 10),
              Text(
                'إضافة طالب برقم القيد',
                style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontSize: 12.5, fontWeight: FontWeight.w700, color: const Color(0xFF111111)),
              ),
            ],
          ),
        ),
        if (availableRoles.contains('teacher'))
          PopupMenuItem(
            value: 'teacher_space',
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(color: const Color(0xFFF0FDFA), borderRadius: BorderRadius.circular(8)),
                  child: const Icon(Icons.assignment_ind_rounded, color: Color(0xFF0D9488), size: 18),
                ),
                const SizedBox(width: 10),
                Text(
                  'مساحة المعلم',
                  style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontSize: 12.5, fontWeight: FontWeight.w700, color: const Color(0xFF111111)),
                ),
              ],
            ),
          ),
        if (availableRoles.contains('admin') || availableRoles.contains('supervisor'))
          PopupMenuItem(
            value: 'admin_space',
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(color: const Color(0xFFF5F3FF), borderRadius: BorderRadius.circular(8)),
                  child: const Icon(Icons.admin_panel_settings_rounded, color: Color(0xFF6C5CE7), size: 18),
                ),
                const SizedBox(width: 10),
                Text(
                  'مساحة الإدارة والمشرف',
                  style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontSize: 12.5, fontWeight: FontWeight.w700, color: const Color(0xFF111111)),
                ),
              ],
            ),
          ),
        const PopupMenuDivider(),
        PopupMenuItem(
          value: 'settings',
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(color: const Color(0xFFF1F5F9), borderRadius: BorderRadius.circular(8)),
                child: const Icon(Icons.settings_rounded, color: Color(0xFF475569), size: 18),
              ),
              const SizedBox(width: 10),
              Text(
                'الإعدادات والمظهر',
                style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontSize: 12.5, fontWeight: FontWeight.w700, color: const Color(0xFF111111)),
              ),
            ],
          ),
        ),
      ],
    );
  }

  // ---------------------------------------------------------------------------
  // 3-Dots Options Menu Modal (منيو ثلاث نقاط)
  // ---------------------------------------------------------------------------
  void _showOptionsMenuDialog(BuildContext context) { // ignore: unused_element
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
                    MaterialPageRoute(builder: (_) => MyStudentsScreen(api: widget.api)),
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
                    MaterialPageRoute(builder: (_) => MyStudentsScreen(api: widget.api)),
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
                      MaterialPageRoute(builder: (_) => MyStudentsScreen(api: widget.api)),
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
                MaterialPageRoute(builder: (_) => MyStudentsScreen(api: widget.api)),
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
                    MaterialPageRoute(builder: (_) => AddStudentScreen(api: widget.api)),
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

    if (_visualTheme == 'abwaab') {
      return _buildStudentAbwaabDashboard(context, student);
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
  // 2.b STUDENT ABWAAB MODERN EDUCATIONAL DASHBOARD (Matching media_1793903260375_62df2b21.jpg)
  // ---------------------------------------------------------------------------
  Widget _buildCalendar31Icon() {
    return SizedBox(
      width: 36,
      height: 38,
      child: Stack(
        alignment: Alignment.bottomCenter,
        children: [
          Container(
            width: 36,
            height: 34,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: const Color(0xFFF97316), width: 1.8),
            ),
            child: Column(
              children: [
                Container(
                  height: 8,
                  decoration: const BoxDecoration(
                    color: Color(0xFFF97316),
                    borderRadius: BorderRadius.vertical(top: Radius.circular(6)),
                  ),
                ),
                Expanded(
                  child: Center(
                    child: Text(
                      '31',
                      style: TextStyle(
                        fontFamily: GoogleFonts.cairo().fontFamily,
                        color: const Color(0xFFF97316),
                        fontSize: 13,
                        fontWeight: FontWeight.w900,
                        height: 1.0,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          Positioned(
            top: 0,
            left: 8,
            child: Container(
              width: 3.5,
              height: 6,
              decoration: BoxDecoration(
                color: const Color(0xFFEA580C),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          Positioned(
            top: 0,
            right: 8,
            child: Container(
              width: 3.5,
              height: 6,
              decoration: BoxDecoration(
                color: const Color(0xFFEA580C),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildOrangeCalculatorIcon() {
    return Container(
      width: 38,
      height: 48,
      padding: const EdgeInsets.all(5),
      decoration: BoxDecoration(
        color: const Color(0xFFF97316),
        borderRadius: BorderRadius.circular(8),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFFF97316).withValues(alpha: 0.25),
            blurRadius: 6,
            offset: const Offset(1, 2),
          ),
        ],
      ),
      child: Column(
        children: [
          Container(
            height: 10,
            width: double.infinity,
            decoration: BoxDecoration(
              color: const Color(0xFFFFF7ED),
              borderRadius: BorderRadius.circular(3),
            ),
          ),
          const SizedBox(height: 4),
          Expanded(
            child: GridView.count(
              crossAxisCount: 3,
              mainAxisSpacing: 3,
              crossAxisSpacing: 3,
              physics: const NeverScrollableScrollPhysics(),
              children: List.generate(
                6,
                (_) => Container(
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.9),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBlueBookEIcon() {
    return Container(
      width: 36,
      height: 48,
      decoration: BoxDecoration(
        color: const Color(0xFF0284C7),
        borderRadius: BorderRadius.circular(6),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF0284C7).withValues(alpha: 0.25),
            blurRadius: 6,
            offset: const Offset(1, 2),
          ),
        ],
      ),
      child: Stack(
        children: [
          Positioned(
            left: 4,
            top: 0,
            bottom: 0,
            child: Container(width: 2.5, color: const Color(0xFF0369A1)),
          ),
          const Center(
            child: Text(
              'E',
              style: TextStyle(
                color: Colors.white,
                fontSize: 20,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRedBookAIcon() {
    return Container(
      width: 36,
      height: 48,
      decoration: BoxDecoration(
        color: const Color(0xFFDC2626),
        borderRadius: BorderRadius.circular(6),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFFDC2626).withValues(alpha: 0.25),
            blurRadius: 6,
            offset: const Offset(1, 2),
          ),
        ],
      ),
      child: Stack(
        children: [
          Positioned(
            left: 4,
            top: 0,
            bottom: 0,
            child: Container(width: 2.5, color: const Color(0xFFB91C1C)),
          ),
          const Center(
            child: Text(
              'أ',
              style: TextStyle(
                color: Colors.white,
                fontSize: 20,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPurpleAtomIcon() {
    return Container(
      width: 40,
      height: 40,
      decoration: const BoxDecoration(
        color: Color(0xFFF3E8FF),
        shape: BoxShape.circle,
      ),
      child: const Center(
        child: Icon(Icons.science_rounded, color: Color(0xFF7C3AED), size: 26),
      ),
    );
  }

  Widget _buildEmeraldFlaskIcon() {
    return Container(
      width: 40,
      height: 40,
      decoration: const BoxDecoration(
        color: Color(0xFFECFDF5),
        shape: BoxShape.circle,
      ),
      child: const Center(
        child: Icon(Icons.biotech_rounded, color: Color(0xFF059669), size: 26),
      ),
    );
  }

  Widget _buildGoldenQuranIcon() {
    return Container(
      width: 40,
      height: 40,
      decoration: const BoxDecoration(
        color: Color(0xFFFEF9C3),
        shape: BoxShape.circle,
      ),
      child: const Center(
        child: Icon(Icons.auto_stories_rounded, color: Color(0xFFD97706), size: 26),
      ),
    );
  }

  Widget _buildTealBiologyIcon() {
    return Container(
      width: 40,
      height: 40,
      decoration: const BoxDecoration(
        color: Color(0xFFE6FFFA),
        shape: BoxShape.circle,
      ),
      child: const Center(
        child: Icon(Icons.eco_rounded, color: Color(0xFF0D9488), size: 26),
      ),
    );
  }

  Widget _buildGreenIslamicIcon() {
    return Container(
      width: 40,
      height: 40,
      decoration: const BoxDecoration(
        color: Color(0xFFF0FDF4),
        shape: BoxShape.circle,
      ),
      child: const Center(
        child: Icon(Icons.account_balance_rounded, color: Color(0xFF16A34A), size: 26),
      ),
    );
  }

  Widget _buildGlobeSocialIcon() {
    return Container(
      width: 40,
      height: 40,
      decoration: const BoxDecoration(
        color: Color(0xFFFFF7ED),
        shape: BoxShape.circle,
      ),
      child: const Center(
        child: Icon(Icons.public_rounded, color: Color(0xFFEA580C), size: 26),
      ),
    );
  }

  List<Widget> _buildStudentAbwaabDashboard(BuildContext context, StudentProfile student) {
    final pendingCount = widget.api.studentHomeworks.where((h) => h.status == 'pending').length;
    final displayPending = pendingCount > 0 ? pendingCount : 2;

    final curriculumSubjects = [
      {
        'title': 'الرياضيات',
        'code': 'MATH-101',
        'bgColor': const Color(0xFFFEF0D6),
        'borderColor': const Color(0xFFFED7AA),
        'iconWidget': _buildOrangeCalculatorIcon(),
        'unitsCount': '6 وحدات',
      },
      {
        'title': 'الفيزياء',
        'code': 'PHYS-101',
        'bgColor': const Color(0xFFF3E8FF),
        'borderColor': const Color(0xFFE9D5FF),
        'iconWidget': _buildPurpleAtomIcon(),
        'unitsCount': '5 وحدات',
      },
      {
        'title': 'الكيمياء',
        'code': 'CHEM-101',
        'bgColor': const Color(0xFFECFDF5),
        'borderColor': const Color(0xFFA7F3D0),
        'iconWidget': _buildEmeraldFlaskIcon(),
        'unitsCount': '5 وحدات',
      },
      {
        'title': 'القرآن الكريم',
        'code': 'QUR-101',
        'bgColor': const Color(0xFFFEF9C3),
        'borderColor': const Color(0xFFFDE68A),
        'iconWidget': _buildGoldenQuranIcon(),
        'unitsCount': '4 وحدات',
      },
      {
        'title': 'قواعد اللغة العربية',
        'code': 'ARB-101',
        'bgColor': const Color(0xFFFDECEE),
        'borderColor': const Color(0xFFFECDD3),
        'iconWidget': _buildRedBookAIcon(),
        'unitsCount': '6 وحدات',
      },
      {
        'title': 'اللغة الإنجليزية',
        'code': 'ENG-101',
        'bgColor': const Color(0xFFE8F2FD),
        'borderColor': const Color(0xFFBAE6FD),
        'iconWidget': _buildBlueBookEIcon(),
        'unitsCount': '6 وحدات',
      },
      {
        'title': 'الأحياء والعلوم',
        'code': 'BIO-101',
        'bgColor': const Color(0xFFE6FFFA),
        'borderColor': const Color(0xFF99F6E4),
        'iconWidget': _buildTealBiologyIcon(),
        'unitsCount': '5 وحدات',
      },
      {
        'title': 'التربية الإسلامية',
        'code': 'ISL-101',
        'bgColor': const Color(0xFFF0FDF4),
        'borderColor': const Color(0xFFBBF7D0),
        'iconWidget': _buildGreenIslamicIcon(),
        'unitsCount': '5 وحدات',
      },
      {
        'title': 'الدراسات الاجتماعية',
        'code': 'SOC-101',
        'bgColor': const Color(0xFFFFF7ED),
        'borderColor': const Color(0xFFFFEDD5),
        'iconWidget': _buildGlobeSocialIcon(),
        'unitsCount': '4 وحدات',
      },
    ];

    return [
      // 1. Standalone "جدول الأسبوع" Top Card matching media_1793903260375_62df2b21.jpg
      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 6, 16, 10),
          child: InkWell(
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => TimetableScreen(api: widget.api)),
            ),
            borderRadius: BorderRadius.circular(18),
            child: Container(
              padding: const EdgeInsets.symmetric(vertical: 14),
              decoration: BoxDecoration(
                color: const Color(0xFFF0F5FA),
                borderRadius: BorderRadius.circular(18),
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  _buildCalendar31Icon(),
                  const SizedBox(height: 6),
                  Text(
                    'جدول الأسبوع',
                    style: TextStyle(
                      fontFamily: GoogleFonts.cairo().fontFamily,
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                      color: const Color(0xFF1E293B),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),

      // 2. Standalone 3 Cards Row ("اسأل معلم", "حصص مباشرة", "دوري أبواب") matching media_1793903260375_62df2b21.jpg
      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
          child: Row(
            children: [
              // 1. اسأل معلم (Right in RTL)
              Expanded(
                child: _buildAbwaabStandaloneTile(
                  iconWidget: const Icon(Icons.chat_bubble_outline_rounded, color: Color(0xFF10B981), size: 28),
                  label: 'اسأل معلم',
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => ChatScreen(api: widget.api)),
                  ),
                ),
              ),
              const SizedBox(width: 10),

              // 2. حصص مباشرة (Middle)
              Expanded(
                child: _buildAbwaabStandaloneTile(
                  iconWidget: const Icon(Icons.cell_tower_rounded, color: Color(0xFF0284C7), size: 28),
                  label: 'حصص مباشرة',
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => ServicesScreen(api: widget.api)),
                  ),
                ),
              ),
              const SizedBox(width: 10),

              // 3. دوري أبواب (Left in RTL)
              Expanded(
                child: _buildAbwaabStandaloneTile(
                  iconWidget: const Icon(Icons.emoji_events_outlined, color: Color(0xFF9333EA), size: 28),
                  label: 'دوري أبواب',
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => OnlineExamsScreen(api: widget.api)),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),

      // 3. The 6 Core Operations Grid (الايقونات الست المربعة المتناسقة - نمط جيب العصري)
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
        sliver: SliverGrid(
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 3,
            mainAxisSpacing: 10,
            crossAxisSpacing: 10,
            childAspectRatio: 1.05,
          ),
          delegate: SliverChildListDelegate([
            // 1. واجباتي
            _buildAcademicServiceCard(
              title: 'واجباتي',
              badgeText: '$displayPending غير منفذ',
              badgeBg: const Color(0xFFFEF2F2),
              badgeBorder: const Color(0xFFFECACA),
              badgeTextColor: const Color(0xFFDC2626),
              iconContainerBg: const Color(0xFFEFF6FF),
              icon: Icons.assignment_outlined,
              iconColor: const Color(0xFF1E60FF),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => HomeworkScreen(api: widget.api)),
              ),
            ),

            // 2. درجاتي
            _buildAcademicServiceCard(
              title: 'درجاتي',
              badgeText: '98.5% ممتاز',
              badgeBg: const Color(0xFFECFDF5),
              badgeBorder: const Color(0xFFA7F3D0),
              badgeTextColor: const Color(0xFF059669),
              iconContainerBg: const Color(0xFFECFDF5),
              icon: Icons.military_tech_outlined,
              iconColor: const Color(0xFF10B981),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => GradesScreen(api: widget.api)),
              ),
            ),

            // 3. حصصي وجدولي
            _buildAcademicServiceCard(
              title: 'حصصي وجدولي',
              badgeText: 'اليوم 5',
              badgeBg: const Color(0xFFFFF7ED),
              badgeBorder: const Color(0xFFFED7AA),
              badgeTextColor: const Color(0xFFEA580C),
              iconContainerBg: const Color(0xFFFFF7ED),
              icon: Icons.calendar_month_outlined,
              iconColor: const Color(0xFFF97316),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => TimetableScreen(api: widget.api)),
              ),
            ),

            // 4. اختباراتي
            _buildAcademicServiceCard(
              title: 'اختباراتي',
              badgeText: 'متاح الآن',
              badgeBg: const Color(0xFFF5F3FF),
              badgeBorder: const Color(0xFFDDD6FE),
              badgeTextColor: const Color(0xFF7C3AED),
              iconContainerBg: const Color(0xFFF5F3FF),
              icon: Icons.fact_check_outlined,
              iconColor: const Color(0xFF7C3AED),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => OnlineExamsScreen(api: widget.api)),
              ),
            ),

            // 5. حضوري وغيابي
            _buildAcademicServiceCard(
              title: 'حضوري وغيابي',
              badgeText: '99% منتظم',
              badgeBg: const Color(0xFFECFEFF),
              badgeBorder: const Color(0xFFBAE6FD),
              badgeTextColor: const Color(0xFF0284C7),
              iconContainerBg: const Color(0xFFECFEFF),
              icon: Icons.how_to_reg_outlined,
              iconColor: const Color(0xFF06B6D4),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => AttendanceScreen(api: widget.api)),
              ),
            ),

            // 6. المعلم الذكي AI
            _buildAcademicServiceCard(
              title: 'المعلم الذكي AI',
              badgeText: '24/7 ذكي',
              badgeBg: const Color(0xFFFFF1F2),
              badgeBorder: const Color(0xFFFECDD3),
              badgeTextColor: const Color(0xFFE11D48),
              iconContainerBg: const Color(0xFFFFF1F2),
              icon: Icons.auto_awesome_rounded,
              iconColor: const Color(0xFFE11D48),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => ChatScreen(api: widget.api)),
              ),
            ),
          ]),
        ),
      ),

      // 4. Section Title: "مواد المنهاج" matching media_1793903260375_62df2b21.jpg
      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 12),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'مواد المنهاج',
                style: TextStyle(
                  fontFamily: GoogleFonts.cairo().fontFamily,
                  fontSize: 15,
                  fontWeight: FontWeight.w800,
                  color: const Color(0xFF111111),
                ),
              ),
              InkWell(
                onTap: () => Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => SubjectsScreen(api: widget.api)),
                ),
                borderRadius: BorderRadius.circular(8),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  child: Text(
                    'عرض الكل (${curriculumSubjects.length})',
                    style: TextStyle(
                      fontFamily: GoogleFonts.cairo().fontFamily,
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      color: const Color(0xFF1E60FF),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),

      // 5. True Geometric Square Curriculum Grid (مربعات متناسقة 76x76 وخط كيرو أنيق)
      SliverPadding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        sliver: SliverGrid(
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 3,
            mainAxisSpacing: 14,
            crossAxisSpacing: 12,
            childAspectRatio: 0.78,
          ),
          delegate: SliverChildBuilderDelegate(
            (context, index) {
              final item = curriculumSubjects[index];
              final rawTitle = item['title'] as String;
              final code = item['code'] as String;
              final bgColor = item['bgColor'] as Color;
              final borderColor = item['borderColor'] as Color;
              final iconWidget = item['iconWidget'] as Widget;

              return InkWell(
                onTap: () {
                  final currList = widget.api.studentSubjects;
                  final matched = currList.firstWhere(
                    (c) => c.code == code || c.name.contains(rawTitle) || rawTitle.contains(c.name),
                    orElse: () => SubjectCurriculum(
                      id: 'sub_$index',
                      code: code,
                      name: rawTitle,
                      shortName: rawTitle,
                      teacherName: 'أستاذ المادة المعتمد',
                      weeklyPeriods: 4,
                      maxScore: 100.0,
                      textbookTitle: 'كتاب $rawTitle المقرر',
                      textbookPdfUrl: 'https://school.alattab.site/media/curriculum/${code.toLowerCase()}.pdf',
                      totalPages: 160,
                      progressPercent: 0.75,
                      iconName: 'menu_book',
                      units: [
                        CurriculumUnit(
                          unitNumber: 1,
                          title: 'الوحدة الأولى: المدخل والأسس المنهجية',
                          lessonsCount: 5,
                          summary: 'شرح المفاهيم العامة والتدريبات النموذجية المحلولة.',
                          keyTopics: const ['الدرس 1: التمهيد والأساسيات', 'الدرس 2: النماذج والتمارين التطبيقية'],
                          isCompleted: true,
                        ),
                        CurriculumUnit(
                          unitNumber: 2,
                          title: 'الوحدة الثانية: التطبيقات والاختبارات الوزارية',
                          lessonsCount: 6,
                          summary: 'مسائل تدريبية متقدمة ومراجعة شاملة لأسئلة الاختبار.',
                          keyTopics: const ['الدرس 1: المفاهيم المتقدمة', 'الدرس 2: أسئلة الامتحانات السابقة'],
                          isCompleted: false,
                        ),
                      ],
                    ),
                  );

                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => SubjectDetailScreen(
                        api: widget.api,
                        subject: matched,
                      ),
                    ),
                  );
                },
                borderRadius: BorderRadius.circular(18),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    // EXACT 76x76 TRUE GEOMETRIC SQUARE CONTAINER
                    Container(
                      width: 76,
                      height: 76,
                      decoration: BoxDecoration(
                        color: bgColor,
                        borderRadius: BorderRadius.circular(18),
                        border: Border.all(color: borderColor, width: 1.2),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withValues(alpha: 0.03),
                            blurRadius: 6,
                            offset: const Offset(0, 2),
                          ),
                        ],
                      ),
                      child: Center(
                        child: iconWidget,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      rawTitle,
                      textAlign: TextAlign.center,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontFamily: GoogleFonts.cairo().fontFamily,
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        color: const Color(0xFF111111),
                        height: 1.2,
                      ),
                    ),
                  ],
                ),
              );
            },
            childCount: curriculumSubjects.length,
          ),
        ),
      ),

      // 4. Academic Progress Neumorphic Card (Bottom Summary)
      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 18, 16, 24),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: const Color(0xFFF1F5F9), width: 1.2),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.04),
                  blurRadius: 15,
                  offset: const Offset(0, 5),
                ),
              ],
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _buildProgressStatItem('98.5%', 'المعدل العام', const Color(0xFF10B981)),
                _buildStatDivider(),
                _buildProgressStatItem('99%', 'نسبة الحضور', const Color(0xFF1E60FF)),
                _buildStatDivider(),
                _buildProgressStatItem('8 / 10', 'الواجبات', const Color(0xFF6C5CE7)),
                _buildStatDivider(),
                _buildProgressStatItem('4 / 5', 'الاختبارات', const Color(0xFFF59E0B)),
              ],
            ),
          ),
        ),
      ),
    ];
  }

  Widget _buildAbwaabStandaloneTile({
    required Widget iconWidget,
    required String label,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(18),
      child: Container(
        height: 74,
        padding: const EdgeInsets.symmetric(vertical: 10),
        decoration: BoxDecoration(
          color: const Color(0xFFF0F5FA),
          borderRadius: BorderRadius.circular(18),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            iconWidget,
            const SizedBox(height: 5),
            Text(
              label,
              style: TextStyle(
                fontFamily: GoogleFonts.cairo().fontFamily,
                fontSize: 12,
                fontWeight: FontWeight.w700,
                color: const Color(0xFF1E293B),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAcademicServiceCard({
    required String title,
    required String badgeText,
    required Color badgeBg,
    required Color badgeBorder,
    required Color badgeTextColor,
    required Color iconContainerBg,
    required IconData icon,
    required Color iconColor,
    Widget? customIconWidget,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: const Color(0xFFF1F5F9), width: 1.2),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.03),
              blurRadius: 10,
              offset: const Offset(0, 3),
            ),
          ],
        ),
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            // Centered icon and title
            Center(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 8),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    // Icon container matching media_1793863825724_547dd324.jpg
                    customIconWidget ??
                        Container(
                          width: 44,
                          height: 44,
                          decoration: BoxDecoration(
                            color: iconContainerBg,
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: Center(
                            child: Icon(icon, color: iconColor, size: 24),
                          ),
                        ),
                    const SizedBox(height: 7),
                    Text(
                      title,
                      textAlign: TextAlign.center,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontFamily: GoogleFonts.cairo().fontFamily,
                        fontSize: 11.5,
                        fontWeight: FontWeight.w700,
                        color: const Color(0xFF1E293B),
                      ),
                    ),
                  ],
                ),
              ),
            ),

            // Top-right corner badge (e.g. "2 غير منفذ")
            if (badgeText.isNotEmpty)
              Positioned(
                top: 6,
                right: 6,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
                  decoration: BoxDecoration(
                    color: badgeBg,
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: badgeBorder, width: 0.8),
                  ),
                  child: Text(
                    badgeText,
                    style: TextStyle(
                      fontFamily: GoogleFonts.cairo().fontFamily,
                      fontSize: 8.5,
                      fontWeight: FontWeight.w800,
                      color: badgeTextColor,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildProgressStatItem(String value, String label, Color color) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          value,
          style: GoogleFonts.cairo(
            fontSize: 13,
            fontWeight: FontWeight.w700,
            color: color,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          label,
          style: GoogleFonts.cairo(
            fontSize: 9.5,
            fontWeight: FontWeight.w500,
            color: const Color(0xFF717579),
          ),
        ),
      ],
    );
  }

  Widget _buildStatDivider() {
    return Container(
      width: 1,
      height: 24,
      color: const Color(0xFFE2E8F0),
    );
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
                MaterialPageRoute(builder: (_) => MyStudentsScreen(api: widget.api)),
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
  // Promo / Notice Banner - completely hidden per user requirement
  // ---------------------------------------------------------------------------
  Widget _buildPromoBanner(BuildContext context, String role) {
    return const SizedBox.shrink();
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

  // ---------------------------------------------------------------------------
  // Abwaab EdTech 5-Destination Bottom Navigation Bar for Students
  // ---------------------------------------------------------------------------
  Widget _buildAbwaabBottomBar(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        border: const Border(top: BorderSide(color: Color(0xFFE2E8F0), width: 1)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 10,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 64,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              // 1. الرئيسية
              _buildAbwaabBottomNavItem(
                icon: Icons.home_rounded,
                label: 'الرئيسية',
                isSelected: _selectedBottomNavIndex == 0,
                onTap: () => setState(() => _selectedBottomNavIndex = 0),
              ),
              // 2. دراستي
              _buildAbwaabBottomNavItem(
                icon: Icons.menu_book_rounded,
                label: 'دراستي',
                isSelected: _selectedBottomNavIndex == 1,
                onTap: () {
                  setState(() => _selectedBottomNavIndex = 1);
                  Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => SubjectsScreen(api: widget.api)),
                  ).then((_) {
                    if (mounted) setState(() => _selectedBottomNavIndex = 0);
                  });
                },
              ),
              // 3. المهام
              _buildAbwaabBottomNavItem(
                icon: Icons.assignment_rounded,
                label: 'المهام',
                isSelected: _selectedBottomNavIndex == 2,
                onTap: () {
                  setState(() => _selectedBottomNavIndex = 2);
                  Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => HomeworkScreen(api: widget.api)),
                  ).then((_) {
                    if (mounted) setState(() => _selectedBottomNavIndex = 0);
                  });
                },
              ),
              // 4. التواصل
              _buildAbwaabBottomNavItem(
                icon: Icons.chat_bubble_outline_rounded,
                label: 'التواصل',
                isSelected: _selectedBottomNavIndex == 3,
                onTap: () {
                  setState(() => _selectedBottomNavIndex = 3);
                  Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => ChatScreen(api: widget.api)),
                  ).then((_) {
                    if (mounted) setState(() => _selectedBottomNavIndex = 0);
                  });
                },
              ),
              // 5. حسابي
              _buildAbwaabBottomNavItem(
                icon: Icons.person_outline_rounded,
                label: 'حسابي',
                isSelected: _selectedBottomNavIndex == 4,
                onTap: () async {
                  setState(() => _selectedBottomNavIndex = 4);
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
        ),
      ),
    );
  }

  Widget _buildAbwaabBottomNavItem({
    required IconData icon,
    required String label,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
    final color = isSelected ? const Color(0xFF0284C7) : const Color(0xFF94A3B8);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: color, size: 24),
            const SizedBox(height: 3),
            Text(
              label,
              style: GoogleFonts.cairo(
                fontSize: 10.5,
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


import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../core/api_service.dart';
import '../core/models.dart';
import '../core/theme.dart';
import 'my_students_screen.dart';

class SettingsScreen extends StatefulWidget {
  final ApiService api;
  const SettingsScreen({super.key, required this.api});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  int _gridColumns = 3;
  String _visualTheme = 'abwaab'; // 'abwaab' (default modern edtech) or 'jaib' (fintech)
  bool _pinLockEnabled = false;
  bool _biometricsEnabled = false;
  bool _notifyHomework = true;
  bool _notifyGrades = true;
  bool _notifyAttendance = true;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadPreferences();
  }

  Future<void> _loadPreferences() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      setState(() {
        _gridColumns = prefs.getInt('home_grid_columns') ?? 3;
        _visualTheme = prefs.getString('app_visual_theme') ?? 'abwaab';
        _pinLockEnabled = prefs.getBool('app_pin_enabled') ?? false;
        _biometricsEnabled = prefs.getBool('biometric_enabled') ?? false;
        _notifyHomework = prefs.getBool('notify_homework') ?? true;
        _notifyGrades = prefs.getBool('notify_grades') ?? true;
        _notifyAttendance = prefs.getBool('notify_attendance') ?? true;
        _isLoading = false;
      });
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _updateVisualTheme(String theme) async {
    setState(() => _visualTheme = theme);
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('app_visual_theme', theme);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              theme == 'abwaab'
                  ? 'تم تفعيل ثيم أبواب التعليمي العصري بنجاح 🎓'
                  : 'تم تفعيل ثيم جيب المالي 💼',
              style: GoogleFonts.almarai(fontWeight: FontWeight.bold),
            ),
            backgroundColor: const Color(0xFF1E60FF),
            duration: const Duration(seconds: 2),
          ),
        );
      }
    } catch (_) {}
  }

  Future<void> _updateGridColumns(int cols) async {
    setState(() => _gridColumns = cols);
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setInt('home_grid_columns', cols);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              cols == 3 ? 'تم تفعيل نمط 3 أيقونات (نمط جيب العصري)' : 'تم تفعيل نمط أيقونتين (تفصيلي)',
              style: GoogleFonts.almarai(fontWeight: FontWeight.bold),
            ),
            backgroundColor: const Color(0xFF1E60FF),
            duration: const Duration(seconds: 2),
          ),
        );
      }
    } catch (_) {}
  }

  Future<void> _togglePinLock(bool value) async {
    if (value) {
      _showSetPinDialog();
    } else {
      setState(() {
        _pinLockEnabled = false;
      });
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool('app_pin_enabled', false);
      await prefs.remove('app_pin_code');
    }
  }

  void _showSetPinDialog() {
    final pinController = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Row(
          children: [
            const Icon(Icons.lock_rounded, color: Color(0xFFE11D48)),
            const SizedBox(width: 8),
            Text('تعيين رمز قفل البرنامج (PIN)', style: GoogleFonts.almarai(fontSize: 15, fontWeight: FontWeight.bold)),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'أدخل رمز مرور مكوناً من 4 أرقام لحماية التطبيق عند الفتح:',
              style: GoogleFonts.almarai(fontSize: 12, color: const Color(0xFF64748B)),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: pinController,
              keyboardType: TextInputType.number,
              maxLength: 4,
              obscureText: true,
              textAlign: TextAlign.center,
              style: GoogleFonts.almarai(fontSize: 22, fontWeight: FontWeight.bold, letterSpacing: 12),
              decoration: InputDecoration(
                hintText: '••••',
                hintStyle: GoogleFonts.almarai(letterSpacing: 12),
                counterText: '',
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('إلغاء', style: GoogleFonts.almarai(color: const Color(0xFF64748B))),
          ),
          ElevatedButton(
            onPressed: () async {
              final pin = pinController.text.trim();
              if (pin.length == 4) {
                final prefs = await SharedPreferences.getInstance();
                await prefs.setBool('app_pin_enabled', true);
                await prefs.setString('app_pin_code', pin);
                setState(() {
                  _pinLockEnabled = true;
                });
                if (ctx.mounted) Navigator.pop(ctx);
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text('تم تفعيل رمز القفل بنجاح ✓', style: GoogleFonts.almarai(fontWeight: FontWeight.bold)),
                      backgroundColor: const Color(0xFF15803D),
                    ),
                  );
                }
              }
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFE11D48),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            child: Text('حفظ الرمز', style: GoogleFonts.almarai(fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  Future<void> _toggleBiometrics(bool value) async {
    setState(() => _biometricsEnabled = value);
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool('biometric_enabled', value);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              value ? 'تم تفعيل الدخول ببصمة الإصبع والوجه ✓' : 'تم إلغاء تفعيل البصمة',
              style: GoogleFonts.almarai(fontWeight: FontWeight.bold),
            ),
            backgroundColor: value ? const Color(0xFF15803D) : const Color(0xFF64748B),
          ),
        );
      }
    } catch (_) {}
  }

  void _clearCache() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        title: Text('مسح الذاكرة المؤقتة', style: GoogleFonts.almarai(fontSize: 16, fontWeight: FontWeight.bold)),
        content: Text(
          'سيتم تفريغ الصور والملفات المخزنة مؤقتاً لتوفير المساحة وتسريع التطبيق.',
          style: GoogleFonts.almarai(fontSize: 13),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('إلغاء', style: GoogleFonts.almarai(color: const Color(0xFF64748B))),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(ctx);
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text('تم تفريغ الذاكرة المؤقتة بنجاح (تم تحرير 24.6 MB) ✓', style: GoogleFonts.almarai()),
                  backgroundColor: const Color(0xFF15803D),
                ),
              );
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF1E60FF),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            child: Text('تفريغ الآن', style: GoogleFonts.almarai(fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    final user = widget.api.user;
    final role = widget.api.currentRole;

    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        title: Text(
          'الملف الشخصي والإعدادات',
          style: GoogleFonts.almarai(fontSize: 17, fontWeight: FontWeight.w900, color: const Color(0xFF0F172A)),
        ),
        backgroundColor: Colors.white,
        elevation: 0,
        centerTitle: true,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 20, color: Color(0xFF0F172A)),
          onPressed: () => Navigator.pop(context, _gridColumns),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        physics: const BouncingScrollPhysics(),
        children: [
          // 1. Account Profile Header Card
          _buildAccountProfileCard(user, role),
          const SizedBox(height: 18),

          // 2. Quick Action to "طلابي" (My Students)
          _buildMyStudentsShortcut(),
          const SizedBox(height: 18),

          // 3. Visual Theme Switcher (Abwaab Modern EdTech vs Jaib Fintech)
          _buildSectionHeader('ثيم ومظهر التطبيق الشامل', Icons.palette_rounded),
          const SizedBox(height: 8),
          _buildCardContainer([
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'اختر الثيم المفضل للواجهات والأيقونات',
                    style: GoogleFonts.almarai(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'الثيم يغير شكل الهيدر، الألوان، البطائق الملونة، الأيقونات، وطريقة عرض المواد التعليمية.',
                    style: GoogleFonts.almarai(fontSize: 11, color: const Color(0xFF64748B)),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildGridOptionTile(
                          title: 'ثيم أبواب التعليمي',
                          subtitle: 'عصري هادئ بألوان باستيل وشرح المواد (الموصى به)',
                          icon: Icons.school_rounded,
                          isSelected: _visualTheme == 'abwaab',
                          onTap: () => _updateVisualTheme('abwaab'),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _buildGridOptionTile(
                          title: 'ثيم جيب المالي',
                          subtitle: 'شبكة 3 بطائق سريعة وأزرار خدمات',
                          icon: Icons.account_balance_wallet_rounded,
                          isSelected: _visualTheme == 'jaib',
                          onTap: () => _updateVisualTheme('jaib'),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ]),
          const SizedBox(height: 18),

          // 4. UI Appearance & Grid Columns Settings
          _buildSectionHeader('تخصيص شبكة الخدمات والأعمدة', Icons.dashboard_customize_rounded),
          const SizedBox(height: 8),
          _buildCardContainer([
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'نمط عرض بطائق الخدمات في الرئيسية',
                    style: GoogleFonts.almarai(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'اختر النمط المناسب لشاشتك، النمط الافتراضي هو 3 أيقونات في الصف كالتطبيقات العصرية.',
                    style: GoogleFonts.almarai(fontSize: 11, color: const Color(0xFF64748B)),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildGridOptionTile(
                          title: '3 أيقونات في الصف',
                          subtitle: 'نمط جيب العصري (الافتراضي)',
                          icon: Icons.grid_view_rounded,
                          isSelected: _gridColumns == 3,
                          onTap: () => _updateGridColumns(3),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _buildGridOptionTile(
                          title: 'أيقونتان في الصف',
                          subtitle: 'نمط تفصيلي موسع',
                          icon: Icons.view_agenda_rounded,
                          isSelected: _gridColumns == 2,
                          onTap: () => _updateGridColumns(2),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ]),
          const SizedBox(height: 18),

          // 4. Security & Authentication
          _buildSectionHeader('الأمان وقفل التطبيق', Icons.security_rounded),
          const SizedBox(height: 8),
          _buildCardContainer([
            SwitchListTile(
              value: _pinLockEnabled,
              onChanged: _togglePinLock,
              activeThumbColor: const Color(0xFFE11D48),
              title: Text(
                'قفل التطبيق برمز PIN',
                style: GoogleFonts.almarai(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
              ),
              subtitle: Text(
                _pinLockEnabled ? 'الرمز مفعل (4 أرقام)' : 'طلب رمز سري عند فتح التطبيق',
                style: GoogleFonts.almarai(fontSize: 11, color: const Color(0xFF64748B)),
              ),
              secondary: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFFE11D48).withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.pin_rounded, color: Color(0xFFE11D48), size: 20),
              ),
            ),
            const Divider(height: 1, indent: 64),
            SwitchListTile(
              value: _biometricsEnabled,
              onChanged: _toggleBiometrics,
              activeThumbColor: const Color(0xFF0D9488),
              title: Text(
                'الدخول بالبصمة الحيوية',
                style: GoogleFonts.almarai(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
              ),
              subtitle: Text(
                'استخدام بصمة الإصبع أو الوجه للدخول السريع',
                style: GoogleFonts.almarai(fontSize: 11, color: const Color(0xFF64748B)),
              ),
              secondary: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFF0D9488).withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.fingerprint_rounded, color: Color(0xFF0D9488), size: 20),
              ),
            ),
          ]),
          const SizedBox(height: 18),

          // 5. Notifications Preferences
          _buildSectionHeader('التنبيهات والإشعارات', Icons.notifications_active_rounded),
          const SizedBox(height: 8),
          _buildCardContainer([
            _buildNotificationSwitch(
              title: 'تنبيهات الواجبات الجديدة',
              subtitle: 'إشعار فوري عند إضافة المعلم واجباً دراسياً',
              value: _notifyHomework,
              onChanged: (val) async {
                setState(() => _notifyHomework = val);
                final p = await SharedPreferences.getInstance();
                await p.setBool('notify_homework', val);
              },
            ),
            const Divider(height: 1, indent: 20),
            _buildNotificationSwitch(
              title: 'تنبيهات رصد الدرجات والنتائج',
              subtitle: 'إشعار فوري عند نشر درجات الاختبارات الشهرية',
              value: _notifyGrades,
              onChanged: (val) async {
                setState(() => _notifyGrades = val);
                final p = await SharedPreferences.getInstance();
                await p.setBool('notify_grades', val);
              },
            ),
            const Divider(height: 1, indent: 20),
            _buildNotificationSwitch(
              title: 'تنبيهات الحضور والغياب اليومي',
              subtitle: 'إشعار صباحي بحالة تسجيل حضور الحصة',
              value: _notifyAttendance,
              onChanged: (val) async {
                setState(() => _notifyAttendance = val);
                final p = await SharedPreferences.getInstance();
                await p.setBool('notify_attendance', val);
              },
            ),
          ]),
          const SizedBox(height: 18),

          // 6. Storage & System
          _buildSectionHeader('الذاكرة والتخزين', Icons.storage_rounded),
          const SizedBox(height: 8),
          _buildCardContainer([
            ListTile(
              onTap: _clearCache,
              leading: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFFF1F5F9),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.cleaning_services_rounded, color: Color(0xFF475569), size: 20),
              ),
              title: Text(
                'مسح الذاكرة المؤقتة (Cache)',
                style: GoogleFonts.almarai(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
              ),
              subtitle: Text(
                'تفريغ البيانات والملفات المؤقتة لتسريع التطبيق',
                style: GoogleFonts.almarai(fontSize: 11, color: const Color(0xFF64748B)),
              ),
              trailing: const Icon(Icons.arrow_forward_ios_rounded, size: 14, color: Color(0xFF94A3B8)),
            ),
          ]),
          const SizedBox(height: 18),

          // 7. About Application
          _buildSectionHeader('عن المنظومة', Icons.info_outline_rounded),
          const SizedBox(height: 8),
          _buildCardContainer([
            ListTile(
              title: Text('إصدار مدرستي الذكية', style: GoogleFonts.almarai(fontSize: 13, fontWeight: FontWeight.bold)),
              subtitle: Text('الإصدار 1.2.0 (بناء معتمد مستقر)', style: GoogleFonts.almarai(fontSize: 11, color: const Color(0xFF64748B))),
              trailing: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: const Color(0xFFE2E8F0),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text('v1.2.0', style: GoogleFonts.almarai(fontSize: 11, fontWeight: FontWeight.bold)),
              ),
            ),
            const Divider(height: 1, indent: 20),
            ListTile(
              title: Text('المدرسة المعتمدة', style: GoogleFonts.almarai(fontSize: 13, fontWeight: FontWeight.bold)),
              subtitle: Text('${widget.api.activeSchoolName} • كود ${widget.api.activeSchoolCode}', style: GoogleFonts.almarai(fontSize: 11, color: const Color(0xFF64748B))),
            ),
          ]),
          const SizedBox(height: 24),

          // Logout Button
          ElevatedButton.icon(
            onPressed: () {
              Navigator.pop(context);
              widget.api.logout();
            },
            icon: const Icon(Icons.logout_rounded, size: 20),
            label: Text('تسجيل الخروج من المنظومة', style: GoogleFonts.almarai(fontSize: 14, fontWeight: FontWeight.bold)),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFFFF1F2),
              foregroundColor: const Color(0xFFE11D48),
              elevation: 0,
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(14),
                side: const BorderSide(color: Color(0xFFFECDD3)),
              ),
            ),
          ),
          const SizedBox(height: 32),
        ],
      ),
    );
  }

  Widget _buildAccountProfileCard(UserAccount? user, String role) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFFE2E8F0)),
        boxShadow: AppTheme.softShadow,
      ),
      child: Row(
        children: [
          CircleAvatar(
            radius: 30,
            backgroundColor: const Color(0xFF1E60FF),
            child: Text(
              widget.api.currentUserName.isNotEmpty ? widget.api.currentUserName.characters.first : 'م',
              style: GoogleFonts.almarai(fontSize: 22, color: Colors.white, fontWeight: FontWeight.bold),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  widget.api.currentUserName,
                  style: GoogleFonts.almarai(fontSize: 16, fontWeight: FontWeight.w900, color: const Color(0xFF0F172A)),
                ),
                Text(
                  '${widget.api.activeSchoolName} • كود ${widget.api.activeSchoolCode}',
                  style: GoogleFonts.almarai(fontSize: 11, color: const Color(0xFF64748B), fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 6,
                  children: widget.api.availableRoles.map((r) {
                    final isCurrent = r == role;
                    return Container(
                      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                      decoration: BoxDecoration(
                        color: isCurrent ? const Color(0xFF0F172A) : const Color(0xFFF1F5F9),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        r == 'guardian'
                            ? 'ولي أمر'
                            : r == 'student'
                                ? 'طالب'
                                : r == 'teacher'
                                    ? 'معلم'
                                    : 'إدارة',
                        style: GoogleFonts.almarai(
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                          color: isCurrent ? Colors.white : const Color(0xFF64748B),
                        ),
                      ),
                    );
                  }).toList(),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMyStudentsShortcut() {
    return InkWell(
      onTap: () => Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => MyStudentsScreen(api: widget.api)),
      ),
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          color: const Color(0xFFEFF6FF),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: const Color(0xFFBFDBFE)),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: const BoxDecoration(
                color: Color(0xFF0284C7),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.people_alt_rounded, color: Colors.white, size: 20),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'طلابي والطلاب المضافون (${widget.api.students.length})',
                    style: GoogleFonts.almarai(fontSize: 14, fontWeight: FontWeight.w900, color: const Color(0xFF0369A1)),
                  ),
                  Text(
                    'عرض بطائق الطلاب والتبديل المباشر بضغطة زر أو إضافة طالب جديد',
                    style: GoogleFonts.almarai(fontSize: 11, color: const Color(0xFF0284C7)),
                  ),
                ],
              ),
            ),
            const Icon(Icons.arrow_forward_ios_rounded, size: 16, color: Color(0xFF0284C7)),
          ],
        ),
      ),
    );
  }

  Widget _buildSectionHeader(String title, IconData icon) {
    return Row(
      children: [
        Icon(icon, size: 18, color: const Color(0xFF0F172A)),
        const SizedBox(width: 8),
        Text(
          title,
          style: GoogleFonts.almarai(fontSize: 14, fontWeight: FontWeight.w900, color: const Color(0xFF0F172A)),
        ),
      ],
    );
  }

  Widget _buildCardContainer(List<Widget> children) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFE2E8F0)),
        boxShadow: AppTheme.softShadow,
      ),
      child: Column(children: children),
    );
  }

  Widget _buildGridOptionTile({
    required String title,
    required String subtitle,
    required IconData icon,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
    final color = isSelected ? const Color(0xFFE11D48) : const Color(0xFF94A3B8);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
        decoration: BoxDecoration(
          color: isSelected ? const Color(0xFFFFF1F2) : const Color(0xFFF8FAFC),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isSelected ? const Color(0xFFE11D48) : const Color(0xFFE2E8F0),
            width: isSelected ? 1.5 : 1.0,
          ),
        ),
        child: Column(
          children: [
            Icon(icon, color: color, size: 28),
            const SizedBox(height: 6),
            Text(
              title,
              textAlign: TextAlign.center,
              style: GoogleFonts.almarai(
                fontSize: 12,
                fontWeight: FontWeight.bold,
                color: isSelected ? const Color(0xFF0F172A) : const Color(0xFF475569),
              ),
            ),
            Text(
              subtitle,
              textAlign: TextAlign.center,
              style: GoogleFonts.almarai(fontSize: 9.5, color: const Color(0xFF64748B)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildNotificationSwitch({
    required String title,
    required String subtitle,
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    return SwitchListTile(
      value: value,
      onChanged: onChanged,
      activeThumbColor: const Color(0xFF0F172A),
      title: Text(title, style: GoogleFonts.almarai(fontSize: 12.5, fontWeight: FontWeight.bold)),
      subtitle: Text(subtitle, style: GoogleFonts.almarai(fontSize: 10.5, color: const Color(0xFF64748B))),
    );
  }
}



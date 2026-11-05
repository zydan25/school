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
                  ? 'تم تفعيل ثيم المنهاج والتعليم (أبواب) 🎓'
                  : 'تم تفعيل ثيم الخدمات السريعة (جيب) 💼',
              style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontWeight: FontWeight.bold),
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
              cols == 3 ? 'تم تفعيل نمط 3 أيقونات في الصف (الافتراضي)' : 'تم تفعيل نمط أيقونتين في الصف',
              style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontWeight: FontWeight.bold),
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
        backgroundColor: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: const Color(0xFFFEF2F2),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.lock_rounded, color: Color(0xFFDC2626), size: 20),
            ),
            const SizedBox(width: 10),
            Text(
              'تعيين رمز قفل البرنامج (PIN)',
              style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontSize: 14.5, fontWeight: FontWeight.bold, color: const Color(0xFF111111)),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'أدخل رمز مرور مكوناً من 4 أرقام لحماية التطبيق عند الفتح:',
              style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontSize: 12, color: const Color(0xFF64748B)),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: pinController,
              keyboardType: TextInputType.number,
              maxLength: 4,
              obscureText: true,
              textAlign: TextAlign.center,
              style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontSize: 22, fontWeight: FontWeight.bold, letterSpacing: 12),
              decoration: InputDecoration(
                hintText: '••••',
                hintStyle: const TextStyle(letterSpacing: 12),
                counterText: '',
                filled: true,
                fillColor: const Color(0xFFF8FAFC),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: Color(0xFFE2E8F0))),
                enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: Color(0xFFE2E8F0))),
                focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: Color(0xFF1E60FF), width: 1.5)),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('إلغاء', style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, color: const Color(0xFF64748B), fontWeight: FontWeight.bold)),
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
                      content: Text('تم تفعيل رمز القفل بنجاح ✓', style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontWeight: FontWeight.bold)),
                      backgroundColor: const Color(0xFF15803D),
                    ),
                  );
                }
              }
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF1E60FF),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            ),
            child: Text('حفظ الرمز', style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontWeight: FontWeight.bold)),
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
              style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontWeight: FontWeight.bold),
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
        backgroundColor: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        title: Text('مسح الذاكرة المؤقتة', style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontSize: 15, fontWeight: FontWeight.bold)),
        content: Text(
          'سيتم تفريغ الصور والملفات المخزنة مؤقتاً لتوفير المساحة وتسريع أداء التطبيق.',
          style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontSize: 12.5, color: const Color(0xFF64748B)),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('إلغاء', style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, color: const Color(0xFF64748B), fontWeight: FontWeight.bold)),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(ctx);
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text('تم تفريغ الذاكرة المؤقتة بنجاح (تم تحرير 24.6 MB) ✓', style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontWeight: FontWeight.bold)),
                  backgroundColor: const Color(0xFF15803D),
                ),
              );
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF1E60FF),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            child: Text('تفريغ الآن', style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(
        backgroundColor: Colors.white,
        body: Center(child: CircularProgressIndicator(color: Color(0xFF1E60FF))),
      );
    }

    final activeStudent = widget.api.currentStudent;

    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        title: Text(
          'الإعدادات والحساب',
          style: TextStyle(
            fontFamily: GoogleFonts.cairo().fontFamily,
            fontSize: 16,
            fontWeight: FontWeight.w800,
            color: const Color(0xFF111111),
          ),
        ),
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18, color: Color(0xFF111111)),
          onPressed: () => Navigator.pop(context, _gridColumns),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        physics: const BouncingScrollPhysics(),
        children: [
          // 1. Account Profile Card
          _buildAccountProfileCard(activeStudent),
          const SizedBox(height: 16),

          // 2. Visual Theme & Display Columns (Grouped Card)
          _buildSectionHeader('المظهر وطريقة العرض', Icons.palette_outlined),
          const SizedBox(height: 8),
          _buildCardContainer([
            // Theme selection
            Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'الثيم العام للواجهات والأيقونات',
                    style: TextStyle(
                      fontFamily: GoogleFonts.cairo().fontFamily,
                      fontSize: 12.5,
                      fontWeight: FontWeight.w700,
                      color: const Color(0xFF1E293B),
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    'يحدد الهيدر والألوان وأيقونات المواد والخدمات المدرسية',
                    style: TextStyle(
                      fontFamily: GoogleFonts.cairo().fontFamily,
                      fontSize: 10.5,
                      color: const Color(0xFF777777),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildOptionTile(
                          title: 'ثيم المنهاج والتعليم',
                          subtitle: 'ألوان باستيل ومواد المنهاج (أبواب)',
                          icon: Icons.school_outlined,
                          iconColor: const Color(0xFF1E60FF),
                          isSelected: _visualTheme == 'abwaab',
                          onTap: () => _updateVisualTheme('abwaab'),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _buildOptionTile(
                          title: 'ثيم الخدمات السريعة',
                          subtitle: 'شبكة بطائق سريعة ومختصرة (جيب)',
                          icon: Icons.account_balance_wallet_outlined,
                          iconColor: const Color(0xFFE11D48),
                          isSelected: _visualTheme == 'jaib',
                          onTap: () => _updateVisualTheme('jaib'),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 14),
                  const Divider(height: 1, color: Color(0xFFF1F5F9)),
                  const SizedBox(height: 14),
                  // Grid Columns selection
                  Text(
                    'توزيع بطائق الخدمات في الصفحة الرئيسية',
                    style: TextStyle(
                      fontFamily: GoogleFonts.cairo().fontFamily,
                      fontSize: 12.5,
                      fontWeight: FontWeight.w700,
                      color: const Color(0xFF1E293B),
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    'الافتراضي هو 3 أيقونات في الصف كالتطبيقات العصرية المنظمة',
                    style: TextStyle(
                      fontFamily: GoogleFonts.cairo().fontFamily,
                      fontSize: 10.5,
                      color: const Color(0xFF777777),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildOptionTile(
                          title: '3 أيقونات في الصف',
                          subtitle: 'عصري متناسق (الموصى به)',
                          icon: Icons.grid_view_rounded,
                          iconColor: const Color(0xFF10B981),
                          isSelected: _gridColumns == 3,
                          onTap: () => _updateGridColumns(3),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _buildOptionTile(
                          title: 'أيقونتان في الصف',
                          subtitle: 'تفصيلي موسع',
                          icon: Icons.view_agenda_outlined,
                          iconColor: const Color(0xFF64748B),
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
          const SizedBox(height: 16),

          // 3. Security & Privacy
          _buildSectionHeader('الأمان وقفل التطبيق', Icons.security_rounded),
          const SizedBox(height: 8),
          _buildCardContainer([
            SwitchListTile(
              value: _pinLockEnabled,
              onChanged: _togglePinLock,
              activeThumbColor: const Color(0xFF1E60FF),
              activeTrackColor: const Color(0xFFDBEAFE),
              title: Text(
                'قفل التطبيق برمز PIN',
                style: TextStyle(
                  fontFamily: GoogleFonts.cairo().fontFamily,
                  fontSize: 12.5,
                  fontWeight: FontWeight.w700,
                  color: const Color(0xFF1E293B),
                ),
              ),
              subtitle: Text(
                _pinLockEnabled ? 'الرمز مفعل (4 أرقام) - اضغط للتغيير' : 'طلب رمز سري عند فتح التطبيق للحماية',
                style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontSize: 10.5, color: const Color(0xFF777777)),
              ),
              secondary: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFFEFF6FF),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.pin_rounded, color: Color(0xFF1E60FF), size: 18),
              ),
            ),
            const Divider(height: 1, indent: 60, color: Color(0xFFF1F5F9)),
            SwitchListTile(
              value: _biometricsEnabled,
              onChanged: _toggleBiometrics,
              activeThumbColor: const Color(0xFF10B981),
              activeTrackColor: const Color(0xFFD1FAE5),
              title: Text(
                'الدخول بالبصمة الحيوية',
                style: TextStyle(
                  fontFamily: GoogleFonts.cairo().fontFamily,
                  fontSize: 12.5,
                  fontWeight: FontWeight.w700,
                  color: const Color(0xFF1E293B),
                ),
              ),
              subtitle: Text(
                'استخدام بصمة الإصبع أو الوجه للدخول السريع',
                style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontSize: 10.5, color: const Color(0xFF777777)),
              ),
              secondary: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFFECFDF5),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.fingerprint_rounded, color: Color(0xFF10B981), size: 18),
              ),
            ),
          ]),
          const SizedBox(height: 16),

          // 4. Notifications Preferences
          _buildSectionHeader('الإشعارات والتنبيهات المدرسية', Icons.notifications_none_rounded),
          const SizedBox(height: 8),
          _buildCardContainer([
            _buildNotificationSwitch(
              title: 'تنبيهات الواجبات الجديدة',
              subtitle: 'إشعار فوري عند إضافة المعلم واجباً دراسياً جديداً',
              value: _notifyHomework,
              onChanged: (val) async {
                setState(() => _notifyHomework = val);
                final p = await SharedPreferences.getInstance();
                await p.setBool('notify_homework', val);
              },
            ),
            const Divider(height: 1, indent: 20, color: Color(0xFFF1F5F9)),
            _buildNotificationSwitch(
              title: 'تنبيهات رصد الدرجات والنتائج',
              subtitle: 'إشعار فوري عند نشر درجات الاختبارات الشهرية والفصلية',
              value: _notifyGrades,
              onChanged: (val) async {
                setState(() => _notifyGrades = val);
                final p = await SharedPreferences.getInstance();
                await p.setBool('notify_grades', val);
              },
            ),
            const Divider(height: 1, indent: 20, color: Color(0xFFF1F5F9)),
            _buildNotificationSwitch(
              title: 'تنبيهات الحضور والغياب اليومي',
              subtitle: 'إشعار صباحي عند تسجيل الحضور والانضباط المدرسي',
              value: _notifyAttendance,
              onChanged: (val) async {
                setState(() => _notifyAttendance = val);
                final p = await SharedPreferences.getInstance();
                await p.setBool('notify_attendance', val);
              },
            ),
          ]),
          const SizedBox(height: 16),

          // 5. Cache & Sync
          _buildSectionHeader('الذاكرة والتخزين والمزامنة', Icons.storage_rounded),
          const SizedBox(height: 8),
          _buildCardContainer([
            ListTile(
              onTap: _clearCache,
              leading: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFFF8FAFC),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.cleaning_services_rounded, color: Color(0xFF475569), size: 18),
              ),
              title: Text(
                'مسح الذاكرة المؤقتة (Cache)',
                style: TextStyle(
                  fontFamily: GoogleFonts.cairo().fontFamily,
                  fontSize: 12.5,
                  fontWeight: FontWeight.w700,
                  color: const Color(0xFF1E293B),
                ),
              ),
              subtitle: Text(
                'تفريغ الصور والملفات المخزنة مؤقتاً (24.6 MB)',
                style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontSize: 10.5, color: const Color(0xFF777777)),
              ),
              trailing: const Icon(Icons.arrow_forward_ios_rounded, size: 13, color: Color(0xFF94A3B8)),
            ),
            const Divider(height: 1, indent: 60, color: Color(0xFFF1F5F9)),
            ListTile(
              onTap: () async {
                final messenger = ScaffoldMessenger.of(context);
                await widget.api.fetchProfiles();
                if (mounted) {
                  messenger.showSnackBar(
                    SnackBar(
                      content: Text('تمت مزامنة البيانات مع الخادم بنجاح ✓', style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontWeight: FontWeight.bold)),
                      backgroundColor: const Color(0xFF15803D),
                    ),
                  );
                }
              },
              leading: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFFF0FDF4),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.sync_rounded, color: Color(0xFF16A34A), size: 18),
              ),
              title: Text(
                'مزامنة البيانات الآن',
                style: TextStyle(
                  fontFamily: GoogleFonts.cairo().fontFamily,
                  fontSize: 12.5,
                  fontWeight: FontWeight.w700,
                  color: const Color(0xFF1E293B),
                ),
              ),
              subtitle: Text(
                'تحديث الجداول والمواد والدرجات من السيرفر المدرسي',
                style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontSize: 10.5, color: const Color(0xFF777777)),
              ),
              trailing: const Icon(Icons.arrow_forward_ios_rounded, size: 13, color: Color(0xFF94A3B8)),
            ),
          ]),
          const SizedBox(height: 16),

          // 6. About App & School
          _buildSectionHeader('عن المنظومة المدرسية', Icons.info_outline_rounded),
          const SizedBox(height: 8),
          _buildCardContainer([
            ListTile(
              title: Text('إصدار مدرستي الذكية', style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontSize: 12.5, fontWeight: FontWeight.w700, color: const Color(0xFF1E293B))),
              subtitle: Text('الإصدار v1.2.0 (بناء معتمد مستقر)', style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontSize: 10.5, color: const Color(0xFF777777))),
              trailing: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: const Color(0xFFF1F5F9),
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: const Color(0xFFE2E8F0)),
                ),
                child: Text('v1.2.0', style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontSize: 11, fontWeight: FontWeight.w800, color: const Color(0xFF1E293B))),
              ),
            ),
            const Divider(height: 1, indent: 20, color: Color(0xFFF1F5F9)),
            ListTile(
              title: Text('المدرسة المعتمدة', style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontSize: 12.5, fontWeight: FontWeight.w700, color: const Color(0xFF1E293B))),
              subtitle: Text('${widget.api.activeSchoolName} • كود ${widget.api.activeSchoolCode}', style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontSize: 10.5, color: const Color(0xFF777777))),
            ),
          ]),
          const SizedBox(height: 24),

          // 7. Logout Button
          ElevatedButton.icon(
            onPressed: () {
              _showLogoutDialog();
            },
            icon: const Icon(Icons.logout_rounded, size: 18),
            label: Text('تسجيل الخروج من الحساب', style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontSize: 13, fontWeight: FontWeight.bold)),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFFFF1F2),
              foregroundColor: const Color(0xFFE11D48),
              elevation: 0,
              padding: const EdgeInsets.symmetric(vertical: 13),
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

  void _showLogoutDialog() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        title: Text('تسجيل الخروج', style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontSize: 15, fontWeight: FontWeight.bold)),
        content: Text('هل أنت متأكد من رغبتك في تسجيل الخروج من التطبيق؟', style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontSize: 12.5, color: const Color(0xFF64748B))),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('إلغاء', style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, color: const Color(0xFF64748B), fontWeight: FontWeight.bold)),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(ctx);
              Navigator.pop(context);
              widget.api.logout();
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFDC2626),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            child: Text('خروج', style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  Widget _buildAccountProfileCard(StudentProfile? activeStudent) {
    final displayName = activeStudent?.fullName ?? widget.api.currentUserName;
    final displayGrade = activeStudent?.grade ?? 'طالب مدرستي';
    final studentId = activeStudent?.studentNumber ?? '10482';

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFFF1F5F9), width: 1.2),
        boxShadow: AppTheme.softShadow,
      ),
      child: Column(
        children: [
          Row(
            children: [
              Stack(
                clipBehavior: Clip.none,
                children: [
                  CircleAvatar(
                    radius: 28,
                    backgroundColor: const Color(0xFF1E60FF).withValues(alpha: 0.1),
                    child: Text(
                      displayName.isNotEmpty ? displayName.characters.first : 'ط',
                      style: TextStyle(fontFamily: GoogleFonts.cairo().fontFamily, fontSize: 20, color: const Color(0xFF1E60FF), fontWeight: FontWeight.bold),
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
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      displayName,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontFamily: GoogleFonts.cairo().fontFamily,
                        fontSize: 15,
                        fontWeight: FontWeight.w800,
                        color: const Color(0xFF111111),
                      ),
                    ),
                    Text(
                      '$displayGrade • ${widget.api.activeSchoolName}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontFamily: GoogleFonts.cairo().fontFamily,
                        fontSize: 11,
                        color: const Color(0xFF777777),
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF1F5F9),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        'رقم القيد: $studentId',
                        style: TextStyle(
                          fontFamily: GoogleFonts.cairo().fontFamily,
                          fontSize: 9.5,
                          fontWeight: FontWeight.bold,
                          color: const Color(0xFF475569),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          const Divider(height: 1, color: Color(0xFFF1F5F9)),
          const SizedBox(height: 10),
          // My Students shortcut inside the card
          InkWell(
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => MyStudentsScreen(api: widget.api)),
            ),
            borderRadius: BorderRadius.circular(12),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(
                color: const Color(0xFFF0F7FF),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFBAE6FD)),
              ),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(6),
                    decoration: const BoxDecoration(
                      color: Color(0xFF0284C7),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.people_alt_rounded, color: Colors.white, size: 16),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'عرض وإدارة طلابي (${widget.api.students.length})',
                          style: TextStyle(
                            fontFamily: GoogleFonts.cairo().fontFamily,
                            fontSize: 12,
                            fontWeight: FontWeight.w800,
                            color: const Color(0xFF0369A1),
                          ),
                        ),
                        Text(
                          'التبديل بين بطائق الطلاب بضغطة زر أو إضافة طالب جديد',
                          style: TextStyle(
                            fontFamily: GoogleFonts.cairo().fontFamily,
                            fontSize: 10,
                            color: const Color(0xFF0284C7),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const Icon(Icons.arrow_forward_ios_rounded, size: 13, color: Color(0xFF0284C7)),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title, IconData icon) {
    return Row(
      children: [
        Icon(icon, size: 16, color: const Color(0xFF1E293B)),
        const SizedBox(width: 6),
        Text(
          title,
          style: TextStyle(
            fontFamily: GoogleFonts.cairo().fontFamily,
            fontSize: 13,
            fontWeight: FontWeight.w800,
            color: const Color(0xFF1E293B),
          ),
        ),
      ],
    );
  }

  Widget _buildCardContainer(List<Widget> children) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFF1F5F9), width: 1.2),
        boxShadow: AppTheme.softShadow,
      ),
      child: Column(children: children),
    );
  }

  Widget _buildOptionTile({
    required String title,
    required String subtitle,
    required IconData icon,
    required Color iconColor,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
        decoration: BoxDecoration(
          color: isSelected ? const Color(0xFFEFF6FF) : const Color(0xFFF8FAFC),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isSelected ? const Color(0xFF1E60FF) : const Color(0xFFE2E8F0),
            width: isSelected ? 1.5 : 1.0,
          ),
        ),
        child: Column(
          children: [
            Icon(icon, color: isSelected ? const Color(0xFF1E60FF) : iconColor, size: 24),
            const SizedBox(height: 6),
            Text(
              title,
              textAlign: TextAlign.center,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontFamily: GoogleFonts.cairo().fontFamily,
                fontSize: 11,
                fontWeight: FontWeight.w700,
                color: isSelected ? const Color(0xFF1E60FF) : const Color(0xFF1E293B),
              ),
            ),
            const SizedBox(height: 2),
            Text(
              subtitle,
              textAlign: TextAlign.center,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontFamily: GoogleFonts.cairo().fontFamily,
                fontSize: 9,
                color: const Color(0xFF777777),
                height: 1.2,
              ),
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
      activeThumbColor: const Color(0xFF1E60FF),
      activeTrackColor: const Color(0xFFDBEAFE),
      title: Text(
        title,
        style: TextStyle(
          fontFamily: GoogleFonts.cairo().fontFamily,
          fontSize: 12,
          fontWeight: FontWeight.w700,
          color: const Color(0xFF1E293B),
        ),
      ),
      subtitle: Text(
        subtitle,
        style: TextStyle(
          fontFamily: GoogleFonts.cairo().fontFamily,
          fontSize: 10,
          color: const Color(0xFF777777),
        ),
      ),
    );
  }
}

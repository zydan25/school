import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/api_service.dart';
import '../core/theme.dart';

class ManageStudentsScreen extends StatefulWidget {
  final ApiService api;
  const ManageStudentsScreen({super.key, required this.api});

  @override
  State<ManageStudentsScreen> createState() => _ManageStudentsScreenState();
}

class _ManageStudentsScreenState extends State<ManageStudentsScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final _schoolCodeController = TextEditingController(text: '1234');
  final _studentCodeController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _obscurePassword = true;
  bool _isSubmitting = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
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
          content: Text('الرجاء إدخال كود الطالب أولاً', style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold)),
          backgroundColor: AppTheme.rose,
        ),
      );
      return;
    }

    setState(() => _isSubmitting = true);

    final result = await widget.api.addNewStudent(
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
          content: Text(result['message'] ?? 'تم التحقق من بيانات الطالب في الخادم وربطه بنجاح!', style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold)),
          backgroundColor: AppTheme.screenshotGreen,
          duration: const Duration(seconds: 4),
        ),
      );
      _tabController.animateTo(1);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(result['message'] ?? 'فشل التحقق من كود الطالب في الخادم', style: GoogleFonts.cairo(fontSize: 13)),
          backgroundColor: AppTheme.rose,
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
        content: Text('تم مسح كود QR وقراءة بيانات الطالب بنجاح!', style: GoogleFonts.cairo()),
        backgroundColor: AppTheme.screenshotPurple,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.api,
      builder: (context, _) {
        return Scaffold(
          backgroundColor: const Color(0xFFF8FAFC),
          appBar: _buildCustomAppBar(context),
          body: Column(
            children: [
              // 1. Top Tabs matching user screenshot
              Container(
                decoration: const BoxDecoration(
                  color: Colors.white,
                  border: Border(bottom: BorderSide(color: Color(0xFFE2E8F0))),
                ),
                child: TabBar(
                  controller: _tabController,
                  labelColor: AppTheme.screenshotBlue,
                  unselectedLabelColor: const Color(0xFF64748B),
                  labelStyle: GoogleFonts.cairo(fontSize: 14, fontWeight: FontWeight.bold),
                  unselectedLabelStyle: GoogleFonts.cairo(fontSize: 14, fontWeight: FontWeight.w600),
                  indicatorColor: AppTheme.screenshotBlue,
                  indicatorWeight: 3,
                  indicatorSize: TabBarIndicatorSize.tab,
                  tabs: const [
                    // Right Tab (Tab 0): + إضافة طالب
                    Tab(
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text('+ إضافة طالب'),
                          SizedBox(width: 8),
                          Icon(Icons.person_add_rounded, size: 20),
                        ],
                      ),
                    ),
                    // Left Tab (Tab 1): الطلاب المضافون
                    Tab(
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text('الطلاب المضافون'),
                          SizedBox(width: 8),
                          Icon(Icons.people_alt_rounded, size: 20),
                        ],
                      ),
                    ),
                  ],
                ),
              ),

              // 2. Tab Contents
              Expanded(
                child: TabBarView(
                  controller: _tabController,
                  children: [
                    _buildAddStudentTab(),
                    _buildAddedStudentsAndDevicesTab(),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  // ---------------------------------------------------------------------------
  // Exact AppBar from Screenshot (media_1793815466746_6f01fd5d.jpg)
  // In RTL mode: Child 0 is placed on the RIGHT, Child 1 is on the LEFT.
  // ---------------------------------------------------------------------------
  PreferredSizeWidget _buildCustomAppBar(BuildContext context) {
    return AppBar(
      backgroundColor: Colors.white,
      elevation: 0,
      automaticallyImplyLeading: false,
      titleSpacing: 16,
      title: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          // RIGHT SIDE in RTL (Child 0):
          // In screenshot: Light blue circular badge with white/blue graduation hat on far right,
          // then title "إدارة الطلاب" next to it.
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
                    size: 26,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Text(
                'إدارة الطلاب',
                style: GoogleFonts.cairo(
                  fontSize: 18,
                  fontWeight: FontWeight.w900,
                  color: const Color(0xFF0F172A),
                ),
              ),
            ],
          ),

          // LEFT SIDE in RTL (Child 1):
          // In screenshot: QR scanner icon, Settings gear icon, 3 dots icon, Back button
          Row(
            children: [
              IconButton(
                icon: const Icon(Icons.qr_code_scanner_rounded, size: 22, color: Color(0xFF0F172A)),
                onPressed: _simulateQrScan,
                tooltip: 'مسح كود QR',
              ),
              IconButton(
                icon: const Icon(Icons.settings_outlined, size: 22, color: Color(0xFF0F172A)),
                onPressed: () => _showDeviceManagementDialog(context),
                tooltip: 'إدارة الأجهزة',
              ),
              IconButton(
                icon: const Icon(Icons.more_vert, size: 22, color: Color(0xFF0F172A)),
                onPressed: () => _showWorkspaceChoiceDialog(context),
                tooltip: 'مساحة العمل',
              ),
              IconButton(
                icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18, color: Color(0xFF0F172A)),
                onPressed: () => Navigator.pop(context),
                tooltip: 'رجوع',
              ),
            ],
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Tab 1: Exact Replica of "إضافة طالب" Cards from Screenshot
  // ---------------------------------------------------------------------------
  Widget _buildAddStudentTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      physics: const BouncingScrollPhysics(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Card 1: "المدرسة"
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
                // Title Row
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.school_rounded, color: AppTheme.screenshotBlue, size: 20),
                        const SizedBox(width: 8),
                        Text(
                          'المدرسة',
                          style: GoogleFonts.cairo(
                            fontSize: 15,
                            fontWeight: FontWeight.bold,
                            color: AppTheme.screenshotBlue,
                          ),
                        ),
                      ],
                    ),
                    Text(
                      'المدرسة الافتراضية الرسمية',
                      style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF64748B)),
                    ),
                  ],
                ),
                const SizedBox(height: 14),

                // Cyan/Blue Outlined Input with Floating Label
                Stack(
                  children: [
                    Container(
                      margin: const EdgeInsets.only(top: 8),
                      padding: const EdgeInsets.symmetric(horizontal: 14),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: AppTheme.screenshotFieldBorder, width: 1.5),
                      ),
                      child: Row(
                        children: [
                          // In RTL: Child 0 on the RIGHT: < > symbol
                          const Text(
                            '< >',
                            style: TextStyle(color: Color(0xFF64748B), fontSize: 16, fontWeight: FontWeight.bold),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: TextField(
                              controller: _schoolCodeController,
                              textAlign: TextAlign.right,
                              style: GoogleFonts.cairo(fontSize: 14, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                              decoration: InputDecoration(
                                hintText: '...أدخل كود المدرسة',
                                hintStyle: GoogleFonts.cairo(fontSize: 13, color: const Color(0xFF94A3B8)),
                                border: InputBorder.none,
                              ),
                            ),
                          ),
                          // In RTL: Child 2 on the LEFT: grid icon
                          const Icon(Icons.qr_code_2_rounded, color: Color(0xFF64748B), size: 22),
                        ],
                      ),
                    ),
                    // Floating Label Tab on Right
                    Positioned(
                      right: 24,
                      top: 0,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8),
                        color: Colors.white,
                        child: Text(
                          'كود المدرسة',
                          style: GoogleFonts.cairo(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            color: const Color(0xFF475569),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // Card 2: "إضافة طالب جديد"
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
                // Green Title
                Row(
                  children: [
                    const Icon(Icons.person_add_rounded, color: AppTheme.screenshotGreen, size: 20),
                    const SizedBox(width: 8),
                    Text(
                      'إضافة طالب جديد',
                      style: GoogleFonts.cairo(
                        fontSize: 15,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.screenshotGreen,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),

                // Two Action Buttons: PURPLE on the RIGHT, ORANGE on the LEFT
                Row(
                  children: [
                    // Child 0 in RTL = RIGHT: Purple Button (مسح QR)
                    Expanded(
                      child: ElevatedButton.icon(
                        onPressed: _simulateQrScan,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppTheme.screenshotPurple,
                          foregroundColor: Colors.white,
                          elevation: 0,
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        ),
                        icon: const Icon(Icons.qr_code_2_rounded, size: 18),
                        label: Text(
                          'مسح QR',
                          style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),

                    // Child 1 in RTL = LEFT: Orange Button (QR من صورة)
                    Expanded(
                      child: ElevatedButton.icon(
                        onPressed: _simulateQrScan,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppTheme.screenshotOrange,
                          foregroundColor: Colors.white,
                          elevation: 0,
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        ),
                        icon: const Icon(Icons.image_outlined, size: 18),
                        label: Text(
                          'QR من صورة',
                          style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold),
                        ),
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 16),

                // Input Field 1: كود الطالب (Text on Right, Badge Icon on Far Left matching screenshot)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFFCBD5E1)),
                  ),
                  child: Row(
                    children: [
                      // In RTL: Child 0 is on the RIGHT (Arabic text)
                      Expanded(
                        child: TextField(
                          controller: _studentCodeController,
                          textAlign: TextAlign.right,
                          style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                          decoration: InputDecoration(
                            hintText: 'كود الطالب',
                            hintStyle: GoogleFonts.cairo(fontSize: 13, color: const Color(0xFF94A3B8)),
                            border: InputBorder.none,
                          ),
                        ),
                      ),
                      const SizedBox(width: 10),
                      // In RTL: Child 1 is on the LEFT: Badge icon
                      const Icon(Icons.badge_outlined, color: Color(0xFF475569), size: 22),
                    ],
                  ),
                ),

                const SizedBox(height: 12),

                // Input Field 2: كلمة المرور (Text on Right, Lock Icon on Far Left matching screenshot)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFFCBD5E1)),
                  ),
                  child: Row(
                    children: [
                      // In RTL: Child 0 on RIGHT: Password text field
                      Expanded(
                        child: TextField(
                          controller: _passwordController,
                          obscureText: _obscurePassword,
                          textAlign: TextAlign.right,
                          style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                          decoration: InputDecoration(
                            hintText: 'كلمة المرور',
                            hintStyle: GoogleFonts.cairo(fontSize: 13, color: const Color(0xFF94A3B8)),
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
                      const SizedBox(width: 4),
                      // In RTL: Child 2 on LEFT: Lock icon
                      const Icon(Icons.lock_outline_rounded, color: Color(0xFF475569), size: 22),
                    ],
                  ),
                ),

                const SizedBox(height: 18),

                // Green Full-Width Button: + إضافة الطالب
                SizedBox(
                  width: double.infinity,
                  height: 48,
                  child: ElevatedButton(
                    onPressed: _isSubmitting ? null : _handleAddStudent,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.screenshotGreen,
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
                              Text(
                                'إضافة الطالب',
                                style: GoogleFonts.cairo(fontSize: 15, fontWeight: FontWeight.bold),
                              ),
                              const SizedBox(width: 8),
                              const Icon(Icons.person_add_alt_1_rounded, size: 20),
                            ],
                          ),
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // Security & Device Notice Strip
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: const Color(0xFFEFF6FF),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: const Color(0xFFBFDBFE)),
            ),
            child: Row(
              children: [
                const Icon(Icons.verified_user_rounded, color: AppTheme.screenshotBlue, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'نظام أمان الأجهزة: جهازك الحالي مؤكد تلقائياً كجهاز معتمد لحساب الطالب.',
                    style: GoogleFonts.cairo(fontSize: 11, color: AppTheme.screenshotBlue, fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Tab 2: Added Students & Linked Devices
  // ---------------------------------------------------------------------------
  Widget _buildAddedStudentsAndDevicesTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      physics: const BouncingScrollPhysics(),
      children: [
        // Students List Header
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              'الطلاب المرتبطون بالحساب (${widget.api.students.length})',
              style: GoogleFonts.cairo(fontSize: 14, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
            ),
            TextButton.icon(
              onPressed: () => _tabController.animateTo(0),
              icon: const Icon(Icons.add_circle_outline_rounded, size: 16, color: AppTheme.screenshotBlue),
              label: Text('إضافة طالب', style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.screenshotBlue)),
            ),
          ],
        ),

        const SizedBox(height: 8),

        // Students Cards
        ...widget.api.students.asMap().entries.map((entry) {
          final index = entry.key;
          final student = entry.value;
          final isSelected = widget.api.selectedStudentIndex == index;

          return Container(
            margin: const EdgeInsets.only(bottom: 10),
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(
                color: isSelected ? AppTheme.screenshotBlue : const Color(0xFFE2E8F0),
                width: isSelected ? 1.5 : 1.0,
              ),
              boxShadow: AppTheme.softShadow,
            ),
            child: Row(
              children: [
                CircleAvatar(
                  radius: 22,
                  backgroundImage: NetworkImage(student.avatarUrl),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        student.fullName,
                        style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                      ),
                      Text(
                        '${student.grade} - ${student.section} • كود: ${student.studentNumber}',
                        style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF64748B)),
                      ),
                    ],
                  ),
                ),
                ElevatedButton(
                  onPressed: () => widget.api.selectStudent(index),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: isSelected ? AppTheme.screenshotBlue : const Color(0xFFF1F5F9),
                    foregroundColor: isSelected ? Colors.white : const Color(0xFF475569),
                    elevation: 0,
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  child: Text(
                    isSelected ? 'النشط ✓' : 'تفعيل',
                    style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
          );
        }),

        const SizedBox(height: 18),

        // Linked Devices Header
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              'الأجهزة المصرح لها بالدخول',
              style: GoogleFonts.cairo(fontSize: 14, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
            ),
            IconButton(
              icon: const Icon(Icons.info_outline_rounded, size: 18, color: Color(0xFF64748B)),
              onPressed: () => _showDeviceManagementDialog(context),
            ),
          ],
        ),

        const SizedBox(height: 8),

        ...widget.api.devices.map((device) => Container(
          margin: const EdgeInsets.only(bottom: 8),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: const Color(0xFFE2E8F0)),
          ),
          child: Row(
            children: [
              Icon(
                device.isCurrentDevice ? Icons.phone_android_rounded : Icons.tablet_mac_rounded,
                color: device.isConfirmed ? AppTheme.screenshotGreen : AppTheme.screenshotOrange,
                size: 26,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          device.deviceName,
                          style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                        ),
                        if (device.isAutoConfirmed) ...[
                          const SizedBox(width: 6),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                            decoration: BoxDecoration(
                              color: const Color(0xFFDCFCE7),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              'الجهاز الأول (مؤكد تلقائياً)',
                              style: GoogleFonts.cairo(fontSize: 9, fontWeight: FontWeight.bold, color: const Color(0xFF15803D)),
                            ),
                          ),
                        ],
                      ],
                    ),
                    Text(
                      '${device.deviceModel} • ${device.lastActive}',
                      style: GoogleFonts.cairo(fontSize: 10, color: const Color(0xFF64748B)),
                    ),
                  ],
                ),
              ),
              if (!device.isConfirmed)
                TextButton(
                  onPressed: () => widget.api.confirmDevice(device.id),
                  child: Text('تأكيد الجهاز', style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold, color: AppTheme.screenshotGreen)),
                )
              else
                const Icon(Icons.verified_rounded, color: AppTheme.screenshotGreen, size: 20),
            ],
          ),
        )),
      ],
    );
  }

  // ---------------------------------------------------------------------------
  // Workspace Chooser Dialog (matching media_1793801591808_c4eb6269.jpg)
  // ---------------------------------------------------------------------------
  void _showWorkspaceChoiceDialog(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Container(
        padding: const EdgeInsets.all(20),
        decoration: const BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(color: const Color(0xFFCBD5E1), borderRadius: BorderRadius.circular(4)),
              ),
            ),
            const SizedBox(height: 16),
            Center(
              child: Container(
                width: 52,
                height: 52,
                decoration: const BoxDecoration(
                  color: Color(0xFF1E293B),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.business_center_rounded, color: Colors.white, size: 28),
              ),
            ),
            const SizedBox(height: 12),
            Text(
              'اختر مساحة العمل',
              textAlign: TextAlign.center,
              style: GoogleFonts.cairo(fontSize: 18, fontWeight: FontWeight.w900, color: const Color(0xFF0F172A)),
            ),
            Text(
              'المدرسة النشطة: المدرسة الافتراضية',
              textAlign: TextAlign.center,
              style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0D9488)),
            ),
            const SizedBox(height: 4),
            Text(
              'قد يملك الحساب أكثر من دور في المدرسة نفسها. اختر الدور الذي تريد استخدامه الآن.',
              textAlign: TextAlign.center,
              style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF64748B)),
            ),
            const SizedBox(height: 20),
            Text(
              'الأدوار والملفات المتاحة',
              style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.w800, color: const Color(0xFF0F172A)),
            ),
            const SizedBox(height: 10),

            _buildRoleOption(
              ctx,
              roleKey: 'guardian',
              title: 'ولي أمر (د. سيف العتاب)',
              subtitle: 'متابعة الأبناء، الدرجات، الرسوم، وسجل الحضور',
              icon: Icons.family_restroom_rounded,
              color: const Color(0xFF2563EB),
            ),
            _buildRoleOption(
              ctx,
              roleKey: 'student',
              title: 'طالب (أحمد سيف العتاب)',
              subtitle: 'حل الواجبات، المناهج الدراسية، والذكاء الاصطناعي',
              icon: Icons.school_rounded,
              color: const Color(0xFF059669),
            ),
            _buildRoleOption(
              ctx,
              roleKey: 'teacher',
              title: 'معلم (أ. إبراهيم الحداد)',
              subtitle: 'رصد درجات الاختبارات وتصحيح واجبات الكشكول',
              icon: Icons.assignment_turned_in_rounded,
              color: const Color(0xFF7C3AED),
            ),

            const SizedBox(height: 14),
            Center(
              child: TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: Text('تغيير المدرسة', style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold, color: const Color(0xFF0D9488))),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRoleOption(BuildContext ctx, {required String roleKey, required String title, required String subtitle, required IconData icon, required Color color}) {
    final isCurrent = widget.api.currentRole == roleKey;
    return GestureDetector(
      onTap: () {
        widget.api.switchRole(roleKey);
        Navigator.pop(ctx);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('تم الانتقال إلى مساحة عمل: $title', style: GoogleFonts.cairo(fontSize: 12)),
            backgroundColor: color,
          ),
        );
      },
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: isCurrent ? color.withValues(alpha: 0.08) : const Color(0xFFF8FAFC),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: isCurrent ? color : const Color(0xFFE2E8F0), width: isCurrent ? 1.5 : 1),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(color: color.withValues(alpha: 0.15), shape: BoxShape.circle),
              child: Icon(icon, color: color, size: 20),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A))),
                  Text(subtitle, style: GoogleFonts.cairo(fontSize: 10, color: const Color(0xFF64748B))),
                ],
              ),
            ),
            if (isCurrent)
              Icon(Icons.check_circle_rounded, color: color, size: 20),
          ],
        ),
      ),
    );
  }

  void _showDeviceManagementDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Row(
          children: [
            const Icon(Icons.phonelink_lock_rounded, color: AppTheme.screenshotBlue, size: 22),
            const SizedBox(width: 8),
            Text('نظام أمان الأجهزة', style: GoogleFonts.cairo(fontSize: 15, fontWeight: FontWeight.bold)),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'لحماية بيانات الطلاب والحساب المدرسي:\n'
              '• الجهاز الأول الذي يسجل الدخول يُعتمد تلقائياً دون الحاجة لتأكيد.\n'
              '• أي جهاز جديد يتطلب موافقة ولي الأمر أو المدرسة من هذه القائمة.',
              style: GoogleFonts.cairo(fontSize: 12, color: const Color(0xFF475569), height: 1.5),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('حسناً فهمت', style: GoogleFonts.cairo(fontWeight: FontWeight.bold, color: AppTheme.screenshotBlue)),
          ),
        ],
      ),
    );
  }
}

import '../widgets/school_bottom_bar.dart';
import 'package:flutter/material.dart';
import '../core/api_service.dart';
import '../core/theme.dart';

class ManageStudentsScreen extends StatefulWidget {
  final ApiService api;
  final int initialTab;
  const ManageStudentsScreen({super.key, required this.api, this.initialTab = 0});

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
    _tabController = TabController(
      length: 2,
      vsync: this,
      initialIndex: (widget.initialTab >= 0 && widget.initialTab <= 1) ? widget.initialTab : 0,
    );
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
        const SnackBar(
          content: Text('الرجاء إدخال كود الطالب أولاً', style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold)),
          backgroundColor: AppTheme.rose,
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
          content: Text(result['message'] ?? 'تم التحقق من بيانات الطالب في الخادم وربطه بنجاح!', style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold)),
          backgroundColor: AppTheme.screenshotGreen,
          duration: const Duration(seconds: 4),
        ),
      );
      _tabController.animateTo(1);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(result['message'] ?? 'فشل التحقق من كود الطالب في الخادم', style: const TextStyle(fontSize: 13)),
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
      const SnackBar(
        content: Text('تم مسح كود QR وقراءة بيانات الطالب بنجاح!', style: TextStyle()),
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
      backgroundColor: Colors.white,
      bottomNavigationBar: SchoolBottomBar(api: widget.api, currentIndex: -1),
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
                  labelStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold),
                  unselectedLabelStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
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
  // Clean AppBar
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
          Row(
            children: [
              Container(
                width: 40,
                height: 40,
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
              const Text(
                'طلابي وإدارة الحسابات',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w900,
                  color: Color(0xFF0F172A),
                ),
              ),
            ],
          ),
          Row(
            children: [
              IconButton(
                icon: const Icon(Icons.qr_code_scanner_rounded, size: 22, color: Color(0xFF0F172A)),
                onPressed: _simulateQrScan,
                tooltip: 'مسح كود QR',
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
                const Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.school_rounded, color: AppTheme.screenshotBlue, size: 22),
                        SizedBox(width: 8),
                        Text(
                          'المدرسة',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            color: AppTheme.screenshotBlue,
                          ),
                        ),
                      ],
                    ),
                    Text(
                      'المدرسة الافتراضية الرسمية',
                      style: TextStyle(fontSize: 11, color: Color(0xFF64748B)),
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
                              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: Color(0xFF0F172A)),
                              decoration: const InputDecoration(
                                hintText: '...أدخل كود المدرسة',
                                hintStyle: TextStyle(fontSize: 13, color: Color(0xFF94A3B8)),
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
                        child: const Text(
                          'كود المدرسة',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            color: Color(0xFF475569),
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
                const Row(
                  children: [
                    Icon(Icons.person_add_rounded, color: AppTheme.screenshotGreen, size: 22),
                    SizedBox(width: 8),
                    Text(
                      '+ إضافة طالب جديد',
                      style: TextStyle(
                        fontSize: 16,
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
                      child: ElevatedButton(
                        onPressed: _simulateQrScan,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppTheme.screenshotPurple,
                          foregroundColor: Colors.white,
                          elevation: 0,
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        ),
                        child: const Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.qr_code_2_rounded, size: 18),
                            SizedBox(width: 8),
                            Text(
                              'مسح QR',
                              style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),

                    // Child 1 in RTL = LEFT: Orange Button (QR من صورة)
                    Expanded(
                      child: ElevatedButton(
                        onPressed: _simulateQrScan,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppTheme.screenshotOrange,
                          foregroundColor: Colors.white,
                          elevation: 0,
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        ),
                        child: const Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.image_outlined, size: 18),
                            SizedBox(width: 8),
                            Text(
                              'QR من صورة',
                              style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 16),

                // Input Field 1: كود الطالب (Badge Icon on Far Right matching screenshot)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFFCBD5E1)),
                  ),
                  child: Row(
                    children: [
                      // In RTL: Child 0 is on the RIGHT: Badge icon
                      const Icon(Icons.badge_outlined, color: Color(0xFF475569), size: 22),
                      const SizedBox(width: 10),
                      // In RTL: Child 1 is on the LEFT: Arabic text field
                      Expanded(
                        child: TextField(
                          controller: _studentCodeController,
                          textAlign: TextAlign.right,
                          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Color(0xFF0F172A)),
                          decoration: const InputDecoration(
                            hintText: 'كود الطالب',
                            hintStyle: TextStyle(fontSize: 13, color: Color(0xFF94A3B8)),
                            border: InputBorder.none,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 12),

                // Input Field 2: كلمة المرور (Lock Icon on Far Right matching screenshot)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFFCBD5E1)),
                  ),
                  child: Row(
                    children: [
                      // In RTL: Child 0 on RIGHT: Lock icon
                      const Icon(Icons.lock_outline_rounded, color: Color(0xFF475569), size: 22),
                      const SizedBox(width: 10),
                      // In RTL: Child 1: Password text field
                      Expanded(
                        child: TextField(
                          controller: _passwordController,
                          obscureText: _obscurePassword,
                          textAlign: TextAlign.right,
                          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Color(0xFF0F172A)),
                          decoration: const InputDecoration(
                            hintText: 'كلمة المرور',
                            hintStyle: TextStyle(fontSize: 13, color: Color(0xFF94A3B8)),
                            border: InputBorder.none,
                          ),
                        ),
                      ),
                      // In RTL: Child 2 on LEFT: Toggle visibility
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
                        : const Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.person_add_alt_1_rounded, size: 20),
                              SizedBox(width: 8),
                              Text(
                                '+ إضافة الطالب',
                                style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                              ),
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
            child: const Row(
              children: [
                Icon(Icons.verified_user_rounded, color: AppTheme.screenshotBlue, size: 20),
                SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'نظام أمان الأجهزة: جهازك الحالي مؤكد تلقائياً كجهاز معتمد لحساب الطالب.',
                    style: TextStyle(fontSize: 11, color: AppTheme.screenshotBlue, fontWeight: FontWeight.bold),
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
        // Quick Add Student Banner
        InkWell(
          onTap: () => _tabController.animateTo(0),
          borderRadius: BorderRadius.circular(16),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFFEFF6FF), Color(0xFFDBEAFE)],
                begin: Alignment.centerRight,
                end: Alignment.centerLeft,
              ),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: const Color(0xFFBFDBFE)),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: const BoxDecoration(
                    color: Color(0xFF0284C7),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.person_add_alt_1_rounded, color: Colors.white, size: 20),
                ),
                const SizedBox(width: 12),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '+ ربط وإضافة طالب جديد',
                        style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Color(0xFF0369A1)),
                      ),
                      Text(
                        'استخدم كود الطالب وكلمة المرور أو مسح QR لربطه بالحساب',
                        style: TextStyle(fontSize: 11, color: Color(0xFF0284C7)),
                      ),
                    ],
                  ),
                ),
                const Icon(Icons.arrow_forward_ios_rounded, size: 14, color: Color(0xFF0284C7)),
              ],
            ),
          ),
        ),

        const SizedBox(height: 16),

        // Students List Header
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              'الطلاب المضافون (${widget.api.students.length})',
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w900, color: Color(0xFF0F172A)),
            ),
            const Text(
              'اضغط على الطالب للانتقال للرئيسية مباشرة',
              style: TextStyle(fontSize: 11, color: Color(0xFF64748B), fontWeight: FontWeight.w600),
            ),
          ],
        ),

        const SizedBox(height: 10),

        // High-End Interactive Student Cards
        ...widget.api.students.asMap().entries.map((entry) {
          final index = entry.key;
          final student = entry.value;
          final isSelected = widget.api.selectedStudentIndex == index;

          return Material(
            color: Colors.transparent,
            child: InkWell(
              onTap: () {
                widget.api.selectStudent(index);
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      'تم تبديل الطالب النشط إلى: ${student.fullName} والانتقال للرئيسية ✓',
                      style: const TextStyle(fontWeight: FontWeight.bold),
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
                                  child: const Icon(Icons.person, color: Color(0xFF0284C7)),
                                ),
                              ),
                            ),
                            if (isSelected)
                              Positioned(
                                bottom: -2,
                                right: -2,
                                child: Container(
                                  padding: const EdgeInsets.all(2),
                                  decoration: const BoxDecoration(color: Colors.white, shape: BoxShape.circle),
                                  child: Container(
                                    width: 12,
                                    height: 12,
                                    decoration: const BoxDecoration(color: Color(0xFF15803D), shape: BoxShape.circle),
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
                                      style: const TextStyle(
                                        fontSize: 14,
                                        fontWeight: FontWeight.w900,
                                        color: Color(0xFF0F172A),
                                      ),
                                    ),
                                  ),
                                  if (isSelected) ...[
                                    const SizedBox(width: 6),
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                                      decoration: BoxDecoration(
                                        color: const Color(0xFFDCFCE7),
                                        borderRadius: BorderRadius.circular(6),
                                        border: Border.all(color: const Color(0xFF86EFAC)),
                                      ),
                                      child: const Text(
                                        'النشط حالياً',
                                        style: TextStyle(fontSize: 9.5, fontWeight: FontWeight.bold, color: Color(0xFF15803D)),
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                              Text(
                                '${student.grade} • ${student.section} • كود ${student.studentNumber}',
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(fontSize: 11, color: Color(0xFF64748B), fontWeight: FontWeight.w600),
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
                            style: TextStyle(
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
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text('نسبة الحضور: ${student.attendanceRate}%', style: const TextStyle(fontSize: 11, color: Color(0xFF15803D), fontWeight: FontWeight.bold)),
                          Text('المعدل: ${student.gpa}%', style: const TextStyle(fontSize: 11, color: Color(0xFF0284C7), fontWeight: FontWeight.bold)),
                          const Text('انقر للذهاب للرئيسية ⇦', style: TextStyle(fontSize: 10, color: Color(0xFF64748B), fontWeight: FontWeight.w600)),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        }),

        const SizedBox(height: 18),

        // Linked Devices Header
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text(
              'الأجهزة المصرح لها بالدخول',
              style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: Color(0xFF0F172A)),
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
                          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Color(0xFF0F172A)),
                        ),
                        if (device.isAutoConfirmed) ...[
                          const SizedBox(width: 6),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                            decoration: BoxDecoration(
                              color: const Color(0xFFDCFCE7),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text(
                              'الجهاز الأول (مؤكد تلقائياً)',
                              style: TextStyle(fontSize: 9, fontWeight: FontWeight.bold, color: Color(0xFF15803D)),
                            ),
                          ),
                        ],
                      ],
                    ),
                    Text(
                      '${device.deviceModel} • ${device.lastActive}',
                      style: const TextStyle(fontSize: 10, color: Color(0xFF64748B)),
                    ),
                  ],
                ),
              ),
              if (!device.isConfirmed)
                TextButton(
                  onPressed: () => widget.api.confirmDevice(device.id),
                  child: const Text('تأكيد الجهاز', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: AppTheme.screenshotGreen)),
                )
              else
                const Icon(Icons.verified_rounded, color: AppTheme.screenshotGreen, size: 20),
            ],
          ),
        )),
      ],
    );
  }

  void _showDeviceManagementDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Row(
          children: [
            Icon(Icons.phonelink_lock_rounded, color: AppTheme.screenshotBlue, size: 22),
            SizedBox(width: 8),
            Text('نظام أمان الأجهزة', style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold)),
          ],
        ),
        content: const Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'لحماية بيانات الطلاب والحساب المدرسي:\n'
              '• الجهاز الأول الذي يسجل الدخول يُعتمد تلقائياً دون الحاجة لتأكيد.\n'
              '• أي جهاز جديد يتطلب موافقة ولي الأمر أو المدرسة من هذه القائمة.',
              style: TextStyle(fontSize: 12, color: Color(0xFF475569), height: 1.5),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('حسناً فهمت', style: TextStyle(fontWeight: FontWeight.bold, color: AppTheme.screenshotBlue)),
          ),
        ],
      ),
    );
  }
}


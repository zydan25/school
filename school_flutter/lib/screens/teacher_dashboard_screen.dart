import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/api_service.dart';
import '../core/models.dart';
import '../core/theme.dart';

class TeacherDashboardScreen extends StatefulWidget {
  final ApiService api;
  const TeacherDashboardScreen({super.key, required this.api});

  @override
  State<TeacherDashboardScreen> createState() => _TeacherDashboardScreenState();
}

class _TeacherDashboardScreenState extends State<TeacherDashboardScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;

  // Grade sheet filters
  String _selectedStage = 'المرحلة الثانوية';
  String _selectedGrade = 'الأول الثانوي';
  String _selectedSection = 'شعبة (أ)';
  String _selectedSubject = 'الرياضيات';
  String _selectedAssessment = 'اختبار الشهر الأول (من 20)';
  final List<String> _assessmentTypes = [
    'اختبار الشهر الأول (من 20)',
    'اختبار الشهر الثاني (من 20)',
    'الواجبات والتطبيقات (من 10)',
    'المواظبة والمشاركة (من 10)',
    'الاختبار الفصلي النهائي (من 50)',
  ];

  // Add Homework form controllers
  final _hwTitleController = TextEditingController();
  final _hwDescController = TextEditingController();
  final _hwDueDateController = TextEditingController(text: 'السبت القادم، 09:00 م');
  bool _hwRequiresImage = true;
  final String _hwSubject = 'الرياضيات';

  // Add Lesson Plan form controllers
  final _lpTopicController = TextEditingController();
  final _lpObjectivesController = TextEditingController();
  final _lpPagesController = TextEditingController();
  final _lpAidsController = TextEditingController();
  final _lpHomeworkController = TextEditingController();
  final _lpNotesController = TextEditingController();
  String _lpSelectedPeriod = 'الحصة الثانية (08:35 ص)';

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    _hwTitleController.dispose();
    _hwDescController.dispose();
    _hwDueDateController.dispose();
    _lpTopicController.dispose();
    _lpObjectivesController.dispose();
    _lpPagesController.dispose();
    _lpAidsController.dispose();
    _lpHomeworkController.dispose();
    _lpNotesController.dispose();
    super.dispose();
  }

  void _handleAddNewHomework() {
    final title = _hwTitleController.text.trim();
    if (title.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('الرجاء إدخال عنوان الواجب', style: GoogleFonts.cairo())),
      );
      return;
    }

    widget.api.teacherAddTextHomework(
      title: title,
      subject: _hwSubject,
      className: '$_selectedGrade - $_selectedSection',
      dueDate: _hwDueDateController.text.trim(),
      description: _hwDescController.text.trim().isNotEmpty
          ? _hwDescController.text.trim()
          : 'حل المسائل في الكشكول ورفع صورة الحل بدقة.',
      requiresImageSolution: _hwRequiresImage,
      maxScore: 10,
    );

    _hwTitleController.clear();
    _hwDescController.clear();

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('تم نشر الواجب لطلاب $_selectedGrade بنجاح!', style: GoogleFonts.cairo(fontWeight: FontWeight.bold)),
        backgroundColor: AppTheme.screenshotGreen,
      ),
    );
  }

  void _handleSaveNewLessonPlan() {
    final topic = _lpTopicController.text.trim();
    if (topic.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('الرجاء إدخال عنوان وموضوع الدرس', style: GoogleFonts.cairo())),
      );
      return;
    }

    widget.api.addDailyLessonPlan(
      subject: _selectedSubject,
      className: '$_selectedGrade - $_selectedSection',
      period: _lpSelectedPeriod,
      topic: topic,
      objectives: _lpObjectivesController.text.trim().isNotEmpty
          ? _lpObjectivesController.text.trim()
          : 'شرح المفاهيم وحل الأمثلة التطبيقية مع الطلاب.',
      pages: _lpPagesController.text.trim().isNotEmpty ? _lpPagesController.text.trim() : 'صـ 50 إلى صـ 56',
      teachingAids: _lpAidsController.text.trim().isNotEmpty ? _lpAidsController.text.trim() : 'السبورة التفاعلية وجهاز العرض',
      homeworkAssigned: _lpHomeworkController.text.trim().isNotEmpty ? _lpHomeworkController.text.trim() : 'حل تمارين الكشكول',
      notes: _lpNotesController.text.trim().isNotEmpty ? _lpNotesController.text.trim() : 'مستوى استيعاب ممتاز.',
    );

    _lpTopicController.clear();
    _lpObjectivesController.clear();
    _lpPagesController.clear();
    _lpAidsController.clear();
    _lpHomeworkController.clear();
    _lpNotesController.clear();
    Navigator.pop(context);

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('تم حفظ وتوثيق خطة الدرس في دفتر التحضير بنجاح!', style: GoogleFonts.cairo(fontWeight: FontWeight.bold)),
        backgroundColor: AppTheme.screenshotGreen,
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
          appBar: AppBar(
            backgroundColor: Colors.white,
            elevation: 0,
            automaticallyImplyLeading: false,
            titleSpacing: 16,
            title: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                // Right side in RTL: Teacher Badge & Title
                Row(
                  children: [
                    Container(
                      width: 40,
                      height: 40,
                      decoration: const BoxDecoration(
                        color: Color(0xFFE0F2FE),
                        shape: BoxShape.circle,
                      ),
                      child: const Center(
                        child: Icon(Icons.school_rounded, color: AppTheme.screenshotBlue, size: 22),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'لوحة المعلم الشاملة',
                          style: GoogleFonts.cairo(fontSize: 16, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                        ),
                        Text(
                          'أ. إبراهيم الحداد • الرياضيات والفيزياء',
                          style: GoogleFonts.cairo(fontSize: 10, color: const Color(0xFF64748B), fontWeight: FontWeight.w600),
                        ),
                      ],
                    ),
                  ],
                ),
                // Left side in RTL: Back button
                IconButton(
                  icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18, color: Color(0xFF0F172A)),
                  onPressed: () => Navigator.pop(context),
                  tooltip: 'رجوع',
                ),
              ],
            ),
            bottom: PreferredSize(
              preferredSize: const Size.fromHeight(48),
              child: Container(
                decoration: const BoxDecoration(
                  border: Border(bottom: BorderSide(color: Color(0xFFE2E8F0))),
                ),
                child: TabBar(
                  controller: _tabController,
                  isScrollable: true,
                  tabAlignment: TabAlignment.start,
                  labelColor: AppTheme.screenshotBlue,
                  unselectedLabelColor: const Color(0xFF64748B),
                  labelStyle: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold),
                  indicatorColor: AppTheme.screenshotBlue,
                  indicatorSize: TabBarIndicatorSize.tab,
                  tabs: const [
                    Tab(
                      child: Row(
                        children: [
                          Icon(Icons.table_chart_rounded, size: 17),
                          SizedBox(width: 6),
                          Text('رصد الدرجات'),
                        ],
                      ),
                    ),
                    Tab(
                      child: Row(
                        children: [
                          Icon(Icons.assignment_turned_in_rounded, size: 17),
                          SizedBox(width: 6),
                          Text('تصحيح الواجبات'),
                        ],
                      ),
                    ),
                    Tab(
                      child: Row(
                        children: [
                          Icon(Icons.how_to_reg_rounded, size: 17),
                          SizedBox(width: 6),
                          Text('تحضير الحصة'),
                        ],
                      ),
                    ),
                    Tab(
                      child: Row(
                        children: [
                          Icon(Icons.menu_book_rounded, size: 17),
                          SizedBox(width: 6),
                          Text('دفتر الدروس'),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          body: TabBarView(
            controller: _tabController,
            children: [
              // Tab 1: Grade Entry Table
              _buildGradeEntryTableTab(),

              // Tab 2: Homework Management & Submissions Correction
              _buildHomeworkManagementTab(),

              // Tab 3: Daily Period Attendance Roster
              _buildDailyAttendanceTab(),

              // Tab 4: Daily Lesson Plan Journal
              _buildLessonPlanJournalTab(),
            ],
          ),
        );
      },
    );
  }

  // ---------------------------------------------------------------------------
  // Tab 1: Streamlined Grade Entry Table
  // ---------------------------------------------------------------------------
  Widget _buildGradeEntryTableTab() {
    final rows = widget.api.teacherGradeRows;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      physics: const BouncingScrollPhysics(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Filter Panel
          Container(
            padding: const EdgeInsets.all(14),
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
                    const Icon(Icons.tune_rounded, color: AppTheme.screenshotBlue, size: 18),
                    const SizedBox(width: 6),
                    Text(
                      'تحديد الصف والشعبة ومادة الرصد:',
                      style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    _buildFilterBadge('المرحلة: $_selectedStage', () {
                      setState(() {
                        _selectedStage = _selectedStage == 'المرحلة الثانوية' ? 'التعليم الأساسي' : 'المرحلة الثانوية';
                        _selectedGrade = _selectedStage == 'المرحلة الثانوية' ? 'الأول الثانوي' : 'التاسع الأساسي';
                      });
                    }),
                    _buildFilterBadge('الصف: $_selectedGrade', () {
                      setState(() {
                        _selectedGrade = _selectedGrade == 'الأول الثانوي' ? 'التاسع الأساسي' : 'الأول الثانوي';
                      });
                    }),
                    _buildFilterBadge('الشعبة: $_selectedSection', () {
                      setState(() {
                        _selectedSection = _selectedSection == 'شعبة (أ)' ? 'شعبة (ب)' : 'شعبة (أ)';
                      });
                    }),
                    _buildFilterBadge('المادة: $_selectedSubject', () {
                      setState(() {
                        _selectedSubject = _selectedSubject == 'الرياضيات' ? 'الفيزياء' : 'الرياضيات';
                      });
                    }),
                    _buildFilterBadge(_selectedAssessment, () {
                      setState(() {
                        final currIdx = _assessmentTypes.indexOf(_selectedAssessment);
                        final nextIdx = (currIdx + 1) % _assessmentTypes.length;
                        _selectedAssessment = _assessmentTypes[nextIdx];
                      });
                    }),
                  ],
                ),
              ],
            ),
          ),

          const SizedBox(height: 14),

          // Table Header Info & Action
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'كشف طلاب $_selectedGrade - $_selectedSection (${rows.length} طلاب)',
                style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
              ),
              ElevatedButton.icon(
                onPressed: () {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text('تم اعتماد وحفظ كافة الدرجات بنجاح في قاعدة البيانات!', style: GoogleFonts.cairo(fontWeight: FontWeight.bold)),
                      backgroundColor: AppTheme.screenshotGreen,
                    ),
                  );
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.screenshotGreen,
                  foregroundColor: Colors.white,
                  elevation: 0,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                ),
                icon: const Icon(Icons.check_circle_rounded, size: 16),
                label: Text('حفظ واعتماد الكل', style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold)),
              ),
            ],
          ),

          const SizedBox(height: 8),

          // Student Grades Table
          Container(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: const Color(0xFFE2E8F0)),
              boxShadow: AppTheme.softShadow,
            ),
            child: ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: rows.length,
              separatorBuilder: (_, __) => const Divider(height: 1, color: Color(0xFFF1F5F9)),
              itemBuilder: (context, index) {
                final row = rows[index];
                return _buildGradeRow(row);
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterBadge(String label, VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: const Color(0xFFF1F5F9),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: const Color(0xFFCBD5E1)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(label, style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold, color: const Color(0xFF334155))),
            const SizedBox(width: 4),
            const Icon(Icons.keyboard_arrow_down_rounded, size: 14, color: Color(0xFF64748B)),
          ],
        ),
      ),
    );
  }

  Widget _buildGradeRow(TeacherStudentGradeRow row) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      child: Row(
        children: [
          CircleAvatar(
            radius: 16,
            backgroundColor: AppTheme.screenshotLightBlue,
            child: Text(
              row.studentName.substring(0, 1),
              style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.screenshotBlue),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  row.studentName,
                  style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                ),
                Text(
                  '${row.studentNumber} • ${row.letterGrade}',
                  style: GoogleFonts.cairo(fontSize: 10, color: const Color(0xFF64748B)),
                ),
              ],
            ),
          ),

          // Inputs for Exam (30) + Homework (10) + Total
          Row(
            children: [
              _buildCompactGradeInput(
                label: 'اختبار (30)',
                value: row.examScore,
                onChanged: (val) {
                  setState(() => row.examScore = val);
                },
              ),
              const SizedBox(width: 6),
              _buildCompactGradeInput(
                label: 'واجب (10)',
                value: row.homeworkScore,
                onChanged: (val) {
                  setState(() => row.homeworkScore = val);
                },
              ),
              const SizedBox(width: 6),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: AppTheme.screenshotGreen.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  '${row.total.toStringAsFixed(1)}/50',
                  style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold, color: AppTheme.screenshotGreen),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildCompactGradeInput({
    required String label,
    required double value,
    required Function(double) onChanged,
  }) {
    final controller = TextEditingController(text: value.toInt().toString());
    return SizedBox(
      width: 58,
      child: Column(
        children: [
          Text(label, style: GoogleFonts.cairo(fontSize: 8, color: const Color(0xFF64748B))),
          Container(
            height: 32,
            margin: const EdgeInsets.only(top: 2),
            child: TextField(
              controller: controller,
              keyboardType: TextInputType.number,
              textAlign: TextAlign.center,
              style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold),
              decoration: InputDecoration(
                contentPadding: const EdgeInsets.all(4),
                filled: true,
                fillColor: const Color(0xFFF8FAFC),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: Color(0xFFCBD5E1))),
                focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: AppTheme.screenshotBlue, width: 1.5)),
              ),
              onSubmitted: (val) {
                final d = double.tryParse(val) ?? value;
                onChanged(d);
              },
            ),
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Tab 2: Homework Management & Submissions Correction
  // ---------------------------------------------------------------------------
  Widget _buildHomeworkManagementTab() {
    final submissions = widget.api.teacherSubmissions;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      physics: const BouncingScrollPhysics(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 1. Add New Homework Card
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
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.add_task_rounded, color: AppTheme.screenshotBlue, size: 20),
                        const SizedBox(width: 8),
                        Text(
                          'إضافة ونشر واجب دراسي جديد',
                          style: GoogleFonts.cairo(fontSize: 14, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                        ),
                      ],
                    ),
                    Text(
                      'اليوم: ${_hwDueDateController.text.split('،').first}',
                      style: GoogleFonts.cairo(fontSize: 10, color: const Color(0xFF64748B)),
                    ),
                  ],
                ),
                const SizedBox(height: 12),

                // Title Input
                TextField(
                  controller: _hwTitleController,
                  style: GoogleFonts.cairo(fontSize: 13),
                  decoration: InputDecoration(
                    labelText: 'عنوان الواجب أو رقم الصفحة',
                    labelStyle: GoogleFonts.cairo(fontSize: 12, color: const Color(0xFF64748B)),
                    hintText: 'مثال: حل تمارين الجبر صفحة 58 في الكشكول',
                    filled: true,
                    fillColor: const Color(0xFFF8FAFC),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFFE2E8F0))),
                  ),
                ),
                const SizedBox(height: 10),

                // Description Input
                TextField(
                  controller: _hwDescController,
                  maxLines: 2,
                  style: GoogleFonts.cairo(fontSize: 12),
                  decoration: InputDecoration(
                    labelText: 'تفاصيل الواجب وملاحظات المعلم للطلاب',
                    labelStyle: GoogleFonts.cairo(fontSize: 12, color: const Color(0xFF64748B)),
                    hintText: 'اكتب نص المسائل أو توجيهات الحل هنا...',
                    filled: true,
                    fillColor: const Color(0xFFF8FAFC),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFFE2E8F0))),
                  ),
                ),
                const SizedBox(height: 10),

                // Option: "الرد برفع صورة الحل من الكشكول"
                Row(
                  children: [
                    Checkbox(
                      value: _hwRequiresImage,
                      activeColor: AppTheme.screenshotGreen,
                      onChanged: (val) => setState(() => _hwRequiresImage = val ?? true),
                    ),
                    Expanded(
                      child: Text(
                        'مطلوب من الطالب رفع صورة الحل (من كشكول المادة)',
                        style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold, color: const Color(0xFF334155)),
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 10),

                // Publish Button
                SizedBox(
                  width: double.infinity,
                  height: 44,
                  child: ElevatedButton.icon(
                    onPressed: _handleAddNewHomework,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.screenshotBlue,
                      foregroundColor: Colors.white,
                      elevation: 0,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    icon: const Icon(Icons.send_rounded, size: 16),
                    label: Text('نشر الواجب لجميع الطلاب الآن', style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold)),
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 18),

          // 2. Student Submissions & Image Correction Section
          Text(
            'حلول الطلاب المستلمة بانتظار التصحيح (${submissions.length})',
            style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
          ),
          const SizedBox(height: 8),

          ...submissions.map((sub) => _buildSubmissionCard(sub)),
        ],
      ),
    );
  }

  Widget _buildSubmissionCard(TeacherHomeworkSubmission sub) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
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
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  CircleAvatar(
                    radius: 16,
                    backgroundColor: AppTheme.screenshotLightBlue,
                    child: Text(
                      sub.studentName.substring(0, 1),
                      style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.screenshotBlue),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        sub.studentName,
                        style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                      ),
                      Text(
                        'وقت التسليم: ${sub.submittedDate}',
                        style: GoogleFonts.cairo(fontSize: 10, color: const Color(0xFF64748B)),
                      ),
                    ],
                  ),
                ],
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: sub.isGraded ? AppTheme.screenshotGreen.withValues(alpha: 0.1) : AppTheme.screenshotOrange.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  sub.isGraded ? 'تم التصحيح (${sub.score?.toInt()}/10)' : 'بانتظار تصحيحك',
                  style: GoogleFonts.cairo(
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                    color: sub.isGraded ? AppTheme.screenshotGreen : AppTheme.screenshotOrange,
                  ),
                ),
              ),
            ],
          ),

          if (sub.studentNote != null) ...[
            const SizedBox(height: 8),
            Text(
              'ملاحظة الطالب: "${sub.studentNote}"',
              style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF475569)),
            ),
          ],

          const SizedBox(height: 12),

          // Preview Solution Image Button & Grade Action
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => _showSolutionImageModal(sub),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppTheme.screenshotBlue,
                    side: const BorderSide(color: AppTheme.screenshotBlue),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  icon: const Icon(Icons.image_search_rounded, size: 16),
                  label: Text('معاينة صورة الحل المرفوعة', style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold)),
                ),
              ),
              const SizedBox(width: 8),
              ElevatedButton(
                onPressed: () => _showGradeDialog(sub),
                style: ElevatedButton.styleFrom(
                  backgroundColor: sub.isGraded ? const Color(0xFFF1F5F9) : AppTheme.screenshotGreen,
                  foregroundColor: sub.isGraded ? const Color(0xFF0F172A) : Colors.white,
                  elevation: 0,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                ),
                child: Text(sub.isGraded ? 'تعديل الدرجة' : 'رصد الدرجة', style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold)),
              ),
            ],
          ),
        ],
      ),
    );
  }

  void _showSolutionImageModal(TeacherHomeworkSubmission sub) {
    showDialog(
      context: context,
      builder: (ctx) => Dialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'صورة حل كشكول: ${sub.studentName}',
                    style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                  ),
                  IconButton(icon: const Icon(Icons.close_rounded), onPressed: () => Navigator.pop(ctx)),
                ],
              ),
              const SizedBox(height: 10),
              ClipRRect(
                borderRadius: BorderRadius.circular(14),
                child: Image.network(
                  sub.solutionImageUrl,
                  height: 320,
                  width: double.infinity,
                  fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) => Container(
                    height: 200,
                    color: const Color(0xFFF1F5F9),
                    child: Center(
                      child: Text('صورة الحل المرفوعة من كشكول الطالب', style: GoogleFonts.cairo()),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 14),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: () {
                    Navigator.pop(ctx);
                    _showGradeDialog(sub);
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.screenshotGreen,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  icon: const Icon(Icons.check_circle_rounded, size: 16),
                  label: Text('رصد وتقييم الحل الآن', style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showGradeDialog(TeacherHomeworkSubmission sub) {
    final scoreController = TextEditingController(text: sub.score?.toInt().toString() ?? '10');
    final noteController = TextEditingController(text: sub.teacherNote ?? 'أحسنت، حل نموذجي ومرتب.');

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Text('تقييم ورصد درجة الطالب', style: GoogleFonts.cairo(fontSize: 15, fontWeight: FontWeight.bold)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('الطالب: ${sub.studentName}', style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            TextField(
              controller: scoreController,
              keyboardType: TextInputType.number,
              decoration: InputDecoration(
                labelText: 'الدرجة المستحقة (من 10)',
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
              ),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: noteController,
              maxLines: 2,
              decoration: InputDecoration(
                labelText: 'ملاحظات المعلم وتوجيهاته للطالب',
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: Text('إلغاء', style: GoogleFonts.cairo())),
          ElevatedButton(
            onPressed: () {
              final s = double.tryParse(scoreController.text.trim()) ?? 10.0;
              widget.api.teacherGradeSubmission(sub.id, s, noteController.text.trim());
              Navigator.pop(ctx);
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text('تم رصد الدرجة (${s.toInt()}/10) وإرسال الملاحظات للطالب!', style: GoogleFonts.cairo()), backgroundColor: AppTheme.screenshotGreen),
              );
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.screenshotGreen,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            child: Text('حفظ واعتماد', style: GoogleFonts.cairo(fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Tab 3: Daily Period Attendance Roster (تحضير الحصة اليومي للشعبة)
  // ---------------------------------------------------------------------------
  Widget _buildDailyAttendanceTab() {
    final roster = widget.api.teacherAttendanceRoster;

    final presentCount = roster.where((s) => s.status == 'present').length;
    final absentCount = roster.where((s) => s.status == 'absent').length;
    final lateCount = roster.where((s) => s.status == 'late').length;
    final excusedCount = roster.where((s) => s.status == 'excused').length;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      physics: const BouncingScrollPhysics(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Period Header Card
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
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.event_available_rounded, color: AppTheme.screenshotBlue, size: 20),
                        const SizedBox(width: 8),
                        Text(
                          'تحضير الحصة: الحصة 2 • الرياضيات',
                          style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                        ),
                      ],
                    ),
                    Text(
                      'الأول الثانوي - شعبة (أ)',
                      style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold, color: AppTheme.screenshotBlue),
                    ),
                  ],
                ),
                const SizedBox(height: 12),

                // Attendance Metrics Summary Strip
                Row(
                  children: [
                    Expanded(child: _buildAttendanceCountChip('حاضر', '$presentCount', AppTheme.screenshotGreen)),
                    const SizedBox(width: 6),
                    Expanded(child: _buildAttendanceCountChip('غائب', '$absentCount', AppTheme.rose)),
                    const SizedBox(width: 6),
                    Expanded(child: _buildAttendanceCountChip('متأخر', '$lateCount', AppTheme.screenshotOrange)),
                    const SizedBox(width: 6),
                    Expanded(child: _buildAttendanceCountChip('معذور', '$excusedCount', AppTheme.screenshotBlue)),
                  ],
                ),

                const SizedBox(height: 12),

                // Quick Action: Mark All Present
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    TextButton.icon(
                      onPressed: () {
                        widget.api.markAllTeacherAttendancePresent();
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text('تم تحضير جميع طلاب الشعبة حاضرين بنجاح!', style: GoogleFonts.cairo()), backgroundColor: AppTheme.screenshotGreen),
                        );
                      },
                      icon: const Icon(Icons.done_all_rounded, size: 16, color: AppTheme.screenshotGreen),
                      label: Text('تحضير الكل حاضر', style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold, color: AppTheme.screenshotGreen)),
                    ),
                    ElevatedButton.icon(
                      onPressed: () {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text('تم اعتماد التحضير وإشعار إدارة المدرسة وأولياء الأمور لحظياً!', style: GoogleFonts.cairo(fontWeight: FontWeight.bold)),
                            backgroundColor: AppTheme.screenshotBlue,
                            duration: const Duration(seconds: 4),
                          ),
                        );
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.screenshotBlue,
                        foregroundColor: Colors.white,
                        elevation: 0,
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                      icon: const Icon(Icons.send_rounded, size: 14),
                      label: Text('إرسال التحضير للإدارة', style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold)),
                    ),
                  ],
                ),
              ],
            ),
          ),

          const SizedBox(height: 14),

          Text(
            'قائمة طلاب الشعبة (${roster.length} طلاب):',
            style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
          ),
          const SizedBox(height: 8),

          // Student Roster with 4 Interactive Status Pills
          Container(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: const Color(0xFFE2E8F0)),
              boxShadow: AppTheme.softShadow,
            ),
            child: ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: roster.length,
              separatorBuilder: (_, __) => const Divider(height: 1, color: Color(0xFFF1F5F9)),
              itemBuilder: (context, index) {
                final student = roster[index];
                return _buildStudentAttendanceItem(student);
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAttendanceCountChip(String label, String count, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Column(
        children: [
          Text(count, style: GoogleFonts.cairo(fontSize: 14, fontWeight: FontWeight.w900, color: color)),
          Text(label, style: GoogleFonts.cairo(fontSize: 9, fontWeight: FontWeight.bold, color: color)),
        ],
      ),
    );
  }

  Widget _buildStudentAttendanceItem(TeacherAttendanceStudent student) {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              CircleAvatar(
                radius: 17,
                backgroundColor: AppTheme.screenshotLightBlue,
                child: Text(
                  student.studentName.substring(0, 1),
                  style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.screenshotBlue),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      student.studentName,
                      style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                    ),
                    Text(
                      student.studentNumber,
                      style: GoogleFonts.cairo(fontSize: 10, color: const Color(0xFF64748B)),
                    ),
                  ],
                ),
              ),
            ],
          ),

          const SizedBox(height: 10),

          // 4 Status Buttons in a row
          Row(
            children: [
              Expanded(
                child: _buildStatusPill(
                  label: 'حاضر',
                  isSelected: student.status == 'present',
                  activeColor: AppTheme.screenshotGreen,
                  icon: Icons.check_circle_rounded,
                  onTap: () => widget.api.markTeacherAttendance(student.studentId, 'present'),
                ),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: _buildStatusPill(
                  label: 'غائب',
                  isSelected: student.status == 'absent',
                  activeColor: AppTheme.rose,
                  icon: Icons.cancel_rounded,
                  onTap: () => widget.api.markTeacherAttendance(student.studentId, 'absent'),
                ),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: _buildStatusPill(
                  label: 'متأخر',
                  isSelected: student.status == 'late',
                  activeColor: AppTheme.screenshotOrange,
                  icon: Icons.access_time_rounded,
                  onTap: () => widget.api.markTeacherAttendance(student.studentId, 'late'),
                ),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: _buildStatusPill(
                  label: 'معذور',
                  isSelected: student.status == 'excused',
                  activeColor: AppTheme.screenshotBlue,
                  icon: Icons.medical_services_rounded,
                  onTap: () => widget.api.markTeacherAttendance(student.studentId, 'excused'),
                ),
              ),
            ],
          ),

          if (student.note != null) ...[
            const SizedBox(height: 6),
            Text(
              'ملاحظة: ${student.note}',
              style: GoogleFonts.cairo(fontSize: 10, color: const Color(0xFF64748B), fontStyle: FontStyle.italic),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildStatusPill({
    required String label,
    required bool isSelected,
    required Color activeColor,
    required IconData icon,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.symmetric(vertical: 6),
        decoration: BoxDecoration(
          color: isSelected ? activeColor : const Color(0xFFF8FAFC),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: isSelected ? activeColor : const Color(0xFFE2E8F0),
            width: isSelected ? 1.5 : 1,
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 13, color: isSelected ? Colors.white : const Color(0xFF64748B)),
            const SizedBox(width: 4),
            Text(
              label,
              style: GoogleFonts.cairo(
                fontSize: 11,
                fontWeight: isSelected ? FontWeight.bold : FontWeight.w600,
                color: isSelected ? Colors.white : const Color(0xFF64748B),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Tab 4: Daily Lesson Plan Journal (دفتر تحضير الدروس اليومي للمعلم)
  // ---------------------------------------------------------------------------
  Widget _buildLessonPlanJournalTab() {
    final plans = widget.api.dailyLessonPlans;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      physics: const BouncingScrollPhysics(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header Card with Add Plan Button & AI Generative Actions
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
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'دفتر التحضير الإلكتروني والذكاء الاصطناعي',
                          style: GoogleFonts.cairo(fontSize: 14, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                        ),
                        Text(
                          'تحضير الدروس وبنوك الأسئلة بالاتصال المباشر بنموذج Gemini 3.5 Flash',
                          style: GoogleFonts.cairo(fontSize: 10, color: const Color(0xFF64748B)),
                        ),
                      ],
                    ),
                    ElevatedButton.icon(
                      onPressed: _showAddLessonPlanDialog,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.screenshotBlue,
                        foregroundColor: Colors.white,
                        elevation: 0,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                      icon: const Icon(Icons.add_rounded, size: 16),
                      label: Text('تحضير يدوي', style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold)),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: _showAiLessonPlanModal,
                        style: OutlinedButton.styleFrom(
                          foregroundColor: const Color(0xFF7C3AED),
                          side: const BorderSide(color: Color(0xFFC4B5FD)),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                          padding: const EdgeInsets.symmetric(vertical: 8),
                        ),
                        icon: const Icon(Icons.auto_awesome_rounded, size: 16, color: Color(0xFF7C3AED)),
                        label: Text('توليد تحضير بالذكاء الاصطناعي 🤖', style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold)),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: _showAiQuizGeneratorModal,
                        style: OutlinedButton.styleFrom(
                          foregroundColor: const Color(0xFF0D9488),
                          side: const BorderSide(color: Color(0xFF99F6E4)),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                          padding: const EdgeInsets.symmetric(vertical: 8),
                        ),
                        icon: const Icon(Icons.quiz_rounded, size: 16, color: Color(0xFF0D9488)),
                        label: Text('توليد بنك أسئلة واختبار 📝', style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold)),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),

          const SizedBox(height: 16),

          Text(
            'سجل الدروس المحضرة (${plans.length} دروس):',
            style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
          ),
          const SizedBox(height: 8),

          ...plans.map((p) => _buildLessonPlanCard(p)),
        ],
      ),
    );
  }

  Widget _buildLessonPlanCard(DailyLessonPlan plan) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
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
          // Top Row: Class, Period & Status
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: AppTheme.screenshotBlue.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      plan.subject,
                      style: GoogleFonts.cairo(fontSize: 10, fontWeight: FontWeight.bold, color: AppTheme.screenshotBlue),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    plan.className,
                    style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold, color: const Color(0xFF334155)),
                  ),
                ],
              ),
              InkWell(
                onTap: () => widget.api.toggleLessonPlanCompleted(plan.id),
                borderRadius: BorderRadius.circular(8),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: plan.isCompleted ? AppTheme.screenshotGreen.withValues(alpha: 0.1) : AppTheme.screenshotOrange.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        plan.isCompleted ? Icons.check_circle_rounded : Icons.schedule_rounded,
                        size: 13,
                        color: plan.isCompleted ? AppTheme.screenshotGreen : AppTheme.screenshotOrange,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        plan.isCompleted ? 'تم إنجاز الخطة' : 'مجدولة للتنفيذ',
                        style: GoogleFonts.cairo(
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                          color: plan.isCompleted ? AppTheme.screenshotGreen : AppTheme.screenshotOrange,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),

          const SizedBox(height: 10),

          // Topic Title
          Text(
            plan.topic,
            style: GoogleFonts.cairo(fontSize: 14, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
          ),
          const SizedBox(height: 6),

          // Objectives
          Text(
            'الأهداف السلوكية: ${plan.objectives}',
            style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF475569), height: 1.4),
          ),
          const SizedBox(height: 8),

          // Detail Chips: Period, Pages, Aids
          Wrap(
            spacing: 8,
            runSpacing: 6,
            children: [
              _buildDetailChip(Icons.access_time_rounded, plan.period),
              _buildDetailChip(Icons.menu_book_rounded, plan.pages),
              _buildDetailChip(Icons.devices_other_rounded, plan.teachingAids),
            ],
          ),

          const SizedBox(height: 10),

          // Homework Assigned
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: const Color(0xFFF8FAFC),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: const Color(0xFFE2E8F0)),
            ),
            child: Row(
              children: [
                const Icon(Icons.edit_note_rounded, color: AppTheme.screenshotOrange, size: 18),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'الواجب المعطى: ${plan.homeworkAssigned}',
                    style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold, color: const Color(0xFF334155)),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDetailChip(IconData icon, String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: const Color(0xFFF1F5F9),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: const Color(0xFF64748B)),
          const SizedBox(width: 4),
          Text(text, style: GoogleFonts.cairo(fontSize: 10, color: const Color(0xFF475569))),
        ],
      ),
    );
  }

  void _showAddLessonPlanDialog() {
    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          title: Text('إضافة خطة درس يومي جديد', style: GoogleFonts.cairo(fontSize: 15, fontWeight: FontWeight.bold)),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                DropdownButtonFormField<String>(
                  initialValue: _lpSelectedPeriod,
                  decoration: InputDecoration(
                    labelText: 'الحصة الدراسية',
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  items: const [
                    DropdownMenuItem(value: 'الحصة الأولى (07:45 ص)', child: Text('الحصة الأولى (07:45 ص)')),
                    DropdownMenuItem(value: 'الحصة الثانية (08:35 ص)', child: Text('الحصة الثانية (08:35 ص)')),
                    DropdownMenuItem(value: 'الحصة الثالثة (09:25 ص)', child: Text('الحصة الثالثة (09:25 ص)')),
                    DropdownMenuItem(value: 'الحصة الرابعة (10:15 ص)', child: Text('الحصة الرابعة (10:15 ص)')),
                  ],
                  onChanged: (val) {
                    if (val != null) setDialogState(() => _lpSelectedPeriod = val);
                  },
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: _lpTopicController,
                  decoration: InputDecoration(
                    labelText: 'عنوان وموضوع الدرس',
                    hintText: 'مثال: المتطابقات المثلثية ومعادلاتها',
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: _lpObjectivesController,
                  maxLines: 2,
                  decoration: InputDecoration(
                    labelText: 'الأهداف السلوكية ومخرجات التعلم',
                    hintText: 'أن يتعلم الطالب كيفية حل المسائل...',
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: _lpPagesController,
                  decoration: InputDecoration(
                    labelText: 'الصفحات المقررة من الكتاب',
                    hintText: 'مثال: صـ 55 إلى صـ 61',
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: _lpAidsController,
                  decoration: InputDecoration(
                    labelText: 'الوسائل التعليمية المستخدمة',
                    hintText: 'السبورة + شاشة العرض + أوراق العمل',
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: _lpHomeworkController,
                  decoration: InputDecoration(
                    labelText: 'الواجب المنزلي المعطى للطلاب',
                    hintText: 'تمارين الكتاب صـ 62 المسألة 2 و 4',
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: Text('إلغاء', style: GoogleFonts.cairo())),
            ElevatedButton(
              onPressed: _handleSaveNewLessonPlan,
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.screenshotBlue,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
              child: Text('حفظ في دفتر التحضير', style: GoogleFonts.cairo(fontWeight: FontWeight.bold)),
            ),
          ],
        ),
      ),
    );
  }

  void _showAiLessonPlanModal() {
    final topicCtrl = TextEditingController(text: 'قوانين نيوتن للحركة وتطبيقاتها');
    String? generatedMarkdown;
    bool isGenerating = false;

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setModalState) => Dialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          child: Container(
            width: 600,
            padding: const EdgeInsets.all(20),
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: const Color(0xFF7C3AED).withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: const Icon(Icons.auto_awesome_rounded, color: Color(0xFF7C3AED), size: 20),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'توليد خطة درس نموذجية بالذكاء الاصطناعي',
                              style: GoogleFonts.cairo(fontSize: 14, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                            ),
                            Text(
                              'نموذج Gemini 3.5 Flash الأكاديمي المعتمد',
                              style: GoogleFonts.cairo(fontSize: 10, color: const Color(0xFF7C3AED), fontWeight: FontWeight.bold),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const Divider(height: 20),
                  TextField(
                    controller: topicCtrl,
                    decoration: InputDecoration(
                      labelText: 'موضوع وعنوان الدرس المراد تحضيره',
                      hintText: 'مثال: قوانين نيوتن للحركة وتطبيقاتها',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                  ),
                  const SizedBox(height: 12),
                  if (isGenerating)
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF5F3FF),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: const Color(0xFFDDD6FE)),
                      ),
                      child: Row(
                        children: [
                          const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF7C3AED)),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              'جاري استدعاء نموذج الذكاء الاصطناعي وصياغة الأهداف السلوكية وخطة السير والتقويم...',
                              style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold, color: const Color(0xFF6D28D9)),
                            ),
                          ),
                        ],
                      ),
                    )
                  else if (generatedMarkdown != null)
                    Container(
                      constraints: const BoxConstraints(maxHeight: 350),
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF8FAFC),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: const Color(0xFFE2E8F0)),
                      ),
                      child: SingleChildScrollView(
                        child: SelectableText(
                          generatedMarkdown!,
                          style: GoogleFonts.cairo(fontSize: 11, height: 1.6, color: const Color(0xFF1E293B)),
                        ),
                      ),
                    ),
                  const SizedBox(height: 16),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      TextButton(onPressed: () => Navigator.pop(ctx), child: Text('إغلاق', style: GoogleFonts.cairo())),
                      const SizedBox(width: 8),
                      if (generatedMarkdown != null)
                        ElevatedButton.icon(
                          onPressed: () {
                            widget.api.addDailyLessonPlan(
                              subject: 'العلوم العامة والفيزياء',
                              className: 'الأول الثانوي - شعبة (أ)',
                              period: 'الحصة الأولى (07:45 ص)',
                              topic: topicCtrl.text.trim(),
                              objectives: 'أهداف سلوكية نموذجية تم توليدها بالذكاء الاصطناعي بدقة تامة.',
                              pages: 'صـ 45 - 55',
                              teachingAids: 'شاشة تفاعلية + محاكاة PhET + تجارب عملية',
                              homeworkAssigned: 'تمارين الكتاب وتطبيقات نيوتن الحياتية',
                              notes: 'تم التحضير بواسطة المساعد الذكي',
                            );
                            Navigator.pop(ctx);
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text('تم إدراج خطة الدرس في دفتر التحضير بنجاح! ✅', style: GoogleFonts.cairo()),
                                backgroundColor: AppTheme.emerald,
                              ),
                            );
                          },
                          style: ElevatedButton.styleFrom(
                            backgroundColor: AppTheme.emerald,
                            foregroundColor: Colors.white,
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                          ),
                          icon: const Icon(Icons.bookmark_add_rounded, size: 16),
                          label: Text('اعتماد في دفتر التحضير 📥', style: GoogleFonts.cairo(fontWeight: FontWeight.bold)),
                        )
                      else
                        ElevatedButton.icon(
                          onPressed: () async {
                            if (topicCtrl.text.trim().isEmpty) return;
                            setModalState(() => isGenerating = true);
                            final result = await widget.api.generateTeacherLessonPlanAi(topic: topicCtrl.text.trim());
                            setModalState(() {
                              isGenerating = false;
                              generatedMarkdown = result ?? 'تعذر الحصول على استجابة من نموذج الذكاء الاصطناعي.';
                            });
                          },
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF7C3AED),
                            foregroundColor: Colors.white,
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                          ),
                          icon: const Icon(Icons.bolt_rounded, size: 16),
                          label: Text('توليد الخطة بالذكاء الاصطناعي 🚀', style: GoogleFonts.cairo(fontWeight: FontWeight.bold)),
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  void _showAiQuizGeneratorModal() {
    final topicCtrl = TextEditingController(text: 'قوانين نيوتن للحركة');
    const int numQuestions = 3;
    List<Map<String, dynamic>>? quizQuestions;
    bool isGenerating = false;

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setModalState) => Dialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          child: Container(
            width: 600,
            padding: const EdgeInsets.all(20),
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: const Color(0xFF0D9488).withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: const Icon(Icons.quiz_rounded, color: Color(0xFF0D9488), size: 20),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'توليد بنك أسئلة واختبار قصير بالذكاء الاصطناعي',
                              style: GoogleFonts.cairo(fontSize: 14, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                            ),
                            Text(
                              'أسئلة اختيار من متعدد مع الإجابات النموذجية والشرح العلمي 🌟',
                              style: GoogleFonts.cairo(fontSize: 10, color: const Color(0xFF0D9488), fontWeight: FontWeight.bold),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const Divider(height: 20),
                  TextField(
                    controller: topicCtrl,
                    decoration: InputDecoration(
                      labelText: 'موضوع الاختبار أو بنك الأسئلة',
                      hintText: 'مثال: قوانين نيوتن للحركة',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                  ),
                  const SizedBox(height: 12),
                  if (isGenerating)
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF0FDFA),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: const Color(0xFFCCFBF1)),
                      ),
                      child: Row(
                        children: [
                          const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF0D9488)),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              'جاري توليد الأسئلة والخيارات والإجابات النموذجية من المنهج عبر الذكاء الاصطناعي...',
                              style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold, color: const Color(0xFF0F766E)),
                            ),
                          ),
                        ],
                      ),
                    )
                  else if (quizQuestions != null)
                    Container(
                      constraints: const BoxConstraints(maxHeight: 380),
                      child: ListView.builder(
                        shrinkWrap: true,
                        itemCount: quizQuestions!.length,
                        itemBuilder: (context, idx) {
                          final q = quizQuestions![idx];
                          final opts = q['options'] is List ? q['options'] as List : [];
                          return Container(
                            margin: const EdgeInsets.only(bottom: 12),
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: const Color(0xFFF8FAFC),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: const Color(0xFFE2E8F0)),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'س${idx + 1}: ${q['question'] ?? ''}',
                                  style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                                ),
                                const SizedBox(height: 6),
                                ...opts.map((opt) => Padding(
                                      padding: const EdgeInsets.symmetric(vertical: 2),
                                      child: Row(
                                        children: [
                                          Icon(
                                            opt == q['correct_answer'] ? Icons.check_circle_rounded : Icons.radio_button_unchecked_rounded,
                                            size: 14,
                                            color: opt == q['correct_answer'] ? AppTheme.emerald : Colors.grey,
                                          ),
                                          const SizedBox(width: 6),
                                          Expanded(
                                            child: Text(
                                              opt.toString(),
                                              style: GoogleFonts.cairo(
                                                fontSize: 11,
                                                color: opt == q['correct_answer'] ? AppTheme.emerald : AppTheme.textMain,
                                                fontWeight: opt == q['correct_answer'] ? FontWeight.bold : FontWeight.normal,
                                              ),
                                            ),
                                          ),
                                        ],
                                      ),
                                    )),
                                if (q['explanation'] != null) ...[
                                  const SizedBox(height: 6),
                                  Container(
                                    padding: const EdgeInsets.all(8),
                                    decoration: BoxDecoration(
                                      color: const Color(0xFFEFF6FF),
                                      borderRadius: BorderRadius.circular(8),
                                    ),
                                    child: Text(
                                      '💡 التفسير: ${q['explanation']}',
                                      style: GoogleFonts.cairo(fontSize: 10, color: const Color(0xFF1E40AF)),
                                    ),
                                  ),
                                ],
                              ],
                            ),
                          );
                        },
                      ),
                    ),
                  const SizedBox(height: 16),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      TextButton(onPressed: () => Navigator.pop(ctx), child: Text('إغلاق', style: GoogleFonts.cairo())),
                      const SizedBox(width: 8),
                      ElevatedButton.icon(
                        onPressed: () async {
                          if (topicCtrl.text.trim().isEmpty) return;
                          setModalState(() => isGenerating = true);
                          final result = await widget.api.generateTeacherQuizAi(topic: topicCtrl.text.trim(), numQuestions: numQuestions);
                          setModalState(() {
                            isGenerating = false;
                            quizQuestions = result;
                          });
                        },
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF0D9488),
                          foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                        ),
                        icon: const Icon(Icons.bolt_rounded, size: 16),
                        label: Text('توليد بنك الأسئلة بالذكاء الاصطناعي 🚀', style: GoogleFonts.cairo(fontWeight: FontWeight.bold)),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

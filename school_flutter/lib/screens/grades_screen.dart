import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/api_service.dart';
import '../core/models.dart';
import '../core/theme.dart';
import 'chat_screen.dart';

class GradesScreen extends StatefulWidget {
  final ApiService api;
  const GradesScreen({super.key, required this.api});

  @override
  State<GradesScreen> createState() => _GradesScreenState();
}

class _GradesScreenState extends State<GradesScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  int _selectedTerm = 0; // 0: الفصل الأول, 1: الفصل الثاني, 2: النتيجة السنوية

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.api,
      builder: (context, _) {
        final currentStudent = widget.api.currentStudent;
        if (currentStudent == null) {
          return Scaffold(
            appBar: AppBar(
              title: const Text('كشف الدرجات والنتائج'),
              leading: IconButton(
                icon: const Icon(Icons.arrow_back_ios_new_rounded),
                onPressed: () => Navigator.pop(context),
              ),
            ),
            body: Center(
              child: Padding(
                padding: const EdgeInsets.all(24.0),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.school_outlined, size: 54, color: AppTheme.textMuted),
                    const SizedBox(height: 16),
                    Text(
                      'لا يوجد ملف طالب نشط مرتبط بحسابك في هذه المدرسة',
                      style: GoogleFonts.tajawal(fontSize: 16, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'يمكنك التحقق من المدرسة النشطة أو إضافة كود الطالب من شاشة إدارة الطلاب.',
                      style: GoogleFonts.tajawal(fontSize: 12, color: const Color(0xFF64748B)),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
            ),
          );
        }

        final grades = widget.api.grades;

        double totalEarned = 0;
        double maxPossible = 0;
        for (var g in grades) {
          totalEarned += g.total;
          maxPossible += g.maxTotal;
        }
        final percentage = maxPossible > 0 ? (totalEarned / maxPossible) * 100 : 0.0;

        return Scaffold(
          appBar: AppBar(
            title: Text(
              'سجل الدرجات والشهادات الرسمية',
              style: GoogleFonts.tajawal(fontWeight: FontWeight.bold),
            ),
            leading: IconButton(
              icon: const Icon(Icons.arrow_back_ios_new_rounded),
              onPressed: () => Navigator.pop(context),
            ),
            bottom: PreferredSize(
              preferredSize: const Size.fromHeight(48),
              child: Container(
                margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: AppTheme.borderLight),
                ),
                child: TabBar(
                  controller: _tabController,
                  labelColor: AppTheme.primaryNavy,
                  unselectedLabelColor: AppTheme.textMuted,
                  labelStyle: GoogleFonts.tajawal(fontSize: 11, fontWeight: FontWeight.bold),
                  indicatorColor: AppTheme.accent,
                  indicatorSize: TabBarIndicatorSize.tab,
                  tabs: const [
                    Tab(text: '📑 كشف الدرجات'),
                    Tab(text: '📅 اختبارات الشهور'),
                    Tab(text: '📊 التحليل البياني'),
                  ],
                ),
              ),
            ),
          ),
          body: TabBarView(
            controller: _tabController,
            children: [
              // Tab 1: Official Report Card
              _buildReportCardTab(currentStudent, grades, percentage, totalEarned, maxPossible),

              // Tab 2: Monthly Assessments & Coursework
              _buildMonthlyAssessmentsTab(currentStudent, grades),

              // Tab 3: Performance Analytics & Charts
              _buildAnalyticsTab(currentStudent, grades, percentage),
            ],
          ),
        );
      },
    );
  }

  // ---------------------------------------------------------------------------
  // Tab 1: Official Report Card
  // ---------------------------------------------------------------------------
  Widget _buildReportCardTab(
    StudentProfile student,
    List<GradeRecord> grades,
    double percentage,
    double totalEarned,
    double maxPossible,
  ) {
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      physics: const BouncingScrollPhysics(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Banner
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: AppTheme.cardGradientTeal,
              borderRadius: BorderRadius.circular(18),
              boxShadow: AppTheme.softShadow,
            ),
            child: Column(
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          student.fullName,
                          style: GoogleFonts.tajawal(
                            fontSize: 15,
                            fontWeight: FontWeight.w900,
                            color: Colors.white,
                          ),
                        ),
                        Text(
                          '${student.grade} - ${student.section} (رقم القيد: ${student.studentNumber})',
                          style: GoogleFonts.tajawal(
                            fontSize: 11,
                            color: Colors.white70,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(
                        'ناجح بتفوق ✓',
                        style: GoogleFonts.tajawal(
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                          color: const Color(0xFF064E3B),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: Colors.black.withValues(alpha: 0.16),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceAround,
                    children: [
                      _buildMetricCol('المعدل التراكمي', '${percentage.toStringAsFixed(1)}%'),
                      Container(width: 1, height: 20, color: Colors.white24),
                      _buildMetricCol('المجموع المحصل', '${totalEarned.toInt()} / ${maxPossible.toInt()}'),
                      Container(width: 1, height: 20, color: Colors.white24),
                      _buildMetricCol('الترتيب الأكاديمي', 'الأول على الشعبة 🥇'),
                    ],
                  ),
                ),
                const SizedBox(height: 10),
                // Certificate View Action Button
                InkWell(
                  onTap: () => _showOfficialCertificateDialog(student, percentage, totalEarned, maxPossible),
                  borderRadius: BorderRadius.circular(10),
                  child: Container(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: Colors.white38),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.workspace_premium_rounded, color: Colors.amber, size: 18),
                        const SizedBox(width: 6),
                        Text(
                          'معاينة واستخراج الشهادة الرقمية المعتمدة 📜',
                          style: GoogleFonts.tajawal(
                            color: Colors.white,
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 14),

          // Term Selector Chips
          Row(
            children: [
              _buildTermChip('الفصل الأول 2026/2027', 0),
              const SizedBox(width: 8),
              _buildTermChip('الفصل الثاني', 1),
              const SizedBox(width: 8),
              _buildTermChip('النتيجة النهائية', 2),
            ],
          ),

          const SizedBox(height: 14),

          // Table
          Container(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppTheme.borderLight),
              boxShadow: AppTheme.softShadow,
            ),
            child: Column(
              children: [
                // Header
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  decoration: BoxDecoration(
                    color: AppTheme.primary.withValues(alpha: 0.05),
                    borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
                    border: const Border(bottom: BorderSide(color: AppTheme.borderLight)),
                  ),
                  child: Row(
                    children: [
                      Expanded(flex: 3, child: _buildTableHeaderText('المادة والمعلم')),
                      Expanded(flex: 2, child: _buildTableHeaderText('الأعمال', align: TextAlign.center)),
                      Expanded(flex: 2, child: _buildTableHeaderText('الاختبار', align: TextAlign.center)),
                      Expanded(flex: 2, child: _buildTableHeaderText('المجموع', align: TextAlign.center)),
                      Expanded(flex: 2, child: _buildTableHeaderText('التقدير', align: TextAlign.center)),
                    ],
                  ),
                ),

                // Rows
                ...List.generate(grades.length, (index) {
                  final g = grades[index];
                  final isEven = index % 2 == 0;
                  return InkWell(
                    onTap: () => _showSubjectDetailModal(g),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                      decoration: BoxDecoration(
                        color: isEven ? Colors.white : AppTheme.background.withValues(alpha: 0.5),
                        border: Border(
                          bottom: index < grades.length - 1
                              ? const BorderSide(color: AppTheme.borderLight, width: 0.6)
                              : BorderSide.none,
                        ),
                      ),
                      child: Row(
                        children: [
                          Expanded(
                            flex: 3,
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Text(
                                      g.subject,
                                      style: GoogleFonts.tajawal(
                                        fontSize: 12,
                                        fontWeight: FontWeight.bold,
                                        color: AppTheme.textMain,
                                      ),
                                    ),
                                    const SizedBox(width: 4),
                                    const Icon(Icons.info_outline_rounded, size: 12, color: AppTheme.accent),
                                  ],
                                ),
                                Text(
                                  g.teacher,
                                  style: GoogleFonts.tajawal(
                                    fontSize: 10,
                                    color: AppTheme.textMuted,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          Expanded(
                            flex: 2,
                            child: Text(
                              (g.homeworkScore + g.participation).toStringAsFixed(1),
                              textAlign: TextAlign.center,
                              style: GoogleFonts.tajawal(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                color: AppTheme.textMain,
                              ),
                            ),
                          ),
                          Expanded(
                            flex: 2,
                            child: Text(
                              g.monthlyExam.toStringAsFixed(1),
                              textAlign: TextAlign.center,
                              style: GoogleFonts.tajawal(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                color: AppTheme.textMain,
                              ),
                            ),
                          ),
                          Expanded(
                            flex: 2,
                            child: Text(
                              g.total.toStringAsFixed(1),
                              textAlign: TextAlign.center,
                              style: GoogleFonts.tajawal(
                                fontSize: 12,
                                fontWeight: FontWeight.w900,
                                color: AppTheme.primary,
                              ),
                            ),
                          ),
                          Expanded(
                            flex: 2,
                            child: Center(
                              child: Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                decoration: BoxDecoration(
                                  color: AppTheme.emerald.withValues(alpha: 0.12),
                                  borderRadius: BorderRadius.circular(6),
                                ),
                                child: Text(
                                  g.letterGrade.split(' ').first,
                                  style: GoogleFonts.tajawal(
                                    fontSize: 10,
                                    fontWeight: FontWeight.bold,
                                    color: AppTheme.emerald,
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                }),

                // Footer
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                  decoration: BoxDecoration(
                    color: AppTheme.primary.withValues(alpha: 0.04),
                    borderRadius: const BorderRadius.vertical(bottom: Radius.circular(16)),
                    border: const Border(top: BorderSide(color: AppTheme.borderLight)),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        'المجموع العام لدرجات الفصل:',
                        style: GoogleFonts.tajawal(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          color: AppTheme.textMain,
                        ),
                      ),
                      Text(
                        '${totalEarned.toInt()} من ${maxPossible.toInt()} درجة (${percentage.toStringAsFixed(1)}%)',
                        style: GoogleFonts.tajawal(
                          fontSize: 12,
                          fontWeight: FontWeight.w900,
                          color: AppTheme.emerald,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Tab 2: Monthly Assessments & Coursework Breakdown
  // ---------------------------------------------------------------------------
  Widget _buildMonthlyAssessmentsTab(StudentProfile student, List<GradeRecord> grades) {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      physics: const BouncingScrollPhysics(),
      itemCount: grades.length,
      itemBuilder: (context, index) {
        final g = grades[index];
        return Container(
          margin: const EdgeInsets.only(bottom: 12),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppTheme.borderLight),
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
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: AppTheme.primary.withValues(alpha: 0.08),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: const Icon(Icons.menu_book_rounded, color: AppTheme.primary, size: 18),
                      ),
                      const SizedBox(width: 10),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            g.subject,
                            style: GoogleFonts.tajawal(fontSize: 13, fontWeight: FontWeight.bold, color: AppTheme.textMain),
                          ),
                          Text(
                            g.teacher,
                            style: GoogleFonts.tajawal(fontSize: 10, color: AppTheme.textMuted),
                          ),
                        ],
                      ),
                    ],
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: AppTheme.emerald.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      g.letterGrade,
                      style: GoogleFonts.tajawal(fontSize: 10, fontWeight: FontWeight.bold, color: AppTheme.emerald),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              // Detailed Metric Pills
              Row(
                children: [
                  Expanded(
                    child: _buildAssessmentPill('اختبار شهر 1', g.monthOneExam.toString(), '20', const Color(0xFF2563EB)),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _buildAssessmentPill('اختبار شهر 2', g.monthTwoExam.toString(), '20', const Color(0xFF7C3AED)),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _buildAssessmentPill('الواجبات والأنشطة', g.homeworkScore.toString(), '10', const Color(0xFFD97706)),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _buildAssessmentPill('المواظبة والحضور', g.participation.toString(), '10', const Color(0xFF059669)),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'ملاحظة المعلم: ${g.teacherRemarks}',
                    style: GoogleFonts.tajawal(fontSize: 10, color: AppTheme.textMuted),
                  ),
                  InkWell(
                    onTap: () => _consultAiForSubject(g.subject),
                    child: Row(
                      children: [
                        const Icon(Icons.auto_awesome_rounded, color: AppTheme.accent, size: 12),
                        const SizedBox(width: 4),
                        Text(
                          'استشارة المساعد الذكي',
                          style: GoogleFonts.tajawal(fontSize: 10, color: AppTheme.accent, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildAssessmentPill(String title, String score, String max, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Column(
        children: [
          Text(title, style: GoogleFonts.tajawal(fontSize: 9, color: AppTheme.textMuted)),
          const SizedBox(height: 2),
          Text(
            '$score / $max',
            style: GoogleFonts.tajawal(fontSize: 11, fontWeight: FontWeight.bold, color: color),
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Tab 3: Performance Analytics & Charts
  // ---------------------------------------------------------------------------
  Widget _buildAnalyticsTab(StudentProfile student, List<GradeRecord> grades, double overallGpa) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      physics: const BouncingScrollPhysics(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // GPA Card
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppTheme.borderLight),
              boxShadow: AppTheme.softShadow,
            ),
            child: Row(
              children: [
                SizedBox(
                  width: 60,
                  height: 60,
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      CircularProgressIndicator(
                        value: overallGpa / 100,
                        backgroundColor: AppTheme.background,
                        color: AppTheme.accent,
                        strokeWidth: 6,
                      ),
                      Center(
                        child: Text(
                          '${overallGpa.toStringAsFixed(0)}%',
                          style: GoogleFonts.tajawal(fontSize: 13, fontWeight: FontWeight.w900, color: AppTheme.primaryNavy),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'الأداء الأكاديمي العام: ممتاز مع مرتبة الشرف 🏆',
                        style: GoogleFonts.tajawal(fontSize: 13, fontWeight: FontWeight.bold, color: AppTheme.textMain),
                      ),
                      Text(
                        'الطالب يحقق نتائج أعلى من متوسط الشعبة بنسبة +14.2%، ومؤهل للترشح للأولمبياد العلمي.',
                        style: GoogleFonts.tajawal(fontSize: 11, color: AppTheme.textMuted),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 16),

          Text(
            'مقارنة تحصيل المواد الدراسية:',
            style: GoogleFonts.tajawal(fontSize: 13, fontWeight: FontWeight.bold, color: AppTheme.textMain),
          ),
          const SizedBox(height: 10),

          // Bar Comparisons
          ...grades.map((g) {
            final double pct = g.maxTotal > 0 ? (g.total / g.maxTotal) : 0;
            return Container(
              margin: const EdgeInsets.only(bottom: 12),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppTheme.borderLight),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        g.subject,
                        style: GoogleFonts.tajawal(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.textMain),
                      ),
                      Text(
                        '${(pct * 100).toStringAsFixed(1)}% (${g.total} / ${g.maxTotal})',
                        style: GoogleFonts.tajawal(fontSize: 11, fontWeight: FontWeight.bold, color: AppTheme.primary),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(6),
                    child: LinearProgressIndicator(
                      value: pct,
                      minHeight: 8,
                      backgroundColor: AppTheme.background,
                      color: pct >= 0.9 ? AppTheme.emerald : (pct >= 0.8 ? AppTheme.accent : Colors.orange),
                    ),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Dialog: Official Certificate
  // ---------------------------------------------------------------------------
  void _showOfficialCertificateDialog(
    StudentProfile student,
    double percentage,
    double totalEarned,
    double maxPossible,
  ) {
    showDialog(
      context: context,
      builder: (context) {
        return Dialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          child: Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: const Color(0xFFD4AF37), width: 2), // Gold border
            ),
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.school_rounded, color: Color(0xFF0F172A), size: 28),
                      const SizedBox(width: 8),
                      Text(
                        'المدرسة الافتراضية الحديثة',
                        style: GoogleFonts.tajawal(fontSize: 15, fontWeight: FontWeight.w900, color: const Color(0xFF0F172A)),
                      ),
                    ],
                  ),
                  Text(
                    'شهادة تفوق وتقدير أكاديمي رسمي',
                    style: GoogleFonts.tajawal(fontSize: 12, color: const Color(0xFFD4AF37), fontWeight: FontWeight.bold),
                  ),
                  const Divider(height: 24, thickness: 1),
                  Text(
                    'تشهد إدارة المدرسة بأن الطالب:',
                    style: GoogleFonts.tajawal(fontSize: 12, color: AppTheme.textMuted),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    student.fullName,
                    style: GoogleFonts.tajawal(fontSize: 16, fontWeight: FontWeight.w900, color: AppTheme.primaryNavy),
                  ),
                  Text(
                    'المقيد برقم قيد (${student.studentNumber}) - ${student.grade}',
                    style: GoogleFonts.tajawal(fontSize: 11, color: AppTheme.textMain),
                  ),
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF8FAFC),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppTheme.borderLight),
                    ),
                    child: Column(
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text('المعدل العام:', style: GoogleFonts.tajawal(fontSize: 11, color: AppTheme.textMuted)),
                            Text('${percentage.toStringAsFixed(1)}%', style: GoogleFonts.tajawal(fontSize: 13, fontWeight: FontWeight.bold, color: AppTheme.emerald)),
                          ],
                        ),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text('الترتيب الأكاديمي:', style: GoogleFonts.tajawal(fontSize: 11, color: AppTheme.textMuted)),
                            Text('الأول على الشعبة 🥇', style: GoogleFonts.tajawal(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.textMain)),
                          ],
                        ),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text('التقدير العام:', style: GoogleFonts.tajawal(fontSize: 11, color: AppTheme.textMuted)),
                            Text('ممتاز مع مرتبة الشرف', style: GoogleFonts.tajawal(fontSize: 12, fontWeight: FontWeight.bold, color: const Color(0xFFD4AF37))),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 14),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Column(
                        children: [
                          const Icon(Icons.qr_code_2_rounded, size: 48, color: AppTheme.primaryNavy),
                          Text('كود التحقق الرقمي', style: GoogleFonts.tajawal(fontSize: 8, color: AppTheme.textMuted)),
                        ],
                      ),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Text('ختم وتوقيع الإدارة العامة', style: GoogleFonts.tajawal(fontSize: 9, fontWeight: FontWeight.bold)),
                          Text('مدير المنصة: د. سيف العتاب', style: GoogleFonts.tajawal(fontSize: 9, color: AppTheme.textMuted)),
                          Text('المشرف الأكاديمي: أ. عبد الرحمن', style: GoogleFonts.tajawal(fontSize: 9, color: AppTheme.textMuted)),
                        ],
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.primaryNavy,
                      foregroundColor: Colors.white,
                      minimumSize: const Size(double.infinity, 40),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    icon: const Icon(Icons.download_rounded, size: 16),
                    label: Text('تنزيل وحفظ الشهادة بصيغة PDF', style: GoogleFonts.tajawal(fontSize: 11, fontWeight: FontWeight.bold)),
                    onPressed: () {
                      Navigator.pop(context);
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text('تم تنزيل الشهادة الرقمية المعتمدة بنجاح ✅', style: GoogleFonts.tajawal()),
                          backgroundColor: AppTheme.emerald,
                        ),
                      );
                    },
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  // ---------------------------------------------------------------------------
  // Modal: Subject Detail
  // ---------------------------------------------------------------------------
  void _showSubjectDetailModal(GradeRecord g) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (context) {
        return Container(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'تفاصيل مادة: ${g.subject}',
                    style: GoogleFonts.tajawal(fontSize: 14, fontWeight: FontWeight.bold, color: AppTheme.primaryNavy),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: AppTheme.emerald.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      g.letterGrade,
                      style: GoogleFonts.tajawal(fontSize: 10, fontWeight: FontWeight.bold, color: AppTheme.emerald),
                    ),
                  ),
                ],
              ),
              Text('المعلم المشرف: ${g.teacher}', style: GoogleFonts.tajawal(fontSize: 11, color: AppTheme.textMuted)),
              const Divider(height: 20),
              _buildDetailRow('اختبار الشهر الأول:', '${g.monthOneExam} من 20 درجة'),
              _buildDetailRow('اختبار الشهر الثاني:', '${g.monthTwoExam} من 20 درجة'),
              _buildDetailRow('الواجبات والتطبيقات:', '${g.homeworkScore} من 10 درجات'),
              _buildDetailRow('المواظبة والمشاركة الصفية:', '${g.participation} من 10 درجات'),
              _buildDetailRow('المجموع الكلي:', '${g.total} من ${g.maxTotal} درجة'),
              _buildDetailRow('الترتيب في المادة:', 'الأول على الشعبة 🥇'),
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AppTheme.background,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  'ملاحظة المعلم: ${g.teacherRemarks}',
                  style: GoogleFonts.tajawal(fontSize: 11, color: AppTheme.textMain),
                ),
              ),
              const SizedBox(height: 14),
              ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.accent,
                  foregroundColor: Colors.white,
                  minimumSize: const Size(double.infinity, 42),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                icon: const Icon(Icons.auto_awesome_rounded, size: 16),
                label: Text('اسأل الذكاء الاصطناعي لرفع مستواك في هذه المادة 🤖', style: GoogleFonts.tajawal(fontSize: 11, fontWeight: FontWeight.bold)),
                onPressed: () {
                  Navigator.pop(context);
                  _consultAiForSubject(g.subject);
                },
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildDetailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: GoogleFonts.tajawal(fontSize: 11, color: AppTheme.textMuted)),
          Text(value, style: GoogleFonts.tajawal(fontSize: 11, fontWeight: FontWeight.bold, color: AppTheme.textMain)),
        ],
      ),
    );
  }

  void _consultAiForSubject(String subject) {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => ChatScreen(api: widget.api)),
    );
    widget.api.askAiCopilot('أريد خطة مراجعة وتمارين إضافية للتفوق أكثر في مادة $subject');
  }

  Widget _buildMetricCol(String label, String value) {
    return Column(
      children: [
        Text(label, style: GoogleFonts.tajawal(color: Colors.white70, fontSize: 10)),
        const SizedBox(height: 2),
        Text(value, style: GoogleFonts.tajawal(color: Colors.white, fontWeight: FontWeight.w900, fontSize: 13)),
      ],
    );
  }

  Widget _buildTermChip(String label, int index) {
    final isSelected = _selectedTerm == index;
    return InkWell(
      onTap: () => setState(() => _selectedTerm = index),
      borderRadius: BorderRadius.circular(14),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected ? AppTheme.primary : Colors.white,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: isSelected ? AppTheme.primary : AppTheme.borderLight,
          ),
        ),
        child: Text(
          label,
          style: GoogleFonts.tajawal(
            fontSize: 11,
            fontWeight: isSelected ? FontWeight.bold : FontWeight.w600,
            color: isSelected ? Colors.white : AppTheme.textMuted,
          ),
        ),
      ),
    );
  }

  Widget _buildTableHeaderText(String text, {TextAlign align = TextAlign.start}) {
    return Text(
      text,
      textAlign: align,
      style: GoogleFonts.tajawal(
        fontSize: 11,
        fontWeight: FontWeight.bold,
        color: AppTheme.textMain,
      ),
    );
  }
}


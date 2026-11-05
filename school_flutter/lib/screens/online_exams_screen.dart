import 'dart:async';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/api_service.dart';
import '../core/models.dart';
import '../core/theme.dart';

class OnlineExamsScreen extends StatefulWidget {
  final ApiService api;
  const OnlineExamsScreen({super.key, required this.api});

  @override
  State<OnlineExamsScreen> createState() => _OnlineExamsScreenState();
}

class _OnlineExamsScreenState extends State<OnlineExamsScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
    _loadExams();
  }

  Future<void> _loadExams() async {
    setState(() => _isLoading = true);
    await widget.api.fetchStudentOnlineExams();
    if (mounted) setState(() => _isLoading = false);
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
        final exams = widget.api.studentOnlineExams;
        final available = exams.where((e) => e.status == 'available' || e.status == 'in_progress').toList();
        final upcoming = exams.where((e) => e.status == 'upcoming').toList();
        final completed = exams.where((e) => e.status == 'submitted' || e.status == 'graded').toList();

        return Scaffold(
          backgroundColor: const Color(0xFFF8FAFC),
          appBar: AppBar(
            backgroundColor: Colors.white,
            elevation: 0,
            title: Text(
              'الاختبارات الإلكترونية',
              style: GoogleFonts.tajawal(
                fontSize: 18,
                fontWeight: FontWeight.w900,
                color: const Color(0xFF0F172A),
              ),
            ),
            actions: [
              IconButton(
                icon: const Icon(Icons.refresh_rounded, color: AppTheme.screenshotBlue),
                onPressed: _loadExams,
                tooltip: 'تحديث الاختبارات',
              ),
            ],
            bottom: TabBar(
              controller: _tabController,
              labelColor: AppTheme.screenshotBlue,
              unselectedLabelColor: const Color(0xFF64748B),
              labelStyle: GoogleFonts.tajawal(fontSize: 13, fontWeight: FontWeight.bold),
              unselectedLabelStyle: GoogleFonts.tajawal(fontSize: 13, fontWeight: FontWeight.w600),
              indicatorColor: AppTheme.screenshotBlue,
              indicatorWeight: 3,
              tabs: const [
                Tab(text: 'الكل'),
                Tab(text: 'المتاحة الآن'),
                Tab(text: 'القادمة'),
                Tab(text: 'المكتملة'),
              ],
            ),
          ),
          body: _isLoading
              ? const Center(child: CircularProgressIndicator(color: AppTheme.screenshotBlue))
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _buildExamList(exams, 'لا توجد اختبارات إلكترونية مسجلة'),
                    _buildExamList(available, 'لا توجد اختبارات متاحة للحل حالياً'),
                    _buildExamList(upcoming, 'لا توجد اختبارات قادمة مجدولة'),
                    _buildExamList(completed, 'لم تكمل أي اختبارات إلكترونية بعد'),
                  ],
                ),
        );
      },
    );
  }

  Widget _buildExamList(List<OnlineExamItem> list, String emptyMessage) {
    if (list.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 72,
                height: 72,
                decoration: BoxDecoration(
                  color: AppTheme.screenshotLightBlue,
                  borderRadius: BorderRadius.circular(20),
                ),
                child: const Icon(Icons.assignment_outlined, size: 36, color: AppTheme.screenshotBlue),
              ),
              const SizedBox(height: 16),
              Text(
                emptyMessage,
                textAlign: TextAlign.center,
                style: GoogleFonts.tajawal(fontSize: 15, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
              ),
              const SizedBox(height: 8),
              Text(
                'يتم إدراج الاختبارات ونشر أوراق الإجابة آلياً وفق الخطة الدراسية لشعبتك.',
                textAlign: TextAlign.center,
                style: GoogleFonts.tajawal(fontSize: 12, color: const Color(0xFF64748B)),
              ),
              const SizedBox(height: 24),
              OutlinedButton.icon(
                onPressed: () => _startSamplePracticeExam(),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppTheme.screenshotBlue,
                  side: const BorderSide(color: AppTheme.screenshotBlue),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                ),
                icon: const Icon(Icons.play_circle_outline_rounded, size: 20),
                label: Text(
                  'خوض اختبار تجريبي تدريبي',
                  style: GoogleFonts.tajawal(fontSize: 13, fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      physics: const BouncingScrollPhysics(),
      itemCount: list.length,
      itemBuilder: (context, index) {
        return _buildExamCard(list[index]);
      },
    );
  }

  Widget _buildExamCard(OnlineExamItem exam) {
    Color statusBg = const Color(0xFFEFF6FF);
    Color statusText = AppTheme.screenshotBlue;
    String statusLabel = 'متاح الآن';

    if (exam.status == 'graded' || exam.status == 'submitted') {
      statusBg = const Color(0xFFDCFCE7);
      statusText = const Color(0xFF166534);
      statusLabel = 'تم التسليم';
    } else if (exam.status == 'upcoming') {
      statusBg = const Color(0xFFFEF3C7);
      statusText = const Color(0xFF92400E);
      statusLabel = 'قادم قريباً';
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 14),
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
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: AppTheme.screenshotLightBlue,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  exam.subjectName,
                  style: GoogleFonts.tajawal(fontSize: 11, fontWeight: FontWeight.bold, color: AppTheme.screenshotBlue),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: statusBg,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  statusLabel,
                  style: GoogleFonts.tajawal(fontSize: 11, fontWeight: FontWeight.bold, color: statusText),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            exam.title,
            style: GoogleFonts.tajawal(fontSize: 15, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
          ),
          if (exam.description.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              exam.description,
              style: GoogleFonts.tajawal(fontSize: 12, color: const Color(0xFF64748B)),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ],
          const SizedBox(height: 12),
          Row(
            children: [
              const Icon(Icons.timer_outlined, size: 16, color: Color(0xFF64748B)),
              const SizedBox(width: 4),
              Text(
                'المدة: ${exam.durationMinutes} دقيقة',
                style: GoogleFonts.tajawal(fontSize: 12, color: const Color(0xFF64748B)),
              ),
              const SizedBox(width: 16),
              const Icon(Icons.grade_outlined, size: 16, color: Color(0xFF64748B)),
              const SizedBox(width: 4),
              Text(
                'الدرجة: ${exam.totalScore.toInt()} درجة',
                style: GoogleFonts.tajawal(fontSize: 12, color: const Color(0xFF64748B)),
              ),
            ],
          ),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: () => _openExamPaper(exam),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.screenshotBlue,
                foregroundColor: Colors.white,
                elevation: 0,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                padding: const EdgeInsets.symmetric(vertical: 10),
              ),
              child: Text(
                exam.status == 'submitted' || exam.status == 'graded' ? 'عرض تفاصيل الإجابة' : 'بدء الاختبار الآن',
                style: GoogleFonts.tajawal(fontSize: 13, fontWeight: FontWeight.bold),
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _startSamplePracticeExam() {
    final sampleExam = OnlineExamItem(
      id: 'practice-1',
      title: 'اختبار تدريبي في ميكانيكا نيوتن ومعادلات الحركة',
      description: 'اختبار تدريبي تفاعلي لقياس جاهزيتك للاختبارات الشهرية الوزارية المعتمدة.',
      subjectName: 'العلوم العامة والفيزياء',
      teacherName: 'أ. إبراهيم الحداد',
      durationMinutes: 15,
      startTime: 'الآن',
      endTime: 'بعد 15 دقيقة',
      totalScore: 20,
      passingScore: 10,
      status: 'available',
    );
    _openExamPaper(sampleExam);
  }

  void _openExamPaper(OnlineExamItem exam) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => ExamPaperScreen(exam: exam, api: widget.api),
      ),
    );
  }
}

// -----------------------------------------------------------------------------
// Interactive Exam Paper Viewer with Timer & Submission (STU-08 & STU-09)
// -----------------------------------------------------------------------------
class ExamPaperScreen extends StatefulWidget {
  final OnlineExamItem exam;
  final ApiService api;
  const ExamPaperScreen({super.key, required this.exam, required this.api});

  @override
  State<ExamPaperScreen> createState() => _ExamPaperScreenState();
}

class _ExamPaperScreenState extends State<ExamPaperScreen> {
  int _currentQuestionIndex = 0;
  final Map<int, int> _selectedAnswers = {};
  late int _remainingSeconds;
  Timer? _timer;

  final List<Map<String, dynamic>> _sampleQuestions = [
    {
      'question': 'ما هو نص قانون نيوتن الأول في الحركة المعتمد في المنهج الوزاري؟',
      'options': [
        'الجسم الساكن يبقى ساكناً والمتحرك يستمر بحركته ما لم تؤثر عليه قوة خارجية محصلة.',
        'لكل فعل رد فعل مساوٍ له في المقدار ومضاد له في الاتجاه.',
        'القوة المحصلة تساوي حاصل ضرب الكتلة في التسارع.',
        'الطاقة لا تفنى ولا تستحدث من العدم ولكن تتحول من شكل لآخر.',
      ],
      'points': 5,
    },
    {
      'question': 'إذا أثرت قوة محصلة مقدارها 20 نيوتن على جسم كتلته 4 كجم، فكم يكون تسارعه الخطي؟',
      'options': [
        '5 م/ث²',
        '80 م/ث²',
        '0.2 م/ث²',
        '16 م/ث²',
      ],
      'points': 5,
    },
    {
      'question': 'ما هي الخاصية التي تعبر عن مقاومة الجسم للتغير في حالته الحركية؟',
      'options': [
        'القصور الذاتي (Inertia)',
        'الوزن النوعي',
        'الاحتكاك الانزلاقي',
        'كمية المادة',
      ],
      'points': 5,
    },
    {
      'question': 'في السقوط الحر للأجسام بالقرب من سطح الأرض بإهمال مقاومة الهواء، يكون التسارع:',
      'options': [
        'ثابتاً ويساوي تقريباً 9.8 م/ث²',
        'متغيراً بحسب كتلة الجسم الساقط',
        'صفراً عند أعلى نقطة دائماً',
        'مساوياً للصفر طوال فترة الهبوط',
      ],
      'points': 5,
    },
  ];

  @override
  void initState() {
    super.initState();
    _remainingSeconds = widget.exam.durationMinutes * 60;
    _startTimer();
  }

  void _startTimer() {
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (_remainingSeconds > 0) {
        setState(() => _remainingSeconds--);
      } else {
        _timer?.cancel();
        _submitExam(autoSubmit: true);
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  String _formatTimer() {
    final m = (_remainingSeconds ~/ 60).toString().padLeft(2, '0');
    final s = (_remainingSeconds % 60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  void _submitExam({bool autoSubmit = false}) {
    _timer?.cancel();
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) {
        return AlertDialog(
          backgroundColor: Colors.white,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: Row(
            children: [
              const Icon(Icons.check_circle_rounded, color: AppTheme.screenshotGreen, size: 24),
              const SizedBox(width: 8),
              Text(
                'تم تسليم ورقة الاختبار',
                style: GoogleFonts.tajawal(fontSize: 16, fontWeight: FontWeight.bold),
              ),
            ],
          ),
          content: Text(
            autoSubmit
                ? 'انتهى الوقت المحدد للاختبار وتم حفظ إجاباتك وتسليمها بنجاح إلى منصة الاختبارات الإلكترونية.'
                : 'تم اعتماد إجاباتك وإرسال ورقة الاختبار إلى خادم المدرسة بنجاح. ستعلن النتائج فور اعتمادها.',
            style: GoogleFonts.tajawal(fontSize: 13, color: const Color(0xFF334155)),
          ),
          actions: [
            ElevatedButton(
              onPressed: () {
                Navigator.pop(context);
                Navigator.pop(context);
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.screenshotGreen,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
              child: Text('العودة للاختبارات', style: GoogleFonts.tajawal(fontWeight: FontWeight.bold)),
            ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final currentQ = _sampleQuestions[_currentQuestionIndex];
    final options = currentQ['options'] as List<String>;

    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        title: Text(
          widget.exam.title,
          style: GoogleFonts.tajawal(fontSize: 15, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
        ),
        actions: [
          Container(
            margin: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: _remainingSeconds < 300 ? const Color(0xFFFEE2E2) : AppTheme.screenshotLightBlue,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              children: [
                Icon(
                  Icons.alarm_rounded,
                  size: 16,
                  color: _remainingSeconds < 300 ? Colors.red : AppTheme.screenshotBlue,
                ),
                const SizedBox(width: 6),
                Text(
                  _formatTimer(),
                  style: GoogleFonts.tajawal(
                    fontSize: 13,
                    fontWeight: FontWeight.bold,
                    color: _remainingSeconds < 300 ? Colors.red : AppTheme.screenshotBlue,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Progress Bar
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'السؤال ${_currentQuestionIndex + 1} من ${_sampleQuestions.length}',
                  style: GoogleFonts.tajawal(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                ),
                Text(
                  '${currentQ['points']} درجات',
                  style: GoogleFonts.tajawal(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.screenshotBlue),
                ),
              ],
            ),
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: (_currentQuestionIndex + 1) / _sampleQuestions.length,
                backgroundColor: const Color(0xFFE2E8F0),
                valueColor: const AlwaysStoppedAnimation(AppTheme.screenshotBlue),
                minHeight: 6,
              ),
            ),
            const SizedBox(height: 20),

            // Question Card
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
                  Text(
                    currentQ['question'],
                    style: GoogleFonts.tajawal(fontSize: 15, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                  ),
                  const SizedBox(height: 18),
                  ...List.generate(options.length, (optIdx) {
                    final isSelected = _selectedAnswers[_currentQuestionIndex] == optIdx;
                    return GestureDetector(
                      onTap: () {
                        setState(() => _selectedAnswers[_currentQuestionIndex] = optIdx);
                      },
                      child: Container(
                        margin: const EdgeInsets.only(bottom: 10),
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                        decoration: BoxDecoration(
                          color: isSelected ? const Color(0xFFEFF6FF) : Colors.white,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(
                            color: isSelected ? AppTheme.screenshotBlue : const Color(0xFFCBD5E1),
                            width: isSelected ? 2 : 1,
                          ),
                        ),
                        child: Row(
                          children: [
                            Container(
                              width: 22,
                              height: 22,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: isSelected ? AppTheme.screenshotBlue : Colors.transparent,
                                border: Border.all(
                                  color: isSelected ? AppTheme.screenshotBlue : const Color(0xFF94A3B8),
                                  width: 2,
                                ),
                              ),
                              child: isSelected
                                  ? const Icon(Icons.check, size: 14, color: Colors.white)
                                  : null,
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                options[optIdx],
                                style: GoogleFonts.tajawal(
                                  fontSize: 13,
                                  fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                                  color: isSelected ? AppTheme.screenshotBlue : const Color(0xFF0F172A),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    );
                  }),
                ],
              ),
            ),

            const SizedBox(height: 24),

            // Navigation Buttons
            Row(
              children: [
                if (_currentQuestionIndex > 0)
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => setState(() => _currentQuestionIndex--),
                      style: OutlinedButton.styleFrom(
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                      child: Text('السابق', style: GoogleFonts.tajawal(fontWeight: FontWeight.bold)),
                    ),
                  ),
                if (_currentQuestionIndex > 0) const SizedBox(width: 12),
                Expanded(
                  child: ElevatedButton(
                    onPressed: () {
                      if (_currentQuestionIndex < _sampleQuestions.length - 1) {
                        setState(() => _currentQuestionIndex++);
                      } else {
                        _submitExam();
                      }
                    },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _currentQuestionIndex == _sampleQuestions.length - 1
                          ? AppTheme.screenshotGreen
                          : AppTheme.screenshotBlue,
                      foregroundColor: Colors.white,
                      elevation: 0,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                    child: Text(
                      _currentQuestionIndex == _sampleQuestions.length - 1 ? 'تسليم الاختبار النهائي' : 'السؤال التالي',
                      style: GoogleFonts.tajawal(fontWeight: FontWeight.bold),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}


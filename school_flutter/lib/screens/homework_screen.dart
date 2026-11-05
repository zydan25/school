import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/api_service.dart';
import '../core/models.dart';
import '../core/theme.dart';

class HomeworkScreen extends StatefulWidget {
  final ApiService api;
  const HomeworkScreen({super.key, required this.api});

  @override
  State<HomeworkScreen> createState() => _HomeworkScreenState();
}

class _HomeworkScreenState extends State<HomeworkScreen> {
  int _selectedFilterIndex = 0; // 0: الكل, 1: قيد الحل, 2: المكتملة
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _loadHomeworks();
  }

  Future<void> _loadHomeworks() async {
    setState(() => _isLoading = true);
    await widget.api.fetchStudentHomeworks();
    if (mounted) setState(() => _isLoading = false);
  }

  Color _getSubjectColor(String subject) {
    if (subject.contains('رياضيات')) return AppTheme.screenshotBlue;
    if (subject.contains('فيزياء')) return AppTheme.screenshotPurple;
    if (subject.contains('عربية')) return AppTheme.screenshotGreen;
    if (subject.contains('كيمياء')) return AppTheme.screenshotOrange;
    return const Color(0xFF4F46E5);
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.api,
      builder: (context, _) {
        final allHomeworks = widget.api.studentHomeworks;
        final filteredHomeworks = allHomeworks.where((hw) {
          if (_selectedFilterIndex == 1) return hw.status == 'pending';
          if (_selectedFilterIndex == 2) return hw.status != 'pending';
          return true;
        }).toList();

        return Scaffold(
          backgroundColor: const Color(0xFFF8FAFC),
          appBar: AppBar(
            backgroundColor: Colors.white,
            elevation: 0,
            title: Text(
              'الواجبات والمهام المدرسية',
              style: GoogleFonts.cairo(fontSize: 16, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
            ),
            leading: IconButton(
              icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18, color: Color(0xFF0F172A)),
              onPressed: () => Navigator.pop(context),
            ),
            actions: [
              IconButton(
                icon: const Icon(Icons.refresh_rounded, color: AppTheme.screenshotBlue),
                onPressed: _loadHomeworks,
                tooltip: 'تحديث الواجبات',
              ),
            ],
          ),
          body: Column(
            children: [
              if (_isLoading)
                const LinearProgressIndicator(
                  color: AppTheme.screenshotBlue,
                  backgroundColor: Color(0xFFE2E8F0),
                  minHeight: 2,
                ),
              // 1. Filter Chips Row
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: Row(
                  children: [
                    _buildFilterChip('الكل (${allHomeworks.length})', 0),
                    const SizedBox(width: 8),
                    _buildFilterChip('مطلوب الحل', 1),
                    const SizedBox(width: 8),
                    _buildFilterChip('تم التسليم', 2),
                  ],
                ),
              ),

              const SizedBox(height: 6),

              // 2. Homework Cards List
              Expanded(
                child: filteredHomeworks.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            const Icon(Icons.assignment_turned_in_rounded, size: 44, color: AppTheme.screenshotGreen),
                            const SizedBox(height: 8),
                            Text(
                              'لا توجد واجبات معلقة في هذا القسم',
                              style: GoogleFonts.cairo(fontWeight: FontWeight.bold, color: const Color(0xFF64748B)),
                            ),
                          ],
                        ),
                      )
                    : ListView.builder(
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                        physics: const BouncingScrollPhysics(),
                        itemCount: filteredHomeworks.length,
                        itemBuilder: (context, index) {
                          final hw = filteredHomeworks[index];
                          return _buildHomeworkCard(context, hw);
                        },
                      ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildFilterChip(String label, int index) {
    final isSelected = _selectedFilterIndex == index;
    return InkWell(
      onTap: () => setState(() => _selectedFilterIndex = index),
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected ? AppTheme.screenshotBlue : Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isSelected ? AppTheme.screenshotBlue : const Color(0xFFE2E8F0),
          ),
          boxShadow: isSelected ? AppTheme.softShadow : null,
        ),
        child: Text(
          label,
          style: GoogleFonts.cairo(
            fontSize: 11,
            fontWeight: isSelected ? FontWeight.bold : FontWeight.w600,
            color: isSelected ? Colors.white : const Color(0xFF64748B),
          ),
        ),
      ),
    );
  }

  Widget _buildHomeworkCard(BuildContext context, HomeworkItem hw) {
    final subjectColor = _getSubjectColor(hw.subject);
    final isPending = hw.status == 'pending';
    final isImageUpload = hw.submissionType == 'image_upload';

    Color statusColor;
    String statusText;
    IconData statusIcon;

    if (hw.status == 'graded') {
      statusColor = AppTheme.screenshotGreen;
      statusText = 'مقيّم (${hw.studentScore}/${hw.maxScore})';
      statusIcon = Icons.stars_rounded;
    } else if (hw.status == 'submitted') {
      statusColor = AppTheme.screenshotBlue;
      statusText = 'تم التسليم';
      statusIcon = Icons.check_circle_outline_rounded;
    } else {
      statusColor = AppTheme.rose;
      statusText = 'مطلوب التسليم';
      statusIcon = Icons.alarm_rounded;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFE2E8F0)),
        boxShadow: AppTheme.softShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header strip
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            decoration: const BoxDecoration(
              color: Color(0xFFF8FAFC),
              borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
              border: Border(bottom: BorderSide(color: Color(0xFFF1F5F9))),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: subjectColor.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        hw.subject,
                        style: GoogleFonts.cairo(
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          color: subjectColor,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      hw.teacherName,
                      style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF64748B), fontWeight: FontWeight.w600),
                    ),
                  ],
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: statusColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Row(
                    children: [
                      Icon(statusIcon, color: statusColor, size: 13),
                      const SizedBox(width: 4),
                      Text(
                        statusText,
                        style: GoogleFonts.cairo(fontSize: 10, fontWeight: FontWeight.bold, color: statusColor),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

          // Body
          Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  hw.title,
                  style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                ),
                const SizedBox(height: 4),
                Text(
                  hw.description,
                  style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF64748B), height: 1.4),
                ),
                const SizedBox(height: 10),

                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.calendar_today_rounded, size: 13, color: Color(0xFF94A3B8)),
                        const SizedBox(width: 4),
                        Text(
                          'الموعد: ${hw.dueDate}',
                          style: GoogleFonts.cairo(fontSize: 10, color: const Color(0xFF64748B)),
                        ),
                        if (isImageUpload) ...[
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                            decoration: BoxDecoration(
                              color: AppTheme.screenshotOrange.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              'كشكول (صورة)',
                              style: GoogleFonts.cairo(fontSize: 9, color: AppTheme.screenshotOrange, fontWeight: FontWeight.bold),
                            ),
                          ),
                        ],
                      ],
                    ),
                    ElevatedButton.icon(
                      onPressed: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => QuestionSolverScreen(api: widget.api, homework: hw),
                          ),
                        );
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: isPending ? AppTheme.screenshotBlue : const Color(0xFF6C5CE7),
                        foregroundColor: Colors.white,
                        elevation: 0,
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                      ),
                      icon: Icon(
                        isImageUpload ? Icons.upload_file_rounded : (isPending ? Icons.edit_note_rounded : Icons.visibility_rounded),
                        size: 15,
                      ),
                      label: Text(
                        isImageUpload ? (isPending ? 'رفع صورة الحل' : 'معاينة الحل') : (isPending ? 'حل الواجب' : 'استعراض الإجابات'),
                        style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// -----------------------------------------------------------------------------
// Interactive Question Paper or Notebook Photo Upload Solver
// -----------------------------------------------------------------------------
class QuestionSolverScreen extends StatefulWidget {
  final ApiService api;
  final HomeworkItem homework;
  const QuestionSolverScreen({super.key, required this.api, required this.homework});

  @override
  State<QuestionSolverScreen> createState() => _QuestionSolverScreenState();
}

class _QuestionSolverScreenState extends State<QuestionSolverScreen> {
  final Map<String, String> _answers = {};
  final TextEditingController _essayController = TextEditingController();
  final TextEditingController _photoNoteController = TextEditingController();
  bool _isPlayingAudio = false;
  String? _selectedPhotoUrl;

  @override
  void initState() {
    super.initState();
    for (var q in widget.homework.questions) {
      if (q.userAnswer != null) {
        _answers[q.id] = q.userAnswer!;
      }
    }
    if (widget.homework.submittedImageUrl != null) {
      _selectedPhotoUrl = widget.homework.submittedImageUrl;
    }
  }

  @override
  void dispose() {
    _essayController.dispose();
    _photoNoteController.dispose();
    super.dispose();
  }

  void _simulatePhotoCapture() {
    setState(() {
      _selectedPhotoUrl = 'https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?auto=format&fit=crop&q=80&w=600';
    });
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('تم التقاط صورة صفحة الكشكول بنجاح! جاهزة للتسليم.', style: GoogleFonts.cairo()),
        backgroundColor: AppTheme.screenshotGreen,
      ),
    );
  }

  void _submitImageHomework() async {
    if (_selectedPhotoUrl == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('الرجاء التقاط أو اختيار صورة صفحة الحل أولاً', style: GoogleFonts.cairo())),
      );
      return;
    }

    widget.api.studentSubmitImageHomework(
      widget.homework.id,
      _selectedPhotoUrl!,
      _photoNoteController.text.trim(),
    );

    await widget.api.submitStudentHomework(
      homeworkId: widget.homework.id,
      submissionText: _photoNoteController.text.trim().isNotEmpty
          ? _photoNoteController.text.trim()
          : 'تم رفع صورة حل الواجب المدرسي في كشكول الطالب واعتماد التسليم.',
    );

    if (mounted) _showSuccessDialog();
  }

  void _submitQuestionsHomework() async {
    widget.api.submitHomeworkAnswer(widget.homework.id, _answers);

    await widget.api.submitStudentHomework(
      homeworkId: widget.homework.id,
      submissionText: 'تمت الإجابة عن أسئلة الواجب التفاعلية وتسليمها إلكترونياً.',
    );

    if (mounted) _showSuccessDialog();
  }

  void _showSuccessDialog() {
    showDialog(
      context: context,
      builder: (ctx) => Dialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  color: AppTheme.screenshotGreen.withValues(alpha: 0.12),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.check_circle_rounded, color: AppTheme.screenshotGreen, size: 36),
              ),
              const SizedBox(height: 10),
              Text(
                'تم تسليم الواجب بنجاح!',
                style: GoogleFonts.cairo(fontSize: 16, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
              ),
              const SizedBox(height: 6),
              Text(
                'تم إرسال الحل للمعلم (${widget.homework.teacherName}) للمراجعة والتقييم.',
                textAlign: TextAlign.center,
                style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF64748B)),
              ),
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: () {
                    Navigator.pop(ctx);
                    Navigator.pop(context);
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF1E60FF),
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  child: Text('العودة للواجبات', style: GoogleFonts.cairo(fontWeight: FontWeight.bold)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final hw = widget.homework;
    final isReadOnly = hw.status != 'pending';
    final isImageUpload = hw.submissionType == 'image_upload';

    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        title: Text(hw.subject, style: GoogleFonts.cairo(fontSize: 16, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A))),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18, color: Color(0xFF0F172A)),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        physics: const BouncingScrollPhysics(),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header Info Card (Compact)
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
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        hw.title,
                        style: GoogleFonts.cairo(fontSize: 14, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: AppTheme.screenshotBlue.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          '${hw.maxScore} درجات',
                          style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold, color: AppTheme.screenshotBlue),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'المعلم: ${hw.teacherName} • الموعد النهائي: ${hw.dueDate}',
                    style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF64748B)),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 12),

            // Teacher Audio Guidance Strip
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: const Color(0xFFEFF6FF),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFBFDBFE)),
              ),
              child: Row(
                children: [
                  IconButton(
                    icon: Icon(
                      _isPlayingAudio ? Icons.pause_circle_filled_rounded : Icons.play_circle_fill_rounded,
                      color: AppTheme.screenshotBlue,
                      size: 28,
                    ),
                    onPressed: () => setState(() => _isPlayingAudio = !_isPlayingAudio),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('توجيه صوتي من المعلم (${hw.teacherName})', style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A))),
                        Text(_isPlayingAudio ? 'جاري الاستماع...' : 'اضغط للاستماع لملاحظات المعلم (0:35 د)', style: GoogleFonts.cairo(fontSize: 10, color: AppTheme.screenshotBlue)),
                      ],
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 16),

            // If Image Upload Mode (حل كشكول مرفوع بالصورة)
            if (isImageUpload) ...[
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
                    Text(
                      'المطلوب كتابة الحل في الكشكول ورفع صورة الصفحة:',
                      style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      hw.description,
                      style: GoogleFonts.cairo(fontSize: 12, color: const Color(0xFF475569), height: 1.5),
                    ),
                    const SizedBox(height: 14),

                    // Image Capture / Pick Section
                    if (_selectedPhotoUrl == null)
                      InkWell(
                        onTap: isReadOnly ? null : _simulatePhotoCapture,
                        borderRadius: BorderRadius.circular(12),
                        child: Container(
                          width: double.infinity,
                          padding: const EdgeInsets.symmetric(vertical: 24),
                          decoration: BoxDecoration(
                            color: const Color(0xFFF8FAFC),
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: const Color(0xFFCBD5E1), style: BorderStyle.solid),
                          ),
                          child: Column(
                            children: [
                              const Icon(Icons.add_a_photo_rounded, size: 36, color: AppTheme.screenshotBlue),
                              const SizedBox(height: 8),
                              Text(
                                'التقط صورة لصفحة الكشكول أو اخترها من المعرض',
                                style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.screenshotBlue),
                              ),
                              Text(
                                'تأكد من وضوح الخط وأرقام المسائل',
                                style: GoogleFonts.cairo(fontSize: 10, color: const Color(0xFF64748B)),
                              ),
                            ],
                          ),
                        ),
                      )
                    else
                      Column(
                        children: [
                          ClipRRect(
                            borderRadius: BorderRadius.circular(12),
                            child: Image.network(
                              _selectedPhotoUrl!,
                              height: 220,
                              width: double.infinity,
                              fit: BoxFit.cover,
                            ),
                          ),
                          if (!isReadOnly) ...[
                            const SizedBox(height: 8),
                            TextButton.icon(
                              onPressed: _simulatePhotoCapture,
                              icon: const Icon(Icons.refresh_rounded, size: 16),
                              label: Text('إعادة التقاط الصورة', style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold)),
                            ),
                          ],
                        ],
                      ),

                    const SizedBox(height: 12),

                    // Student Note
                    TextField(
                      controller: _photoNoteController,
                      enabled: !isReadOnly,
                      style: GoogleFonts.cairo(fontSize: 12),
                      decoration: InputDecoration(
                        labelText: 'ملاحظة للمعلم حول الحل (اختياري)',
                        labelStyle: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF64748B)),
                        filled: true,
                        fillColor: const Color(0xFFF8FAFC),
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFFE2E8F0))),
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 16),

              if (!isReadOnly)
                SizedBox(
                  width: double.infinity,
                  height: 46,
                  child: ElevatedButton.icon(
                    onPressed: _submitImageHomework,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.screenshotGreen,
                      foregroundColor: Colors.white,
                      elevation: 0,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    icon: const Icon(Icons.send_rounded, size: 18),
                    label: Text('اعتماد وتسليم صورة الكشكول للمعلم', style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold)),
                  ),
                ),
            ] else ...[
              // Interactive questions mode
              ...List.generate(hw.questions.length, (index) {
                final q = hw.questions[index];
                return _buildQuestionCard(q, index + 1, isReadOnly);
              }),

              const SizedBox(height: 16),

              if (!isReadOnly)
                SizedBox(
                  width: double.infinity,
                  height: 46,
                  child: ElevatedButton.icon(
                    onPressed: _submitQuestionsHomework,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.screenshotGreen,
                      foregroundColor: Colors.white,
                      elevation: 0,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    icon: const Icon(Icons.send_rounded, size: 18),
                    label: Text('اعتماد وتسليم الإجابات للمعلم', style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold)),
                  ),
                ),
            ],

            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  Widget _buildQuestionCard(QuestionItem q, int number, bool isReadOnly) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFE2E8F0)),
        boxShadow: AppTheme.softShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'السؤال $number',
                style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.screenshotBlue),
              ),
              Text('${q.points} درجات', style: GoogleFonts.cairo(fontSize: 10, color: const Color(0xFF64748B))),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            q.text,
            style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A), height: 1.4),
          ),
          const SizedBox(height: 10),

          if (q.type == 'mcq' && q.options != null)
            ...q.options!.map((opt) {
              final isChosen = _answers[q.id] == opt;
              return InkWell(
                onTap: isReadOnly ? null : () => setState(() => _answers[q.id] = opt),
                borderRadius: BorderRadius.circular(8),
                child: Container(
                  margin: const EdgeInsets.only(bottom: 6),
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                  decoration: BoxDecoration(
                    color: isChosen ? AppTheme.screenshotBlue.withValues(alpha: 0.08) : const Color(0xFFF8FAFC),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: isChosen ? AppTheme.screenshotBlue : const Color(0xFFE2E8F0)),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        isChosen ? Icons.radio_button_checked : Icons.radio_button_off,
                        color: isChosen ? AppTheme.screenshotBlue : const Color(0xFF94A3B8),
                        size: 16,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          opt,
                          style: GoogleFonts.cairo(
                            fontSize: 12,
                            fontWeight: isChosen ? FontWeight.bold : FontWeight.normal,
                            color: isChosen ? AppTheme.screenshotBlue : const Color(0xFF0F172A),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              );
            })
          else
            TextField(
              controller: _essayController,
              enabled: !isReadOnly,
              maxLines: 3,
              style: GoogleFonts.cairo(fontSize: 12),
              decoration: InputDecoration(
                hintText: isReadOnly ? (_answers[q.id] ?? 'تم الحل') : 'اكتب الإجابة هنا...',
                filled: true,
                fillColor: const Color(0xFFF8FAFC),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: Color(0xFFE2E8F0))),
              ),
              onChanged: (val) => _answers[q.id] = val,
            ),
        ],
      ),
    );
  }
}



import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/api_service.dart';
import '../core/models.dart';
import '../core/theme.dart';
import 'chat_screen.dart';
import 'subject_detail_screen.dart';

class SubjectsScreen extends StatefulWidget {
  final ApiService api;
  const SubjectsScreen({super.key, required this.api});

  @override
  State<SubjectsScreen> createState() => _SubjectsScreenState();
}

class _SubjectsScreenState extends State<SubjectsScreen> {
  String _searchQuery = '';
  final Set<String> _downloadedBooks = {};
  final Map<String, double> _downloadProgress = {};
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _loadSubjects();
  }

  Future<void> _loadSubjects() async {
    setState(() => _isLoading = true);
    await widget.api.fetchStudentSubjects();
    if (mounted) setState(() => _isLoading = false);
  }

  void _startDownload(SubjectCurriculum subject) {
    if (_downloadedBooks.contains(subject.id)) {
      _showBookPreviewDialog(subject);
      return;
    }

    setState(() {
      _downloadProgress[subject.id] = 0.1;
    });

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'بدأ تنزيل "${subject.textbookTitle}" بصيغة PDF...',
          style: GoogleFonts.almarai(fontSize: 13),
        ),
        backgroundColor: AppTheme.screenshotBlue,
        duration: const Duration(seconds: 2),
      ),
    );

    // Simulate progressive download
    Future.delayed(const Duration(milliseconds: 300), () {
      if (mounted) setState(() => _downloadProgress[subject.id] = 0.45);
    });
    Future.delayed(const Duration(milliseconds: 700), () {
      if (mounted) setState(() => _downloadProgress[subject.id] = 0.85);
    });
    Future.delayed(const Duration(milliseconds: 1100), () {
      if (mounted) {
        setState(() {
          _downloadProgress.remove(subject.id);
          _downloadedBooks.add(subject.id);
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'اكتمل تحميل الكتاب المدرسي بنجاح! جاهز للقراءة دون اتصال.',
              style: GoogleFonts.almarai(fontSize: 13, fontWeight: FontWeight.bold),
            ),
            backgroundColor: AppTheme.screenshotGreen,
            action: SnackBarAction(
              label: 'فتح الكتاب',
              textColor: Colors.white,
              onPressed: () => _showBookPreviewDialog(subject),
            ),
          ),
        );
      }
    });
  }

  void _showBookPreviewDialog(SubjectCurriculum subject) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Container(
        height: MediaQuery.of(ctx).size.height * 0.88,
        decoration: const BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        child: Column(
          children: [
            // Handle bar
            Container(
              margin: const EdgeInsets.only(top: 12, bottom: 8),
              width: 44,
              height: 4,
              decoration: BoxDecoration(
                color: const Color(0xFFCBD5E1),
                borderRadius: BorderRadius.circular(4),
              ),
            ),

            // Top Header
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: AppTheme.screenshotLightBlue,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Icon(Icons.menu_book_rounded, color: AppTheme.screenshotBlue, size: 24),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          subject.textbookTitle,
                          style: GoogleFonts.almarai(
                            fontSize: 15,
                            fontWeight: FontWeight.bold,
                            color: const Color(0xFF0F172A),
                          ),
                        ),
                        Text(
                          'معتمد رسمياً من وزارة التربية والتعليم • ${subject.totalPages} صفحة',
                          style: GoogleFonts.almarai(fontSize: 11, color: const Color(0xFF64748B)),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close_rounded, color: Color(0xFF64748B)),
                    onPressed: () => Navigator.pop(ctx),
                  ),
                ],
              ),
            ),

            const Divider(height: 1, color: Color(0xFFE2E8F0)),

            // Book Reader / Syllabus Browser
            Expanded(
              child: ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  // Ministry badge & Book Cover simulation
                  Container(
                    padding: const EdgeInsets.all(18),
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [Color(0xFF0F172A), Color(0xFF1E293B)],
                        begin: Alignment.topRight,
                        end: Alignment.bottomLeft,
                      ),
                      borderRadius: BorderRadius.circular(16),
                      boxShadow: AppTheme.softShadow,
                    ),
                    child: Row(
                      children: [
                        Container(
                          width: 70,
                          height: 95,
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: AppTheme.screenshotBlue, width: 2),
                          ),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Icon(Icons.auto_stories_rounded, color: AppTheme.screenshotBlue, size: 30),
                              const SizedBox(height: 4),
                              Text(
                                subject.shortName,
                                textAlign: TextAlign.center,
                                style: GoogleFonts.almarai(
                                  fontSize: 10,
                                  fontWeight: FontWeight.w900,
                                  color: const Color(0xFF0F172A),
                                ),
                              ),
                              Text(
                                '2026',
                                style: GoogleFonts.almarai(fontSize: 8, color: const Color(0xFF64748B)),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                decoration: BoxDecoration(
                                  color: AppTheme.screenshotGreen.withValues(alpha: 0.2),
                                  borderRadius: BorderRadius.circular(6),
                                ),
                                child: Text(
                                  'النسخة المدرسية المعتمدة PDF',
                                  style: GoogleFonts.almarai(
                                    fontSize: 10,
                                    fontWeight: FontWeight.bold,
                                    color: const Color(0xFF4ADE80),
                                  ),
                                ),
                              ),
                              const SizedBox(height: 6),
                              Text(
                                subject.name,
                                style: GoogleFonts.almarai(
                                  fontSize: 15,
                                  fontWeight: FontWeight.bold,
                                  color: Colors.white,
                                ),
                              ),
                              Text(
                                'إعداد وتدريس: ${subject.teacherName}',
                                style: GoogleFonts.almarai(fontSize: 11, color: const Color(0xFF94A3B8)),
                              ),
                              const SizedBox(height: 6),
                              Text(
                                'عدد الحصص المقررة: ${subject.weeklyPeriods} حصص أسبوعياً',
                                style: GoogleFonts.almarai(fontSize: 11, color: const Color(0xFF38BDF8)),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 20),

                  // Units Index Header
                  Text(
                    'فهرس الوحدات والدروس المقررة',
                    style: GoogleFonts.almarai(
                      fontSize: 14,
                      fontWeight: FontWeight.w800,
                      color: const Color(0xFF0F172A),
                    ),
                  ),
                  const SizedBox(height: 10),

                  // Units list
                  ...subject.units.map((unit) => Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF8FAFC),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: unit.isCompleted ? const Color(0xFF86EFAC) : const Color(0xFFE2E8F0),
                      ),
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
                                  width: 28,
                                  height: 28,
                                  decoration: BoxDecoration(
                                    color: unit.isCompleted ? const Color(0xFFDCFCE7) : AppTheme.screenshotLightBlue,
                                    shape: BoxShape.circle,
                                  ),
                                  child: Center(
                                    child: Text(
                                      '${unit.unitNumber}',
                                      style: GoogleFonts.almarai(
                                        fontSize: 12,
                                        fontWeight: FontWeight.bold,
                                        color: unit.isCompleted ? const Color(0xFF15803D) : AppTheme.screenshotBlue,
                                      ),
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 10),
                                Text(
                                  unit.title,
                                  style: GoogleFonts.almarai(
                                    fontSize: 13,
                                    fontWeight: FontWeight.bold,
                                    color: const Color(0xFF0F172A),
                                  ),
                                ),
                              ],
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: unit.isCompleted
                                    ? const Color(0xFFDCFCE7)
                                    : const Color(0xFFFEF3C7),
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: Text(
                                unit.isCompleted ? 'تم إنجازها ✓' : '${unit.lessonsCount} دروس',
                                style: GoogleFonts.almarai(
                                  fontSize: 10,
                                  fontWeight: FontWeight.bold,
                                  color: unit.isCompleted
                                      ? const Color(0xFF15803D)
                                      : const Color(0xFFB45309),
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text(
                          unit.summary,
                          style: GoogleFonts.almarai(fontSize: 11, color: const Color(0xFF475569), height: 1.4),
                        ),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 6,
                          runSpacing: 4,
                          children: unit.keyTopics.map((topic) => Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(6),
                              border: Border.all(color: const Color(0xFFCBD5E1)),
                            ),
                            child: Text(
                              '• $topic',
                              style: GoogleFonts.almarai(fontSize: 10, color: const Color(0xFF334155)),
                            ),
                          )).toList(),
                        ),
                      ],
                    ),
                  )),

                  const SizedBox(height: 16),

                  // Quick AI Question Button
                  SizedBox(
                    width: double.infinity,
                    height: 48,
                    child: ElevatedButton.icon(
                      onPressed: () {
                        Navigator.pop(ctx);
                        Navigator.push(
                          context,
                          MaterialPageRoute(builder: (_) => ChatScreen(api: widget.api)),
                        );
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.screenshotPurple,
                        foregroundColor: Colors.white,
                        elevation: 0,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      icon: const Icon(Icons.psychology_rounded, size: 20),
                      label: Text(
                        'اسأل الذكاء الاصطناعي عن منهج ${subject.shortName}',
                        style: GoogleFonts.almarai(fontSize: 13, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  IconData _getSubjectIcon(String iconName) {
    switch (iconName) {
      case 'calculate':
        return Icons.calculate_rounded;
      case 'bolt':
        return Icons.bolt_rounded;
      case 'science':
        return Icons.science_rounded;
      case 'menu_book':
        return Icons.menu_book_rounded;
      case 'language':
        return Icons.language_rounded;
      case 'auto_stories':
        return Icons.auto_stories_rounded;
      case 'laptop_mac':
        return Icons.laptop_mac_rounded;
      default:
        return Icons.school_rounded;
    }
  }

  Color _getSubjectColor(String iconName) {
    switch (iconName) {
      case 'calculate':
        return const Color(0xFF2563EB); // Blue
      case 'bolt':
        return const Color(0xFFD97706); // Amber
      case 'science':
        return const Color(0xFF059669); // Emerald
      case 'menu_book':
        return const Color(0xFFDC2626); // Red
      case 'language':
        return const Color(0xFF7C3AED); // Purple
      case 'auto_stories':
        return const Color(0xFF0D9488); // Teal
      case 'laptop_mac':
        return const Color(0xFF0284C7); // Cyan
      default:
        return const Color(0xFF475569);
    }
  }

  @override
  Widget build(BuildContext context) {
    final subjects = widget.api.studentSubjects.where((s) {
      if (_searchQuery.trim().isEmpty) return true;
      final q = _searchQuery.toLowerCase();
      return s.name.toLowerCase().contains(q) ||
          s.shortName.toLowerCase().contains(q) ||
          s.teacherName.toLowerCase().contains(q);
    }).toList();

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
            // Right: School Icon + Title (RTL layout)
            Row(
              children: [
                Container(
                  width: 42,
                  height: 42,
                  decoration: const BoxDecoration(
                    color: AppTheme.screenshotLightBlue,
                    shape: BoxShape.circle,
                  ),
                  child: const Center(
                    child: Icon(
                      Icons.menu_book_rounded,
                      color: AppTheme.screenshotBlue,
                      size: 24,
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'المواد والمناهج الدراسية',
                      style: GoogleFonts.almarai(
                        fontSize: 16,
                        fontWeight: FontWeight.w900,
                        color: const Color(0xFF0F172A),
                      ),
                    ),
                    Text(
                      '${widget.api.currentStudent?.grade ?? 'المنهج الدراسي'} • المنهج المعتمد',
                      style: GoogleFonts.almarai(fontSize: 11, color: const Color(0xFF64748B)),
                    ),
                  ],
                ),
              ],
            ),

            // Left: Actions
            Row(
              children: [
                IconButton(
                  icon: const Icon(Icons.refresh_rounded, size: 20, color: AppTheme.screenshotBlue),
                  onPressed: _loadSubjects,
                  tooltip: 'تحديث المواد',
                ),
                IconButton(
                  icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18, color: Color(0xFF0F172A)),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),
          ],
        ),
      ),
      body: Column(
        children: [
          if (_isLoading)
            const LinearProgressIndicator(
              color: AppTheme.screenshotBlue,
              backgroundColor: Color(0xFFE2E8F0),
              minHeight: 2,
            ),
          // 1. Search Bar & Summary
          Container(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 14),
            decoration: const BoxDecoration(
              color: Colors.white,
              border: Border(bottom: BorderSide(color: Color(0xFFE2E8F0))),
            ),
            child: Column(
              children: [
                // Search Field
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14),
                  decoration: BoxDecoration(
                    color: const Color(0xFFF8FAFC),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFFE2E8F0)),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.search_rounded, color: Color(0xFF64748B), size: 20),
                      const SizedBox(width: 8),
                      Expanded(
                        child: TextField(
                          onChanged: (v) => setState(() => _searchQuery = v),
                          style: GoogleFonts.almarai(fontSize: 13, color: const Color(0xFF0F172A)),
                          decoration: InputDecoration(
                            hintText: 'ابحث في المواد المقررة أو أسماء المعلمين...',
                            hintStyle: GoogleFonts.almarai(fontSize: 12, color: const Color(0xFF94A3B8)),
                            border: InputBorder.none,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 10),

                // Fast Stats Pills
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    _buildTopPill('المواد المسجلة', '${widget.api.subjects.length} مواد', const Color(0xFF2563EB)),
                    _buildTopPill('الحصص الأسبوعية', '31 حصة', const Color(0xFF059669)),
                    _buildTopPill('تحميل المنهج', 'متوفر PDF 📥', const Color(0xFF7C3AED)),
                  ],
                ),
              ],
            ),
          ),

          // 2. Subjects List
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              physics: const BouncingScrollPhysics(),
              itemCount: subjects.length,
              itemBuilder: (context, index) {
                final subject = subjects[index];
                final isDownloaded = _downloadedBooks.contains(subject.id);
                final progress = _downloadProgress[subject.id];
                final iconColor = _getSubjectColor(subject.iconName);

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
                      // Header Row
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Container(
                            width: 46,
                            height: 46,
                            decoration: BoxDecoration(
                              color: iconColor.withValues(alpha: 0.12),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Icon(_getSubjectIcon(subject.iconName), color: iconColor, size: 24),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Expanded(
                                      child: Text(
                                        subject.name,
                                        style: GoogleFonts.almarai(
                                          fontSize: 14,
                                          fontWeight: FontWeight.bold,
                                          color: const Color(0xFF0F172A),
                                        ),
                                      ),
                                    ),
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                      decoration: BoxDecoration(
                                        color: const Color(0xFFF1F5F9),
                                        borderRadius: BorderRadius.circular(6),
                                      ),
                                      child: Text(
                                        '${subject.weeklyPeriods} حصص/أسبوع',
                                        style: GoogleFonts.almarai(
                                          fontSize: 10,
                                          fontWeight: FontWeight.bold,
                                          color: const Color(0xFF475569),
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  'المعلم: ${subject.teacherName} • ${subject.code}',
                                  style: GoogleFonts.almarai(fontSize: 11, color: const Color(0xFF64748B)),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),

                      const SizedBox(height: 12),

                      // Progress bar
                      Row(
                        children: [
                          Expanded(
                            child: ClipRRect(
                              borderRadius: BorderRadius.circular(4),
                              child: LinearProgressIndicator(
                                value: subject.progressPercent,
                                backgroundColor: const Color(0xFFF1F5F9),
                                valueColor: AlwaysStoppedAnimation<Color>(iconColor),
                                minHeight: 6,
                              ),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Text(
                            'الإنجاز: ${(subject.progressPercent * 100).toInt()}%',
                            style: GoogleFonts.almarai(
                              fontSize: 11,
                              fontWeight: FontWeight.bold,
                              color: const Color(0xFF334155),
                            ),
                          ),
                        ],
                      ),

                      const SizedBox(height: 12),
                      const Divider(height: 1, color: Color(0xFFF1F5F9)),
                      const SizedBox(height: 10),

                      // Textbook name & Pages
                      Row(
                        children: [
                          const Icon(Icons.picture_as_pdf_rounded, color: Color(0xFFE11D48), size: 18),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Text(
                              subject.textbookTitle,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: GoogleFonts.almarai(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                color: const Color(0xFF334155),
                              ),
                            ),
                          ),
                          Text(
                            '${subject.totalPages} صفحة',
                            style: GoogleFonts.almarai(fontSize: 10, color: const Color(0xFF94A3B8)),
                          ),
                        ],
                      ),

                      const SizedBox(height: 12),

                      // Action Buttons Row: Download PDF / View Book + Details
                      Row(
                        children: [
                          // Button 1: Download / Open PDF
                          Expanded(
                            flex: 3,
                            child: ElevatedButton.icon(
                              onPressed: () => _startDownload(subject),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: isDownloaded
                                    ? const Color(0xFFDCFCE7)
                                    : AppTheme.screenshotLightBlue,
                                foregroundColor: isDownloaded
                                    ? const Color(0xFF15803D)
                                    : AppTheme.screenshotBlue,
                                elevation: 0,
                                padding: const EdgeInsets.symmetric(vertical: 9),
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                              ),
                              icon: progress != null
                                  ? const SizedBox(
                                      width: 14,
                                      height: 14,
                                      child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.screenshotBlue),
                                    )
                                  : Icon(
                                      isDownloaded ? Icons.menu_book_rounded : Icons.download_rounded,
                                      size: 16,
                                    ),
                              label: Text(
                                progress != null
                                    ? 'جاري التحميل ${(progress * 100).toInt()}%...'
                                    : (isDownloaded ? 'قراءة الكتاب PDF' : 'تحميل المنهج PDF'),
                                style: GoogleFonts.almarai(fontSize: 12, fontWeight: FontWeight.bold),
                              ),
                            ),
                          ),

                          const SizedBox(width: 8),

                          // Button 2: Subject Detail Screen (Abwaab Course View)
                          Expanded(
                            flex: 2,
                            child: ElevatedButton(
                              onPressed: () => Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (_) => SubjectDetailScreen(api: widget.api, subject: subject),
                                ),
                              ),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: const Color(0xFF1E60FF),
                                foregroundColor: Colors.white,
                                elevation: 0,
                                padding: const EdgeInsets.symmetric(vertical: 9),
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                              ),
                              child: Text(
                                'شرح الدروس',
                                style: GoogleFonts.almarai(fontSize: 12, fontWeight: FontWeight.bold),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTopPill(String title, String value, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Text('$title: ', style: GoogleFonts.almarai(fontSize: 10, color: const Color(0xFF64748B))),
          Text(
            value,
            style: GoogleFonts.almarai(fontSize: 10, fontWeight: FontWeight.bold, color: color),
          ),
        ],
      ),
    );
  }
}



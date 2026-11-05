import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/api_service.dart';
import '../core/models.dart';
import 'lesson_viewer_screen.dart';
import 'online_exams_screen.dart';
import 'chat_screen.dart';

class SubjectDetailScreen extends StatefulWidget {
  final ApiService api;
  final SubjectCurriculum subject;

  const SubjectDetailScreen({
    super.key,
    required this.api,
    required this.subject,
  });

  @override
  State<SubjectDetailScreen> createState() => _SubjectDetailScreenState();
}

class _SubjectDetailScreenState extends State<SubjectDetailScreen> {
  int _selectedTabPill = 1; // 1: اختبارات (Selected as in screenshot)

  Widget _buildAbwaabPurpleLogo() {
    return Container(
      width: 26,
      height: 28,
      decoration: BoxDecoration(
        color: Colors.transparent,
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(14)),
        border: Border.all(color: const Color(0xFF7C3AED), width: 4.5),
      ),
      child: Align(
        alignment: Alignment.topCenter,
        child: Container(
          height: 6,
          color: Colors.white,
        ),
      ),
    );
  }

  Widget _buildYellowFolderQuestionIcon() {
    return Stack(
      clipBehavior: Clip.none,
      children: [
        Container(
          width: 38,
          height: 38,
          decoration: BoxDecoration(
            color: const Color(0xFFFEF3C7),
            borderRadius: BorderRadius.circular(10),
          ),
          child: const Center(
            child: Icon(Icons.folder_rounded, color: Color(0xFFF59E0B), size: 26),
          ),
        ),
        Positioned(
          bottom: -2,
          left: -2,
          child: Container(
            width: 16,
            height: 16,
            decoration: BoxDecoration(
              color: const Color(0xFF0284C7),
              borderRadius: BorderRadius.circular(4),
            ),
            child: const Center(
              child: Text(
                '؟',
                style: TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold, height: 1.0),
              ),
            ),
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final sub = widget.subject;
    final activeStudent = widget.api.currentStudent;
    final studentFirstName = activeStudent != null
        ? activeStudent.fullName.split(' ').first
        : 'بلال';

    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        automaticallyImplyLeading: false,
        title: Row(
          mainAxisAlignment: MainAxisAlignment.end,
          children: [
            Text(
              sub.name,
              style: GoogleFonts.cairo(
                fontSize: 18,
                fontWeight: FontWeight.w700,
                color: const Color(0xFF1A1D1F),
              ),
            ),
            const SizedBox(width: 8),
            _buildAbwaabPurpleLogo(),
            const SizedBox(width: 14),
            InkWell(
              onTap: () => Navigator.pop(context),
              borderRadius: BorderRadius.circular(10),
              child: const Padding(
                padding: EdgeInsets.all(4),
                child: Icon(Icons.arrow_forward_ios_rounded, size: 20, color: Color(0xFF0F172A)),
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.auto_awesome_rounded, color: Color(0xFF0284C7)),
            tooltip: 'المساعد الذكي للمادة',
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => ChatScreen(api: widget.api)),
            ),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        physics: const BouncingScrollPhysics(),
        children: [
          // 1. Horizontal Tab / Action Pills row matching Screen 3 in media_1793903260400_0cb23ad7.jpg
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            physics: const BouncingScrollPhysics(),
            child: Row(
              children: [
                _buildActionTab(
                  index: 0,
                  label: 'شرح المادة',
                  icon: Icons.smart_display_outlined,
                ),
                const SizedBox(width: 12),
                _buildActionTab(
                  index: 1,
                  label: 'اختبارات',
                  icon: Icons.edit_note_rounded,
                ),
                const SizedBox(width: 12),
                _buildActionTab(
                  index: 2,
                  label: 'مراجعة نهاية الفصل',
                  icon: Icons.published_with_changes_rounded,
                ),
              ],
            ),
          ),

          const SizedBox(height: 24),

          // 2. "أسئلة خصيصاً لك" matching media_1793903260400_0cb23ad7.jpg
          Text(
            'أسئلة خصيصاً لك',
            style: GoogleFonts.cairo(
              fontSize: 14.5,
              fontWeight: FontWeight.w700,
              color: const Color(0xFF1A1D1F),
            ),
          ),
          const SizedBox(height: 10),
          InkWell(
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => OnlineExamsScreen(api: widget.api)),
              );
            },
            borderRadius: BorderRadius.circular(18),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
              decoration: BoxDecoration(
                color: const Color(0xFFF7F5FC),
                borderRadius: BorderRadius.circular(18),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.03),
                    blurRadius: 10,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Row(
                children: [
                  Stack(
                    clipBehavior: Clip.none,
                    children: [
                      Container(
                        width: 40,
                        height: 40,
                        decoration: const BoxDecoration(
                          color: Color(0xFF7C3AED),
                          shape: BoxShape.circle,
                        ),
                        child: const Center(
                          child: Icon(Icons.sync_rounded, color: Colors.white, size: 24),
                        ),
                      ),
                      Positioned(
                        top: -3,
                        right: -3,
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1.5),
                          decoration: BoxDecoration(
                            color: const Color(0xFFEF4444),
                            borderRadius: BorderRadius.circular(10),
                            border: Border.all(color: Colors.white, width: 1.5),
                          ),
                          child: const Text(
                            '28',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
                              height: 1.1,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Text(
                      '$studentFirstName، أخطائك السابقة هنا!',
                      style: GoogleFonts.cairo(
                        fontSize: 13.5,
                        fontWeight: FontWeight.w700,
                        color: const Color(0xFF1A1D1F),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 20),

          // 3. "اختبارات جاهزة" matching media_1793903260400_0cb23ad7.jpg
          Text(
            'اختبارات جاهزة',
            style: GoogleFonts.cairo(
              fontSize: 14.5,
              fontWeight: FontWeight.w700,
              color: const Color(0xFF1A1D1F),
            ),
          ),
          const SizedBox(height: 10),
          InkWell(
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => OnlineExamsScreen(api: widget.api)),
              );
            },
            borderRadius: BorderRadius.circular(18),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
              decoration: BoxDecoration(
                color: const Color(0xFFF3F7FA),
                borderRadius: BorderRadius.circular(18),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.03),
                    blurRadius: 10,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Row(
                children: [
                  _buildYellowFolderQuestionIcon(),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Text(
                      'اختبارات الوحدة',
                      style: GoogleFonts.cairo(
                        fontSize: 13.5,
                        fontWeight: FontWeight.w700,
                        color: const Color(0xFF1A1D1F),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 24),

          // 4. "دروس ووحدات المنهج"
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'وحدات ودروس المنهج',
                style: GoogleFonts.cairo(
                  fontSize: 14.5,
                  fontWeight: FontWeight.w700,
                  color: const Color(0xFF1A1D1F),
                ),
              ),
              Text(
                '${sub.units.length} وحدات • ${sub.teacherName}',
                style: GoogleFonts.cairo(
                  fontSize: 11,
                  color: const Color(0xFF717579),
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),

          const SizedBox(height: 12),

          // Units List
          ...sub.units.map((unit) {
            final topics = unit.keyTopics.isNotEmpty
                ? unit.keyTopics
                : [
                    'الدرس 1: المفاهيم الأساسية والمدخل',
                    'الدرس 2: القوانين والتطبيقات المعملية',
                    'الدرس 3: نماذج محلولة ومراجعة وزارية',
                  ];

            return Container(
              margin: const EdgeInsets.only(bottom: 12),
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
              child: ExpansionTile(
                initiallyExpanded: unit.unitNumber == 1,
                shape: const Border(),
                leading: Container(
                  width: 34,
                  height: 34,
                  decoration: BoxDecoration(
                    color: const Color(0xFFEFF6FF),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Center(
                    child: Text(
                      '${unit.unitNumber}',
                      style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.w700, color: const Color(0xFF1E60FF)),
                    ),
                  ),
                ),
                title: Text(
                  unit.title,
                  style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.w700, color: const Color(0xFF1A1D1F)),
                ),
                subtitle: Text(
                  '${unit.lessonsCount > 0 ? unit.lessonsCount : topics.length} دروس تعليمية',
                  style: GoogleFonts.cairo(fontSize: 10.5, fontWeight: FontWeight.w500, color: const Color(0xFF717579)),
                ),
                children: topics.asMap().entries.map((entry) {
                  final idx = entry.key + 1;
                  final topicTitle = entry.value;
                  return InkWell(
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => LessonViewerScreen(
                            api: widget.api,
                            subjectName: sub.name,
                            lessonTitle: topicTitle,
                            teacherName: sub.teacherName,
                          ),
                        ),
                      );
                    },
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      decoration: const BoxDecoration(
                        border: Border(top: BorderSide(color: Color(0xFFF1F5F9))),
                      ),
                      child: Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(6),
                            decoration: const BoxDecoration(
                              color: Color(0xFFEFF6FF),
                              shape: BoxShape.circle,
                            ),
                            child: const Icon(Icons.play_arrow_rounded, size: 16, color: Color(0xFF1E60FF)),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  topicTitle,
                                  style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.w700, color: const Color(0xFF1A1D1F)),
                                ),
                                Text(
                                  'الدرس $idx • انقر لمشاهدة الشرح التفاعلي بالفيديو',
                                  style: GoogleFonts.cairo(fontSize: 10, fontWeight: FontWeight.w500, color: const Color(0xFF717579)),
                                ),
                              ],
                            ),
                          ),
                          const Icon(Icons.arrow_forward_ios_rounded, size: 12, color: Color(0xFFCBD5E1)),
                        ],
                      ),
                    ),
                  );
                }).toList(),
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildActionTab({
    required int index,
    required String label,
    required IconData icon,
  }) {
    final isSelected = _selectedTabPill == index;
    return InkWell(
      onTap: () {
        setState(() => _selectedTabPill = index);
        if (index == 1) {
          Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => OnlineExamsScreen(api: widget.api)),
          );
        }
      },
      borderRadius: BorderRadius.circular(16),
      child: Container(
        width: 104,
        height: 78,
        decoration: BoxDecoration(
          color: isSelected ? const Color(0xFF2563EB) : Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: isSelected ? null : Border.all(color: const Color(0xFFE2E8F0), width: 1.2),
          boxShadow: isSelected
              ? [
                  BoxShadow(
                    color: const Color(0xFF2563EB).withValues(alpha: 0.28),
                    blurRadius: 10,
                    offset: const Offset(0, 4),
                  ),
                ]
              : null,
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              icon,
              size: 26,
              color: isSelected ? Colors.white : const Color(0xFF475569),
            ),
            const SizedBox(height: 6),
            Text(
              label,
              maxLines: 1,
              style: GoogleFonts.cairo(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                color: isSelected ? Colors.white : const Color(0xFF1A1D1F),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

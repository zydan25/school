import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/api_service.dart';
import 'chat_screen.dart';

class LessonViewerScreen extends StatefulWidget {
  final ApiService api;
  final String subjectName;
  final String lessonTitle;
  final String teacherName;
  final String videoUrl;

  const LessonViewerScreen({
    super.key,
    required this.api,
    required this.subjectName,
    required this.lessonTitle,
    required this.teacherName,
    this.videoUrl = '',
  });

  @override
  State<LessonViewerScreen> createState() => _LessonViewerScreenState();
}

class _LessonViewerScreenState extends State<LessonViewerScreen> {
  bool _isPlaying = true;
  bool _isLiked = true;
  bool _isSaved = false;
  int _selectedPlaylistIndex = 0;

  final List<Map<String, String>> _playlist = [
    {
      'title': '1. القواعد الإملائية: همزة القطع وألف الوصل',
      'duration': '12:45',
      'teacher': 'أ. أحمد السعيد',
      'completed': 'true',
    },
    {
      'title': '2. مواضع همزة القطع في الأسماء والأفعال',
      'duration': '15:20',
      'teacher': 'أ. أحمد السعيد',
      'completed': 'false',
    },
    {
      'title': '3. تدريبات تطبيقية ونماذج وزارية',
      'duration': '09:15',
      'teacher': 'أ. أحمد السعيد',
      'completed': 'false',
    },
    {
      'title': '4. اختبار ختامي قصير على الوحدة',
      'duration': '05:00',
      'teacher': 'أ. أحمد السعيد',
      'completed': 'false',
    },
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        centerTitle: true,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18, color: Color(0xFF0F172A)),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(
          widget.subjectName,
          style: GoogleFonts.cairo(fontSize: 16, fontWeight: FontWeight.w900, color: const Color(0xFF0F172A)),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.auto_awesome_rounded, color: Color(0xFF0284C7)),
            tooltip: 'اسأل المساعد الذكي عن هذا الدرس',
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => ChatScreen(api: widget.api)),
            ),
          ),
        ],
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // 1. Video Player Area matching Screen 1 in Screenshot
          AspectRatio(
            aspectRatio: 16 / 9,
            child: Container(
              color: const Color(0xFF0F172A),
              child: Stack(
                alignment: Alignment.center,
                children: [
                  // Simulated interactive classroom board preview
                  Container(
                    decoration: const BoxDecoration(
                      gradient: LinearGradient(
                        colors: [
                          Color(0xFF1E293B),
                          Color(0xFF0F172A),
                        ],
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                      ),
                    ),
                    child: Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: Colors.white24),
                            ),
                            child: Column(
                              children: [
                                const Icon(Icons.cast_for_education_rounded, color: Colors.amber, size: 36),
                                const SizedBox(height: 8),
                                Text(
                                  widget.lessonTitle,
                                  textAlign: TextAlign.center,
                                  style: GoogleFonts.cairo(
                                    fontSize: 14,
                                    fontWeight: FontWeight.bold,
                                    color: Colors.white,
                                  ),
                                ),
                                Text(
                                  widget.teacherName,
                                  style: GoogleFonts.cairo(fontSize: 11, color: Colors.white70),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),

                  // Play / Pause Button Overlay
                  Center(
                    child: IconButton(
                      iconSize: 56,
                      icon: Icon(
                        _isPlaying ? Icons.pause_circle_filled_rounded : Icons.play_circle_filled_rounded,
                        color: Colors.white.withValues(alpha: 0.9),
                      ),
                      onPressed: () => setState(() => _isPlaying = !_isPlaying),
                    ),
                  ),

                  // Bottom video controls bar
                  Positioned(
                    bottom: 0,
                    left: 0,
                    right: 0,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                      decoration: const BoxDecoration(
                        gradient: LinearGradient(
                          colors: [Colors.transparent, Colors.black87],
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                        ),
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text('04:15 / 12:45', style: GoogleFonts.cairo(fontSize: 11, color: Colors.white)),
                          const Row(
                            children: [
                              Icon(Icons.subtitles_rounded, color: Colors.white, size: 18),
                              SizedBox(width: 12),
                              Icon(Icons.settings_rounded, color: Colors.white, size: 18),
                              SizedBox(width: 12),
                              Icon(Icons.fullscreen_rounded, color: Colors.white, size: 20),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),

          // 2. Video Title & Interactive Action Row (لم يعجبني • شارك • حفظ) matching Screenshot
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  widget.lessonTitle,
                  style: GoogleFonts.cairo(
                    fontSize: 15,
                    fontWeight: FontWeight.w900,
                    color: const Color(0xFF0F172A),
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '${widget.teacherName} • شرح متاح دون إنترنت',
                  style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF64748B), fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 12),

                // Action Bar matching Screenshot 1 (لم يعجبني • شارك • حفظ)
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    _buildActionButton(
                      icon: _isLiked ? Icons.thumb_up_rounded : Icons.thumb_up_outlined,
                      label: 'أعجبني',
                      isActive: _isLiked,
                      onTap: () => setState(() => _isLiked = !_isLiked),
                    ),
                    _buildActionButton(
                      icon: Icons.thumb_down_outlined,
                      label: 'لم يعجبني',
                      isActive: false,
                      onTap: () {},
                    ),
                    _buildActionButton(
                      icon: Icons.share_rounded,
                      label: 'شارك',
                      isActive: false,
                      onTap: () {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text('تم نسخ رابط الدرس بنجاح ✓', style: GoogleFonts.cairo())),
                        );
                      },
                    ),
                    _buildActionButton(
                      icon: _isSaved ? Icons.bookmark_rounded : Icons.bookmark_outline_rounded,
                      label: _isSaved ? 'محفوظ' : 'حفظ',
                      isActive: _isSaved,
                      onTap: () {
                        setState(() => _isSaved = !_isSaved);
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text(
                              _isSaved ? 'تم حفظ الدرس في المفضلة ✓' : 'تمت إزالة الدرس من المفضلة',
                              style: GoogleFonts.cairo(),
                            ),
                          ),
                        );
                      },
                    ),
                  ],
                ),
              ],
            ),
          ),

          const Divider(height: 16),

          // 3. Lesson Playlist Section matching Screenshot 1
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'محتويات الوحدة (${_playlist.length} دروس)',
                  style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.w800, color: const Color(0xFF0F172A)),
                ),
                Text(
                  'مكتمل 1 من ${_playlist.length}',
                  style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF15803D), fontWeight: FontWeight.bold),
                ),
              ],
            ),
          ),

          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              physics: const BouncingScrollPhysics(),
              itemCount: _playlist.length,
              itemBuilder: (context, idx) {
                final item = _playlist[idx];
                final isSelected = _selectedPlaylistIndex == idx;

                return InkWell(
                  onTap: () => setState(() => _selectedPlaylistIndex = idx),
                  borderRadius: BorderRadius.circular(14),
                  child: Container(
                    margin: const EdgeInsets.only(bottom: 10),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: isSelected ? const Color(0xFFEFF6FF) : const Color(0xFFF8FAFC),
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(
                        color: isSelected ? const Color(0xFF0284C7) : const Color(0xFFE2E8F0),
                        width: isSelected ? 1.5 : 1.0,
                      ),
                    ),
                    child: Row(
                      children: [
                        Container(
                          width: 44,
                          height: 44,
                          decoration: BoxDecoration(
                            color: isSelected ? const Color(0xFF0284C7) : Colors.white,
                            borderRadius: BorderRadius.circular(10),
                            border: Border.all(color: const Color(0xFFCBD5E1)),
                          ),
                          child: Center(
                            child: Icon(
                              item['completed'] == 'true' ? Icons.check_circle_rounded : Icons.play_arrow_rounded,
                              color: item['completed'] == 'true'
                                  ? const Color(0xFF15803D)
                                  : (isSelected ? Colors.white : const Color(0xFF0284C7)),
                              size: 22,
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                item['title']!,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: GoogleFonts.cairo(
                                  fontSize: 12.5,
                                  fontWeight: FontWeight.bold,
                                  color: isSelected ? const Color(0xFF0284C7) : const Color(0xFF0F172A),
                                ),
                              ),
                              Row(
                                children: [
                                  Text(
                                    item['duration']!,
                                    style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF64748B)),
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    '• ${item['teacher']!}',
                                    style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF94A3B8)),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActionButton({
    required IconData icon,
    required String label,
    required bool isActive,
    required VoidCallback onTap,
  }) {
    final color = isActive ? const Color(0xFF0284C7) : const Color(0xFF64748B);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        child: Column(
          children: [
            Icon(icon, color: color, size: 20),
            const SizedBox(height: 2),
            Text(label, style: GoogleFonts.cairo(fontSize: 10.5, color: color, fontWeight: FontWeight.bold)),
          ],
        ),
      ),
    );
  }
}

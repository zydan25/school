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
      'title': '1. Ø§Ù„Ù‚ÙˆØ§Ø¹Ø¯ Ø§Ù„Ø¥Ù…Ù„Ø§Ø¦ÙŠØ©: Ù‡Ù…Ø²Ø© Ø§Ù„Ù‚Ø·Ø¹ ÙˆØ£Ù„Ù Ø§Ù„ÙˆØµÙ„',
      'duration': '12:45',
      'teacher': 'Ø£. Ø£Ø­Ù…Ø¯ Ø§Ù„Ø³Ø¹ÙŠØ¯',
      'completed': 'true',
    },
    {
      'title': '2. Ù…ÙˆØ§Ø¶Ø¹ Ù‡Ù…Ø²Ø© Ø§Ù„Ù‚Ø·Ø¹ ÙÙŠ Ø§Ù„Ø£Ø³Ù…Ø§Ø¡ ÙˆØ§Ù„Ø£ÙØ¹Ø§Ù„',
      'duration': '15:20',
      'teacher': 'Ø£. Ø£Ø­Ù…Ø¯ Ø§Ù„Ø³Ø¹ÙŠØ¯',
      'completed': 'false',
    },
    {
      'title': '3. ØªØ¯Ø±ÙŠØ¨Ø§Øª ØªØ·Ø¨ÙŠÙ‚ÙŠØ© ÙˆÙ†Ù…Ø§Ø°Ø¬ ÙˆØ²Ø§Ø±ÙŠØ©',
      'duration': '09:15',
      'teacher': 'Ø£. Ø£Ø­Ù…Ø¯ Ø§Ù„Ø³Ø¹ÙŠØ¯',
      'completed': 'false',
    },
    {
      'title': '4. Ø§Ø®ØªØ¨Ø§Ø± Ø®ØªØ§Ù…ÙŠ Ù‚ØµÙŠØ± Ø¹Ù„Ù‰ Ø§Ù„ÙˆØ­Ø¯Ø©',
      'duration': '05:00',
      'teacher': 'Ø£. Ø£Ø­Ù…Ø¯ Ø§Ù„Ø³Ø¹ÙŠØ¯',
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
          style: GoogleFonts.almarai(fontSize: 16, fontWeight: FontWeight.w900, color: const Color(0xFF0F172A)),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.auto_awesome_rounded, color: Color(0xFF0284C7)),
            tooltip: 'Ø§Ø³Ø£Ù„ Ø§Ù„Ù…Ø³Ø§Ø¹Ø¯ Ø§Ù„Ø°ÙƒÙŠ Ø¹Ù† Ù‡Ø°Ø§ Ø§Ù„Ø¯Ø±Ø³',
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
                                  style: GoogleFonts.almarai(
                                    fontSize: 14,
                                    fontWeight: FontWeight.bold,
                                    color: Colors.white,
                                  ),
                                ),
                                Text(
                                  widget.teacherName,
                                  style: GoogleFonts.almarai(fontSize: 11, color: Colors.white70),
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
                          Text('04:15 / 12:45', style: GoogleFonts.almarai(fontSize: 11, color: Colors.white)),
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

          // 2. Video Title & Interactive Action Row (Ù„Ù… ÙŠØ¹Ø¬Ø¨Ù†ÙŠ â€¢ Ø´Ø§Ø±Ùƒ â€¢ Ø­ÙØ¸) matching Screenshot
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  widget.lessonTitle,
                  style: GoogleFonts.almarai(
                    fontSize: 15,
                    fontWeight: FontWeight.w900,
                    color: const Color(0xFF0F172A),
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '${widget.teacherName} â€¢ Ø´Ø±Ø­ Ù…ØªØ§Ø­ Ø¯ÙˆÙ† Ø¥Ù†ØªØ±Ù†Øª',
                  style: GoogleFonts.almarai(fontSize: 11, color: const Color(0xFF64748B), fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 12),

                // Action Bar matching Screenshot 1 (Ù„Ù… ÙŠØ¹Ø¬Ø¨Ù†ÙŠ â€¢ Ø´Ø§Ø±Ùƒ â€¢ Ø­ÙØ¸)
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    _buildActionButton(
                      icon: _isLiked ? Icons.thumb_up_rounded : Icons.thumb_up_outlined,
                      label: 'Ø£Ø¹Ø¬Ø¨Ù†ÙŠ',
                      isActive: _isLiked,
                      onTap: () => setState(() => _isLiked = !_isLiked),
                    ),
                    _buildActionButton(
                      icon: Icons.thumb_down_outlined,
                      label: 'Ù„Ù… ÙŠØ¹Ø¬Ø¨Ù†ÙŠ',
                      isActive: false,
                      onTap: () {},
                    ),
                    _buildActionButton(
                      icon: Icons.share_rounded,
                      label: 'Ø´Ø§Ø±Ùƒ',
                      isActive: false,
                      onTap: () {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text('ØªÙ… Ù†Ø³Ø® Ø±Ø§Ø¨Ø· Ø§Ù„Ø¯Ø±Ø³ Ø¨Ù†Ø¬Ø§Ø­ âœ“', style: GoogleFonts.almarai())),
                        );
                      },
                    ),
                    _buildActionButton(
                      icon: _isSaved ? Icons.bookmark_rounded : Icons.bookmark_outline_rounded,
                      label: _isSaved ? 'Ù…Ø­ÙÙˆØ¸' : 'Ø­ÙØ¸',
                      isActive: _isSaved,
                      onTap: () {
                        setState(() => _isSaved = !_isSaved);
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text(
                              _isSaved ? 'ØªÙ… Ø­ÙØ¸ Ø§Ù„Ø¯Ø±Ø³ ÙÙŠ Ø§Ù„Ù…ÙØ¶Ù„Ø© âœ“' : 'ØªÙ…Øª Ø¥Ø²Ø§Ù„Ø© Ø§Ù„Ø¯Ø±Ø³ Ù…Ù† Ø§Ù„Ù…ÙØ¶Ù„Ø©',
                              style: GoogleFonts.almarai(),
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
                  'Ù…Ø­ØªÙˆÙŠØ§Øª Ø§Ù„ÙˆØ­Ø¯Ø© (${_playlist.length} Ø¯Ø±ÙˆØ³)',
                  style: GoogleFonts.almarai(fontSize: 13, fontWeight: FontWeight.w800, color: const Color(0xFF0F172A)),
                ),
                Text(
                  'Ù…ÙƒØªÙ…Ù„ 1 Ù…Ù† ${_playlist.length}',
                  style: GoogleFonts.almarai(fontSize: 11, color: const Color(0xFF15803D), fontWeight: FontWeight.bold),
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
                                style: GoogleFonts.almarai(
                                  fontSize: 12.5,
                                  fontWeight: FontWeight.bold,
                                  color: isSelected ? const Color(0xFF0284C7) : const Color(0xFF0F172A),
                                ),
                              ),
                              Row(
                                children: [
                                  Text(
                                    item['duration']!,
                                    style: GoogleFonts.almarai(fontSize: 11, color: const Color(0xFF64748B)),
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    'â€¢ ${item['teacher']!}',
                                    style: GoogleFonts.almarai(fontSize: 11, color: const Color(0xFF94A3B8)),
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
            Text(label, style: GoogleFonts.almarai(fontSize: 10.5, color: color, fontWeight: FontWeight.bold)),
          ],
        ),
      ),
    );
  }
}


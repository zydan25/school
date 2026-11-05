import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/api_service.dart';
import '../core/models.dart';
import '../core/theme.dart';

class ChatScreen extends StatefulWidget {
  final ApiService api;
  const ChatScreen({super.key, required this.api});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final TextEditingController _aiInputController = TextEditingController();
  final TextEditingController _humanInputController = TextEditingController();
  final ScrollController _aiScrollController = ScrollController();
  final ScrollController _humanScrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    _aiInputController.dispose();
    _humanInputController.dispose();
    _aiScrollController.dispose();
    _humanScrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom(ScrollController controller) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (controller.hasClients) {
        controller.animateTo(
          controller.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.api,
      builder: (context, _) {
        final currentStudent = widget.api.currentStudent;
        final studentName = currentStudent?.fullName ?? 'حساب الطالب';
        final firstName = currentStudent?.fullName.split(' ').first ?? 'الطالب';
        final aiMessages = widget.api.currentStudentAiChat;
        final humanMessages = widget.api.humanChatMessages;

        return Scaffold(
          appBar: AppBar(
            title: Column(
              children: [
                Text(
                  'المحادثات المدرسية والذكاء الاصطناعي',
                  style: GoogleFonts.cairo(fontSize: 15, fontWeight: FontWeight.bold),
                ),
                Text(
                  'الطالب المستفيد: $studentName',
                  style: GoogleFonts.cairo(fontSize: 11, color: AppTheme.accent, fontWeight: FontWeight.bold),
                ),
              ],
            ),
            leading: IconButton(
              icon: const Icon(Icons.arrow_back_ios_new_rounded),
              onPressed: () => Navigator.pop(context),
            ),
            actions: [
              IconButton(
                icon: const Icon(Icons.refresh_rounded),
                tooltip: 'بدء محادثة ذكية جديدة',
                onPressed: () {
                  showDialog(
                    context: context,
                    builder: (ctx) => AlertDialog(
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
                      title: Text(
                        'بدء محادثة جديدة',
                        style: GoogleFonts.cairo(fontWeight: FontWeight.bold, fontSize: 16),
                      ),
                      content: Text(
                        'هل تريد مسح سجل المحادثة الحالية مع المعلم الذكي والبدء من جديد؟',
                        style: GoogleFonts.cairo(fontSize: 13),
                      ),
                      actions: [
                        TextButton(
                          onPressed: () => Navigator.pop(ctx),
                          child: Text('إلغاء', style: GoogleFonts.cairo(color: const Color(0xFF64748B))),
                        ),
                        ElevatedButton(
                          onPressed: () {
                            widget.api.clearCurrentStudentAiChat();
                            Navigator.pop(ctx);
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text('تم بدء محادثة جديدة بنجاح ✓', style: GoogleFonts.cairo(fontWeight: FontWeight.bold)),
                                duration: const Duration(seconds: 2),
                                behavior: SnackBarBehavior.floating,
                                backgroundColor: const Color(0xFF15803D),
                              ),
                            );
                          },
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFFE11D48),
                            foregroundColor: Colors.white,
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                          ),
                          child: Text('بدء جديد', style: GoogleFonts.cairo(fontWeight: FontWeight.bold)),
                        ),
                      ],
                    ),
                  );
                },
              ),
            ],
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
                  labelStyle: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold),
                  indicatorColor: AppTheme.accent,
                  indicatorSize: TabBarIndicatorSize.tab,
                  tabs: [
                    Tab(
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.auto_awesome_rounded, color: AppTheme.accent, size: 16),
                          const SizedBox(width: 6),
                          Text('المساعد الذكي ($firstName)'),
                        ],
                      ),
                    ),
                    const Tab(
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.forum_rounded, size: 16),
                          SizedBox(width: 6),
                          Text('المعلمون والإدارة'),
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
              // Tab 1: AI Student Copilot
              _buildAiCopilotTab(currentStudent, aiMessages),

              // Tab 2: Human Teachers Chat
              _buildHumanChatTab(humanMessages),
            ],
          ),
        );
      },
    );
  }

  // ---------------------------------------------------------------------------
  // Tab 1: AI Copilot for Current Student
  // ---------------------------------------------------------------------------
  Widget _buildAiCopilotTab(StudentProfile? student, List<ChatMessage> messages) {
    return Column(
      children: [
        // AI Student Info Banner
        Container(
          margin: const EdgeInsets.fromLTRB(16, 10, 16, 4),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [Color(0xFF0F172A), Color(0xFF1E3A8A)],
              begin: Alignment.topRight,
              end: Alignment.bottomLeft,
            ),
            borderRadius: BorderRadius.circular(14),
          ),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.15),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.psychology_rounded, color: Colors.amber, size: 20),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'المعلم الذكي المخصص لـ ${student?.fullName ?? 'الطالب'}',
                      style: GoogleFonts.cairo(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold),
                    ),
                    Text(
                      'جاهز لشرح دروس ${student?.grade ?? 'المنهج الدراسي'} وتبسيط الواجبات فوراً 🎓',
                      style: GoogleFonts.cairo(color: Colors.white70, fontSize: 10),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),

        // Quick Suggestion Chips
        SizedBox(
          height: 38,
          child: ListView(
            scrollDirection: Axis.horizontal,
            physics: const BouncingScrollPhysics(),
            padding: const EdgeInsets.symmetric(horizontal: 16),
            children: [
              _buildAiPromptChip('📚 واجبات اليوم', 'ما هي الواجبات المعلقة والمطلوبة مني اليوم؟'),
              _buildAiPromptChip('📅 جدول حصص اليوم', 'ما هي الحصص والمواد المتبقية لليوم؟'),
              _buildAiPromptChip('⚡ قانون نيوتن الثاني', 'اشرح لي قانون نيوتن الثاني بالتفصيل مع مسائل وأمثلة عملية'),
              _buildAiPromptChip('📐 اتصال الدوال والنهايات', 'ما هي شروط اتصال الدالة عند نقطة في الرياضيات؟'),
              _buildAiPromptChip('⚗️ الأكسدة والاختزال', 'ما الفرق بين العامل المؤكسد والعامل المختزل في الكيمياء؟'),
              _buildAiPromptChip('📊 نصائح للتفوق والدرجات', 'كيف أحسن درجاتي في مادة الفيزياء للحفاظ على الترتيب الأول؟'),
            ],
          ),
        ),

        const SizedBox(height: 4),

        // Messages List
        Expanded(
          child: ListView.builder(
            controller: _aiScrollController,
            padding: const EdgeInsets.all(16),
            physics: const BouncingScrollPhysics(),
            itemCount: messages.length + (widget.api.isAiThinking ? 1 : 0),
            itemBuilder: (context, index) {
              if (index < messages.length) {
                final msg = messages[index];
                return _buildAiBubble(msg);
              }
              return _buildThinkingBubble();
            },
          ),
        ),

        // Input Bar
        _buildChatInput(
          controller: _aiInputController,
          hint: 'اسأل المعلم الذكي عن أي سؤال أو مسألة...',
          onSend: (text) {
            widget.api.askAiCopilot(text);
            _aiInputController.clear();
            _scrollToBottom(_aiScrollController);
          },
          isAi: true,
        ),
      ],
    );
  }

  Widget _buildAiPromptChip(String label, String prompt) {
    return Padding(
      padding: const EdgeInsets.only(left: 8),
      child: ActionChip(
        label: Text(label, style: GoogleFonts.cairo(fontSize: 10, fontWeight: FontWeight.bold, color: AppTheme.accent)),
        backgroundColor: const Color(0xFFEFF6FF),
        side: const BorderSide(color: Color(0xFFBFDBFE)),
        onPressed: () {
          widget.api.askAiCopilot(prompt);
          _scrollToBottom(_aiScrollController);
        },
      ),
    );
  }

  Widget _buildAiBubble(ChatMessage msg) {
    final isMe = msg.isMe;
    return Align(
      alignment: isMe ? Alignment.centerLeft : Alignment.centerRight,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        constraints: const BoxConstraints(maxWidth: 340),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: isMe ? const Color(0xFF0F172A) : Colors.white,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(16),
            topRight: const Radius.circular(16),
            bottomLeft: Radius.circular(isMe ? 4 : 16),
            bottomRight: Radius.circular(isMe ? 16 : 4),
          ),
          border: isMe ? null : Border.all(color: const Color(0xFFE2E8F0)),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.04),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (!isMe) ...[
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        padding: const EdgeInsets.all(4),
                        decoration: BoxDecoration(
                          color: const Color(0xFFEFF6FF),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: const Icon(Icons.auto_awesome_rounded, color: Color(0xFF0284C7), size: 14),
                      ),
                      const SizedBox(width: 6),
                      Text(
                        msg.senderName,
                        style: GoogleFonts.cairo(
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          color: const Color(0xFF0284C7),
                        ),
                      ),
                    ],
                  ),
                  InkWell(
                    onTap: () {
                      Clipboard.setData(ClipboardData(text: msg.text));
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text('تم نسخ الإجابة إلى الحافظة ✓', style: GoogleFonts.cairo(fontWeight: FontWeight.bold, fontSize: 12)),
                          duration: const Duration(seconds: 2),
                          behavior: SnackBarBehavior.floating,
                          backgroundColor: const Color(0xFF1E60FF),
                        ),
                      );
                    },
                    borderRadius: BorderRadius.circular(6),
                    child: Padding(
                      padding: const EdgeInsets.all(4),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.copy_rounded, size: 13, color: Color(0xFF64748B)),
                          const SizedBox(width: 3),
                          Text(
                            'نسخ',
                            style: GoogleFonts.cairo(fontSize: 10, color: const Color(0xFF64748B), fontWeight: FontWeight.bold),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 6),
            ],
            SelectableText(
              msg.text,
              style: GoogleFonts.cairo(
                fontSize: 12.5,
                color: isMe ? Colors.white : const Color(0xFF0F172A),
                height: 1.5,
              ),
            ),
            const SizedBox(height: 6),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                if (!isMe)
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      InkWell(
                        onTap: () {
                          widget.api.askAiCopilot('اشرح النقطة السابقة بمثال إضافي مبسط وتطبيقي أكثر');
                          _scrollToBottom(_aiScrollController);
                        },
                        borderRadius: BorderRadius.circular(12),
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: const Color(0xFFF1F5F9),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            '💡 مثال إضافي',
                            style: GoogleFonts.cairo(fontSize: 9.5, fontWeight: FontWeight.bold, color: const Color(0xFF475569)),
                          ),
                        ),
                      ),
                      const SizedBox(width: 6),
                      InkWell(
                        onTap: () {
                          widget.api.askAiCopilot('اعطني سؤالاً اختبارياً تدريبياً على ما شرحته لي للتو لاختبار فهمي');
                          _scrollToBottom(_aiScrollController);
                        },
                        borderRadius: BorderRadius.circular(12),
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: const Color(0xFFF1F5F9),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            '📝 تدريب',
                            style: GoogleFonts.cairo(fontSize: 9.5, fontWeight: FontWeight.bold, color: const Color(0xFF475569)),
                          ),
                        ),
                      ),
                    ],
                  )
                else
                  const SizedBox.shrink(),
                Text(
                  msg.time,
                  style: GoogleFonts.cairo(
                    fontSize: 9.5,
                    color: isMe ? Colors.white70 : const Color(0xFF94A3B8),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildThinkingBubble() {
    return Align(
      alignment: Alignment.centerRight,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        constraints: const BoxConstraints(maxWidth: 320),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: const Color(0xFFF0FDF4),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: const Color(0xFFBBF7D0)),
          boxShadow: AppTheme.softShadow,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(
              width: 14,
              height: 14,
              child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF16A34A)),
            ),
            const SizedBox(width: 8),
            Flexible(
              child: Text(
                'المساعد الذكي (Gemini 3.5 Flash) يستحضر بيانات المنهج ويكتب الإجابة...',
                style: GoogleFonts.cairo(
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                  color: const Color(0xFF166534),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Tab 2: Human Teachers & School Admin Chat
  // ---------------------------------------------------------------------------
  Widget _buildHumanChatTab(List<ChatMessage> messages) {
    return Column(
      children: [
        // Messages List
        Expanded(
          child: ListView.builder(
            controller: _humanScrollController,
            padding: const EdgeInsets.all(16),
            physics: const BouncingScrollPhysics(),
            itemCount: messages.length,
            itemBuilder: (context, index) {
              final msg = messages[index];
              return _buildHumanBubble(msg);
            },
          ),
        ),

        // Input Bar
        _buildChatInput(
          controller: _humanInputController,
          hint: 'اكتب رسالتك للمعلم أو شؤون الطلاب...',
          onSend: (text) {
            widget.api.addHumanChatMessage(text);
            _humanInputController.clear();
            _scrollToBottom(_humanScrollController);
          },
          isAi: false,
        ),
      ],
    );
  }

  Widget _buildHumanBubble(ChatMessage msg) {
    final isMe = msg.isMe;
    return Align(
      alignment: isMe ? Alignment.centerLeft : Alignment.centerRight,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        constraints: const BoxConstraints(maxWidth: 320),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: isMe ? AppTheme.accent : Colors.white,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(16),
            topRight: const Radius.circular(16),
            bottomLeft: Radius.circular(isMe ? 4 : 16),
            bottomRight: Radius.circular(isMe ? 16 : 4),
          ),
          border: isMe ? null : Border.all(color: AppTheme.borderLight),
          boxShadow: AppTheme.softShadow,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (!isMe) ...[
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    msg.senderName,
                    style: GoogleFonts.cairo(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.primaryNavy,
                    ),
                  ),
                  const SizedBox(width: 4),
                  Text(
                    '(${msg.senderRole})',
                    style: GoogleFonts.cairo(fontSize: 9, color: AppTheme.textMuted),
                  ),
                ],
              ),
              const SizedBox(height: 4),
            ],
            Text(
              msg.text,
              style: GoogleFonts.cairo(
                fontSize: 12,
                color: isMe ? Colors.white : AppTheme.textMain,
                height: 1.4,
              ),
            ),
            const SizedBox(height: 4),
            Align(
              alignment: Alignment.bottomLeft,
              child: Text(
                msg.time,
                style: GoogleFonts.cairo(
                  fontSize: 9,
                  color: isMe ? Colors.white70 : AppTheme.textMuted,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildChatInput({
    required TextEditingController controller,
    required String hint,
    required Function(String) onSend,
    required bool isAi,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white,
        border: const Border(top: BorderSide(color: AppTheme.borderLight)),
        boxShadow: AppTheme.softShadow,
      ),
      child: SafeArea(
        child: Row(
          children: [
            Expanded(
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 14),
                decoration: BoxDecoration(
                  color: const Color(0xFFF8FAFC),
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(color: AppTheme.borderLight),
                ),
                child: TextField(
                  controller: controller,
                  style: GoogleFonts.cairo(fontSize: 12, color: AppTheme.textMain),
                  decoration: InputDecoration(
                    hintText: hint,
                    hintStyle: GoogleFonts.cairo(fontSize: 11, color: AppTheme.textMuted),
                    border: InputBorder.none,
                  ),
                  onSubmitted: (val) {
                    if (val.trim().isNotEmpty) onSend(val.trim());
                  },
                ),
              ),
            ),
            const SizedBox(width: 8),
            InkWell(
              onTap: () {
                if (controller.text.trim().isNotEmpty) {
                  onSend(controller.text.trim());
                }
              },
              borderRadius: BorderRadius.circular(24),
              child: Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: isAi ? AppTheme.accent : AppTheme.primaryNavy,
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.send_rounded, color: Colors.white, size: 18),
              ),
            ),
          ],
        ),
      ),
    );
  }
}



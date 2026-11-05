import '../widgets/school_bottom_bar.dart';
import 'package:flutter/material.dart';
import '../core/api_service.dart';
import '../core/models.dart';
import '../core/theme.dart';

class TimetableScreen extends StatefulWidget {
  final ApiService api;
  const TimetableScreen({super.key, required this.api});

  @override
  State<TimetableScreen> createState() => _TimetableScreenState();
}

class _TimetableScreenState extends State<TimetableScreen> {
  String _selectedDay = 'الأحد';
  final List<String> _days = ['الأحد', 'الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس'];
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _refreshTimetable();
  }

  Future<void> _refreshTimetable() async {
    setState(() => _isLoading = true);
    await widget.api.fetchStudentTimetable();
    if (mounted) setState(() => _isLoading = false);
  }

  @override
  Widget build(BuildContext context) {
    final allPeriods = widget.api.studentTimetablePeriods.isNotEmpty
        ? widget.api.studentTimetablePeriods
        : widget.api.timetable;
    final periods = allPeriods.where((p) => p.dayName == _selectedDay).toList();

    return Scaffold(
      backgroundColor: Colors.white,
      bottomNavigationBar: SchoolBottomBar(api: widget.api, currentIndex: -1),
      appBar: AppBar(
        scrolledUnderElevation: 0,
        title: const Text('جدول الحصص الأسبوعي'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded),
          onPressed: () => Navigator.pop(context),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded, color: AppTheme.accent),
            onPressed: _refreshTimetable,
            tooltip: 'تحديث الجدول',
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator(color: AppTheme.accent))
          : Column(
        children: [
          // Days Bar
          Container(
            height: 52,
            margin: const EdgeInsets.symmetric(vertical: 8),
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              itemCount: _days.length,
              itemBuilder: (context, index) {
                final day = _days[index];
                final isSelected = _selectedDay == day;
                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: ChoiceChip(
                    label: Text(
                      day,
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: isSelected ? FontWeight.bold : FontWeight.w600,
                        color: isSelected ? Colors.white : AppTheme.textMain,
                      ),
                    ),
                    selected: isSelected,
                    selectedColor: AppTheme.primary,
                    backgroundColor: Colors.white,
                    showCheckmark: false,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                      side: BorderSide(
                        color: isSelected ? AppTheme.primary : AppTheme.borderLight,
                      ),
                    ),
                    onSelected: (val) {
                      if (val) setState(() => _selectedDay = day);
                    },
                  ),
                );
              },
            ),
          ),

          // Periods Timeline
          Expanded(
            child: periods.isEmpty
                ? Center(
                    child: Text(
                      'لا توجد حصص مسجلة ليوم $_selectedDay',
                      style: const TextStyle(color: AppTheme.textMuted),
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                    itemCount: periods.length,
                    itemBuilder: (context, index) {
                      final p = periods[index];
                      return _buildPeriodCard(p, index + 1);
                    },
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildPeriodCard(TimetablePeriod p, int number) {
    final isMath = p.subject.contains('رياضيات');
    final isScience = p.subject.contains('فيزياء') || p.subject.contains('كيمياء');
    Color accent = isMath ? AppTheme.purple : (isScience ? AppTheme.accent : AppTheme.emerald);

    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppTheme.borderLight),
        boxShadow: AppTheme.softShadow,
      ),
      child: Row(
        children: [
          // Period Number Box
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: accent.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Center(
              child: Text(
                '0$number',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w900,
                  color: accent,
                ),
              ),
            ),
          ),
          const SizedBox(width: 14),

          // Period Info
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      p.subject,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w800,
                        color: AppTheme.textMain,
                      ),
                    ),
                    Text(
                      p.time,
                      style: const TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.accent,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    const Icon(Icons.person_outline, size: 14, color: AppTheme.textMuted),
                    const SizedBox(width: 4),
                    Text(
                      p.teacher,
                      style: const TextStyle(fontSize: 11, color: AppTheme.textMuted),
                    ),
                    const SizedBox(width: 12),
                    const Icon(Icons.meeting_room_outlined, size: 14, color: AppTheme.textMuted),
                    const SizedBox(width: 4),
                    Text(
                      p.classroom,
                      style: const TextStyle(fontSize: 11, color: AppTheme.textMuted),
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


import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/api_service.dart';
import '../core/models.dart';
import '../core/theme.dart';

class AttendanceScreen extends StatefulWidget {
  final ApiService api;
  const AttendanceScreen({super.key, required this.api});

  @override
  State<AttendanceScreen> createState() => _AttendanceScreenState();
}

class _AttendanceScreenState extends State<AttendanceScreen> {
  final _reasonController = TextEditingController();
  final _dateController = TextEditingController(text: 'اليوم، الأربعاء 4 نوفمبر 2026');
  bool _hasMedicalReport = true;

  @override
  void dispose() {
    _reasonController.dispose();
    _dateController.dispose();
    super.dispose();
  }

  void _showSubmitExcuseModal() {
    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          title: Row(
            children: [
              const Icon(Icons.medical_services_rounded, color: AppTheme.screenshotBlue, size: 22),
              const SizedBox(width: 8),
              Text(
                'تقديم عذر غياب معتمد',
                style: GoogleFonts.tajawal(fontSize: 15, fontWeight: FontWeight.bold),
              ),
            ],
          ),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'سيتم إرسال هذا العذر إلى إدارة المدرسة ومعلمي الصف لاعتماده.',
                  style: GoogleFonts.tajawal(fontSize: 11, color: const Color(0xFF64748B)),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _dateController,
                  decoration: InputDecoration(
                    labelText: 'تاريخ يوم الغياب',
                    prefixIcon: const Icon(Icons.calendar_today_rounded, size: 18),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: _reasonController,
                  maxLines: 3,
                  decoration: InputDecoration(
                    labelText: 'سبب وظروف الغياب بالتفصيل',
                    hintText: 'مثال: وعكة صحية ومراجعة الطبيب...',
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Checkbox(
                      value: _hasMedicalReport,
                      activeColor: AppTheme.screenshotGreen,
                      onChanged: (val) => setDialogState(() => _hasMedicalReport = val ?? true),
                    ),
                    Expanded(
                      child: Text(
                        'إرفاق تقرير طبي / إشعار مراجعة معتمد',
                        style: GoogleFonts.tajawal(fontSize: 11, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ],
                ),
                if (_hasMedicalReport)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF1F5F9),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: const Color(0xFFCBD5E1)),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.attach_file_rounded, size: 16, color: AppTheme.screenshotBlue),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(
                            'medical_report_2026.pdf (مرفق جاهز)',
                            style: GoogleFonts.tajawal(fontSize: 10, fontWeight: FontWeight.bold, color: AppTheme.screenshotBlue),
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: Text('إلغاء', style: GoogleFonts.tajawal()),
            ),
            ElevatedButton(
              onPressed: () {
                final reason = _reasonController.text.trim();
                if (reason.isEmpty) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('الرجاء كتابة سبب الغياب', style: GoogleFonts.tajawal())),
                  );
                  return;
                }
                widget.api.submitAbsenceExcuse(
                  date: _dateController.text.trim(),
                  reason: reason,
                  medicalReportUrl: _hasMedicalReport ? 'https://school.alattab.site/media/reports/medical.pdf' : null,
                );
                _reasonController.clear();
                Navigator.pop(ctx);
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text('تم تقديم عذر الغياب إلى الإدارة بنجاح!', style: GoogleFonts.tajawal(fontWeight: FontWeight.bold)),
                    backgroundColor: AppTheme.screenshotGreen,
                  ),
                );
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.screenshotBlue,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
              child: Text('إرسال العذر', style: GoogleFonts.tajawal(fontWeight: FontWeight.bold)),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.api,
      builder: (context, _) {
        final student = widget.api.currentStudent;
        final studentName = student?.fullName ?? 'حساب الطالب';
        final attendanceRate = student?.attendanceRate ?? 98.0;
        final excuses = widget.api.absenceExcuses;

        return Scaffold(
          backgroundColor: const Color(0xFFF8FAFC),
          appBar: AppBar(
            backgroundColor: Colors.white,
            elevation: 0,
            title: Text(
              'سجل الحضور والمواظبة • $studentName',
              style: GoogleFonts.tajawal(fontSize: 15, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
            ),
            leading: IconButton(
              icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18, color: Color(0xFF0F172A)),
              onPressed: () => Navigator.pop(context),
            ),
            actions: [
              IconButton(
                icon: const Icon(Icons.add_comment_rounded, color: AppTheme.screenshotBlue),
                tooltip: 'تقديم عذر غياب',
                onPressed: _showSubmitExcuseModal,
              ),
            ],
          ),
          body: SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            physics: const BouncingScrollPhysics(),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Circular Attendance Metric Card
                Container(
                  padding: const EdgeInsets.all(18),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: const Color(0xFFE2E8F0)),
                    boxShadow: AppTheme.softShadow,
                  ),
                  child: Row(
                    children: [
                      Stack(
                        alignment: Alignment.center,
                        children: [
                          SizedBox(
                            width: 76,
                            height: 76,
                            child: CircularProgressIndicator(
                              value: attendanceRate / 100,
                              strokeWidth: 8,
                              backgroundColor: const Color(0xFFF1F5F9),
                              valueColor: const AlwaysStoppedAnimation<Color>(AppTheme.screenshotGreen),
                            ),
                          ),
                          Text(
                            '${attendanceRate.toInt()}%',
                            style: GoogleFonts.tajawal(
                              fontSize: 17,
                              fontWeight: FontWeight.w900,
                              color: AppTheme.screenshotGreen,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'نسبة الحضور التراكمية',
                              style: GoogleFonts.tajawal(
                                fontSize: 15,
                                fontWeight: FontWeight.bold,
                                color: const Color(0xFF0F172A),
                              ),
                            ),
                            const SizedBox(height: 3),
                            Text(
                              'سجل ممتاز ومثالي للعام الدراسي 2026/2027 بدون أي غياب غير مبرر.',
                              style: GoogleFonts.tajawal(
                                fontSize: 11,
                                color: const Color(0xFF64748B),
                                height: 1.4,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 14),

                // Stat Counter Cards
                Row(
                  children: [
                    Expanded(child: _buildAttendancePill('أيام الحضور', '38 يوم', AppTheme.screenshotGreen, Icons.check_circle_rounded)),
                    const SizedBox(width: 8),
                    Expanded(child: _buildAttendancePill('غياب بعذر', '1 يوم', AppTheme.screenshotOrange, Icons.medical_services_rounded)),
                    const SizedBox(width: 8),
                    Expanded(child: _buildAttendancePill('غياب غير مبرر', '0 يوم', AppTheme.rose, Icons.cancel_outlined)),
                  ],
                ),

                const SizedBox(height: 14),

                // Submit Excuse Action Banner
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: const Color(0xFFEFF6FF),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: const Color(0xFFBFDBFE)),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.info_outline_rounded, color: AppTheme.screenshotBlue, size: 22),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'هل تغيب الطالب أو لديه ظرف طارئ؟',
                              style: GoogleFonts.tajawal(fontSize: 12, fontWeight: FontWeight.bold, color: const Color(0xFF1E3A8A)),
                            ),
                            Text(
                              'يمكنك تقديم عذر غياب رسمي وإرفاق الإشعار الطبي لاعتماده فوراً.',
                              style: GoogleFonts.tajawal(fontSize: 10, color: const Color(0xFF3B82F6)),
                            ),
                          ],
                        ),
                      ),
                      ElevatedButton(
                        onPressed: _showSubmitExcuseModal,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppTheme.screenshotBlue,
                          foregroundColor: Colors.white,
                          elevation: 0,
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                        ),
                        child: Text('+ تقديم عذر', style: GoogleFonts.tajawal(fontSize: 11, fontWeight: FontWeight.bold)),
                      ),
                    ],
                  ),
                ),

                if (excuses.isNotEmpty) ...[
                  const SizedBox(height: 18),
                  Text(
                    'أعذار الغياب المقدمة (${excuses.length})',
                    style: GoogleFonts.tajawal(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                  ),
                  const SizedBox(height: 8),
                  ...excuses.map((exc) => _buildExcuseCard(exc)),
                ],

                const SizedBox(height: 18),

                // Section Header
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'سجل الأيام والحصص الأخيرة',
                      style: GoogleFonts.tajawal(fontSize: 13, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                    ),
                    Text(
                      'تحديث لحظي من بوابة الحضور',
                      style: GoogleFonts.tajawal(fontSize: 10, color: AppTheme.screenshotBlue),
                    ),
                  ],
                ),

                const SizedBox(height: 8),

                // Attendance Logs List
                _buildDayLog('الأربعاء 4 نوفمبر 2026', 'حاضر في الموعد المحدد (07:40 ص)', true),
                _buildDayLog('الثلاثاء 3 نوفمبر 2026', 'غياب بعذر طبي معتمد من الإدارة', false, isExcused: true),
                _buildDayLog('الإثنين 2 نوفمبر 2026', 'حاضر في الموعد المحدد (07:50 ص)', true),
                _buildDayLog('الأحد 1 نوفمبر 2026', 'حاضر في الموعد المحدد (07:45 ص)', true),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildAttendancePill(String title, String val, Color color, IconData icon) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Column(
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(height: 4),
          Text(
            val,
            style: GoogleFonts.tajawal(fontSize: 13, fontWeight: FontWeight.w900, color: color),
          ),
          Text(
            title,
            style: GoogleFonts.tajawal(fontSize: 10, color: const Color(0xFF64748B)),
          ),
        ],
      ),
    );
  }

  Widget _buildExcuseCard(AbsenceExcuse exc) {
    final isApproved = exc.status == 'approved';
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFE2E8F0)),
        boxShadow: AppTheme.softShadow,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CircleAvatar(
            radius: 16,
            backgroundColor: isApproved ? AppTheme.screenshotGreen.withValues(alpha: 0.1) : AppTheme.screenshotOrange.withValues(alpha: 0.1),
            child: Icon(
              isApproved ? Icons.verified_rounded : Icons.pending_actions_rounded,
              size: 16,
              color: isApproved ? AppTheme.screenshotGreen : AppTheme.screenshotOrange,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      exc.date,
                      style: GoogleFonts.tajawal(fontSize: 12, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: isApproved ? AppTheme.screenshotGreen.withValues(alpha: 0.1) : AppTheme.screenshotOrange.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        isApproved ? 'معتمد من الإدارة' : 'قيد المراجعة',
                        style: GoogleFonts.tajawal(fontSize: 9, fontWeight: FontWeight.bold, color: isApproved ? AppTheme.screenshotGreen : AppTheme.screenshotOrange),
                      ),
                    ),
                  ],
                ),
                Text(
                  exc.reason,
                  style: GoogleFonts.tajawal(fontSize: 11, color: const Color(0xFF475569)),
                ),
                if (exc.medicalReportUrl != null) ...[
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      const Icon(Icons.picture_as_pdf_rounded, size: 12, color: AppTheme.screenshotBlue),
                      const SizedBox(width: 4),
                      Text('تقرير طبي مرفق', style: GoogleFonts.tajawal(fontSize: 9, color: AppTheme.screenshotBlue, fontWeight: FontWeight.bold)),
                    ],
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDayLog(String date, String desc, bool isPresent, {bool isExcused = false}) {
    Color col = isPresent ? AppTheme.screenshotGreen : (isExcused ? AppTheme.screenshotOrange : AppTheme.rose);
    IconData icon = isPresent ? Icons.check_circle_rounded : (isExcused ? Icons.medical_services_rounded : Icons.cancel_rounded);

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFE2E8F0)),
        boxShadow: AppTheme.softShadow,
      ),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: col.withValues(alpha: 0.1),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, color: col, size: 18),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  date,
                  style: GoogleFonts.tajawal(fontSize: 12, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                ),
                Text(
                  desc,
                  style: GoogleFonts.tajawal(fontSize: 10, color: const Color(0xFF64748B)),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}


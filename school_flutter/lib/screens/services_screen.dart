import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/api_service.dart';
import '../core/theme.dart';

class ServicesScreen extends StatelessWidget {
  final ApiService api;
  const ServicesScreen({super.key, required this.api});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('الخدمات المدرسية والمرافق'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        physics: const BouncingScrollPhysics(),
        children: [
          // Bus Transport Card
          _buildServiceSection(
            title: 'خدمة النقل المدرسي (الحافلات)',
            subtitle: 'الحافلة رقم (12) - خط سير حدة والستين',
            icon: Icons.directions_bus_filled_rounded,
            color: AppTheme.amber,
            items: [
              _buildServiceDetail('السائق المسؤول', 'أبو ريان - هاتف: 771234567'),
              _buildServiceDetail('وقت الانطلاق الصباحي', '06:45 ص من نقطة التجمع'),
              _buildServiceDetail('حالة الحافلة اليوم', 'وصلت المدرسة بنجاح (07:35 ص)'),
            ],
          ),

          const SizedBox(height: 16),

          // Clinic Card
          _buildServiceSection(
            title: 'الصحة والعيادة المدرسية',
            subtitle: 'الملف الصحي الدوري للطالب',
            icon: Icons.local_hospital_rounded,
            color: AppTheme.emerald,
            items: [
              _buildServiceDetail('فصيلة الدم', 'O+ (موجب)'),
              _buildServiceDetail('آخر فحص طبي دوري', '15 أكتوبر 2026 - سليم ولله الحمد'),
              _buildServiceDetail('الحساسية والاحتياطات', 'لا توجد أي حساسية دوائية مسجلة'),
            ],
          ),

          const SizedBox(height: 16),

          // Library Card
          _buildServiceSection(
            title: 'المكتبة والكتب المدرسية',
            subtitle: 'استعارة المراجع والكتب الثقافية',
            icon: Icons.local_library_rounded,
            color: AppTheme.purple,
            items: [
              _buildServiceDetail('الكتب المستلمة', 'المجموعة الكاملة للعام الدراسي 2026/2027'),
              _buildServiceDetail('الكتب المعارة حالياً', 'كتاب: مقدمة في الخوارزميات والبرمجة'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildServiceSection({
    required String title,
    required String subtitle,
    required IconData icon,
    required Color color,
    required List<Widget> items,
  }) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppTheme.borderLight),
        boxShadow: AppTheme.softShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, color: color, size: 24),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: GoogleFonts.cairo(
                        fontSize: 15,
                        fontWeight: FontWeight.w800,
                        color: AppTheme.textMain,
                      ),
                    ),
                    Text(
                      subtitle,
                      style: GoogleFonts.cairo(
                        fontSize: 11,
                        color: AppTheme.textMuted,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          const Divider(height: 1, color: AppTheme.borderLight),
          const SizedBox(height: 10),
          ...items,
        ],
      ),
    );
  }

  Widget _buildServiceDetail(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: GoogleFonts.cairo(
              fontSize: 12,
              color: AppTheme.textMuted,
              fontWeight: FontWeight.w600,
            ),
          ),
          Text(
            value,
            style: GoogleFonts.cairo(
              fontSize: 12,
              color: AppTheme.textMain,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }
}

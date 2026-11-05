import '../widgets/school_bottom_bar.dart';

import 'package:flutter/material.dart';

import '../core/api_service.dart';

import '../core/theme.dart';



class ServicesScreen extends StatelessWidget {

  final ApiService api;

  const ServicesScreen({super.key, required this.api});



  @override

  Widget build(BuildContext context) {

    return Scaffold(

      backgroundColor: Colors.white,

      bottomNavigationBar: SchoolBottomBar(api: api, currentIndex: -1),

      appBar: AppBar(

        scrolledUnderElevation: 0,

        title: const Text(

          'الخدمات المدرسية والمرافق',

          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: AppTheme.textMain),

        ),

        centerTitle: true,

        leading: IconButton(

          icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18),

          onPressed: () => Navigator.pop(context),

        ),

      ),

      body: ListView(

        padding: const EdgeInsets.all(18),

        physics: const BouncingScrollPhysics(),

        children: [

          // 1. Bus Transport Card

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



          // 2. School Library Card

          _buildServiceSection(

            title: 'المكتبة المدرسية ومصادر التعلم',

            subtitle: 'استعارة المراجع والكتب الثقافية المعتمدة',

            icon: Icons.local_library_rounded,

            color: AppTheme.purple,

            items: [

              _buildServiceDetail('المقررات المستلمة', 'المجموعة الكاملة للعام الدراسي 2026/2027'),

              _buildServiceDetail('الكتب المعارة حالياً', 'كتاب: مقدمة في الخوارزميات والبرمجة'),

              _buildServiceDetail('مواعيد المكتبة', 'يومياً خلال أوقات الفسحة والأنشطة'),

            ],

          ),



          const SizedBox(height: 16),



          // 3. Student Activities & Sports Facility Card

          _buildServiceSection(

            title: 'الأنشطة المدرسية والصالة الرياضية',

            subtitle: 'الملاعب الرياضية والنوادي العلمية',

            icon: Icons.sports_volleyball_rounded,

            color: AppTheme.accent,

            items: [

              _buildServiceDetail('النادي المسجل به الطالب', 'نادي الروبوت والذكاء الاصطناعي'),

              _buildServiceDetail('يوم النشاط الأسبوعي', 'كل ثلاثاء - الفترة المسائية 03:00 م'),

              _buildServiceDetail('مشرف النشاط', 'أ. إبراهيم الحداد'),

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

                      style: const TextStyle(

                        fontSize: 14,

                        fontWeight: FontWeight.w800,

                        color: AppTheme.textMain,

                      ),

                    ),

                    Text(

                      subtitle,

                      style: const TextStyle(

                        fontSize: 11,

                        color: AppTheme.textMuted,

                        fontWeight: FontWeight.w600,

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

          Text(label, style: const TextStyle(fontSize: 12, color: AppTheme.textMuted, fontWeight: FontWeight.bold)),

          Text(value, style: const TextStyle(fontSize: 12, color: AppTheme.textMain, fontWeight: FontWeight.w700)),

        ],

      ),

    );

  }

}




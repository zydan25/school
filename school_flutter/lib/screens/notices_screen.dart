import '../widgets/school_bottom_bar.dart';

import 'package:flutter/material.dart';

import '../core/api_service.dart';

import '../core/theme.dart';



class NoticesScreen extends StatelessWidget {

  final ApiService api;

  const NoticesScreen({super.key, required this.api});



  @override

  Widget build(BuildContext context) {

    return Scaffold(

      backgroundColor: Colors.white,

      bottomNavigationBar: SchoolBottomBar(api: api, currentIndex: -1),

      appBar: AppBar(

        scrolledUnderElevation: 0,

        title: const Text('التعاميم والإعلانات المدرسية'),

        leading: IconButton(

          icon: const Icon(Icons.arrow_back_ios_new_rounded),

          onPressed: () => Navigator.pop(context),

        ),

      ),

      body: ListView(

        padding: const EdgeInsets.all(20),

        physics: const BouncingScrollPhysics(),

        children: [

          _buildNoticeCard(

            title: 'بدء اختبارات منتصف الفصل الدراسي الأول',

            date: 'منذ يومين • إدارة المدرسة',

            content: 'نحيطكم علماً بأن جدول الاختبارات الشهرية قد تم اعتماده، ويرجى من جميع الطلاب الالتزام بالحضور بالزي المدرسي الموحد والحضور المبكر.',

            tag: 'هام جداً',

            tagColor: AppTheme.rose,

          ),

          _buildNoticeCard(

            title: 'افتتاح مسابقة الروبوت والذكاء الاصطناعي',

            date: 'منذ 4 أيام • قسم الأنشطة الطلابية',

            content: 'يسر النادي العلمي الإعلان عن بدء التسجيل في مسابقة الابتكار والبرمجة للعام الحالي لطلاب المرحلة الثانوية والأساسية.',

            tag: 'أنشطة',

            tagColor: AppTheme.accent,

          ),

          _buildNoticeCard(

            title: 'جدول الإجازات الرسمية المعتمدة',

            date: 'منذ أسبوع • شؤون الطلاب',

            content: 'يمكنكم الاطلاع على التقويم الأكاديمي المحدث المتضمن مواعيد الإجازات الفصلية ونهاية العام.',

            tag: 'تقويم',

            tagColor: AppTheme.purple,

          ),

        ],

      ),

    );

  }



  Widget _buildNoticeCard({

    required String title,

    required String date,

    required String content,

    required String tag,

    required Color tagColor,

  }) {

    return Container(

      margin: const EdgeInsets.only(bottom: 14),

      padding: const EdgeInsets.all(18),

      decoration: BoxDecoration(

        color: Colors.white,

        borderRadius: BorderRadius.circular(18),

        border: Border.all(color: AppTheme.borderLight),

        boxShadow: AppTheme.softShadow,

      ),

      child: Column(

        crossAxisAlignment: CrossAxisAlignment.start,

        children: [

          Row(

            mainAxisAlignment: MainAxisAlignment.spaceBetween,

            children: [

              Container(

                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),

                decoration: BoxDecoration(

                  color: tagColor.withValues(alpha: 0.12),

                  borderRadius: BorderRadius.circular(8),

                ),

                child: Text(

                  tag,

                  style: TextStyle(

                    color: tagColor,

                    fontSize: 11,

                    fontWeight: FontWeight.bold,

                  ),

                ),

              ),

              Text(

                date,

                style: const TextStyle(fontSize: 11, color: AppTheme.textMuted),

              ),

            ],

          ),

          const SizedBox(height: 10),

          Text(

            title,

            style: const TextStyle(

              fontSize: 15,

              fontWeight: FontWeight.w800,

              color: AppTheme.textMain,

            ),

          ),

          const SizedBox(height: 6),

          Text(

            content,

            style: const TextStyle(

              fontSize: 12,

              color: AppTheme.textMuted,

              height: 1.5,

            ),

          ),

        ],

      ),

    );

  }

}




import 'package:flutter/material.dart';
import '../core/api_service.dart';
import '../screens/subjects_screen.dart';
import '../screens/homework_screen.dart';
import '../screens/chat_screen.dart';
import '../screens/settings_screen.dart';

/// Unified Modern Clean / Neumorphic-Light Bottom Navigation Bar
/// Used consistently across all student & portal screens.
class SchoolBottomBar extends StatelessWidget {
  final ApiService api;
  final int currentIndex; // 0: الرئيسية, 1: دراستي, 2: المهام, 3: التواصل, 4: حسابي, -1: none

  const SchoolBottomBar({
    super.key,
    required this.api,
    required this.currentIndex,
  });

  void _navigate(BuildContext context, int index) {
    if (index == currentIndex) return;

    if (index == 0) {
      Navigator.of(context).popUntil((route) => route.isFirst);
      return;
    }

    Widget target;
    switch (index) {
      case 1:
        target = SubjectsScreen(api: api);
        break;
      case 2:
        target = HomeworkScreen(api: api);
        break;
      case 3:
        target = ChatScreen(api: api);
        break;
      case 4:
        target = SettingsScreen(api: api);
        break;
      default:
        return;
    }

    if (currentIndex == 0) {
      Navigator.push(context, MaterialPageRoute(builder: (_) => target));
    } else {
      Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => target));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        border: const Border(top: BorderSide(color: Color(0xFFF1F5F9), width: 1.2)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 15,
            offset: const Offset(0, -4),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 66,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _buildNavItem(
                context: context,
                index: 0,
                icon: Icons.home_rounded,
                label: 'الرئيسية',
              ),
              _buildNavItem(
                context: context,
                index: 1,
                icon: Icons.menu_book_rounded,
                label: 'دراستي',
              ),
              _buildNavItem(
                context: context,
                index: 2,
                icon: Icons.assignment_rounded,
                label: 'المهام',
              ),
              _buildNavItem(
                context: context,
                index: 3,
                icon: Icons.chat_bubble_outline_rounded,
                label: 'التواصل',
              ),
              _buildNavItem(
                context: context,
                index: 4,
                icon: Icons.person_outline_rounded,
                label: 'حسابي',
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildNavItem({
    required BuildContext context,
    required int index,
    required IconData icon,
    required String label,
  }) {
    final isSelected = currentIndex == index;
    const activeColor = Color(0xFF1E60FF);
    const inactiveColor = Color(0xFF717579);

    return InkWell(
      onTap: () => _navigate(context, index),
      borderRadius: BorderRadius.circular(14),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
              decoration: BoxDecoration(
                color: isSelected ? const Color(0xFFEFF6FF) : Colors.transparent,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(
                icon,
                color: isSelected ? activeColor : inactiveColor,
                size: 22,
              ),
            ),
            const SizedBox(height: 3),
            Text(
              label,
              style: TextStyle(
                fontSize: 10.5,
                fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                color: isSelected ? activeColor : inactiveColor,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

import { StyleSheet, View } from "react-native";
import { Text } from "react-native-paper";
import { BookOpen, CalendarDays, ClipboardCheck, GraduationCap, Sparkles } from "lucide-react-native";

import { palette, radius, spacing } from "@/core/theme/tokens";
import { AppActionTile } from "@/shared/components/app-action-tile";
import { AppAvatar } from "@/shared/components/app-avatar";
import { AppCard } from "@/shared/components/app-card";
import { AppSectionHeader } from "@/shared/components/app-section-header";
import { previewLessons } from "@/features/design-preview/data";

type Props = { onAction: (label: string) => void };

export function StudentDashboardPreview({ onAction }: Props) {
  return (
    <View style={styles.content}>
      <View style={styles.hero}>
        <View style={styles.heroTop}>
          <View style={styles.heroText}>
            <Text style={styles.heroEyebrow}>أهلاً بك يا أحمد</Text>
            <Text style={styles.heroTitle}>نتمنى لك يوماً دراسياً ممتعاً</Text>
            <Text style={styles.heroMeta}>الصف السادس — الشعبة أ</Text>
          </View>
          <AppAvatar name="أحمد" size={58} backgroundColor={palette.successTint} color={palette.primary} />
        </View>
        <View style={styles.heroStats}>
          <HeroStat value="5" label="حصص اليوم" />
          <View style={styles.heroDivider} />
          <HeroStat value="2" label="واجبات معلقة" />
          <View style={styles.heroDivider} />
          <HeroStat value="96%" label="الحضور" />
        </View>
      </View>

      <AppSectionHeader title="ماذا تريد أن تفعل؟" subtitle="اختر الخدمة التي تحتاجها" />
      <View style={styles.actionsGrid}>
        <AppActionTile icon={CalendarDays} label="جدولي" onPress={() => onAction("الجدول الدراسي")} />
        <AppActionTile icon={BookOpen} label="واجباتي" color={palette.info} tint={palette.infoTint} onPress={() => onAction("الواجبات")} />
        <AppActionTile icon={GraduationCap} label="نتائجي" color={palette.success} tint={palette.successTint} onPress={() => onAction("النتائج والدرجات")} />
        <AppActionTile icon={ClipboardCheck} label="اختباراتي" onPress={() => onAction("الاختبارات")} />
      </View>

      <AppSectionHeader title="حصصي القادمة" trailing="اليوم" />
      <AppCard padding={4}>
        {previewLessons.map((lesson, index) => (
          <View key={lesson.id} style={[styles.lessonRow, index === previewLessons.length - 1 && styles.lastLesson]}>
            <View style={styles.lessonTime}><Text style={styles.lessonTimeText}>{lesson.time}</Text></View>
            <View style={styles.lessonInfo}>
              <Text style={styles.lessonSubject}>{lesson.subject}</Text>
              <Text style={styles.lessonMeta}>{lesson.teacher} · {lesson.room}</Text>
            </View>
            <BookOpen size={19} color={palette.secondary} />
          </View>
        ))}
      </AppCard>

      <AppCard padding={14}>
        <View style={styles.encouragement}>
          <View style={styles.encouragementIcon}><Sparkles color={palette.secondary} size={20} /></View>
          <View style={styles.encouragementText}>
            <Text style={styles.encouragementTitle}>خطوة صغيرة كل يوم تصنع فرقاً كبيراً</Text>
            <Text style={styles.encouragementDescription}>ابدأ بواجباتك، وراجع جدولك، واستعد لحصتك القادمة.</Text>
          </View>
        </View>
      </AppCard>
    </View>
  );
}

function HeroStat({ value, label }: { value: string; label: string }) {
  return <View style={styles.heroStat}><Text style={styles.heroStatValue}>{value}</Text><Text style={styles.heroStatLabel}>{label}</Text></View>;
}

const styles = StyleSheet.create({
  content: { gap: spacing.md },
  hero: { backgroundColor: palette.primary, padding: spacing.lg, borderRadius: radius.xl, gap: spacing.lg },
  heroTop: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  heroText: { flex: 1, alignItems: "flex-start", gap: 5 },
  heroEyebrow: { color: palette.onPrimarySoft, fontSize: 12, fontWeight: "700", textAlign: "right" },
  heroTitle: { color: palette.white, fontWeight: "800", fontSize: 17, lineHeight: 25, textAlign: "right" },
  heroMeta: { color: palette.onPrimaryText, fontSize: 11, textAlign: "right" },
  heroStats: { flexDirection: "row", alignItems: "center" },
  heroStat: { flex: 1, alignItems: "center", gap: 3 },
  heroStatValue: { color: palette.white, fontWeight: "800", fontSize: 19 },
  heroStatLabel: { color: palette.onPrimaryMuted, fontSize: 10, textAlign: "center" },
  heroDivider: { width: 1, height: 34, backgroundColor: palette.onPrimaryDivider },
  actionsGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  lessonRow: { minHeight: 67, flexDirection: "row", alignItems: "center", gap: spacing.md, paddingHorizontal: spacing.sm, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: palette.border },
  lastLesson: { borderBottomWidth: 0 },
  lessonTime: { backgroundColor: palette.primaryTint, paddingVertical: 7, paddingHorizontal: 9, borderRadius: 9 },
  lessonTimeText: { color: palette.info, fontWeight: "800", fontSize: 11 },
  lessonInfo: { flex: 1, alignItems: "flex-start", gap: 3 },
  lessonSubject: { color: palette.primary, fontSize: 13, fontWeight: "800", textAlign: "right" },
  lessonMeta: { color: palette.muted, fontSize: 10, textAlign: "right" },
  encouragement: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  encouragementIcon: { width: 42, height: 42, borderRadius: 14, backgroundColor: palette.secondaryTint, alignItems: "center", justifyContent: "center" },
  encouragementText: { flex: 1, alignItems: "flex-start", gap: 4 },
  encouragementTitle: { color: palette.primary, fontWeight: "800", fontSize: 12, textAlign: "right" },
  encouragementDescription: { color: palette.muted, fontSize: 11, lineHeight: 17, textAlign: "right" },
});

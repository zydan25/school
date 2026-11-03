import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import {
  Bell,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  ClipboardCheck,
  Clock3,
  GraduationCap,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react-native";
import { Avatar, Card, Text } from "react-native-paper";

import { AppIcon } from "@/shared/components/app-icon";
import { palette, radius, spacing } from "@/core/theme/tokens";

type Persona = "student" | "guardian" | "teacher";

const personas: { value: Persona; label: string }[] = [
  { value: "student", label: "الطالب" },
  { value: "guardian", label: "ولي الأمر" },
  { value: "teacher", label: "المعلم" },
];

export function DesignPreviewScreen() {
  const [persona, setPersona] = useState<Persona>("guardian");

  return (
    <ScrollView style={styles.page} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <View style={styles.brand}>
          <View style={styles.logo}>
            <AppIcon icon={GraduationCap} size={25} color={palette.white} />
          </View>
          <View>
            <Text style={styles.schoolName}>مدرستي</Text>
            <Text style={styles.schoolCaption}>منصة School التعليمية</Text>
          </View>
        </View>
        <Pressable style={styles.notificationButton} accessibilityLabel="الإشعارات">
          <AppIcon icon={Bell} color={palette.primary} />
          <View style={styles.notificationDot} />
        </Pressable>
      </View>

      <View style={styles.intro}>
        <Text style={styles.eyebrow}>معاينة نظام التصميم</Text>
        <Text variant="headlineSmall" style={styles.title}>واجهة واحدة، لكل أدوار المدرسة</Text>
        <Text style={styles.subtitle}>اختر الدور لمعاينة اتجاه البطاقات والصفحة الرئيسية.</Text>
      </View>

      <View style={styles.personaSelector}>
        {personas.map((item) => {
          const selected = persona === item.value;
          return (
            <Pressable
              key={item.value}
              onPress={() => setPersona(item.value)}
              style={[styles.personaButton, selected && styles.personaButtonActive]}
              accessibilityRole="button"
              accessibilityState={{ selected }}
            >
              <Text style={[styles.personaText, selected && styles.personaTextActive]}>
                {item.label}
              </Text>
            </Pressable>
          );
        })}
      </View>

      {persona === "guardian" ? <GuardianPreview /> : null}
      {persona === "teacher" ? <TeacherPreview /> : null}
      {persona === "student" ? <StudentPreview /> : null}

      <Text style={styles.footer}>بيانات وأسماء تجريبية للمعاينة فقط — ليست متصلة بالخادم بعد.</Text>
    </ScrollView>
  );
}

function GuardianPreview() {
  return (
    <>
      <View style={styles.welcomeRow}>
        <View style={styles.textBlock}>
          <Text style={styles.eyebrow}>مساحة ولي الأمر</Text>
          <Text style={styles.sectionTitle}>مرحباً بك 👋</Text>
          <Text style={styles.subtitle}>تابع أبناءك من مكان واحد</Text>
        </View>
        <Avatar.Text size={48} label="أب" style={styles.avatarParent} />
      </View>

      <SectionTitle title="أبنائي" trailing="3 طلاب" />
      <View style={styles.childrenGrid}>
        <ChildCard name="أحمد" grade="الصف السادس" tint="#E8F0FF" initials="أ" selected />
        <ChildCard name="محمد" grade="الصف الرابع" tint="#E6F5EE" initials="م" />
        <ChildCard name="عمر" grade="الصف الثاني" tint="#FFF1E2" initials="ع" />
      </View>

      <SectionTitle title="ملخص أحمد" trailing="الطالب المحدد" />
      <View style={styles.statsRow}>
        <StatCard icon={CheckCircle2} value="96%" label="الحضور" color={palette.success} />
        <StatCard icon={BookOpen} value="2" label="واجبات" color={palette.info} />
        <StatCard icon={Wallet} value="—" label="الرسوم" color={palette.secondary} />
      </View>

      <SectionTitle title="الوصول السريع" />
      <View style={styles.actionsGrid}>
        <ActionTile icon={CalendarDays} label="الجدول" />
        <ActionTile icon={ClipboardCheck} label="الحضور" />
        <ActionTile icon={GraduationCap} label="الدرجات" />
        <ActionTile icon={Wallet} label="كشف الحساب" />
      </View>
    </>
  );
}

function TeacherPreview() {
  return (
    <>
      <View style={styles.welcomeRow}>
        <View style={styles.textBlock}>
          <Text style={styles.eyebrow}>مساحة المعلم</Text>
          <Text style={styles.sectionTitle}>صباح الخير، أستاذ خالد</Text>
          <Text style={styles.subtitle}>هذه شعبك المسندة لهذا العام</Text>
        </View>
        <Avatar.Text size={48} label="خ" style={styles.avatarTeacher} />
      </View>

      <View style={styles.statsRow}>
        <StatCard icon={Users} value="42" label="الطلاب" color={palette.info} />
        <StatCard icon={BookOpen} value="3" label="الشعب" color={palette.secondary} />
        <StatCard icon={CalendarDays} value="5" label="حصص اليوم" color={palette.success} />
      </View>

      <SectionTitle title="شُعبي الدراسية" trailing="3 شعب" />
      <View style={styles.classList}>
        <ClassCard grade="الصف السادس" section="الشعبة أ" subject="الرياضيات" count="24 طالباً" tint="#E8F0FF" />
        <ClassCard grade="الصف الخامس" section="الشعبة ب" subject="الرياضيات" count="18 طالباً" tint="#E6F5EE" />
        <ClassCard grade="الصف الرابع" section="الشعبة أ" subject="العلوم" count="20 طالباً" tint="#FFF1E2" />
      </View>

      <SectionTitle title="إجراءات سريعة" />
      <View style={styles.actionsGrid}>
        <ActionTile icon={CheckCircle2} label="رصد الحضور" />
        <ActionTile icon={BookOpen} label="إضافة واجب" />
        <ActionTile icon={ClipboardCheck} label="الدرجات" />
        <ActionTile icon={CalendarDays} label="جدول الحصص" />
      </View>
    </>
  );
}

function StudentPreview() {
  return (
    <>
      <View style={styles.studentHero}>
        <View style={styles.heroTop}>
          <View style={styles.heroText}>
            <Text style={styles.heroEyebrow}>أهلاً بك يا أحمد</Text>
            <Text style={styles.heroName}>نتمنى لك يوماً دراسياً ممتعاً</Text>
            <Text style={styles.heroMeta}>الصف السادس — الشعبة أ</Text>
          </View>
          <Avatar.Text size={58} label="أ" style={styles.avatarStudent} />
        </View>
        <View style={styles.heroStats}>
          <HeroStat value="5" label="حصص اليوم" />
          <View style={styles.heroDivider} />
          <HeroStat value="2" label="واجبات معلقة" />
          <View style={styles.heroDivider} />
          <HeroStat value="96%" label="الحضور" />
        </View>
      </View>

      <SectionTitle title="ماذا تريد أن تفعل؟" />
      <View style={styles.actionsGrid}>
        <ActionTile icon={CalendarDays} label="جدولي" />
        <ActionTile icon={BookOpen} label="واجباتي" />
        <ActionTile icon={GraduationCap} label="نتائجي" />
        <ActionTile icon={ClipboardCheck} label="اختباراتي" />
      </View>

      <SectionTitle title="حصصي القادمة" trailing="اليوم" />
      <View style={styles.lessonList}>
        <LessonRow time="08:00" subject="الرياضيات" teacher="أ. خالد" />
        <LessonRow time="09:00" subject="اللغة العربية" teacher="أ. أحمد" />
        <LessonRow time="10:00" subject="العلوم" teacher="أ. سامي" />
      </View>
    </>
  );
}

function SectionTitle({ title, trailing }: { title: string; trailing?: string }) {
  return (
    <View style={styles.sectionHeading}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {trailing ? <Text style={styles.trailing}>{trailing}</Text> : null}
    </View>
  );
}

function ChildCard({
  name, grade, tint, initials, selected = false,
}: {
  name: string; grade: string; tint: string; initials: string; selected?: boolean;
}) {
  return (
    <Pressable style={[styles.childCard, selected && styles.childCardSelected]}>
      <Avatar.Text size={46} label={initials} style={{ backgroundColor: tint }} color={palette.primary} />
      <Text style={styles.childName}>{name}</Text>
      <Text style={styles.childGrade}>{grade}</Text>
      {selected ? <Text style={styles.selectedLabel}>محدد</Text> : null}
    </Pressable>
  );
}

function StatCard({
  icon, value, label, color,
}: {
  icon: LucideIcon; value: string; label: string; color: string;
}) {
  return (
    <View style={styles.statCard}>
      <AppIcon icon={icon} size={20} color={color} />
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

function ActionTile({ icon, label }: { icon: LucideIcon; label: string }) {
  return (
    <Pressable style={styles.actionTile}>
      <AppIcon icon={icon} size={23} color={palette.secondary} />
      <Text style={styles.actionLabel}>{label}</Text>
    </Pressable>
  );
}

function ClassCard({
  grade, section, subject, count, tint,
}: {
  grade: string; section: string; subject: string; count: string; tint: string;
}) {
  return (
    <Card mode="contained" style={styles.classCard}>
      <Card.Content style={styles.classContent}>
        <Avatar.Text size={42} label={section.slice(-1)} style={{ backgroundColor: tint }} color={palette.primary} />
        <View style={styles.classInfo}>
          <Text style={styles.classGrade}>{grade} — {section}</Text>
          <Text style={styles.classSubject}>{subject}</Text>
          <Text style={styles.classCount}>{count}</Text>
        </View>
        <AppIcon icon={Clock3} size={18} color={palette.muted} />
      </Card.Content>
    </Card>
  );
}

function HeroStat({ value, label }: { value: string; label: string }) {
  return (
    <View style={styles.heroStat}>
      <Text style={styles.heroStatValue}>{value}</Text>
      <Text style={styles.heroStatLabel}>{label}</Text>
    </View>
  );
}

function LessonRow({ time, subject, teacher }: { time: string; subject: string; teacher: string }) {
  return (
    <View style={styles.lessonRow}>
      <View style={styles.lessonTime}>
        <Text style={styles.lessonTimeText}>{time}</Text>
      </View>
      <View style={styles.lessonInfo}>
        <Text style={styles.lessonSubject}>{subject}</Text>
        <Text style={styles.lessonTeacher}>{teacher}</Text>
      </View>
      <AppIcon icon={BookOpen} color={palette.secondary} size={19} />
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: palette.background },
  content: { paddingHorizontal: spacing.lg, paddingTop: spacing.xl, paddingBottom: 44, gap: spacing.lg, direction: "rtl" },
  header: { flexDirection: "row-reverse", alignItems: "center", justifyContent: "space-between" },
  brand: { flexDirection: "row-reverse", alignItems: "center", gap: spacing.sm },
  logo: { width: 46, height: 46, borderRadius: 14, backgroundColor: palette.primary, alignItems: "center", justifyContent: "center" },
  schoolName: { color: palette.primary, fontWeight: "800", fontSize: 17, textAlign: "right" },
  schoolCaption: { color: palette.muted, fontSize: 11, textAlign: "right" },
  notificationButton: { height: 42, width: 42, borderRadius: 14, backgroundColor: palette.surface, alignItems: "center", justifyContent: "center", borderColor: palette.border, borderWidth: 1 },
  notificationDot: { position: "absolute", top: 9, right: 10, width: 7, height: 7, borderRadius: 4, backgroundColor: palette.secondary },
  intro: { gap: 5 },
  eyebrow: { color: palette.secondary, fontWeight: "700", fontSize: 12, textAlign: "right" },
  title: { color: palette.primary, fontWeight: "800", textAlign: "right", marginTop: 3 },
  subtitle: { color: palette.muted, textAlign: "right", fontSize: 13, lineHeight: 20 },
  personaSelector: { flexDirection: "row-reverse", gap: 8, backgroundColor: "#E8EDF3", borderRadius: radius.md, padding: 4 },
  personaButton: { flex: 1, minHeight: 42, borderRadius: 11, justifyContent: "center", alignItems: "center" },
  personaButtonActive: { backgroundColor: palette.surface },
  personaText: { color: palette.muted, fontWeight: "600" },
  personaTextActive: { color: palette.primary, fontWeight: "800" },
  welcomeRow: { flexDirection: "row-reverse", justifyContent: "space-between", alignItems: "center" },
  textBlock: { flex: 1, alignItems: "flex-start", gap: 3 },
  sectionTitle: { color: palette.primary, fontSize: 16, fontWeight: "800", textAlign: "right" },
  avatarParent: { backgroundColor: "#E8F0FF" },
  avatarTeacher: { backgroundColor: "#E6F5EE" },
  avatarStudent: { backgroundColor: "#E6F5EE" },
  sectionHeading: { flexDirection: "row-reverse", alignItems: "center", justifyContent: "space-between", marginTop: 2 },
  trailing: { color: palette.muted, fontSize: 12 },
  childrenGrid: { flexDirection: "row-reverse", gap: spacing.sm },
  childCard: { flex: 1, alignItems: "center", gap: 6, paddingVertical: 13, paddingHorizontal: 3, backgroundColor: palette.surface, borderRadius: radius.md, borderWidth: 1, borderColor: palette.border },
  childCardSelected: { borderColor: palette.secondary, borderWidth: 1.5 },
  childName: { color: palette.primary, fontWeight: "800", fontSize: 13 },
  childGrade: { color: palette.muted, fontSize: 10 },
  selectedLabel: { color: palette.secondary, fontSize: 10, fontWeight: "800" },
  statsRow: { flexDirection: "row-reverse", gap: spacing.sm },
  statCard: { flex: 1, alignItems: "center", gap: 5, paddingVertical: 13, backgroundColor: palette.surface, borderRadius: radius.md, borderWidth: 1, borderColor: palette.border },
  statValue: { color: palette.primary, fontSize: 19, fontWeight: "800" },
  statLabel: { color: palette.muted, fontSize: 11 },
  actionsGrid: { flexDirection: "row-reverse", flexWrap: "wrap", gap: spacing.sm },
  actionTile: { width: "48%", minHeight: 86, backgroundColor: palette.surface, borderRadius: radius.md, borderWidth: 1, borderColor: palette.border, alignItems: "center", justifyContent: "center", gap: 8 },
  actionLabel: { color: palette.primary, fontSize: 12, fontWeight: "700" },
  classList: { gap: spacing.sm },
  classCard: { backgroundColor: palette.surface, borderRadius: radius.md, borderColor: palette.border, borderWidth: 1 },
  classContent: { flexDirection: "row-reverse", alignItems: "center", gap: spacing.md },
  classInfo: { flex: 1, alignItems: "flex-start" },
  classGrade: { color: palette.primary, fontSize: 14, fontWeight: "800", textAlign: "right" },
  classSubject: { color: palette.secondary, fontSize: 12, marginTop: 2 },
  classCount: { color: palette.muted, fontSize: 11, marginTop: 3 },
  studentHero: { backgroundColor: palette.primary, padding: 18, borderRadius: radius.xl, gap: 18 },
  heroTop: { flexDirection: "row-reverse", alignItems: "center", gap: 12 },
  heroText: { flex: 1, alignItems: "flex-start", gap: 4 },
  heroEyebrow: { color: "#C7D7EA", fontSize: 12, fontWeight: "700" },
  heroName: { color: palette.white, fontWeight: "800", fontSize: 17, textAlign: "right" },
  heroMeta: { color: "#DAE5F2", fontSize: 12 },
  heroStats: { flexDirection: "row-reverse", alignItems: "center" },
  heroStat: { flex: 1, alignItems: "center", gap: 3 },
  heroStatValue: { color: palette.white, fontWeight: "800", fontSize: 20 },
  heroStatLabel: { color: "#D7E2EF", fontSize: 10 },
  heroDivider: { width: 1, height: 34, backgroundColor: "#506986" },
  lessonList: { backgroundColor: palette.surface, borderRadius: radius.lg, paddingHorizontal: 14, borderWidth: 1, borderColor: palette.border },
  lessonRow: { minHeight: 68, flexDirection: "row-reverse", alignItems: "center", gap: 12, borderBottomColor: palette.border, borderBottomWidth: StyleSheet.hairlineWidth },
  lessonTime: { backgroundColor: "#E8F0FF", paddingVertical: 7, paddingHorizontal: 9, borderRadius: 9 },
  lessonTimeText: { color: palette.info, fontWeight: "800", fontSize: 12 },
  lessonInfo: { flex: 1, alignItems: "flex-start" },
  lessonSubject: { color: palette.primary, fontSize: 13, fontWeight: "800" },
  lessonTeacher: { color: palette.muted, fontSize: 11, marginTop: 3 },
  footer: { color: palette.muted, textAlign: "center", fontSize: 11, marginTop: 4 },
});

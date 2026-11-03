import { useMemo } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Text } from "react-native-paper";
import { BookOpen, CalendarDays, CheckCircle2, ClipboardCheck, Users } from "lucide-react-native";

import { palette, radius, spacing } from "@/core/theme/tokens";
import { AppActionTile } from "@/shared/components/app-action-tile";
import { AppAvatar } from "@/shared/components/app-avatar";
import { AppCard } from "@/shared/components/app-card";
import { AppEmptyState } from "@/shared/components/app-empty-state";
import { AppSectionHeader } from "@/shared/components/app-section-header";
import { AppStatCard } from "@/shared/components/app-stat-card";
import { previewClasses } from "@/features/design-preview/data";

type Props = { selectedClassId: string; onSelectClass: (classId: string) => void; empty: boolean; onAction: (label: string) => void };

export function TeacherDashboardPreview({ selectedClassId, onSelectClass, empty, onAction }: Props) {
  const selectedClass = useMemo(
    () => previewClasses.find((item) => item.id === selectedClassId) ?? previewClasses[0],
    [selectedClassId],
  );
  const totalStudents = previewClasses.reduce((sum, item) => sum + item.studentCount, 0);

  return (
    <View style={styles.content}>
      <View style={styles.welcomeRow}>
        <View style={styles.welcomeText}>
          <Text style={styles.eyebrow}>مساحة المعلم</Text>
          <Text style={styles.title}>صباح الخير، أستاذ خالد</Text>
          <Text style={styles.subtitle}>تابع حصصك وشعبك المسندة لهذا العام</Text>
        </View>
        <AppAvatar name="خالد" size={52} backgroundColor={palette.successTint} color={palette.success} />
      </View>

      <View style={styles.statsRow}>
        <AppStatCard icon={Users} value={String(totalStudents)} label="الطلاب" color={palette.info} tint={palette.infoTint} />
        <AppStatCard icon={BookOpen} value={String(previewClasses.length)} label="الشعب" />
        <AppStatCard icon={CalendarDays} value="5" label="حصص اليوم" color={palette.success} tint={palette.successTint} />
      </View>

      <AppSectionHeader title="شُعبي الدراسية" trailing={empty ? "لا توجد إسنادات" : previewClasses.length + " شعب"} />
      {empty ? (
        <AppEmptyState
          icon={BookOpen}
          title="لم يتم إسناد شعب إليك بعد"
          description="ستظهر هنا الشعب والمواد التي تعتمدها إدارة المدرسة لك. لن نعرض طلاباً من شعب غير مسندة إليك."
          actionLabel="معاينة رسالة الإسناد"
          onAction={() => onAction("لا توجد إسنادات نشطة لهذا المعلم")}
        />
      ) : (
        <>
          <View style={styles.classList}>
            {previewClasses.map((item) => {
              const selected = item.id === selectedClass.id;
              return (
                <Pressable key={item.id} onPress={() => onSelectClass(item.id)}
                  accessibilityRole="button" accessibilityState={{ selected }}
                  accessibilityLabel={item.grade + " " + item.section + " " + item.subject}
                  style={({ pressed }) => pressed && styles.pressed}>
                  <AppCard padding={13} style={selected ? styles.selectedClass : undefined}>
                    <View style={styles.classRow}>
                      <View style={[styles.classMark, { backgroundColor: item.tint }]}>
                        <Text style={styles.classInitial}>{item.section.slice(-1)}</Text>
                      </View>
                      <View style={styles.classInfo}>
                        <Text style={styles.classTitle}>{item.grade} — {item.section}</Text>
                        <Text style={styles.classSubject}>{item.subject}</Text>
                        <Text style={styles.classCount}>{item.studentCount} طالباً</Text>
                      </View>
                      <View style={styles.classState}>
                        <Text style={[styles.classStateText, selected && styles.classStateSelected]}>{selected ? "محددة" : "عرض الشعبة"}</Text>
                      </View>
                    </View>
                  </AppCard>
                </Pressable>
              );
            })}
          </View>

          <AppSectionHeader title={"طلاب " + selectedClass.section} trailing={selectedClass.grade} />
          <AppCard padding={13}>
            <View style={styles.studentGrid}>
              {selectedClass.students.map((student) => (
                <View key={student.id} style={styles.studentTile}>
                  <AppAvatar name={student.name} size={43} backgroundColor={student.tint} />
                  <Text style={styles.studentName}>{student.name}</Text>
                </View>
              ))}
            </View>
            <View style={styles.studentsFooter}>
              <Text style={styles.studentsFooterText}>عينة من {selectedClass.studentCount} طالباً في الشعبة</Text>
              <Text style={styles.studentsFooterText}>بيانات تجريبية</Text>
            </View>
          </AppCard>

          <AppSectionHeader title="إجراءات سريعة" />
          <View style={styles.actionsGrid}>
            <AppActionTile icon={CheckCircle2} label="رصد الحضور" color={palette.success} tint={palette.successTint} onPress={() => onAction("رصد حضور " + selectedClass.section)} />
            <AppActionTile icon={BookOpen} label="إضافة واجب" onPress={() => onAction("إضافة واجب إلى " + selectedClass.section)} />
            <AppActionTile icon={ClipboardCheck} label="إدخال الدرجات" color={palette.info} tint={palette.infoTint} onPress={() => onAction("دفتر درجات " + selectedClass.section)} />
            <AppActionTile icon={CalendarDays} label="جدول الحصص" onPress={() => onAction("جدول " + selectedClass.section)} />
          </View>
        </>
      )}

      <AppCard padding={13}>
        <View style={styles.tipRow}>
          <CheckCircle2 size={19} color={palette.success} />
          <Text style={styles.tipText}>مصدر شعب المعلم وطلابها هو الإسناد الأكاديمي المعتمد في المدرسة.</Text>
        </View>
      </AppCard>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { gap: spacing.md },
  welcomeRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.md, paddingVertical: spacing.xs },
  welcomeText: { flex: 1, alignItems: "flex-start", gap: 4 },
  eyebrow: { color: palette.secondary, fontSize: 11, fontWeight: "800", textAlign: "right" },
  title: { color: palette.primary, fontSize: 19, fontWeight: "800", textAlign: "right" },
  subtitle: { color: palette.muted, fontSize: 12, lineHeight: 19, textAlign: "right" },
  statsRow: { flexDirection: "row", gap: spacing.sm },
  classList: { gap: spacing.sm },
  selectedClass: { borderColor: palette.secondary, borderWidth: 1.5, backgroundColor: palette.surfaceSoft },
  classRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  classMark: { width: 44, height: 44, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  classInitial: { color: palette.primary, fontWeight: "800", fontSize: 17 },
  classInfo: { flex: 1, alignItems: "flex-start", gap: 2 },
  classTitle: { color: palette.primary, fontWeight: "800", fontSize: 13, textAlign: "right" },
  classSubject: { color: palette.secondary, fontSize: 12 },
  classCount: { color: palette.muted, fontSize: 11 },
  classState: { paddingHorizontal: 8, paddingVertical: 5, borderRadius: radius.pill, backgroundColor: "#F1F5F9" },
  classStateText: { color: palette.muted, fontSize: 9, fontWeight: "700" },
  classStateSelected: { color: palette.success },
  studentGrid: { flexDirection: "row", flexWrap: "wrap", justifyContent: "flex-start", gap: spacing.md },
  studentTile: { width: "21%", minWidth: 58, alignItems: "center", gap: 5 },
  studentName: { color: palette.primary, fontSize: 11, fontWeight: "700" },
  studentsFooter: { marginTop: spacing.md, paddingTop: spacing.sm, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: palette.border, flexDirection: "row", justifyContent: "space-between", gap: spacing.sm },
  studentsFooterText: { color: palette.muted, fontSize: 10 },
  actionsGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  tipRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  tipText: { flex: 1, color: palette.muted, fontSize: 11, lineHeight: 18, textAlign: "right" },
  pressed: { opacity: 0.76 },
});

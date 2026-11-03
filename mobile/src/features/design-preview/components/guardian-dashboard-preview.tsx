import { useMemo } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Text } from "react-native-paper";
import { CalendarDays, CheckCircle2, ClipboardCheck, GraduationCap, Plus, Wallet } from "lucide-react-native";

import { palette, radius, spacing } from "@/core/theme/tokens";
import { AppActionTile } from "@/shared/components/app-action-tile";
import { AppAvatar } from "@/shared/components/app-avatar";
import { AppCard } from "@/shared/components/app-card";
import { AppEmptyState } from "@/shared/components/app-empty-state";
import { AppSectionHeader } from "@/shared/components/app-section-header";
import { AppStatCard } from "@/shared/components/app-stat-card";
import { previewChildren } from "@/features/design-preview/data";

type Props = {
  selectedChildId: string;
  onSelectChild: (childId: string) => void;
  empty: boolean;
  onAddChild: () => void;
  onAction: (label: string) => void;
};

export function GuardianDashboardPreview({ selectedChildId, onSelectChild, empty, onAddChild, onAction }: Props) {
  const selectedChild = useMemo(
    () => previewChildren.find((child) => child.id === selectedChildId) ?? previewChildren[0],
    [selectedChildId],
  );

  return (
    <View style={styles.content}>
      <View style={styles.welcomeRow}>
        <View style={styles.welcomeText}>
          <Text style={styles.eyebrow}>مساحة ولي الأمر</Text>
          <Text style={styles.title}>مرحباً بك 👋</Text>
          <Text style={styles.subtitle}>تابع أبناءك واطمئن على يومهم الدراسي</Text>
        </View>
        <AppAvatar name="ولي الأمر" size={52} backgroundColor={palette.primaryTint} />
      </View>

      <AppSectionHeader title="أبنائي" trailing={empty ? "لا توجد ملفات" : previewChildren.length + " طلاب"} />
      {empty ? (
        <AppEmptyState
          icon={GraduationCap}
          title="لم يتم ربط أبناء بحسابك بعد"
          description="بعد اعتماد المدرسة لارتباط ملفات الأبناء بحسابك ستظهر أسماؤهم هنا، وستتمكن من متابعة بيانات كل واحد منهم."
          actionLabel="معاينة طلب إضافة ابن"
          onAction={onAddChild}
        />
      ) : (
        <>
          <View style={styles.childrenGrid}>
            {previewChildren.map((child) => {
              const selected = selectedChild.id === child.id;
              return (
                <Pressable key={child.id} onPress={() => onSelectChild(child.id)}
                  accessibilityRole="button" accessibilityState={{ selected }}
                  accessibilityLabel={"اختيار " + child.name}
                  style={({ pressed }) => [styles.childCard, selected && styles.childCardSelected, pressed && styles.pressed]}>
                  <AppAvatar name={child.name} size={48} backgroundColor={child.tint} color={palette.primary} />
                  <Text style={styles.childName}>{child.name}</Text>
                  <Text style={styles.childGrade}>{child.grade}</Text>
                  <Text style={[styles.childSelected, !selected && styles.childNotSelected]}>
                    {selected ? "الطالب المحدد" : child.section}
                  </Text>
                </Pressable>
              );
            })}
            <Pressable onPress={onAddChild} accessibilityRole="button" accessibilityLabel="معاينة إضافة أو ربط ابن"
              style={({ pressed }) => [styles.addChildCard, pressed && styles.pressed]}>
              <View style={styles.addIcon}><Plus size={22} color={palette.secondary} /></View>
              <Text style={styles.addChildText}>إضافة ابن</Text>
              <Text style={styles.childGrade}>بعد اعتماد الربط</Text>
            </Pressable>
          </View>

          <AppSectionHeader title={"ملخص " + selectedChild.name} trailing={selectedChild.grade + " · " + selectedChild.section} />
          <View style={styles.statsRow}>
            <AppStatCard icon={CheckCircle2} value={selectedChild.attendance} label="الحضور" color={palette.success} tint={palette.successTint} />
            <AppStatCard icon={ClipboardCheck} value={selectedChild.homeworkCount} label="واجبات معلقة" color={palette.info} tint={palette.infoTint} />
            <AppStatCard icon={Wallet} value={selectedChild.feesLabel} label="الرسوم" color={palette.secondary} tint="#E8F5F2" />
          </View>

          <AppSectionHeader title="الوصول السريع" />
          <View style={styles.actionsGrid}>
            <AppActionTile icon={CalendarDays} label="الجدول" onPress={() => onAction("جدول " + selectedChild.name)} />
            <AppActionTile icon={ClipboardCheck} label="الحضور" tint={palette.successTint} color={palette.success} onPress={() => onAction("حضور " + selectedChild.name)} />
            <AppActionTile icon={GraduationCap} label="الدرجات" tint={palette.infoTint} color={palette.info} onPress={() => onAction("درجات " + selectedChild.name)} />
            <AppActionTile icon={Wallet} label="كشف الحساب" onPress={() => onAction("كشف حساب " + selectedChild.name)} />
          </View>
        </>
      )}

      <AppCard padding={13}>
        <View style={styles.tipRow}>
          <CheckCircle2 size={19} color={palette.success} />
          <Text style={styles.tipText}>لا تظهر بيانات أي ابن إلا بعد ربطه بحساب ولي الأمر والتحقق من العلاقة لدى الخادم.</Text>
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
  title: { color: palette.primary, fontSize: 20, fontWeight: "800", textAlign: "right" },
  subtitle: { color: palette.muted, fontSize: 12, lineHeight: 19, textAlign: "right" },
  childrenGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  childCard: { width: "30%", minWidth: 88, flexGrow: 1, alignItems: "center", gap: 5, paddingVertical: 12, paddingHorizontal: 4, backgroundColor: palette.surface, borderRadius: radius.md, borderWidth: 1, borderColor: palette.border },
  childCardSelected: { borderColor: palette.secondary, borderWidth: 1.5, backgroundColor: palette.surfaceSoft },
  childName: { color: palette.primary, fontSize: 13, fontWeight: "800" },
  childGrade: { color: palette.muted, fontSize: 10, textAlign: "center" },
  childSelected: { color: palette.secondary, fontSize: 9, fontWeight: "800", textAlign: "center" },
  childNotSelected: { color: palette.muted, fontWeight: "500" },
  addChildCard: { width: "30%", minWidth: 88, flexGrow: 1, alignItems: "center", justifyContent: "center", gap: 5, paddingVertical: 12, paddingHorizontal: 4, backgroundColor: palette.secondarySurface, borderRadius: radius.md, borderWidth: 1, borderColor: palette.secondaryBorder, borderStyle: "dashed" },
  addIcon: { width: 48, height: 48, borderRadius: 24, backgroundColor: palette.secondaryTint, alignItems: "center", justifyContent: "center" },
  addChildText: { color: palette.primary, fontSize: 12, fontWeight: "800" },
  statsRow: { flexDirection: "row", gap: spacing.sm },
  actionsGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  tipRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  tipText: { flex: 1, color: palette.muted, fontSize: 11, lineHeight: 18, textAlign: "right" },
  pressed: { opacity: 0.75 },
});

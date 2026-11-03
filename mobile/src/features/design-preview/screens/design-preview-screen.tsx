import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Text } from "react-native-paper";
import { Eye, EyeOff, Info } from "lucide-react-native";

import { palette, radius, spacing } from "@/core/theme/tokens";
import { AppIcon } from "@/shared/components/app-icon";
import { AppNotice } from "@/shared/components/app-notice";
import { DashboardHeader } from "@/features/design-preview/components/dashboard-header";
import { GuardianDashboardPreview } from "@/features/design-preview/components/guardian-dashboard-preview";
import { PersonaSwitcher, type PreviewPersona } from "@/features/design-preview/components/persona-switcher";
import { StudentDashboardPreview } from "@/features/design-preview/components/student-dashboard-preview";
import { TeacherDashboardPreview } from "@/features/design-preview/components/teacher-dashboard-preview";

export function DesignPreviewScreen() {
  const [persona, setPersona] = useState<PreviewPersona>("guardian");
  const [selectedChildId, setSelectedChildId] = useState("child-ahmed");
  const [selectedClassId, setSelectedClassId] = useState("class-grade-six-a");
  const [showEmptyState, setShowEmptyState] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  function handleAction(label: string) {
    setNotice("معاينة فقط: " + label + ". ستفتح الشاشة الفعلية بعد ربط وحدتها بعقد API المعتمد.");
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={["top", "left", "right"]}>
      <ScrollView style={styles.page} contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <DashboardHeader
          userName={persona === "teacher" ? "خالد" : persona === "student" ? "أحمد" : "ولي الأمر"}
          onNotificationsPress={() => handleAction("الإشعارات")}
        />

        <View style={styles.intro}>
          <Text style={styles.eyebrow}>معاينة تفاعلية لنظام التصميم</Text>
          <Text style={styles.title}>واجهة واحدة، لكل أدوار المدرسة</Text>
          <Text style={styles.subtitle}>اختر مساحة العمل لمراجعة شكل الصفحة والبطاقات وطريقة عرض المعلومات.</Text>
        </View>

        <PersonaSwitcher
          value={persona}
          onChange={(nextPersona) => {
            setPersona(nextPersona);
            setNotice(null);
            setShowEmptyState(false);
          }}
        />

        {persona !== "student" ? (
          <Pressable
            onPress={() => {
              setShowEmptyState((current) => !current);
              setNotice(null);
            }}
            accessibilityRole="switch"
            accessibilityState={{ checked: showEmptyState }}
            style={({ pressed }) => [styles.emptyToggle, pressed && styles.pressed]}
          >
            <View style={styles.emptyToggleIcon}>
              <AppIcon icon={showEmptyState ? EyeOff : Eye} size={17} color={showEmptyState ? palette.warning : palette.secondary} />
            </View>
            <View style={styles.emptyToggleText}>
              <Text style={styles.emptyToggleTitle}>معاينة حالة عدم وجود ملفات</Text>
              <Text style={styles.emptyToggleSubtitle}>
                {showEmptyState ? "وضع البيانات الفارغة مفعل" : "اعرض كيف تبدو الشاشة قبل ربط الأبناء أو الشعب"}
              </Text>
            </View>
            <View style={[styles.switchTrack, showEmptyState && styles.switchTrackActive]}>
              <View style={styles.switchThumb} />
            </View>
          </Pressable>
        ) : null}

        {notice ? <AppNotice message={notice} onDismiss={() => setNotice(null)} /> : null}

        {persona === "guardian" ? (
          <GuardianDashboardPreview
            selectedChildId={selectedChildId}
            onSelectChild={(childId) => {
              setSelectedChildId(childId);
              setNotice(null);
            }}
            empty={showEmptyState}
            onAddChild={() => handleAction("طلب ربط ابن بحساب ولي الأمر")}
            onAction={handleAction}
          />
        ) : null}

        {persona === "teacher" ? (
          <TeacherDashboardPreview
            selectedClassId={selectedClassId}
            onSelectClass={(classId) => {
              setSelectedClassId(classId);
              setNotice(null);
            }}
            empty={showEmptyState}
            onAction={handleAction}
          />
        ) : null}

        {persona === "student" ? <StudentDashboardPreview onAction={handleAction} /> : null}

        <View style={styles.previewFooter}>
          <Info size={15} color={palette.muted} />
          <Text style={styles.footerText}>هذه معاينة تصميم ببيانات افتراضية؛ لا تقرأ أو تعدل بيانات المدرسة الفعلية.</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: palette.background, direction: "rtl" },
  page: { flex: 1, backgroundColor: palette.background },
  content: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, paddingBottom: 44, gap: spacing.lg, direction: "rtl" },
  intro: { gap: 5, alignItems: "flex-start" },
  eyebrow: { color: palette.secondary, fontSize: 11, fontWeight: "800", textAlign: "right" },
  title: { color: palette.primary, fontWeight: "800", fontSize: 22, textAlign: "right" },
  subtitle: { color: palette.muted, fontSize: 12, lineHeight: 20, textAlign: "right" },
  emptyToggle: { flexDirection: "row", alignItems: "center", gap: spacing.sm, backgroundColor: palette.surface, borderWidth: 1, borderColor: palette.border, borderRadius: radius.md, padding: spacing.sm },
  emptyToggleIcon: { width: 34, height: 34, borderRadius: 11, backgroundColor: palette.neutralTint, alignItems: "center", justifyContent: "center" },
  emptyToggleText: { flex: 1, alignItems: "flex-start", gap: 2 },
  emptyToggleTitle: { color: palette.primary, fontSize: 12, fontWeight: "800", textAlign: "right" },
  emptyToggleSubtitle: { color: palette.muted, fontSize: 10, textAlign: "right" },
  switchTrack: { width: 42, height: 24, borderRadius: 12, backgroundColor: palette.neutralTrack, padding: 3, justifyContent: "center", alignItems: "flex-start" },
  switchTrackActive: { backgroundColor: palette.secondary, alignItems: "flex-end" },
  switchThumb: { width: 18, height: 18, borderRadius: 9, backgroundColor: palette.white },
  previewFooter: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.xs, paddingTop: spacing.xs },
  footerText: { flexShrink: 1, color: palette.muted, fontSize: 10, textAlign: "center", lineHeight: 16 },
  pressed: { opacity: 0.75 },
});

import { useEffect, useState } from "react";
import { router } from "expo-router";
import { StyleSheet, View } from "react-native";
import { ActivityIndicator, Button, Text } from "react-native-paper";
import { Building2, LogOut, School } from "lucide-react-native";

import { useAuthStore } from "@/core/auth/auth-store";
import { AppAvatar } from "@/shared/components/app-avatar";
import { AppCard } from "@/shared/components/app-card";
import { AppEmptyState } from "@/shared/components/app-empty-state";
import { AppScreen } from "@/shared/components/app-screen";
import { AppSectionHeader } from "@/shared/components/app-section-header";
import { AppIcon } from "@/shared/components/app-icon";
import { palette, spacing } from "@/core/theme/tokens";

const roleLabels: Record<string, string> = {
  student: "طالب",
  guardian: "ولي أمر",
  teacher: "معلم",
  admin: "إدارة",
  "school-admin": "إدارة المدرسة",
  school_admin: "إدارة المدرسة",
  "school-director": "مدير المدرسة",
  school_director: "مدير المدرسة",
  principal: "مدير المدرسة",
  "school-principal": "مدير المدرسة",
  "academic-coordinator": "منسق أكاديمي",
  academic_coordinator: "منسق أكاديمي",
  "academic-head": "رئيس الشؤون الأكاديمية",
  academic_head: "رئيس الشؤون الأكاديمية",
  "exam-controller": "مسؤول الاختبارات",
  exam_controller: "مسؤول الاختبارات",
  "student-affairs": "شؤون الطلاب",
  student_affairs: "شؤون الطلاب",
  accountant: "محاسب",
  "school-accountant": "محاسب المدرسة",
  school_accountant: "محاسب المدرسة",
  hr: "الموارد البشرية",
  "hr-manager": "مدير الموارد البشرية",
  hr_manager: "مدير الموارد البشرية",
  "hr-specialist": "أخصائي موارد بشرية",
  hr_specialist: "أخصائي موارد بشرية",
  librarian: "أمين المكتبة",
  "store-keeper": "أمين المخزن",
  store_keeper: "أمين المخزن",
  "inventory-manager": "مسؤول المخزون",
  inventory_manager: "مسؤول المخزون",
  "gate-security": "أمن المدرسة",
  gate_security: "أمن المدرسة",
  "school-gate-guard": "حارس بوابة المدرسة",
};

export function SchoolSelectionScreen() {
  const session = useAuthStore((state) => state.session);
  const hasHydrated = useAuthStore((state) => state.hasHydrated);
  const chooseSchool = useAuthStore((state) => state.chooseSchool);
  const logout = useAuthStore((state) => state.logout);
  const [selectionError, setSelectionError] = useState("");

  useEffect(() => {
    if (hasHydrated && !session) router.replace("/login" as never);
  }, [hasHydrated, session]);

  async function selectSchool(id: string) {
    setSelectionError("");
    try {
      await chooseSchool(id);
      router.replace("/workspace" as never);
    } catch (error) {
      setSelectionError(error instanceof Error ? error.message : "تعذر اختيار المدرسة.");
    }
  }

  if (!session) return <AppScreen compact><ActivityIndicator /></AppScreen>;

  return (
    <AppScreen>
      <View style={styles.header}>
        <View style={styles.icon}><AppIcon icon={Building2} color={palette.white} size={25} /></View>
        <Text style={styles.title}>اختر المدرسة</Text>
        <Text style={styles.subtitle}>هذا الحساب مرتبط بالمدارس التالية. اختر المدرسة التي تريد العمل فيها.</Text>
      </View>

      {selectionError ? <Text style={styles.selectionError}>{selectionError}</Text> : null}
      {session.schools.length ? (
        <>
          <AppSectionHeader title="مدارسي" trailing={session.schools.length + " مدارس"} />
          {session.schools.map((school) => (
            <AppCard key={school.id} padding={14}>
              <View style={styles.schoolRow}>
                <AppAvatar name={school.name} size={48} backgroundColor={palette.primaryTint} />
                <View style={styles.schoolInfo}>
                  <Text style={styles.schoolName}>{school.name}</Text>
                  <Text style={styles.schoolCode}>{school.code ? "كود المدرسة: " + school.code : "مدرسة متاحة لحسابك"}</Text>
                  <Text style={styles.roles}>
                    {school.roles.length
                      ? school.roles.map((role) => roleLabels[role] ?? role).join(" · ")
                      : "سيتم تحميل ملفاتك وأدوارك عند الاختيار"}
                  </Text>
                </View>
                <Button mode="contained" compact onPress={() => void selectSchool(school.id)} buttonColor={palette.primary}>اختيار</Button>
              </View>
            </AppCard>
          ))}
        </>
      ) : (
        <>
          <AppEmptyState
            icon={School}
            title="لا توجد مدرسة مرتبطة بحسابك"
            description="تم تسجيل الدخول بنجاح، لكن لا توجد عضوية مدرسية نشطة. اطلب من إدارة المدرسة إرسال دعوة إلى رقم هاتفك أو بريدك الموثق، ثم أدخل رمزها هنا لقبول العضوية."
          />
          <Button mode="contained" icon="ticket-confirmation" onPress={() => router.push("/accept-invitation" as never)} buttonColor={palette.primary}>
            لدي رمز دعوة للمدرسة
          </Button>
        </>
      )}

      <View style={styles.footer}>
        {session.schools.length ? (
          <Button mode="text" onPress={() => router.push("/accept-invitation" as never)} textColor={palette.secondary}>
            الانضمام إلى مدرسة أخرى برمز دعوة
          </Button>
        ) : null}
        <Button mode="text" onPress={() => void logout().then(() => router.replace("/login" as never))} icon={LogOut} textColor={palette.muted}>تسجيل الخروج</Button>
      </View>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  header: { alignItems: "center", gap: spacing.sm, paddingVertical: spacing.xl },
  icon: { width: 58, height: 58, borderRadius: 20, backgroundColor: palette.primary, alignItems: "center", justifyContent: "center" },
  title: { color: palette.primary, fontSize: 22, fontWeight: "900" },
  subtitle: { color: palette.muted, fontSize: 12, textAlign: "center", lineHeight: 20 },
  schoolRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  schoolInfo: { flex: 1, alignItems: "flex-start", gap: 3 },
  schoolName: { color: palette.primary, fontSize: 14, fontWeight: "800", textAlign: "right" },
  schoolCode: { color: palette.muted, fontSize: 10 },
  roles: { color: palette.secondary, fontSize: 10, lineHeight: 16 },
  footer: { alignItems: "center", paddingVertical: spacing.md },
  selectionError: { color: palette.danger, fontSize: 12, textAlign: "right" },
});

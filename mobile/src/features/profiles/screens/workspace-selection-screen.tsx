import { useMemo } from "react";
import { router } from "expo-router";
import { StyleSheet, View } from "react-native";
import { ActivityIndicator, Button, Text } from "react-native-paper";
import { BriefcaseBusiness, GraduationCap, Users, UserRound, ShieldCheck } from "lucide-react-native";
import { useQuery } from "@tanstack/react-query";

import { useAuthStore } from "@/core/auth/auth-store";
import { getMyProfiles } from "@/features/profiles/api/profiles-api";
import { buildWorkspaceOptions } from "@/features/profiles/workspaces";
import { AppCard } from "@/shared/components/app-card";
import { AppEmptyState } from "@/shared/components/app-empty-state";
import { AppIcon } from "@/shared/components/app-icon";
import { AppNotice } from "@/shared/components/app-notice";
import { AppScreen } from "@/shared/components/app-screen";
import { AppSectionHeader } from "@/shared/components/app-section-header";
import { getApiErrorMessage } from "@/core/api/api-client";
import { palette, spacing } from "@/core/theme/tokens";

const icons = {
  student: GraduationCap,
  guardian: Users,
  teacher: UserRound,
  employee: BriefcaseBusiness,
  management: ShieldCheck,
};

export function WorkspaceSelectionScreen() {
  const session = useAuthStore((state) => state.session);
  const chooseWorkspace = useAuthStore((state) => state.chooseWorkspace);
  const schoolId = session?.activeSchoolId;
  const profilesQuery = useQuery({
    queryKey: ["identity", "my-profiles", session?.user.id, session?.sessionId, schoolId],
    queryFn: getMyProfiles,
    enabled: Boolean(session?.accessToken && schoolId),
    staleTime: 30_000,
  });
  const options = useMemo(
    () => session && profilesQuery.data ? buildWorkspaceOptions(session, profilesQuery.data) : [],
    [session, profilesQuery.data],
  );
  const school = session?.schools.find((item) => item.id === schoolId);

  async function selectWorkspace(type: (typeof options)[number]["type"]) {
    await chooseWorkspace(type);
    router.replace("/home" as never);
  }

  if (!session || !schoolId) return <AppScreen compact><ActivityIndicator /></AppScreen>;

  return (
    <AppScreen>
      <View style={styles.header}>
        <View style={styles.icon}><AppIcon icon={BriefcaseBusiness} color={palette.white} size={25} /></View>
        <Text style={styles.title}>اختر مساحة العمل</Text>
        <Text style={styles.subtitle}>المدرسة النشطة: {school?.name ?? "المدرسة"}</Text>
        <Text style={styles.hint}>قد يملك الحساب أكثر من دور في المدرسة نفسها. اختر الدور الذي تريد استخدامه الآن.</Text>
      </View>

      <AppSectionHeader title="الأدوار والملفات المتاحة" />
      {profilesQuery.isLoading ? (
        <View style={styles.loading}><ActivityIndicator color={palette.secondary} /><Text style={styles.loadingText}>جارٍ تحميل ملفاتك من المدرسة...</Text></View>
      ) : profilesQuery.isError ? (
        <AppNotice message={getApiErrorMessage(profilesQuery.error)} />
      ) : options.length ? (
        options.map((option) => {
          const Icon = icons[option.type];
          return (
            <AppCard key={option.type} padding={14}>
              <View style={styles.optionRow}>
                <View style={styles.optionIcon}><AppIcon icon={Icon} color={palette.secondary} size={24} /></View>
                <View style={styles.optionText}>
                  <Text style={styles.optionTitle}>{option.title}</Text>
                  <Text style={styles.optionDescription}>{option.description}</Text>
                  {option.count && option.count > 1 ? (
                    <Text style={styles.multipleProfiles}>
                      توجد عدة ملفات لهذا الدور؛ واجهات الخادم الحالية تختار الملف النشط الأول لهذا النوع.
                    </Text>
                  ) : null}
                </View>
                <Button mode="contained" compact onPress={() => void selectWorkspace(option.type)} buttonColor={palette.primary}>دخول</Button>
              </View>
            </AppCard>
          );
        })
      ) : (
        <AppEmptyState
          icon={ShieldCheck}
          title="لا توجد مساحة عمل جاهزة"
          description="لم يرجع الخادم ملف طالب أو ولي أمر أو معلم أو موظف أو دور إدارة نشطاً لهذه المدرسة. اطلب من إدارة المدرسة استكمال العضوية والملف الوظيفي."
        />
      )}

      <View style={styles.footer}>
        <Button mode="text" onPress={() => router.replace("/schools" as never)} textColor={palette.secondary}>تغيير المدرسة</Button>
      </View>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  header: { alignItems: "center", gap: spacing.sm, paddingVertical: spacing.lg },
  icon: { width: 58, height: 58, borderRadius: 20, backgroundColor: palette.primary, alignItems: "center", justifyContent: "center" },
  title: { color: palette.primary, fontSize: 22, fontWeight: "900" },
  subtitle: { color: palette.secondary, fontSize: 12, fontWeight: "700", textAlign: "center" },
  hint: { color: palette.muted, fontSize: 11, lineHeight: 18, textAlign: "center" },
  loading: { alignItems: "center", gap: spacing.sm, paddingVertical: spacing.xl },
  loadingText: { color: palette.muted, fontSize: 12 },
  optionRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  optionIcon: { width: 48, height: 48, borderRadius: 15, backgroundColor: palette.secondaryTint, alignItems: "center", justifyContent: "center" },
  optionText: { flex: 1, alignItems: "flex-start", gap: 3 },
  optionTitle: { color: palette.primary, fontSize: 14, fontWeight: "800" },
  optionDescription: { color: palette.muted, fontSize: 11, lineHeight: 17 },
  multipleProfiles: { color: palette.warning, fontSize: 10, lineHeight: 15, textAlign: "right" },
  footer: { alignItems: "center", paddingVertical: spacing.md },
});

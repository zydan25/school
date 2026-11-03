import { useMemo, useState } from "react";
import { View, Pressable, StyleSheet } from "react-native";
import { ActivityIndicator, Text } from "react-native-paper";
import { useQuery } from "@tanstack/react-query";

import { useAuthStore } from "@/core/auth/auth-store";
import { getGradeEntries } from "@/features/modules/api/school-modules-api";
import { getMyProfiles } from "@/features/profiles/api/profiles-api";
import { authenticatedRequest } from "@/core/api/authenticated-request";
import { getApiErrorMessage } from "@/core/api/api-client";
import { AppNotice } from "@/shared/components/app-notice";
import { AppScreen } from "@/shared/components/app-screen";
import { palette, spacing } from "@/core/theme/tokens";
import {
  formatAmount,
  ModuleCard,
  ModuleEmpty,
  ModuleHeader,
  StatusPill,
  ValueLine,
} from "@/features/modules/components/module-primitives";

type Child = { id: string; name: string; student_id_number: string };

export function GradesScreen() {
  const workspace = useAuthStore((state) => state.session?.activeWorkspace);
  const guardian = workspace === "guardian";
  const childrenQuery = useQuery({
    queryKey: ["module", "grades-children"],
    queryFn: () => authenticatedRequest<{ results: Child[] }>("app/my/children/"),
    enabled: guardian,
  });
  const profileQuery = useQuery({
    queryKey: ["module", "grades-student-profile"],
    queryFn: getMyProfiles,
    enabled: workspace === "student",
  });
  const [selectedChildId, setSelectedChildId] = useState("");
  const entriesQuery = useQuery({
    queryKey: ["module", "gradebook-entries"],
    queryFn: getGradeEntries,
  });

  const children = childrenQuery.data?.results ?? [];
  const studentProfile = profileQuery.data?.students?.[0];
  const selectedStudentId = guardian ? (children.find((item) => item.id === selectedChildId) ?? children[0])?.id : studentProfile?.id;
  const selectedName = guardian
    ? (children.find((item) => item.id === selectedStudentId)?.name ?? "الابن")
    : studentProfile?.full_name ?? "ملفي الدراسي";

  const entries = useMemo(() => {
    const rows = entriesQuery.data ?? [];
    if (selectedStudentId) return rows.filter((item) => item.student === selectedStudentId);
    return rows;
  }, [entriesQuery.data, selectedStudentId]);

  const byTerm = useMemo(() => {
    const groups = new Map<string, typeof entries>();
    for (const entry of entries) {
      const name = entry.academic_term_name ?? entry.academic_term;
      groups.set(name, [...(groups.get(name) ?? []), entry]);
    }
    return Array.from(groups.entries());
  }, [entries]);

  return (
    <AppScreen>
      <ModuleHeader title="الدرجات والتقييم" subtitle="الدرجات المنشورة والمعتمدة من المدرسة فقط" trailing={entries.length + " نتيجة"} />
      {guardian ? (
        <View style={styles.childChips}>
          {children.map((child) => {
            const selected = child.id === (selectedStudentId ?? selectedChildId);
            return (
              <Pressable key={child.id} onPress={() => setSelectedChildId(child.id)}
                style={[styles.childChip, selected && styles.selectedChip]}>
                <Text style={[styles.childChipText, selected && styles.selectedChipText]}>{child.name}</Text>
              </Pressable>
            );
          })}
        </View>
      ) : null}
      {entriesQuery.isLoading || (guardian && childrenQuery.isLoading) || (workspace === "student" && profileQuery.isLoading) ? (
        <ActivityIndicator color={palette.secondary} />
      ) : null}
      {entriesQuery.isError ? <AppNotice message={getApiErrorMessage(entriesQuery.error)} /> : null}
      {guardian && childrenQuery.isError ? <AppNotice message={getApiErrorMessage(childrenQuery.error)} /> : null}
      {!entriesQuery.isLoading && !entries.length ? (
        <ModuleEmpty title="لا توجد درجات منشورة" body="ستظهر هنا النتائج بعد اعتمادها ونشرها من المدرسة. لا يعرض التطبيق درجات المسودات أو الدرجات غير المنشورة." />
      ) : null}
      {byTerm.map(([term, rows]) => (
        <View key={term} style={styles.group}>
          <Text style={styles.termTitle}>{term}</Text>
          {rows.map((entry) => (
            <ModuleCard key={entry.id}>
              <View style={styles.entryTop}>
                <View style={styles.entryTitle}>
                  <Text style={styles.subject}>{entry.subject_name ?? entry.subject}</Text>
                  <Text style={styles.type}>{entry.assessment_type ?? "تقييم"}</Text>
                </View>
                <StatusPill value="published" labels={{ published: "منشورة" }} />
              </View>
              {guardian ? <ValueLine label="الطالب" value={entry.student_name ?? selectedName} /> : null}
              <View style={styles.scoreLine}>
                <Text style={styles.score}>{formatAmount(entry.score)}</Text>
                <Text style={styles.maxScore}>من {formatAmount(entry.max_score)}</Text>
              </View>
              <ValueLine label="النسبة" value={Number(entry.max_score) > 0 ? formatAmount((Number(entry.score) / Number(entry.max_score)) * 100) + "%" : "—"} />
              {entry.graded_at ? <ValueLine label="تاريخ الرصد" value={entry.graded_at.slice(0, 10)} /> : null}
            </ModuleCard>
          ))}
        </View>
      ))}
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  childChips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  childChip: { borderWidth: 1, borderColor: palette.border, borderRadius: 30, paddingVertical: 8, paddingHorizontal: 12 },
  selectedChip: { backgroundColor: palette.primary, borderColor: palette.primary },
  childChipText: { color: palette.primary, fontSize: 11, fontWeight: "700" },
  selectedChipText: { color: palette.white },
  group: { gap: spacing.sm, marginTop: spacing.md },
  termTitle: { color: palette.primary, fontSize: 14, fontWeight: "900", textAlign: "right" },
  entryTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm },
  entryTitle: { flex: 1, alignItems: "flex-start", gap: 4 },
  subject: { color: palette.primary, fontSize: 13, fontWeight: "800", textAlign: "right" },
  type: { color: palette.muted, fontSize: 10 },
  scoreLine: { flexDirection: "row", alignItems: "baseline", gap: 6, paddingVertical: 9 },
  score: { color: palette.success, fontSize: 24, fontWeight: "900" },
  maxScore: { color: palette.muted, fontSize: 11 },
});

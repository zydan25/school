import { useMemo, useState } from "react";
import { router } from "expo-router";
import { ScrollView, StyleSheet, View } from "react-native";
import { ActivityIndicator, Button, Dialog, Portal, Text, TextInput } from "react-native-paper";
import { BookOpen, ClipboardCheck, GraduationCap, RefreshCw } from "lucide-react-native";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuthStore } from "@/core/auth/auth-store";
import {
  loadAcademicWorkspaceData,
  submitHomework,
  type GradeRecord,
  type HomeworkItem,
  type HomeworkSubmission,
} from "@/features/academics/api/academics-api";
import { AppCard } from "@/shared/components/app-card";
import { AppEmptyState } from "@/shared/components/app-empty-state";
import { AppIcon } from "@/shared/components/app-icon";
import { AppNotice } from "@/shared/components/app-notice";
import { AppScreen } from "@/shared/components/app-screen";
import { AppSectionHeader } from "@/shared/components/app-section-header";
import { getApiErrorMessage } from "@/core/api/api-client";
import { palette, radius, spacing } from "@/core/theme/tokens";

type Tab = "homework" | "grades";

const submissionLabels: Record<string, string> = {
  submitted: "تم التسليم",
  late: "تم التسليم متأخراً",
  graded: "تم التصحيح",
  resubmit: "مطلوب إعادة التسليم",
};

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ar-YE", { dateStyle: "medium" }).format(date);
}

function formatNumber(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  return Number.isFinite(number)
    ? new Intl.NumberFormat("ar-YE", { maximumFractionDigits: 2 }).format(number)
    : String(value);
}

export function AcademicsScreen() {
  const session = useAuthStore((state) => state.session);
  const workspace = session?.activeWorkspace;
  const schoolId = session?.activeSchoolId;
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("homework");
  const [selectedHomework, setSelectedHomework] = useState<HomeworkItem | null>(null);
  const [submissionText, setSubmissionText] = useState("");
  const [submitError, setSubmitError] = useState("");

  const query = useQuery({
    queryKey: ["academics", "workspace", session?.user.id, session?.sessionId, schoolId, workspace],
    queryFn: () => loadAcademicWorkspaceData(workspace!),
    enabled: Boolean(session?.accessToken && schoolId && workspace),
    staleTime: 30_000,
  });

  const submitMutation = useMutation({
    mutationFn: () => {
      if (!selectedHomework) throw new Error("حدد الواجب أولاً.");
      return submitHomework(selectedHomework.id, submissionText.trim());
    },
    retry: 0,
    onSuccess: async () => {
      setSelectedHomework(null);
      setSubmissionText("");
      setSubmitError("");
      await queryClient.invalidateQueries({
        queryKey: ["academics", "workspace", session?.user.id, session?.sessionId, schoolId, workspace],
      });
    },
    onError: (error) => setSubmitError(getApiErrorMessage(error)),
  });

  const submissionsByHomework = useMemo(() => {
    const map = new Map<string, HomeworkSubmission[]>();
    for (const item of query.data?.submissions ?? []) {
      const current = map.get(item.homework) ?? [];
      current.push(item);
      map.set(item.homework, current);
    }
    return map;
  }, [query.data?.submissions]);

  if (!session || !workspace || !schoolId) {
    return (
      <AppScreen compact>
        <ActivityIndicator color={palette.secondary} />
        <Text style={styles.muted}>جارٍ تجهيز بياناتك الأكاديمية...</Text>
      </AppScreen>
    );
  }

  const isStudent = workspace === "student";
  const canSubmit = isStudent;

  return (
    <AppScreen>
      <View style={styles.header}>
        <View style={styles.headerIcon}>
          <AppIcon icon={tab === "homework" ? BookOpen : GraduationCap} size={25} color={palette.white} />
        </View>
        <Text style={styles.title}>الدراسة والتقييم</Text>
        <Text style={styles.subtitle}>
          {workspace === "guardian"
            ? "واجبات ونتائج الأبناء التي سمحت المدرسة بنشرها."
            : workspace === "teacher"
              ? "واجباتك وتسليمات الطلاب وسجلات التقييم."
              : "تابع واجباتك وتسليماتك ودرجاتك المنشورة."}
        </Text>
      </View>

      <View style={styles.tabs}>
        <Button
          mode={tab === "homework" ? "contained" : "text"}
          onPress={() => setTab("homework")}
          buttonColor={tab === "homework" ? palette.primary : "transparent"}
          textColor={tab === "homework" ? palette.white : palette.muted}
          compact
          style={styles.tabButton}
        >
          الواجبات
        </Button>
        <Button
          mode={tab === "grades" ? "contained" : "text"}
          onPress={() => setTab("grades")}
          buttonColor={tab === "grades" ? palette.primary : "transparent"}
          textColor={tab === "grades" ? palette.white : palette.muted}
          compact
          style={styles.tabButton}
        >
          الدرجات
        </Button>
      </View>

      {query.isLoading ? (
        <View style={styles.loading}>
          <ActivityIndicator color={palette.secondary} size="large" />
          <Text style={styles.muted}>جارٍ تحميل بيانات الدراسة من المدرسة...</Text>
        </View>
      ) : query.isError ? (
        <AppCard padding={15}>
          <AppNotice message={getApiErrorMessage(query.error)} />
          <Button mode="outlined" icon={RefreshCw} onPress={() => void query.refetch()} textColor={palette.primary} style={styles.retry}>
            إعادة المحاولة
          </Button>
        </AppCard>
      ) : tab === "homework" ? (
        <View style={styles.list}>
          <AppSectionHeader title="الواجبات والتكليفات" trailing={(query.data?.homeworks.length ?? 0) + " واجبات"} />
          {query.data?.homeworks.length ? (
            query.data.homeworks.map((homework) => (
              <HomeworkCard
                key={homework.id}
                homework={homework}
                submissions={submissionsByHomework.get(homework.id) ?? []}
                canSubmit={canSubmit}
                onSubmit={() => {
                  setSelectedHomework(homework);
                  setSubmissionText("");
                  setSubmitError("");
                }}
              />
            ))
          ) : (
            <AppEmptyState
              icon={BookOpen}
              title="لا توجد واجبات حالياً"
              description="لم يرجع الخادم واجبات نشطة تخص الشعبة أو الأبناء أو الإسنادات المرتبطة بحسابك."
            />
          )}
        </View>
      ) : (
        <View style={styles.list}>
          <AppSectionHeader title="سجل الدرجات" trailing={(query.data?.grades.length ?? 0) + " سجلات"} />
          {query.data?.grades.length ? (
            query.data.grades.map((grade) => <GradeCard key={grade.id} grade={grade} />)
          ) : (
            <AppEmptyState
              icon={ClipboardCheck}
              title="لا توجد درجات منشورة"
              description="ستظهر النتائج هنا بعد اعتماد المدرسة ونشر الدرجات للطلاب وأولياء الأمور."
            />
          )}
        </View>
      )}

      <View style={styles.footer}>
        <Button mode="text" onPress={() => router.back()} textColor={palette.secondary}>العودة إلى الرئيسية</Button>
        <Button mode="text" onPress={() => void query.refetch()} textColor={palette.muted}>تحديث</Button>
      </View>

      <Portal>
        <Dialog visible={Boolean(selectedHomework)} onDismiss={() => setSelectedHomework(null)} style={styles.dialog}>
          <Dialog.Title style={styles.dialogTitle}>تسليم الواجب</Dialog.Title>
          <Dialog.Content>
            {selectedHomework ? (
              <View style={styles.dialogContent}>
                <Text style={styles.dialogHomework}>{selectedHomework.title}</Text>
                <Text style={styles.dialogDescription}>{selectedHomework.description}</Text>
                <TextInput
                  mode="outlined"
                  label="اكتب الحل أو إجابتك"
                  value={submissionText}
                  onChangeText={setSubmissionText}
                  multiline
                  numberOfLines={5}
                  style={styles.responseInput}
                  contentStyle={styles.responseContent}
                  outlineColor={palette.border}
                  activeOutlineColor={palette.secondary}
                />
                {submitError ? <AppNotice message={submitError} /> : null}
                <Text style={styles.note}>إرسال النص متاح الآن. إرفاق ملف سيكون خطوة تالية بعد إضافة منتقي ملفات متوافق مع Android وiOS.</Text>
              </View>
            ) : null}
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={() => setSelectedHomework(null)} textColor={palette.muted} disabled={submitMutation.isPending}>إلغاء</Button>
            <Button
              onPress={() => submitMutation.mutate()}
              loading={submitMutation.isPending}
              disabled={submitMutation.isPending || !submissionText.trim()}
              textColor={palette.primary}
            >
              إرسال الحل
            </Button>
          </Dialog.Actions>
        </Dialog>
      </Portal>
    </AppScreen>
  );
}

function HomeworkCard({
  homework,
  submissions,
  canSubmit,
  onSubmit,
}: {
  homework: HomeworkItem;
  submissions: HomeworkSubmission[];
  canSubmit: boolean;
  onSubmit: () => void;
}) {
  const submission = submissions[0];
  const isResubmit = submission?.status === "resubmit";
  const maySubmit = canSubmit && (!submission || isResubmit);

  return (
    <AppCard padding={14}>
      <View style={styles.cardStack}>
        <View style={styles.homeworkTop}>
          <View style={styles.flex}>
            <Text style={styles.cardTitle}>{homework.title}</Text>
            <Text style={styles.cardMeta}>{homework.subject_name} · {homework.section_name}</Text>
          </View>
          <View style={[styles.pill, submission?.status === "graded" ? styles.pillSuccess : isResubmit ? styles.pillWarning : styles.pillNeutral]}>
            <Text style={styles.pillText}>{submission ? submissionLabels[submission.status] ?? submission.status : "لم يتم التسليم"}</Text>
          </View>
        </View>
        <Text style={styles.description}>{homework.description}</Text>
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>تاريخ الإسناد</Text>
          <Text style={styles.infoValue}>{formatDate(homework.assigned_date)}</Text>
        </View>
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>آخر موعد</Text>
          <Text style={styles.infoValue}>{formatDate(homework.due_date)}</Text>
        </View>
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>الدرجة العظمى</Text>
          <Text style={styles.infoValue}>{formatNumber(homework.max_score)}</Text>
        </View>
        {submission?.status === "graded" ? (
          <AppNotice tone="success" message={"درجتك: " + formatNumber(submission.score) + " من " + formatNumber(homework.max_score) + (submission.teacher_feedback ? " · " + submission.teacher_feedback : "")} />
        ) : null}
        {submission && submission.status !== "graded" ? (
          <Text style={styles.submissionMeta}>آخر تسليم: {formatDate(submission.submitted_at)} · {submission.attempts.length} محاولات محفوظة</Text>
        ) : null}
        {maySubmit ? (
          <Button mode="contained" icon="send" onPress={onSubmit} buttonColor={palette.primary} contentStyle={styles.actionButton}>
            {isResubmit ? "إعادة تسليم الواجب" : "تسليم الواجب"}
          </Button>
        ) : null}
        {!canSubmit && submissions.length ? (
          <Text style={styles.submissionMeta}>التسليمات: {submissions.length}</Text>
        ) : null}
      </View>
    </AppCard>
  );
}

function GradeCard({ grade }: { grade: GradeRecord }) {
  return (
    <AppCard padding={14}>
      <View style={styles.cardStack}>
        <Text style={styles.cardTitle}>{grade.assessment_title}</Text>
        <Text style={styles.cardMeta}>{grade.subject_name}{grade.academic_term_name ? " · " + grade.academic_term_name : ""}</Text>
        <View style={styles.gradeScore}>
          <Text style={styles.gradeValue}>{formatNumber(grade.score)}</Text>
          <Text style={styles.gradeMax}>/ {formatNumber(grade.max_score)}</Text>
        </View>
        {grade.graded_at ? <Text style={styles.submissionMeta}>تاريخ الرصد: {formatDate(grade.graded_at)}</Text> : null}
        {grade.teacher_feedback ? <AppNotice message={grade.teacher_feedback} /> : null}
      </View>
    </AppCard>
  );
}

const styles = StyleSheet.create({
  header: { alignItems: "center", gap: spacing.sm, paddingVertical: spacing.md },
  headerIcon: { width: 58, height: 58, borderRadius: 20, backgroundColor: palette.primary, alignItems: "center", justifyContent: "center" },
  title: { color: palette.primary, fontSize: 22, fontWeight: "900" },
  subtitle: { color: palette.muted, fontSize: 12, lineHeight: 19, textAlign: "center" },
  tabs: { flexDirection: "row", gap: spacing.sm, padding: 4, backgroundColor: palette.neutralTint, borderRadius: radius.md },
  tabButton: { flex: 1 },
  loading: { alignItems: "center", paddingVertical: spacing.xxl, gap: spacing.sm },
  muted: { color: palette.muted, fontSize: 12, textAlign: "center" },
  retry: { marginTop: spacing.sm },
  list: { gap: spacing.md },
  cardStack: { gap: spacing.sm },
  homeworkTop: { flexDirection: "row", alignItems: "flex-start", gap: spacing.sm },
  flex: { flex: 1, gap: 4 },
  cardTitle: { color: palette.primary, fontSize: 14, fontWeight: "800", textAlign: "right" },
  cardMeta: { color: palette.secondary, fontSize: 11, textAlign: "right" },
  description: { color: palette.text, fontSize: 12, lineHeight: 19, textAlign: "right" },
  pill: { borderRadius: radius.pill, paddingHorizontal: 9, paddingVertical: 5 },
  pillSuccess: { backgroundColor: palette.successTint },
  pillWarning: { backgroundColor: palette.warningTint },
  pillNeutral: { backgroundColor: palette.neutralTint },
  pillText: { color: palette.text, fontSize: 9, fontWeight: "700" },
  infoRow: { flexDirection: "row", justifyContent: "space-between", gap: spacing.md },
  infoLabel: { color: palette.muted, fontSize: 11 },
  infoValue: { color: palette.text, fontSize: 11, fontWeight: "700" },
  submissionMeta: { color: palette.muted, fontSize: 10, lineHeight: 16, textAlign: "right" },
  actionButton: { minHeight: 42 },
  gradeScore: { flexDirection: "row", alignItems: "baseline", justifyContent: "flex-start", gap: 4 },
  gradeValue: { color: palette.success, fontSize: 24, fontWeight: "900" },
  gradeMax: { color: palette.muted, fontSize: 13 },
  footer: { flexDirection: "row", justifyContent: "center", gap: spacing.sm, paddingTop: spacing.md },
  dialog: { backgroundColor: palette.surface },
  dialogTitle: { textAlign: "right", color: palette.primary, fontWeight: "900" },
  dialogContent: { gap: spacing.sm },
  dialogHomework: { textAlign: "right", color: palette.primary, fontWeight: "800" },
  dialogDescription: { textAlign: "right", color: palette.muted, lineHeight: 19, fontSize: 12 },
  responseInput: { backgroundColor: palette.surface },
  responseContent: { textAlign: "right", minHeight: 100 },
  note: { color: palette.muted, fontSize: 10, lineHeight: 16, textAlign: "right" },
});

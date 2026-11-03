import { useMemo, useState } from "react";
import { View, StyleSheet } from "react-native";
import { ActivityIndicator, Button, Text, TextInput } from "react-native-paper";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuthStore } from "@/core/auth/auth-store";
import {
  gradeHomework,
  getHomeworkList,
  getHomeworkSubmissions,
  requestHomeworkResubmission,
  submitHomework,
  type HomeworkItem,
  type HomeworkSubmission,
} from "@/features/modules/api/school-modules-api";
import { getApiErrorMessage } from "@/core/api/api-client";
import { AppNotice } from "@/shared/components/app-notice";
import { AppScreen } from "@/shared/components/app-screen";
import { palette, spacing } from "@/core/theme/tokens";
import {
  formatAmount,
  formatDate,
  ModuleCard,
  ModuleEmpty,
  ModuleHeader,
  StatusPill,
  ValueLine,
} from "@/features/modules/components/module-primitives";

const statusLabels: Record<string, string> = {
  submitted: "تم التسليم",
  late: "تسليم متأخر",
  graded: "تم التصحيح",
  resubmit: "مطلوب إعادة التسليم",
};

export function HomeworkScreen() {
  const workspace = useAuthStore((state) => state.session?.activeWorkspace);
  const isStudent = workspace === "student";
  const isTeacher = workspace === "teacher" || workspace === "management";
  const isGuardian = workspace === "guardian";

  const homeworkQuery = useQuery({
    queryKey: ["module", "homework-list"],
    queryFn: getHomeworkList,
  });
  const submissionsQuery = useQuery({
    queryKey: ["module", "homework-submissions"],
    queryFn: () => getHomeworkSubmissions(),
  });

  const title = isStudent ? "واجباتي" : isTeacher ? "واجبات الشعب" : "واجبات الأبناء";

  return (
    <AppScreen>
      <ModuleHeader title={title} subtitle="الواجبات ومواعيد التسليم ومحاولات الطلاب وتقييم المعلم" />
      {homeworkQuery.isLoading || submissionsQuery.isLoading ? <ActivityIndicator color={palette.secondary} /> : null}
      {homeworkQuery.isError ? <AppNotice message={getApiErrorMessage(homeworkQuery.error)} /> : null}
      {submissionsQuery.isError ? <AppNotice message={getApiErrorMessage(submissionsQuery.error)} /> : null}
      {!homeworkQuery.isLoading && !homeworkQuery.isError && !homeworkQuery.data?.length ? (
        <ModuleEmpty title="لا توجد واجبات حالياً" body="لم يرجع الخادم واجبات نشطة للشعبة أو الملفات المرتبطة بحسابك." />
      ) : null}
      {(homeworkQuery.data ?? []).map((homework) => {
        const submissions = (submissionsQuery.data ?? []).filter((item) => item.homework === homework.id);
        const ownSubmission = submissions[0];
        return (
          <HomeworkCard
            key={homework.id}
            homework={homework}
            submissions={submissions}
            ownSubmission={ownSubmission}
            isStudent={isStudent}
            isTeacher={isTeacher}
            isGuardian={isGuardian}
          />
        );
      })}
    </AppScreen>
  );
}

function HomeworkCard({
  homework,
  submissions,
  ownSubmission,
  isStudent,
  isTeacher,
  isGuardian,
}: {
  homework: HomeworkItem;
  submissions: HomeworkSubmission[];
  ownSubmission?: HomeworkSubmission;
  isStudent: boolean;
  isTeacher: boolean;
  isGuardian: boolean;
}) {
  const queryClient = useQueryClient();
  const [answer, setAnswer] = useState("");
  const [grades, setGrades] = useState<Record<string, string>>({});
  const [feedback, setFeedback] = useState<Record<string, string>>({});
  const [resubmitReasons, setResubmitReasons] = useState<Record<string, string>>({});

  const submitMutation = useMutation({
    mutationFn: () => submitHomework(homework.id, answer.trim()),
    onSuccess: async () => {
      setAnswer("");
      await queryClient.invalidateQueries({ queryKey: ["module", "homework-submissions"] });
    },
  });
  const gradeMutation = useMutation({
    mutationFn: ({ submissionId, score, note }: { submissionId: string; score: string; note: string }) =>
      gradeHomework(submissionId, score, note),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["module", "homework-submissions"] }),
  });
  const resubmitMutation = useMutation({
    mutationFn: ({ submissionId, reason }: { submissionId: string; reason: string }) =>
      requestHomeworkResubmission(submissionId, reason),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["module", "homework-submissions"] }),
  });

  const canSubmit = isStudent && (!ownSubmission || ownSubmission.status === "resubmit");
  const dueDate = new Date(homework.due_date);
  const overdue = Number.isFinite(dueDate.getTime()) && dueDate.getTime() < Date.now();

  return (
    <ModuleCard>
      <View style={styles.header}>
        <View style={styles.headerText}>
          <Text style={styles.title}>{homework.title}</Text>
          <Text style={styles.subtitle}>{homework.subject_name ?? homework.subject} · {homework.section_name ?? homework.section}</Text>
        </View>
        {ownSubmission ? <StatusPill value={ownSubmission.status} labels={statusLabels} /> : null}
      </View>
      <Text style={styles.description}>{homework.description}</Text>
      <ValueLine label="تاريخ الإسناد" value={formatDate(homework.assigned_date)} />
      <ValueLine label="موعد التسليم" value={formatDate(homework.due_date)} />
      <ValueLine label="الدرجة العظمى" value={formatAmount(homework.max_score)} />

      {isStudent ? (
        <View style={styles.actionArea}>
          {ownSubmission ? (
            <>
              <ValueLine label="حالتك" value={statusLabels[ownSubmission.status] ?? ownSubmission.status} />
              {ownSubmission.score !== null && ownSubmission.score !== undefined ? <ValueLine label="درجتك" value={formatAmount(ownSubmission.score)} /> : null}
              {ownSubmission.teacher_feedback ? <ValueLine label="ملاحظات المعلم" value={ownSubmission.teacher_feedback} /> : null}
              <Text style={styles.footnote}>عدد المحاولات المحفوظة: {ownSubmission.attempts?.length ?? 0}</Text>
            </>
          ) : null}
          {canSubmit ? (
            <>
              {ownSubmission?.status === "resubmit" ? <AppNotice message="طلب المعلم إعادة تسليم الواجب. أرسل محاولة جديدة مع مراعاة ملاحظاته." /> : null}
              {overdue ? <AppNotice message="موعد التسليم المحدد مضى؛ سيحفظ الخادم المحاولة كتسليم متأخر." /> : null}
              <TextInput mode="outlined" label="اكتب إجابتك أو الحل" value={answer} onChangeText={setAnswer}
                multiline numberOfLines={4} style={styles.input} contentStyle={styles.inputText} />
              <Button mode="contained" buttonColor={palette.primary} loading={submitMutation.isPending}
                disabled={submitMutation.isPending || !answer.trim()}
                onPress={() => submitMutation.mutate()}>
                {ownSubmission ? "إرسال محاولة جديدة" : "تسليم الواجب"}
              </Button>
              {submitMutation.isError ? <AppNotice message={getApiErrorMessage(submitMutation.error)} /> : null}
              {submitMutation.isSuccess ? <AppNotice tone="success" message="تم تسليم الإجابة وحفظ المحاولة لدى الخادم." /> : null}
            </>
          ) : null}
          {!canSubmit && ownSubmission?.status === "graded" ? (
            <AppNotice message="اكتمل تصحيح هذا الواجب. لا يسمح الخادم بإعادة التسليم بعد التصحيح." />
          ) : null}
        </View>
      ) : null}

      {isTeacher ? (
        <View style={styles.actionArea}>
          <Text style={styles.sectionLabel}>التسليمات ({submissions.length})</Text>
          {!submissions.length ? <Text style={styles.footnote}>لم تصل تسليمات لهذا الواجب بعد.</Text> : null}
          {submissions.map((submission) => (
            <View key={submission.id} style={styles.submission}>
              <View style={styles.header}>
                <Text style={styles.studentName}>{submission.student_name}</Text>
                <StatusPill value={submission.status} labels={statusLabels} />
              </View>
              <Text style={styles.answer}>{submission.submission_text || "لم يكتب الطالب إجابة نصية."}</Text>
              {submission.score !== null && submission.score !== undefined ? <ValueLine label="الدرجة الحالية" value={formatAmount(submission.score)} /> : null}
              {submission.teacher_feedback ? <ValueLine label="ملاحظات سابقة" value={submission.teacher_feedback} /> : null}

              {["submitted", "late"].includes(submission.status) ? (
                <>
                  <TextInput mode="outlined" label={"الدرجة من " + homework.max_score}
                    value={grades[submission.id] ?? ""} onChangeText={(value) => setGrades((current) => ({ ...current, [submission.id]: value }))}
                    keyboardType="decimal-pad" style={styles.input} contentStyle={styles.inputText} />
                  <TextInput mode="outlined" label="ملاحظات التصحيح (اختياري)"
                    value={feedback[submission.id] ?? ""} onChangeText={(value) => setFeedback((current) => ({ ...current, [submission.id]: value }))}
                    multiline style={styles.input} contentStyle={styles.inputText} />
                  <Button mode="contained" buttonColor={palette.primary} loading={gradeMutation.isPending}
                    disabled={gradeMutation.isPending || !grades[submission.id]?.trim()}
                    onPress={() => gradeMutation.mutate({ submissionId: submission.id, score: grades[submission.id].trim(), note: feedback[submission.id] ?? "" })}>
                    حفظ التصحيح
                  </Button>
                  <TextInput mode="outlined" label="سبب طلب إعادة التسليم"
                    value={resubmitReasons[submission.id] ?? ""}
                    onChangeText={(value) => setResubmitReasons((current) => ({ ...current, [submission.id]: value }))}
                    style={styles.input} contentStyle={styles.inputText} />
                  <Button mode="outlined" textColor={palette.secondary} loading={resubmitMutation.isPending}
                    disabled={resubmitMutation.isPending || !resubmitReasons[submission.id]?.trim()}
                    onPress={() => resubmitMutation.mutate({ submissionId: submission.id, reason: resubmitReasons[submission.id].trim() })}>
                    طلب إعادة التسليم
                  </Button>
                </>
              ) : null}
            </View>
          ))}
          {gradeMutation.isError ? <AppNotice message={getApiErrorMessage(gradeMutation.error)} /> : null}
          {resubmitMutation.isError ? <AppNotice message={getApiErrorMessage(resubmitMutation.error)} /> : null}
        </View>
      ) : null}

      {isGuardian ? (
        <View style={styles.actionArea}>
          {submissions.map((submission) => (
            <View key={submission.id}>
              <ValueLine label={submission.student_name} value={statusLabels[submission.status] ?? submission.status} />
              {submission.score !== null && submission.score !== undefined ? <ValueLine label="الدرجة" value={formatAmount(submission.score)} /> : null}
              {submission.teacher_feedback ? <ValueLine label="ملاحظات المعلم" value={submission.teacher_feedback} /> : null}
            </View>
          ))}
          {!submissions.length ? <Text style={styles.footnote}>لا توجد محاولة تسليم مسجلة لهذا الواجب بعد.</Text> : null}
        </View>
      ) : null}
    </ModuleCard>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", gap: spacing.sm },
  headerText: { flex: 1, gap: 4, alignItems: "flex-start" },
  title: { color: palette.primary, fontWeight: "900", fontSize: 14, textAlign: "right" },
  subtitle: { color: palette.secondary, fontSize: 10, lineHeight: 16, textAlign: "right" },
  description: { color: palette.text, fontSize: 12, lineHeight: 20, textAlign: "right", marginVertical: 8 },
  actionArea: { gap: spacing.sm, marginTop: spacing.sm },
  input: { backgroundColor: palette.surface },
  inputText: { textAlign: "right" },
  footnote: { color: palette.muted, fontSize: 10, lineHeight: 16, textAlign: "right" },
  sectionLabel: { color: palette.primary, fontWeight: "800", fontSize: 12, textAlign: "right" },
  submission: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: palette.border, paddingTop: spacing.sm, gap: spacing.sm },
  studentName: { color: palette.primary, fontSize: 12, fontWeight: "800" },
  answer: { color: palette.text, fontSize: 11, lineHeight: 19, textAlign: "right" },
});

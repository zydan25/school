import { useMemo, useState } from "react";
import { StyleSheet, View } from "react-native";
import { ActivityIndicator, Button, Text, TextInput } from "react-native-paper";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuthStore } from "@/core/auth/auth-store";
import {
  getExamPaper,
  getOnlineExams,
  startOnlineExam,
  submitOnlineExam,
  type ExamQuestion,
} from "@/features/modules/api/school-modules-api";
import { getApiErrorMessage } from "@/core/api/api-client";
import { AppNotice } from "@/shared/components/app-notice";
import { AppScreen } from "@/shared/components/app-screen";
import { palette, spacing } from "@/core/theme/tokens";
import {
  ModuleCard,
  ModuleEmpty,
  ModuleHeader,
  ValueLine,
} from "@/features/modules/components/module-primitives";

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("ar-YE", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

export function ExamsScreen() {
  const workspace = useAuthStore((state) => state.session?.activeWorkspace);
  const queryClient = useQueryClient();
  const [activeExamId, setActiveExamId] = useState<string | null>(null);
  const [deadline, setDeadline] = useState<string | null>(null);
  const [submissionId, setSubmissionId] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const examsQuery = useQuery({
    queryKey: ["module", "online-exams"],
    queryFn: getOnlineExams,
    enabled: workspace === "student",
  });
  const paperQuery = useQuery({
    queryKey: ["module", "online-exam-paper", activeExamId],
    queryFn: () => getExamPaper(activeExamId!),
    enabled: Boolean(activeExamId && submissionId),
    retry: false,
  });
  const startMutation = useMutation({
    mutationFn: startOnlineExam,
    onSuccess: async (result, examId) => {
      setSubmissionId(result.submission_id);
      setDeadline(result.deadline);
      setActiveExamId(examId);
      await queryClient.invalidateQueries({ queryKey: ["module", "online-exams"] });
    },
  });
  const submitMutation = useMutation({
    mutationFn: ({ examId, payload }: { examId: string; payload: Record<string, string> }) =>
      submitOnlineExam(examId, payload),
    onSuccess: async () => {
      setActiveExamId(null);
      setSubmissionId(null);
      setDeadline(null);
      setAnswers({});
      await queryClient.invalidateQueries({ queryKey: ["module", "online-exams"] });
    },
  });

  const exams = examsQuery.data ?? [];
  const activeExam = useMemo(() => exams.find((item) => item.id === activeExamId), [exams, activeExamId]);

  if (workspace !== "student") {
    return (
      <AppScreen>
        <ModuleHeader title="الاختبارات الإلكترونية" subtitle="أداء الاختبارات المنشورة للطلاب" />
        <ModuleEmpty title="واجهة أداء الاختبار للطالب" body="إنشاء الاختبارات وإدارتها ومراجعة نتائجها من وحدات المعلم والإدارة تأتي ضمن لوحة التقييم المتخصصة." />
      </AppScreen>
    );
  }

  return (
    <AppScreen>
      <ModuleHeader title="اختباراتي الإلكترونية" subtitle="الاختبارات المنشورة والمتاحة وفق الشعبة والسنة والوقت المحدد" trailing={exams.length + " اختبارات"} />
      {examsQuery.isLoading ? <ActivityIndicator color={palette.secondary} /> : null}
      {examsQuery.isError ? <AppNotice message={getApiErrorMessage(examsQuery.error)} /> : null}
      {!examsQuery.isLoading && !exams.length ? (
        <ModuleEmpty title="لا توجد اختبارات منشورة" body="ستظهر الاختبارات هنا بعد أن تنشرها المدرسة وتدخل ضمن صفك وشعبتك والفترة المحددة." />
      ) : null}

      {!activeExamId ? exams.map((exam) => (
        <ModuleCard key={exam.id}>
          <Text style={styles.examTitle}>{exam.title}</Text>
          <Text style={styles.subject}>{exam.subject_name}</Text>
          <ValueLine label="بداية الاختبار" value={formatDateTime(exam.start_time)} />
          <ValueLine label="نهاية الاختبار" value={formatDateTime(exam.end_time)} />
          <ValueLine label="المدة" value={exam.duration_minutes + " دقيقة"} />
          <ValueLine label="الدرجة الكلية" value={exam.total_marks} />
          {exam.instructions ? <Text style={styles.instructions}>{exam.instructions}</Text> : null}
          <Button mode="contained" buttonColor={palette.primary} loading={startMutation.isPending}
            disabled={startMutation.isPending}
            onPress={() => startMutation.mutate(exam.id)}>
            بدء الاختبار / استكمال محاولة جارية
          </Button>
        </ModuleCard>
      )) : (
        <ModuleCard>
          <View style={styles.activeHeader}>
            <Text style={styles.examTitle}>{paperQuery.data?.exam.title ?? activeExam?.title ?? "الاختبار"}</Text>
            <Text style={styles.timerLabel}>آخر موعد: {formatDateTime(deadline)}</Text>
          </View>
          {paperQuery.isLoading ? <ActivityIndicator color={palette.secondary} /> : null}
          {paperQuery.isError ? <AppNotice message={getApiErrorMessage(paperQuery.error)} /> : null}
          {paperQuery.data?.exam.instructions ? <Text style={styles.instructions}>{paperQuery.data.exam.instructions}</Text> : null}
          <AppNotice message="تُرسل الإجابات إلى الخادم عند التسليم النهائي فقط؛ لا تغلق الاختبار قبل التسليم، لأن المسودة غير المرسلة لا تحفظ في هذه النسخة." />
          {(paperQuery.data?.questions ?? []).map((question, index) => (
            <QuestionCard
              key={question.id}
              question={question}
              index={index}
              answer={answers[question.id] ?? ""}
              onChange={(value) => setAnswers((current) => ({ ...current, [question.id]: value }))}
            />
          ))}
          {paperQuery.data?.questions.length ? (
            <View style={styles.submitArea}>
              <Text style={styles.footnote}>
                أجِب عن الأسئلة ثم اضغط تسليم نهائي. بعد قبول الخادم للتسليم لن تتمكن من تعديل الإجابات.
              </Text>
              <Button mode="contained" buttonColor={palette.success} loading={submitMutation.isPending}
                disabled={submitMutation.isPending}
                onPress={() => submitMutation.mutate({ examId: activeExamId, payload: answers })}>
                تسليم الاختبار نهائياً
              </Button>
            </View>
          ) : null}
          {submitMutation.isError ? <AppNotice message={getApiErrorMessage(submitMutation.error)} /> : null}
        </ModuleCard>
      )}

      {startMutation.isError ? <AppNotice message={getApiErrorMessage(startMutation.error)} /> : null}
      {submitMutation.isSuccess ? <AppNotice tone="success" message="أكد الخادم استلام إجابات الاختبار." /> : null}
    </AppScreen>
  );
}

function QuestionCard({
  question,
  index,
  answer,
  onChange,
}: {
  question: ExamQuestion;
  index: number;
  answer: string;
  onChange: (value: string) => void;
}) {
  const isChoice = question.question_type === "mcq";
  const isBoolean = question.question_type === "true_false";
  return (
    <View style={styles.question}>
      <View style={styles.questionHeader}>
        <Text style={styles.questionTitle}>السؤال {index + 1}</Text>
        <Text style={styles.marks}>{question.default_marks} درجة</Text>
      </View>
      <Text style={styles.questionText}>{question.question_text}</Text>
      {isChoice ? (
        <View style={styles.options}>
          {question.options_json.map((option) => (
            <Button key={option.id} compact mode={answer === option.id ? "contained" : "outlined"}
              buttonColor={answer === option.id ? palette.primary : undefined}
              textColor={answer === option.id ? palette.white : palette.secondary}
              onPress={() => onChange(option.id)}>
              {option.text}
            </Button>
          ))}
        </View>
      ) : isBoolean ? (
        <View style={styles.options}>
          <Button compact mode={answer === "true" ? "contained" : "outlined"}
            buttonColor={answer === "true" ? palette.primary : undefined}
            textColor={answer === "true" ? palette.white : palette.secondary}
            onPress={() => onChange("true")}>صح</Button>
          <Button compact mode={answer === "false" ? "contained" : "outlined"}
            buttonColor={answer === "false" ? palette.primary : undefined}
            textColor={answer === "false" ? palette.white : palette.secondary}
            onPress={() => onChange("false")}>خطأ</Button>
        </View>
      ) : (
        <TextInput mode="outlined" label="إجابتك" value={answer} onChangeText={onChange}
          multiline numberOfLines={3} style={styles.input} contentStyle={styles.inputText} />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  examTitle: { color: palette.primary, fontSize: 15, fontWeight: "900", textAlign: "right" },
  subject: { color: palette.secondary, fontSize: 11, fontWeight: "700", textAlign: "right", marginTop: 4, marginBottom: 7 },
  instructions: { color: palette.text, fontSize: 11, lineHeight: 19, textAlign: "right", marginVertical: 8 },
  activeHeader: { gap: 5, marginBottom: spacing.sm },
  timerLabel: { color: palette.warning, fontSize: 10, textAlign: "right", fontWeight: "700" },
  question: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: palette.border, paddingTop: spacing.md, marginTop: spacing.md, gap: spacing.sm },
  questionHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  questionTitle: { color: palette.primary, fontWeight: "800", fontSize: 12 },
  marks: { color: palette.muted, fontSize: 10 },
  questionText: { color: palette.text, fontSize: 12, lineHeight: 20, textAlign: "right" },
  options: { flexDirection: "row", flexWrap: "wrap", gap: 7 },
  input: { backgroundColor: palette.surface },
  inputText: { textAlign: "right" },
  submitArea: { gap: spacing.sm, marginTop: spacing.lg },
  footnote: { color: palette.muted, fontSize: 10, lineHeight: 17, textAlign: "right" },
});

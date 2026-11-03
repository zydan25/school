import { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Button, Text, TextInput, ActivityIndicator } from "react-native-paper";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpenCheck, CalendarCheck2, Users } from "lucide-react-native";

import { useAuthStore } from "@/core/auth/auth-store";
import { authenticatedRequest } from "@/core/api/authenticated-request";
import { getApiErrorMessage } from "@/core/api/api-client";
import { AppNotice } from "@/shared/components/app-notice";
import { AppScreen } from "@/shared/components/app-screen";
import { useModuleQueryScope } from "@/features/modules/hooks/use-module-query-scope";
import { AppIcon } from "@/shared/components/app-icon";
import { palette, spacing } from "@/core/theme/tokens";
import {
  createAttendanceExcuse,
  getAttendanceExcuses,
  getAttendanceRecords,
  getAttendanceScores,
  getAttendanceRegister,
  getAttendanceRegisters,
  approveAttendanceRegister,
  reviewAttendanceExcuse,
  getAttendanceStatusTypes,
  getStudentsForAttendance,
  getTeacherAssignmentsForAttendance,
  openAttendanceRegister,
  recordAttendanceBulk,
  submitAttendanceRegister,
  type AttendanceExcuse,
  type AttendanceRegister,
  type AttendanceRow,
  type AttendanceScore,
  type AttendanceStatusOption,
  type AttendanceStudent,
  type TeacherAttendanceAssignment,
} from "@/features/modules/api/school-modules-api";
import {
  formatAmount,
  formatDate,
  ModuleCard,
  ModuleEmpty,
  ModuleHeader,
  StatusPill,
  ValueLine,
} from "@/features/modules/components/module-primitives";

type GuardianChild = {
  id: string;
  student_id_number: string;
  name: string;
  grade: string;
  section: string;
};

const attendanceLabels: Record<string, string> = {
  present: "حاضر",
  absent_unexcused: "غائب دون عذر",
  absent_excused: "غائب بعذر",
  late: "متأخر",
  late_excused: "متأخر بعذر",
  early_departure: "انصراف مبكر",
  authorized_departure: "انصراف بإذن",
  partial_attendance: "حضور جزئي",
  distance_learning: "تعليم عن بعد",
  school_activity: "نشاط مدرسي",
  non_school_day: "عطلة",
  cancelled_session: "حصة ملغاة",
};

const excuseLabels: Record<string, string> = {
  advance_absence: "استئذان غياب مسبق",
  post_absence_excuse: "عذر لغياب سابق",
  late_excuse: "عذر تأخر صباحي",
  update_excuse: "طلب مراجعة غياب",
  draft: "مسودة",
  submitted: "مقدم للدراسة",
  under_review: "قيد التدقيق",
  approved: "مقبول",
  rejected: "مرفوض",
  cancelled: "ملغي",
};

function todayIso() {
  const now = new Date();
  return [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
  ].join("-");
}

function isValidDateRange(start: string, end: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(start) || !/^\d{4}-\d{2}-\d{2}$/.test(end)) {
    return false;
  }
  const startDate = new Date(start + "T12:00:00");
  const endDate = new Date(end + "T12:00:00");
  return !Number.isNaN(startDate.getTime()) &&
    !Number.isNaN(endDate.getTime()) &&
    startDate.toISOString().slice(0, 10) === start &&
    endDate.toISOString().slice(0, 10) === end &&
    endDate >= startDate;
}

export function AttendanceScreen() {
  const workspace = useAuthStore((state) => state.session?.activeWorkspace);
  return (
    <AppScreen>
      {workspace === "guardian" ? <GuardianAttendance /> :
        workspace === "teacher" ? <TeacherAttendance /> :
          workspace === "management" ? <ManagementAttendance /> :
          <ModuleEmpty
            title="سجل الحضور"
            body="السجل الذاتي للطالب يحتاج مسار قراءة مخصصاً من الخادم. هذه الوحدة تعرض حالياً سجل أبناء ولي الأمر، وتتيح للمعلم رصد سجل الشعبة وفق صلاحياته."
          />}
    </AppScreen>
  );
}

function GuardianAttendance() {
  const queryClient = useQueryClient();
  const queryScope = useModuleQueryScope();
  const [selectedChildId, setSelectedChildId] = useState("");
  const [requestType, setRequestType] = useState("post_absence_excuse");
  const [startDate, setStartDate] = useState(todayIso());
  const [endDate, setEndDate] = useState(todayIso());
  const [reason, setReason] = useState("");
  const childrenQuery = useQuery({
    queryKey: ["module", "guardian-children", ...queryScope],
    queryFn: () => authenticatedRequest<{ results: GuardianChild[] }>("app/my/children/"),
  });
  const children = childrenQuery.data?.results ?? [];
  const activeChild = children.find((item) => item.id === selectedChildId) ?? children[0];
  const attendanceQuery = useQuery({
    queryKey: ["module", "attendance", "guardian", activeChild?.id, ...queryScope],
    queryFn: () => getAttendanceRecords(activeChild?.id),
    enabled: Boolean(activeChild?.id),
  });
  const scoresQuery = useQuery({
    queryKey: ["module", "attendance-scores", activeChild?.id, ...queryScope],
    queryFn: () => getAttendanceScores(activeChild?.id),
    enabled: Boolean(activeChild?.id),
  });
  const excusesQuery = useQuery({
    queryKey: ["module", "attendance-excuses", ...queryScope],
    queryFn: getAttendanceExcuses,
  });
  const createMutation = useMutation({
    mutationFn: createAttendanceExcuse,
    onSuccess: async () => {
      setReason("");
      await queryClient.invalidateQueries({ queryKey: ["module", "attendance-excuses"] });
    },
  });

  return (
    <>
      <ModuleHeader
        title="الحضور والغياب"
        subtitle="سجل الأبناء ودرجات المواظبة وطلبات الأعذار المعتمدة من المدرسة"
        trailing={children.length + " أبناء"}
      />
      {childrenQuery.isLoading ? <ActivityIndicator color={palette.secondary} /> : null}
      {childrenQuery.isError ? <AppNotice message={getApiErrorMessage(childrenQuery.error)} /> : null}
      {!childrenQuery.isLoading && !children.length ? (
        <ModuleEmpty title="لا يوجد أبناء مرتبطون" body="لم يعثر الخادم على أبناء مرتبطين بملف ولي الأمر في المدرسة النشطة." />
      ) : null}

      {children.length ? (
        <>
          <View style={styles.childChips}>
            {children.map((child) => {
              const selected = child.id === (activeChild?.id ?? selectedChildId);
              return (
                <Pressable key={child.id} onPress={() => setSelectedChildId(child.id)}
                  style={[styles.childChip, selected && styles.selectedChip]}>
                  <Text style={[styles.childChipText, selected && styles.selectedChipText]}>{child.name}</Text>
                </Pressable>
              );
            })}
          </View>

          <View style={styles.sectionTitle}>
            <AppIcon icon={CalendarCheck2} color={palette.secondary} size={19} />
            <Text style={styles.sectionHeading}>سجل الحضور</Text>
          </View>
          {attendanceQuery.isLoading ? <ActivityIndicator color={palette.secondary} /> : null}
          {attendanceQuery.isError ? <AppNotice message={getApiErrorMessage(attendanceQuery.error)} /> : null}
          {!attendanceQuery.isLoading && attendanceQuery.data?.results.length === 0 ? (
            <ModuleEmpty title="لا توجد سجلات حضور" body="لا توجد سجلات مسجلة لهذا الابن ضمن البيانات التي أتاحها الخادم." />
          ) : null}
          {(attendanceQuery.data?.results ?? []).map((row) => (
            <AttendanceRecordCard key={row.id} row={row} />
          ))}

          <View style={styles.sectionTitle}>
            <AppIcon icon={BookOpenCheck} color={palette.secondary} size={19} />
            <Text style={styles.sectionHeading}>درجات المواظبة</Text>
          </View>
          {scoresQuery.isLoading ? <ActivityIndicator color={palette.secondary} /> : null}
          {scoresQuery.isError ? <AppNotice message={getApiErrorMessage(scoresQuery.error)} /> : null}
          {(scoresQuery.data?.results ?? []).map((score) => (
            <AttendanceScoreCard key={score.id} score={score} />
          ))}
          {!scoresQuery.isLoading && scoresQuery.data?.results.length === 0 ? (
            <ModuleEmpty title="لا توجد درجات مواظبة منشورة" body="لم ينشئ النظام بعد درجات فصلية للمواظبة لهذا الابن." />
          ) : null}

          <View style={styles.sectionTitle}>
            <AppIcon icon={Users} color={palette.secondary} size={19} />
            <Text style={styles.sectionHeading}>طلب عذر أو استئذان</Text>
          </View>
          <ModuleCard>
            <Text style={styles.fieldLabel}>نوع الطلب</Text>
            <View style={styles.requestTypes}>
              {[
                ["post_absence_excuse", "عذر غياب سابق"],
                ["advance_absence", "غياب مسبق"],
                ["late_excuse", "عذر تأخر"],
                ["update_excuse", "مراجعة غياب"],
              ].map(([value, label]) => (
                <Button key={value} compact mode={requestType === value ? "contained" : "outlined"}
                  buttonColor={requestType === value ? palette.primary : undefined}
                  textColor={requestType === value ? palette.white : palette.secondary}
                  onPress={() => setRequestType(value)}>
                  {label}
                </Button>
              ))}
            </View>
            <TextInput mode="outlined" label="من تاريخ (YYYY-MM-DD)" value={startDate} onChangeText={setStartDate} style={styles.input} contentStyle={styles.inputText} />
            <TextInput mode="outlined" label="إلى تاريخ (YYYY-MM-DD)" value={endDate} onChangeText={setEndDate} style={styles.input} contentStyle={styles.inputText} />
            <TextInput mode="outlined" label="سبب العذر" value={reason} onChangeText={setReason} multiline numberOfLines={3} style={styles.input} contentStyle={styles.inputText} />
            <Button mode="contained" buttonColor={palette.primary} loading={createMutation.isPending}
              disabled={createMutation.isPending || !reason.trim() || !activeChild?.id || !isValidDateRange(startDate, endDate)}
              onPress={() => createMutation.mutate({
                student: activeChild!.id, request_type: requestType,
                start_date: startDate.trim(), end_date: endDate.trim(), reason: reason.trim(),
              })}>
              إرسال الطلب للمراجعة
            </Button>
            {createMutation.isError ? <AppNotice message={getApiErrorMessage(createMutation.error)} /> : null}
            {createMutation.isSuccess ? <AppNotice tone="success" message="تم إرسال الطلب إلى المدرسة." /> : null}
            <Text style={styles.footnote}>قبول العذر أو رفضه يتم من إدارة المدرسة؛ لا يعتمد التطبيق الطلب محلياً.</Text>
          </ModuleCard>

          <View style={styles.sectionTitle}><Text style={styles.sectionHeading}>طلبات الأعذار السابقة</Text></View>
          {excusesQuery.isLoading ? <ActivityIndicator color={palette.secondary} /> : null}
          {excusesQuery.isError ? <AppNotice message={getApiErrorMessage(excusesQuery.error)} /> : null}
          {(excusesQuery.data ?? []).map((item) => <ExcuseCard key={item.id} item={item} />)}
          {!excusesQuery.isLoading && !excusesQuery.data?.length ? <ModuleEmpty title="لا توجد طلبات سابقة" body="ستظهر هنا الطلبات التي أرسلتها للمدرسة." /> : null}
        </>
      ) : null}
    </>
  );
}

function AttendanceRecordCard({ row }: { row: AttendanceRow }) {
  return (
    <ModuleCard>
      <View style={styles.cardTop}>
        <Text style={styles.cardTitle}>{formatDate(row.date)}</Text>
        <StatusPill value={row.status} labels={attendanceLabels} />
      </View>
      <ValueLine label="الشعبة" value={row.section} />
      <ValueLine label="الفترة" value={row.session_type === "daily_morning" ? "صباحي" : row.session_type} />
      {row.late_minutes > 0 ? <ValueLine label="دقائق التأخر" value={formatAmount(row.late_minutes)} /> : null}
      {row.notes ? <ValueLine label="ملاحظات" value={row.notes} /> : null}
    </ModuleCard>
  );
}

function AttendanceScoreCard({ score }: { score: AttendanceScore }) {
  return (
    <ModuleCard>
      <View style={styles.cardTop}>
        <Text style={styles.cardTitle}>{score.academic_term}{score.subject ? " · " + score.subject : ""}</Text>
        <Text style={styles.score}>{formatAmount(score.final_score)}</Text>
      </View>
      <ValueLine label="الدرجة قبل الخصم" value={formatAmount(score.raw_score)} />
      <ValueLine label="غياب دون عذر" value={String(score.unexcused_absence_count)} />
      <ValueLine label="غياب بعذر" value={String(score.excused_absence_count)} />
      <ValueLine label="مرات التأخر" value={String(score.late_count)} />
      <ValueLine label="إجمالي الخصم" value={formatAmount(score.deduction_total)} />
    </ModuleCard>
  );
}

function ExcuseCard({ item }: { item: AttendanceExcuse }) {
  return (
    <ModuleCard>
      <View style={styles.cardTop}>
        <Text style={styles.cardTitle}>{item.student_name}</Text>
        <StatusPill value={item.status} labels={excuseLabels} />
      </View>
      <ValueLine label="نوع الطلب" value={excuseLabels[item.request_type] ?? item.request_type} />
      <ValueLine label="الفترة" value={formatDate(item.start_date) + " – " + formatDate(item.end_date)} />
      <ValueLine label="السبب" value={item.reason} />
      {item.review_notes ? <ValueLine label="ملاحظة المدرسة" value={item.review_notes} /> : null}
    </ModuleCard>
  );
}

function ManagementAttendance() {
  const queryClient = useQueryClient();
  const queryScope = useModuleQueryScope();
  const [date, setDate] = useState(todayIso());
  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});

  const registersQuery = useQuery({
    queryKey: ["module", "attendance-management-registers", date, ...queryScope],
    queryFn: () => getAttendanceRegisters(date),
    enabled: isValidDateRange(date, date),
    refetchInterval: 30_000,
  });
  const excusesQuery = useQuery({
    queryKey: ["module", "attendance-management-excuses", ...queryScope],
    queryFn: () => getAttendanceExcuses("submitted"),
    refetchInterval: 30_000,
  });

  const approveRegisterMutation = useMutation({
    mutationFn: approveAttendanceRegister,
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["module", "attendance-management-registers"],
      });
    },
  });
  const reviewExcuseMutation = useMutation({
    mutationFn: ({ id, approved }: { id: string; approved: boolean }) =>
      reviewAttendanceExcuse(id, approved, reviewNotes[id] ?? ""),
    onSuccess: async (_, variables) => {
      setReviewNotes((current) => {
        const next = { ...current };
        delete next[variables.id];
        return next;
      });
      await queryClient.invalidateQueries({
        queryKey: ["module", "attendance-management-excuses", ...queryScope],
      });
      await queryClient.invalidateQueries({ queryKey: ["module", "attendance"] });
      await queryClient.invalidateQueries({ queryKey: ["module", "attendance-excuses"] });
      await queryClient.invalidateQueries({ queryKey: ["module", "attendance-scores"] });
    },
  });

  const registers = registersQuery.data ?? [];
  const submittedRegisters = registers.filter((item) => item.status === "submitted");
  const excuses = excusesQuery.data ?? [];

  return (
    <>
      <ModuleHeader
        title="مراجعة الحضور والأعذار"
        subtitle="اعتماد سجلات المعلمين ومراجعة أعذار أولياء الأمور. يتحقق الخادم من الصلاحية وحالة كل سجل قبل التنفيذ."
      />

      <ModuleCard>
        <Text style={styles.fieldLabel}>تاريخ سجلات الحضور</Text>
        <TextInput
          mode="outlined"
          label="التاريخ (YYYY-MM-DD)"
          value={date}
          onChangeText={setDate}
          style={styles.input}
          contentStyle={styles.inputText}
        />
        {!isValidDateRange(date, date) ? (
          <AppNotice message="أدخل تاريخاً صحيحاً بصيغة YYYY-MM-DD." />
        ) : null}
        <View style={styles.managementSummary}>
          <View style={styles.managementMetric}>
            <Text style={styles.managementMetricValue}>{submittedRegisters.length}</Text>
            <Text style={styles.managementMetricLabel}>سجلات بانتظار الاعتماد</Text>
          </View>
          <View style={styles.managementMetric}>
            <Text style={styles.managementMetricValue}>{excuses.length}</Text>
            <Text style={styles.managementMetricLabel}>أعذار بانتظار المراجعة</Text>
          </View>
        </View>
      </ModuleCard>

      <View style={styles.sectionTitle}>
        <AppIcon icon={CalendarCheck2} color={palette.secondary} size={19} />
        <Text style={styles.sectionHeading}>سجلات الحضور المرسلة</Text>
      </View>
      {registersQuery.isLoading ? <ActivityIndicator color={palette.secondary} /> : null}
      {registersQuery.isError ? (
        <AppNotice message={getApiErrorMessage(registersQuery.error)} />
      ) : null}
      {!registersQuery.isLoading && !registersQuery.isError && !submittedRegisters.length ? (
        <ModuleEmpty
          title="لا توجد سجلات تنتظر الاعتماد"
          body="لم يرسل المعلمون سجلات حضور معلقة لهذا التاريخ، أو لا تتوفر لك صلاحية قراءة سجلات هذه المدرسة."
        />
      ) : null}
      {submittedRegisters.map((register) => {
        const absentCount = register.student_records.filter((item) =>
          ["absent_unexcused", "absent_excused"].includes(item.status_category),
        ).length;
        const lateCount = register.student_records.filter((item) =>
          ["late", "late_excused"].includes(item.status_category),
        ).length;
        return (
          <ModuleCard key={register.id}>
            <View style={styles.cardTop}>
              <View style={styles.studentDetails}>
                <Text style={styles.cardTitle}>{register.section_name}</Text>
                <Text style={styles.footnote}>
                  {register.grade_name ? register.grade_name + " · " : ""}
                  {formatDate(register.date)}
                </Text>
              </View>
              <StatusPill value={register.status} labels={{ submitted: "مرسل للمراجعة" }} />
            </View>
            <ValueLine label="عدد الطلاب في السجل" value={String(register.student_records.length)} />
            <ValueLine label="غياب" value={String(absentCount)} />
            <ValueLine label="تأخر" value={String(lateCount)} />
            <ValueLine label="وقت الإرسال" value={register.submitted_at ? formatDate(register.submitted_at) : "—"} />
            <Button
              mode="contained"
              buttonColor={palette.success}
              loading={approveRegisterMutation.isPending}
              disabled={approveRegisterMutation.isPending}
              onPress={() => approveRegisterMutation.mutate(register.id)}
            >
              اعتماد سجل الحضور
            </Button>
          </ModuleCard>
        );
      })}
      {approveRegisterMutation.isError ? (
        <AppNotice message={getApiErrorMessage(approveRegisterMutation.error)} />
      ) : null}
      {approveRegisterMutation.isSuccess ? (
        <AppNotice tone="success" message="استلم الخادم طلب الاعتماد ونفذ انتقال السجل حسب دورة الاعتماد." />
      ) : null}

      <View style={styles.sectionTitle}>
        <AppIcon icon={Users} color={palette.secondary} size={19} />
        <Text style={styles.sectionHeading}>أعذار أولياء الأمور</Text>
      </View>
      {excusesQuery.isLoading ? <ActivityIndicator color={palette.secondary} /> : null}
      {excusesQuery.isError ? <AppNotice message={getApiErrorMessage(excusesQuery.error)} /> : null}
      {!excusesQuery.isLoading && !excusesQuery.isError && !excuses.length ? (
        <ModuleEmpty
          title="لا توجد أعذار معلقة"
          body="لا توجد طلبات في حالة مقدم للدراسة. لا يظهر هنا الطلب إلا قبل مراجعته، ويزيله الخادم من قائمة الانتظار بعد القبول أو الرفض."
        />
      ) : null}
      {excuses.map((item) => (
        <ModuleCard key={item.id}>
          <View style={styles.cardTop}>
            <Text style={styles.cardTitle}>{item.student_name}</Text>
            <StatusPill value={item.status} labels={excuseLabels} />
          </View>
          <ValueLine label="ولي الأمر" value={item.guardian_name ?? "—"} />
          <ValueLine label="نوع الطلب" value={excuseLabels[item.request_type] ?? item.request_type} />
          <ValueLine label="الفترة" value={formatDate(item.start_date) + " – " + formatDate(item.end_date)} />
          <ValueLine label="السبب" value={item.reason} />
          <TextInput
            mode="outlined"
            label="ملاحظات المراجعة (اختياري)"
            value={reviewNotes[item.id] ?? ""}
            onChangeText={(value) => setReviewNotes((current) => ({ ...current, [item.id]: value }))}
            multiline
            numberOfLines={2}
            style={styles.input}
            contentStyle={styles.inputText}
          />
          <View style={styles.reviewButtons}>
            <Button
              mode="contained"
              buttonColor={palette.success}
              loading={reviewExcuseMutation.isPending}
              disabled={reviewExcuseMutation.isPending}
              onPress={() => reviewExcuseMutation.mutate({ id: item.id, approved: true })}
            >
              قبول العذر
            </Button>
            <Button
              mode="outlined"
              textColor={palette.danger}
              loading={reviewExcuseMutation.isPending}
              disabled={reviewExcuseMutation.isPending}
              onPress={() => reviewExcuseMutation.mutate({ id: item.id, approved: false })}
            >
              رفض العذر
            </Button>
          </View>
        </ModuleCard>
      ))}
      {reviewExcuseMutation.isError ? (
        <AppNotice message={getApiErrorMessage(reviewExcuseMutation.error)} />
      ) : null}
      {reviewExcuseMutation.isSuccess ? (
        <AppNotice tone="success" message="تمت مراجعة الطلب عبر الخادم وتحديث حالته وسجل الحضور المتأثر عند الموافقة." />
      ) : null}
      <AppNotice message="إذا لم يكن دورك يملك صلاحية اعتماد الحضور أو مراجعة الأعذار، سيمنع الخادم العملية وتظهر رسالة الصلاحيات. لا يغيّر التطبيق السجل أو حالة العذر محلياً." />
    </>
  );
}

function TeacherAttendance() {
  const queryClient = useQueryClient();
  const queryScope = useModuleQueryScope();
  const [assignmentId, setAssignmentId] = useState("");
  const [statuses, setStatuses] = useState<Record<string, string>>({});
  const date = todayIso();

  const assignmentsQuery = useQuery({
    queryKey: ["module", "teacher-attendance-assignments", ...queryScope],
    queryFn: getTeacherAssignmentsForAttendance,
  });
  const assignments = assignmentsQuery.data ?? [];
  const assignment = assignments.find((item) => item.id === assignmentId) ?? assignments[0];

  const statusQuery = useQuery({
    queryKey: ["module", "attendance-status-types", ...queryScope],
    queryFn: getAttendanceStatusTypes,
  });
  const studentsQuery = useQuery({
    queryKey: ["module", "attendance-students", assignment?.section, assignment?.academic_year, ...queryScope],
    queryFn: () => getStudentsForAttendance(assignment!.section, assignment!.academic_year),
    enabled: Boolean(assignment?.section && assignment?.academic_year),
  });
  const registerQuery = useQuery({
    queryKey: ["module", "attendance-register", assignment?.section, date, ...queryScope],
    queryFn: () => getAttendanceRegister(assignment!.section, date),
    enabled: Boolean(assignment?.section),
  });

  const statusOptions = statusQuery.data ?? [];
  const record = registerQuery.data;
  const recordedStatusByStudent = useMemo(() => {
    const map: Record<string, string> = {};
    record?.student_records.forEach((item) => { map[item.student] = item.status_category; });
    return map;
  }, [record?.id, record?.student_records]);
  const defaultStatus = statusOptions.find((item) => item.is_default);
  const getStudentStatus = (studentId: string) =>
    statuses[studentId] ?? recordedStatusByStudent[studentId] ?? defaultStatus?.category ?? "";

  const isEditable = record?.status === "open";
  const students = studentsQuery.data ?? [];
  const allStudentsHaveStatus = students.length > 0 &&
    students.every((student) => Boolean(getStudentStatus(student.id)));

  const openMutation = useMutation({
    mutationFn: () => openAttendanceRegister(assignment!.academic_year, assignment!.section, date),
    onSuccess: async () => {
      setStatuses({});
      await queryClient.invalidateQueries({ queryKey: ["module", "attendance-register"] });
    },
  });
  const saveMutation = useMutation({
    mutationFn: (registerId: string) => {
      const records = students.map((student) => ({
        student_id: student.id,
        status_category: getStudentStatus(student.id),
      }));
      if (records.some((item) => !item.status_category)) {
        throw new Error("حدد حالة الحضور لكل طالب قبل حفظ السجل.");
      }
      return recordAttendanceBulk(registerId, records);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["module", "attendance-register"] });
    },
  });
  const submitMutation = useMutation({
    mutationFn: (registerId: string) => submitAttendanceRegister(registerId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["module", "attendance-register"] });
    },
  });

  useEffect(() => {
    if (!record) return;
    const initial: Record<string, string> = {};
    record.student_records.forEach((item) => {
      initial[item.student] = item.status_category;
    });
    setStatuses(initial);
  }, [record?.id, record?.student_records.length]);

  return (
    <>
      <ModuleHeader title="رصد الحضور" subtitle="افتح سجل الشعبة، راجع الحالات الافتراضية من الخادم، ثم احفظ وأرسل السجل للمراجعة." trailing={date} />
      {assignmentsQuery.isLoading ? <ActivityIndicator color={palette.secondary} /> : null}
      {assignmentsQuery.isError ? <AppNotice message={getApiErrorMessage(assignmentsQuery.error)} /> : null}
      {!assignmentsQuery.isLoading && !assignments.length ? (
        <ModuleEmpty title="لا توجد إسنادات تدريسية" body="لا يمكن رصد الحضور قبل أن تسند الإدارة إليك شعبة وسنة دراسية نشطة." />
      ) : null}

      {assignments.length ? (
        <>
          <ModuleCard>
            <Text style={styles.fieldLabel}>الشعبة والمادة</Text>
            {assignments.map((item) => {
              const selected = item.id === (assignment?.id ?? assignmentId);
              return (
                <Pressable key={item.id} onPress={() => {
                  setAssignmentId(item.id);
                  setStatuses({});
                }} style={[styles.assignmentChoice, selected && styles.assignmentChoiceSelected]}>
                  <Text style={[styles.assignmentText, selected && styles.selectedChipText]}>
                    {item.section_name} · {item.subject_name}
                  </Text>
                </Pressable>
              );
            })}
          </ModuleCard>

          {statusQuery.isLoading || studentsQuery.isLoading || registerQuery.isLoading ? (
            <ActivityIndicator color={palette.secondary} />
          ) : null}
          {statusQuery.isError ? <AppNotice message={getApiErrorMessage(statusQuery.error)} /> : null}
          {studentsQuery.isError ? <AppNotice message={getApiErrorMessage(studentsQuery.error)} /> : null}
          {registerQuery.isError ? <AppNotice message={getApiErrorMessage(registerQuery.error)} /> : null}
          {!statusQuery.isLoading && !statusOptions.length ? (
            <AppNotice message="لا توجد حالات حضور نشطة معرفة لهذه المدرسة. اطلب من الإدارة تهيئة حالات الحضور قبل الرصد." />
          ) : null}

          {record ? (
            <ModuleCard>
              <View style={styles.cardTop}>
                <Text style={styles.cardTitle}>سجل {record.section_name}</Text>
                <StatusPill value={record.status} labels={{ open: "مفتوح للرصد", submitted: "مرسل للمراجعة", approved: "معتمد", locked: "مقفل" }} />
              </View>
              <Text style={styles.footnote}>
                الحالات الأولية مستمدة من السجل الرسمي في الخادم، بما فيها الأعذار المعتمدة. أي تغيير هنا يُحفظ كعملية رصد موثقة.
              </Text>
            </ModuleCard>
          ) : (
            <ModuleCard>
              <Text style={styles.cardTitle}>سجل اليوم غير مفتوح</Text>
              <Button mode="contained" buttonColor={palette.primary} loading={openMutation.isPending}
                disabled={openMutation.isPending || studentsQuery.isLoading || !students.length || !statusOptions.length}
                onPress={() => openMutation.mutate()}>
                فتح سجل حضور اليوم
              </Button>
              <Text style={styles.footnote}>عند فتح السجل يجهز الخادم سجلات الطلاب ويطبق الحالة الافتراضية أو العذر المعتمد إن وجد.</Text>
            </ModuleCard>
          )}
          {openMutation.isError ? <AppNotice message={getApiErrorMessage(openMutation.error)} /> : null}

          {students.map((student) => {
            const selectedStatus = getStudentStatus(student.id);
            return (
              <ModuleCard key={student.id}>
                <View style={styles.cardTop}>
                  <View style={styles.studentDetails}>
                    <Text style={styles.cardTitle}>{student.full_name}</Text>
                    <Text style={styles.footnote}>{student.student_id_number}</Text>
                  </View>
                  <StatusPill value={selectedStatus || "unselected"}
                    labels={{ ...attendanceLabels, unselected: "لم تحدد" }} />
                </View>
                <View style={styles.requestTypes}>
                  {statusOptions.map((option) => (
                    <Button key={option.id} compact
                      mode={selectedStatus === option.category ? "contained" : "outlined"}
                      buttonColor={selectedStatus === option.category ? palette.primary : undefined}
                      textColor={selectedStatus === option.category ? palette.white : palette.secondary}
                      disabled={!record || !isEditable}
                      onPress={() => setStatuses((current) => ({ ...current, [student.id]: option.category }))}>
                      {option.name}
                    </Button>
                  ))}
                </View>
              </ModuleCard>
            );
          })}

          {record ? (
            <ModuleCard>
              <Button mode="contained" buttonColor={palette.secondary} loading={saveMutation.isPending}
                disabled={saveMutation.isPending || !isEditable || !allStudentsHaveStatus || !statusOptions.length}
                onPress={() => saveMutation.mutate(record.id)}>
                حفظ الرصد
              </Button>
              <Button mode="outlined" textColor={palette.primary} loading={submitMutation.isPending}
                disabled={submitMutation.isPending || !isEditable || !allStudentsHaveStatus}
                onPress={() => submitMutation.mutate(record.id)}>
                إرسال السجل للمراجعة
              </Button>
              {!allStudentsHaveStatus && isEditable ? (
                <Text style={styles.footnote}>اختر حالة صالحة لكل طالب قبل حفظ السجل أو إرساله.</Text>
              ) : null}
              {saveMutation.isError ? <AppNotice message={getApiErrorMessage(saveMutation.error)} /> : null}
              {saveMutation.isSuccess ? <AppNotice tone="success" message="تم حفظ الرصد في الخادم." /> : null}
              {submitMutation.isError ? <AppNotice message={getApiErrorMessage(submitMutation.error)} /> : null}
              {submitMutation.isSuccess ? <AppNotice tone="success" message="تم إرسال السجل إلى دورة المراجعة الرسمية." /> : null}
            </ModuleCard>
          ) : null}
        </>
      ) : null}
    </>
  );
}

const styles = StyleSheet.create({
  childChips: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  childChip: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 30, borderWidth: 1, borderColor: palette.border, backgroundColor: palette.surface },
  selectedChip: { borderColor: palette.primary, backgroundColor: palette.primary },
  childChipText: { color: palette.primary, fontSize: 11, fontWeight: "700" },
  selectedChipText: { color: palette.white, fontWeight: "800" },
  sectionTitle: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: spacing.md },
  sectionHeading: { color: palette.primary, fontSize: 14, fontWeight: "800" },
  cardTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm, marginBottom: 5 },
  cardTitle: { color: palette.primary, fontSize: 13, fontWeight: "800", textAlign: "right", flexShrink: 1 },
  score: { color: palette.success, fontSize: 18, fontWeight: "900" },
  fieldLabel: { color: palette.muted, fontSize: 11, fontWeight: "700", textAlign: "right" },
  requestTypes: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  input: { backgroundColor: palette.surface },
  inputText: { textAlign: "right" },
  footnote: { color: palette.muted, fontSize: 10, lineHeight: 16, textAlign: "right" },
  assignmentChoice: { paddingVertical: 9, paddingHorizontal: 10, borderRadius: 10, borderWidth: 1, borderColor: palette.border, marginTop: 6 },
  assignmentChoiceSelected: { borderColor: palette.primary, backgroundColor: palette.primary },
  assignmentText: { color: palette.text, fontSize: 11, textAlign: "right" },
  studentDetails: { flex: 1, gap: 3, alignItems: "flex-start" },
  managementSummary: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.sm },
  managementMetric: { flex: 1, backgroundColor: palette.surfaceSoft, borderWidth: 1, borderColor: palette.border, borderRadius: 12, padding: 10, gap: 4 },
  managementMetricValue: { color: palette.primary, fontSize: 20, fontWeight: "900", textAlign: "right" },
  managementMetricLabel: { color: palette.muted, fontSize: 10, textAlign: "right" },
  reviewButtons: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
});

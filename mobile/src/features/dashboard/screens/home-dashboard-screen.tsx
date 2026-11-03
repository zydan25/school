import { useEffect, useMemo, useState } from "react";
import { router } from "expo-router";
import { Pressable, StyleSheet, View } from "react-native";
import { ActivityIndicator, Button, Text } from "react-native-paper";
import { BookOpen, BriefcaseBusiness, Building2, CalendarDays, ClipboardCheck, GraduationCap, LogOut, RefreshCw, Repeat2, Users } from "lucide-react-native";
import { useQuery } from "@tanstack/react-query";

import { useAuthStore } from "@/core/auth/auth-store";
import type { WorkspaceType } from "@/core/auth/types";
import {
  countStudentsForSection,
  loadDashboardData,
  type GuardianChild,
  type Lesson,
  type StudentSummary,
  type TeacherAssignment,
} from "@/features/dashboard/api/dashboard-api";
import { AppActionTile } from "@/shared/components/app-action-tile";
import { AppAvatar } from "@/shared/components/app-avatar";
import { AppCard } from "@/shared/components/app-card";
import { AppEmptyState } from "@/shared/components/app-empty-state";
import { AppNotice } from "@/shared/components/app-notice";
import { AppScreen } from "@/shared/components/app-screen";
import { AppSectionHeader } from "@/shared/components/app-section-header";
import { getApiErrorMessage } from "@/core/api/api-client";
import { palette, radius, spacing } from "@/core/theme/tokens";

const workspaceLabels: Record<WorkspaceType, string> = {
  student: "الطالب",
  guardian: "ولي الأمر",
  teacher: "المعلم",
  employee: "الموظف",
  management: "الإدارة",
};

const statusLabels: Record<string, string> = {
  active: "نشط",
  graduated: "متخرج",
  withdrawn: "منسحب",
  suspended: "موقوف",
};

export function HomeDashboardScreen() {
  const session = useAuthStore((state) => state.session);
  const logout = useAuthStore((state) => state.logout);
  const hasHydrated = useAuthStore((state) => state.hasHydrated);
  const [selectedChildId, setSelectedChildId] = useState<string | null>(null);

  const schoolId = session?.activeSchoolId;
  const workspace = session?.activeWorkspace;
  const school = session?.schools.find((item) => item.id === schoolId);

  useEffect(() => {
    if (!hasHydrated) return;
    if (!session) router.replace("/login" as never);
    else if (!schoolId) router.replace("/schools" as never);
    else if (!workspace) router.replace("/workspace" as never);
  }, [hasHydrated, session, schoolId, workspace]);
  const dashboardQuery = useQuery({
    queryKey: ["school-dashboard", session?.user.id, session?.sessionId, schoolId, workspace],
    queryFn: () => loadDashboardData(workspace as WorkspaceType),
    enabled: Boolean(session?.accessToken && schoolId && workspace),
    staleTime: 30_000,
  });

  const selectedChild = useMemo(() => {
    const children = dashboardQuery.data?.children ?? [];
    return children.find((child) => child.id === selectedChildId) ?? children[0] ?? null;
  }, [dashboardQuery.data?.children, selectedChildId]);

  if (!session || !schoolId || !workspace) {
    return (
      <AppScreen compact>
        <ActivityIndicator color={palette.secondary} />
        <Text style={styles.mutedCenter}>جارٍ تجهيز مساحة العمل...</Text>
      </AppScreen>
    );
  }

  const fullName = session.user.full_name || session.user.phone;
  const currentWorkspace = workspaceLabels[workspace];

  async function doLogout() {
    try {
      await logout();
    } finally {
      router.replace("/login" as never);
    }
  }

  return (
    <AppScreen>
      <View style={styles.topBar}>
        <View style={styles.identity}>
          <AppAvatar name={fullName} size={44} backgroundColor={palette.primaryTint} />
          <View style={styles.identityText}>
            <Text style={styles.schoolName}>{school?.name ?? "مدرستي"}</Text>
            <Text style={styles.userName}>{fullName}</Text>
            <Text style={styles.workspace}>{currentWorkspace}</Text>
          </View>
        </View>
        <View style={styles.topActions}>
          <Pressable accessibilityRole="button" accessibilityLabel="تغيير مساحة العمل" onPress={() => router.push("/workspace" as never)} style={styles.headerButton}>
            <Repeat2 size={18} color={palette.primary} />
          </Pressable>
          <Pressable accessibilityRole="button" accessibilityLabel="تغيير المدرسة" onPress={() => router.push("/schools" as never)} style={styles.headerButton}>
            <Building2 size={18} color={palette.primary} />
          </Pressable>
          <Pressable accessibilityRole="button" accessibilityLabel="تسجيل الخروج" onPress={() => void doLogout()} style={styles.headerButton}>
            <LogOut size={18} color={palette.danger} />
          </Pressable>
        </View>
      </View>

      <View style={styles.welcome}>
        <Text style={styles.welcomeTitle}>مرحباً بك 👋</Text>
        <Text style={styles.welcomeSubtitle}>هذه بيانات المدرسة المرتبطة بحسابك، وتُحمّل حسب الدور المحدد.</Text>
      </View>

      {dashboardQuery.isLoading ? (
        <View style={styles.loading}>
          <ActivityIndicator color={palette.secondary} size="large" />
          <Text style={styles.mutedCenter}>جارٍ تحميل بياناتك من الخادم...</Text>
        </View>
      ) : dashboardQuery.isError ? (
        <AppCard padding={15}>
          <AppNotice message={getApiErrorMessage(dashboardQuery.error)} />
          <Button mode="outlined" onPress={() => void dashboardQuery.refetch()} icon={RefreshCw} style={styles.retryButton}>إعادة المحاولة</Button>
        </AppCard>
      ) : (
        <>
          {workspace === "guardian" ? (
            <GuardianDashboard
              children={dashboardQuery.data?.children ?? []}
              selectedChild={selectedChild}
              onSelectChild={setSelectedChildId}
              lessons={dashboardQuery.data?.lessons ?? []}
            />
          ) : null}

          {workspace === "student" ? (
            <StudentDashboard
              students={dashboardQuery.data?.students ?? []}
              lessons={dashboardQuery.data?.lessons ?? []}
            />
          ) : null}

          {workspace === "teacher" ? (
            <TeacherDashboard
              assignments={dashboardQuery.data?.assignments ?? []}
              students={dashboardQuery.data?.students ?? []}
              lessons={dashboardQuery.data?.lessons ?? []}
            />
          ) : null}

          {workspace === "employee" ? (
            <EmployeeDashboard staff={dashboardQuery.data?.staff ?? []} />
          ) : null}

          {workspace === "management" ? <ManagementDashboard /> : null}
        </>
      )}

      {["student", "guardian", "teacher"].includes(workspace) ? (
        <View style={styles.academicShortcut}>
          <AppActionTile
            icon={BookOpen}
            label={workspace === "guardian" ? "واجبات ودرجات الأبناء" : "الواجبات والدرجات"}
            onPress={() => router.push("/academics" as never)}
            color={palette.info}
            tint={palette.infoTint}
          />
          <AppActionTile
            icon={ClipboardCheck}
            label="النتائج المنشورة"
            onPress={() => router.push("/academics?tab=grades" as never)}
            color={palette.success}
            tint={palette.successTint}
          />
        </View>
      ) : null}

      <View style={styles.bottomActions}>
        <Button mode="text" compact onPress={() => router.push("/workspace" as never)} textColor={palette.secondary}>تبديل الدور</Button>
        <Button mode="text" compact onPress={() => router.push("/schools" as never)} textColor={palette.secondary}>تبديل المدرسة</Button>
        <Button mode="text" compact onPress={() => void dashboardQuery.refetch()} textColor={palette.muted}>تحديث البيانات</Button>
      </View>
    </AppScreen>
  );
}

function GuardianDashboard({
  children,
  selectedChild,
  onSelectChild,
  lessons,
}: {
  children: GuardianChild[];
  selectedChild: GuardianChild | null;
  onSelectChild: (id: string) => void;
  lessons: Lesson[];
}) {
  return (
    <View style={styles.sectionStack}>
      <AppSectionHeader title="أبنائي" trailing={children.length + " أبناء"} />
      {children.length ? (
        <>
          <View style={styles.childrenGrid}>
            {children.map((child) => {
              const selected = child.id === selectedChild?.id;
              return (
                <Pressable key={child.id} onPress={() => onSelectChild(child.id)}
                  accessibilityRole="button" accessibilityState={{ selected }}
                  style={[styles.childCard, selected && styles.childCardSelected]}>
                  <AppAvatar name={child.name} size={46} backgroundColor={selected ? palette.secondaryTint : palette.primaryTint} />
                  <Text style={styles.childName}>{child.name}</Text>
                  <Text style={styles.childGrade}>{child.grade}</Text>
                  <Text style={styles.childSection}>{child.section}</Text>
                </Pressable>
              );
            })}
          </View>
          {selectedChild ? (
            <AppCard padding={14}>
              <View style={styles.detailHeader}>
                <Text style={styles.cardTitle}>ملف {selectedChild.name}</Text>
                <Text style={styles.status}>{statusLabels[selectedChild.status] ?? selectedChild.status}</Text>
              </View>
              <DetailLine label="الرقم المدرسي" value={selectedChild.student_id_number} />
              <DetailLine label="الصف" value={selectedChild.grade} />
              <DetailLine label="الشعبة" value={selectedChild.section} />
              <DetailLine label="إشعارات ولي الأمر" value={selectedChild.receives_notifications === null ? "غير محدد" : selectedChild.receives_notifications ? "مفعلة" : "غير مفعلة"} />
            </AppCard>
          ) : null}
          <LessonsSection lessons={lessons} title="جداول الأبناء" />
        </>
      ) : (
        <AppEmptyState
          icon={Users}
          title="لا يوجد أبناء مرتبطون بحسابك"
          description="لم يرجع الخادم ملفات أبناء مرتبطة بولي الأمر في المدرسة النشطة. لا يمكن إضافة ابن من التطبيق حالياً؛ يجب أن تنشئ المدرسة العلاقة وتتحقق منها."
        />
      )}
    </View>
  );
}

function StudentDashboard({ students, lessons }: { students: StudentSummary[]; lessons: Lesson[] }) {
  const student = students[0];
  return (
    <View style={styles.sectionStack}>
      <AppSectionHeader title="ملفي الدراسي" trailing={students.length + " ملفات"} />
      {student ? (
        <AppCard padding={15}>
          <View style={styles.studentHeader}>
            <AppAvatar name={student.full_name} size={58} backgroundColor={palette.successTint} />
            <View style={styles.studentTitleBlock}>
              <Text style={styles.cardTitle}>{student.full_name}</Text>
              <Text style={styles.secondaryText}>الرقم المدرسي: {student.student_id_number}</Text>
            </View>
          </View>
          <DetailLine label="الصف" value={student.grade_level_name} />
          <DetailLine label="الشعبة" value={student.section_name} />
          <DetailLine label="السنة الدراسية" value={student.academic_year_name} />
          <DetailLine label="حالة القيد" value={statusLabels[student.status] ?? student.status} />
        </AppCard>
      ) : (
        <AppEmptyState icon={GraduationCap} title="لا يوجد ملف طالب مرتبط" description="دور الطالب موجود، لكن الخادم لم يرجع ملف طالب مرتبطاً بالحساب في هذه المدرسة. تواصل مع شؤون الطلاب لربط الملف." />
      )}
      <LessonsSection lessons={lessons} />
    </View>
  );
}

function TeacherDashboard({
  assignments,
  students,
  lessons,
}: {
  assignments: TeacherAssignment[];
  students: StudentSummary[];
  lessons: Lesson[];
}) {
  return (
    <View style={styles.sectionStack}>
      <View style={styles.statsRow}>
        <MiniStat value={String(assignments.length)} label="الإسنادات" />
        <MiniStat value={String(new Set(assignments.map((item) => item.section).filter(Boolean)).size)} label="الشعب" />
        <MiniStat value={String(new Set(assignments.map((item) => item.subject).filter(Boolean)).size)} label="المواد" />
      </View>
      <AppSectionHeader title="شُعبي المسندة" trailing={assignments.length + " إسنادات"} />
      {assignments.length ? assignments.map((assignment) => {
        const count = countStudentsForSection(students, assignment.section);
        return (
          <AppCard key={assignment.id} padding={14}>
            <View style={styles.assignmentRow}>
              <View style={styles.assignmentMark}><Text style={styles.assignmentInitial}>{(assignment.section_name ?? "ش").slice(0, 1)}</Text></View>
              <View style={styles.assignmentInfo}>
                <Text style={styles.cardTitle}>{assignment.section_name ?? "الشعبة"}</Text>
                <Text style={styles.secondaryText}>{assignment.subject_name ?? "المادة"}</Text>
                {count !== null ? <Text style={styles.mutedText}>طلاب ظاهرون في النتيجة: {count}</Text> : null}
              </View>
            </View>
          </AppCard>
        );
      }) : (
        <AppEmptyState icon={BookOpen} title="لا توجد شعب مسندة" description="لم يرجع الخادم إسنادات دراسية لهذا المعلم في المدرسة النشطة. راجع الإدارة الأكاديمية للتأكد من إسناد الشعب والمواد." />
      )}
      <LessonsSection lessons={lessons} />
    </View>
  );
}

function EmployeeDashboard({ staff }: { staff: { id: string; employee_number?: string; job_title?: string; role?: string }[] }) {
  return (
    <View style={styles.sectionStack}>
      <AppSectionHeader title="ملفي الوظيفي" trailing={staff.length + " ملفات"} />
      {staff.length ? staff.map((item) => (
        <AppCard key={item.id} padding={15}>
          <Text style={styles.cardTitle}>{item.job_title || "موظف"}</Text>
          <DetailLine label="الرقم الوظيفي" value={item.employee_number || "غير محدد"} />
          <DetailLine label="المسمى/الدور" value={item.role || "غير محدد"} />
        </AppCard>
      )) : (
        <AppEmptyState icon={BriefcaseBusiness} title="لا يوجد ملف وظيفي" description="لم يرجع الخادم ملف موظف مرتبطاً بهذه المدرسة لهذا الحساب." />
      )}
    </View>
  );
}

function ManagementDashboard() {
  return (
    <AppCard padding={16}>
      <Text style={styles.cardTitle}>مساحة الإدارة المدرسية</Text>
      <Text style={styles.secondaryText}>
        تم التحقق من دور الإدارة في عضويتك. ستظهر إجراءات الإدارة في وحداتها المخصصة، وستُعرض كل عملية وفق الصلاحيات التي يسمح بها الخادم.
      </Text>
      <AppNotice message="هذه بداية مساحة العمل المتصلة. لم نضع أرقاماً إدارية افتراضية أو نعرض بيانات لم نطلبها من الخادم." />
    </AppCard>
  );
}

function LessonsSection({ lessons, title = "الجدول الدراسي" }: { lessons: Lesson[]; title?: string }) {
  return (
    <View style={styles.sectionStack}>
      <AppSectionHeader title={title} trailing={lessons.length + " حصص"} />
      {lessons.length ? (
        <AppCard padding={4}>
          {lessons.slice(0, 8).map((lesson, index) => (
            <View key={lesson.id} style={[styles.lessonRow, index === Math.min(lessons.length, 8) - 1 && styles.lastLesson]}>
              <View style={styles.lessonTime}>
                <Text style={styles.lessonTimeText}>{String(lesson.start_time).slice(0, 5)}</Text>
              </View>
              <View style={styles.lessonInfo}>
                <Text style={styles.lessonSubject}>{lesson.subject}</Text>
                <Text style={styles.lessonMeta}>{lesson.teacher} · {lesson.section}{lesson.classroom ? " · " + lesson.classroom : ""}</Text>
              </View>
              <Text style={styles.lessonPeriod}>حصة {lesson.period_number}</Text>
            </View>
          ))}
        </AppCard>
      ) : (
        <AppEmptyState icon={CalendarDays} title="لا توجد حصص في الجدول" description="لم يرجع الخادم حصصاً لهذا الملف وفق الجدول الفعال. قد يكون الجدول غير منشور أو لا توجد حصص لليوم." />
      )}
    </View>
  );
}

function DetailLine({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.detailLine}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text style={styles.detailValue}>{value || "—"}</Text>
    </View>
  );
}

function MiniStat({ value, label }: { value: string; label: string }) {
  return (
    <View style={styles.miniStat}>
      <Text style={styles.miniStatValue}>{value}</Text>
      <Text style={styles.miniStatLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  mutedCenter: { color: palette.muted, textAlign: "center", fontSize: 12 },
  topBar: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm },
  identity: { flex: 1, flexDirection: "row", alignItems: "center", gap: spacing.sm },
  identityText: { flex: 1, alignItems: "flex-start", gap: 2 },
  schoolName: { color: palette.primary, fontSize: 13, fontWeight: "800", textAlign: "right" },
  userName: { color: palette.text, fontSize: 11, textAlign: "right" },
  workspace: { color: palette.secondary, fontSize: 10, fontWeight: "700" },
  topActions: { flexDirection: "row", gap: 5 },
  headerButton: { width: 36, height: 36, borderRadius: 12, borderWidth: 1, borderColor: palette.border, backgroundColor: palette.surface, alignItems: "center", justifyContent: "center" },
  welcome: { paddingVertical: spacing.sm, gap: 4 },
  welcomeTitle: { color: palette.primary, fontSize: 21, fontWeight: "900", textAlign: "right" },
  welcomeSubtitle: { color: palette.muted, fontSize: 11, lineHeight: 17, textAlign: "right" },
  loading: { alignItems: "center", gap: spacing.sm, paddingVertical: spacing.xxl },
  retryButton: { marginTop: spacing.sm, borderColor: palette.secondary },
  sectionStack: { gap: spacing.md },
  childrenGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  childCard: { width: "30%", minWidth: 88, flexGrow: 1, alignItems: "center", gap: 4, padding: spacing.sm, borderRadius: radius.md, backgroundColor: palette.surface, borderWidth: 1, borderColor: palette.border },
  childCardSelected: { borderColor: palette.secondary, backgroundColor: palette.surfaceSoft },
  childName: { color: palette.primary, fontSize: 12, fontWeight: "800" },
  childGrade: { color: palette.muted, fontSize: 10 },
  childSection: { color: palette.secondary, fontSize: 10 },
  detailHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: spacing.sm, marginBottom: spacing.sm },
  cardTitle: { color: palette.primary, fontSize: 14, fontWeight: "800", textAlign: "right" },
  status: { color: palette.success, fontSize: 10, fontWeight: "700" },
  detailLine: { flexDirection: "row", justifyContent: "space-between", gap: spacing.md, paddingVertical: 7, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: palette.border },
  detailLabel: { color: palette.muted, fontSize: 11 },
  detailValue: { color: palette.text, fontSize: 11, fontWeight: "700", textAlign: "left", flexShrink: 1 },
  studentHeader: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingBottom: spacing.sm },
  studentTitleBlock: { flex: 1, alignItems: "flex-start", gap: 3 },
  secondaryText: { color: palette.secondary, fontSize: 11, lineHeight: 18, textAlign: "right" },
  mutedText: { color: palette.muted, fontSize: 10 },
  statsRow: { flexDirection: "row", gap: spacing.sm },
  miniStat: { flex: 1, alignItems: "center", gap: 4, paddingVertical: 12, borderRadius: radius.md, backgroundColor: palette.surface, borderWidth: 1, borderColor: palette.border },
  miniStatValue: { color: palette.primary, fontWeight: "900", fontSize: 19 },
  miniStatLabel: { color: palette.muted, fontSize: 10 },
  assignmentRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  assignmentMark: { width: 44, height: 44, borderRadius: 14, backgroundColor: palette.secondaryTint, alignItems: "center", justifyContent: "center" },
  assignmentInitial: { color: palette.primary, fontSize: 18, fontWeight: "900" },
  assignmentInfo: { flex: 1, alignItems: "flex-start", gap: 3 },
  lessonRow: { minHeight: 65, flexDirection: "row", alignItems: "center", gap: spacing.sm, paddingHorizontal: spacing.sm, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: palette.border },
  lastLesson: { borderBottomWidth: 0 },
  lessonTime: { paddingVertical: 7, paddingHorizontal: 8, borderRadius: 9, backgroundColor: palette.primaryTint },
  lessonTimeText: { color: palette.info, fontWeight: "800", fontSize: 11 },
  lessonInfo: { flex: 1, alignItems: "flex-start", gap: 3 },
  lessonSubject: { color: palette.primary, fontWeight: "800", fontSize: 12, textAlign: "right" },
  lessonMeta: { color: palette.muted, fontSize: 10, textAlign: "right", lineHeight: 15 },
  lessonPeriod: { color: palette.muted, fontSize: 9 },
  academicShortcut: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  bottomActions: { flexDirection: "row", flexWrap: "wrap", justifyContent: "center", gap: spacing.xs, paddingTop: spacing.sm },
});

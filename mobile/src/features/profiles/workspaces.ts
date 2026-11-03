import type { AuthSession, ProfileCollection, WorkspaceType } from "@/core/auth/types";

export type WorkspaceOption = {
  type: WorkspaceType;
  title: string;
  description: string;
  count?: number;
};

const MANAGEMENT_ROLES = new Set([
  "admin", "school-admin", "school_admin", "school-director", "school_director",
  "principal", "school-principal", "academic-coordinator", "academic_coordinator",
  "academic-head", "academic_head", "exam-controller", "exam_controller",
  "student-affairs", "student_affairs", "accountant", "school-accountant",
  "school_accountant", "hr", "hr-manager", "hr_manager", "librarian",
  "store-keeper", "store_keeper", "inventory-manager", "inventory_manager",
  "gate-security", "gate_security", "school-gate-guard",
]);

export function buildWorkspaceOptions(
  session: AuthSession,
  profiles: ProfileCollection,
): WorkspaceOption[] {
  const school = session.schools.find((item) => item.id === session.activeSchoolId);
  const roles = new Set(school?.roles ?? []);
  const options: WorkspaceOption[] = [];

  if (roles.has("student") && profiles.students.length) {
    options.push({
      type: "student",
      title: "مساحة الطالب",
      description: profiles.students.length > 1
        ? profiles.students.length + " ملفات طلاب مرتبطة بالحساب"
        : profiles.students[0].full_name,
      count: profiles.students.length,
    });
  }

  if (roles.has("guardian") && profiles.guardians.length) {
    options.push({
      type: "guardian",
      title: "مساحة ولي الأمر",
      description: profiles.guardians.length > 1
        ? profiles.guardians.length + " ملفات أولياء أمور مرتبطة بالحساب"
        : "متابعة الأبناء والخدمات الأسرية",
      count: profiles.guardians.length,
    });
  }

  if (roles.has("teacher") && profiles.teachers.length) {
    options.push({
      type: "teacher",
      title: "مساحة المعلم",
      description: profiles.teachers.length > 1
        ? profiles.teachers.length + " ملفات معلمين مرتبطة بالحساب"
        : profiles.teachers[0].specialization || "الشعب والإسنادات والجدول",
      count: profiles.teachers.length,
    });
  }

  if (profiles.staff.length) {
    options.push({
      type: "employee",
      title: "مساحة الموظف",
      description: profiles.staff[0].job_title || "الخدمات الوظيفية",
      count: profiles.staff.length,
    });
  }

  if (session.user.is_platform_admin || Array.from(roles).some((role) => MANAGEMENT_ROLES.has(role))) {
    options.push({
      type: "management",
      title: "مساحة الإدارة",
      description: "الإدارة المدرسية والخدمات المسموح بها حسب صلاحياتك",
    });
  }

  return options;
}

import { ApiError } from "@/core/api/api-client";
import { authenticatedRequest } from "@/core/api/authenticated-request";
import type { ApiPage } from "@/core/api/api-response";
import { getMyProfiles } from "@/features/profiles/api/profiles-api";
import type { ProfileCollection, WorkspaceType } from "@/core/auth/types";

export type GuardianChild = {
  id: string;
  student_id_number: string;
  name: string;
  grade: string;
  section: string;
  status: string;
  receives_notifications: boolean | null;
  can_pickup: boolean | null;
};

export type StudentSummary = {
  id: string;
  student_id_number: string;
  full_name: string;
  grade_level_name: string;
  section_name: string;
  section: string;
  academic_year_name: string;
  status: string;
};

export type TeacherAssignment = {
  id: string;
  teacher?: string;
  subject?: string;
  section?: string;
  academic_year?: string;
  teacher_name?: string;
  subject_name?: string;
  section_name?: string;
};

export type Lesson = {
  id: string;
  day_of_week: number;
  period_number: number;
  start_time: string;
  end_time: string;
  subject: string;
  section: string;
  section_id: string;
  teacher: string;
  classroom?: string | null;
};

export type StaffProfile = ProfileCollection["staff"][number];

export type DashboardData = {
  children?: GuardianChild[];
  students?: StudentSummary[];
  assignments?: TeacherAssignment[];
  lessons?: Lesson[];
  profiles?: ProfileCollection;
  staff?: StaffProfile[];
};

type GuardianChildrenResponse = { guardian_id: string; results: GuardianChild[] };
type ListResponse<T> = T[] | ApiPage<T>;

const MAX_LIST_PAGES = 50;

async function getList<T>(path: string): Promise<T[]> {
  const configuredBase = process.env.EXPO_PUBLIC_API_BASE_URL?.trim();
  if (!configuredBase) {
    throw new Error("عنوان الخادم غير مضبوط.");
  }

  const normalizedBase = configuredBase.endsWith("/")
    ? configuredBase
    : configuredBase + "/";
  const baseUrl = new URL(normalizedBase);
  let pageUrl = new URL(path.replace(/^\/+/, ""), normalizedBase);
  const results: T[] = [];

  for (let page = 0; page < MAX_LIST_PAGES && pageUrl; page += 1) {
    if (
      pageUrl.origin !== baseUrl.origin ||
      !pageUrl.pathname.startsWith(baseUrl.pathname)
    ) {
      throw new Error("رفض التطبيق رابط صفحة خارج نطاق API المدرسة.");
    }

    const response = await authenticatedRequest<ListResponse<T>>(pageUrl.toString());
    if (Array.isArray(response)) {
      results.push(...response);
      return results;
    }

    results.push(...response.results);
    if (!response.next) return results;

    pageUrl = new URL(response.next, pageUrl);
  }

  if (pageUrl) {
    throw new Error("قائمة الخادم تحتوي على صفحات أكثر من الحد المسموح للتحميل.");
  }

  return results;
}

async function getLessons(profileType: "student" | "teacher" | "guardian") {
  try {
    return await authenticatedRequest<Lesson[]>(
      "app/my/timetable/?profile_type=" + profileType,
    );
  } catch (error) {
    // A role can be valid before a timetable is published or while an
    // assignment is inactive. Keep the profile dashboard usable in that case.
    if (error instanceof ApiError && [403, 404].includes(error.status)) {
      return [];
    }
    throw error;
  }
}

export async function loadDashboardData(workspace: WorkspaceType): Promise<DashboardData> {
  if (workspace === "guardian") {
    const [children, lessons] = await Promise.all([
      authenticatedRequest<GuardianChildrenResponse>("app/my/children/"),
      getLessons("guardian"),
    ]);
    return { children: children.results ?? [], lessons };
  }

  if (workspace === "student") {
    const [students, lessons] = await Promise.all([
      getList<StudentSummary>("students/"),
      getLessons("student"),
    ]);
    return { students, lessons };
  }

  if (workspace === "teacher") {
    const [assignments, lessons] = await Promise.all([
      getList<TeacherAssignment>("app/teacher-assignments/"),
      getLessons("teacher"),
    ]);
    // A teacher without active assignments must still see the proper empty
    // state; the student endpoint is intentionally not queried in that case.
    const students = assignments.length
      ? await getList<StudentSummary>("students/")
      : [];
    return { assignments, students, lessons };
  }

  if (workspace === "employee") {
    const profiles = await getMyProfiles();
    return { profiles, staff: profiles.staff };
  }

  const profiles = await getMyProfiles();
  return { profiles };
}

export function countStudentsForSection(
  students: StudentSummary[] | undefined,
  sectionId: string | undefined,
): number | null {
  if (!students || !sectionId) return null;
  return students.filter((student) => student.section === sectionId).length;
}

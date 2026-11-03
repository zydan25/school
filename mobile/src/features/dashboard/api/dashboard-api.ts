import { authenticatedRequest } from "@/core/api/authenticated-request";
import { toResults, type ApiPage } from "@/core/api/api-response";
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

async function getList<T>(path: string): Promise<T[]> {
  const response = await authenticatedRequest<ListResponse<T>>(path);
  return toResults(response);
}

async function getLessons(profileType: "student" | "teacher" | "guardian") {
  return authenticatedRequest<Lesson[]>(
    "app/my/timetable/?profile_type=" + profileType,
  );
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
    const [assignments, students, lessons] = await Promise.all([
      getList<TeacherAssignment>("app/teacher-assignments/"),
      getList<StudentSummary>("students/"),
      getLessons("teacher"),
    ]);
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

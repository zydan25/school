import { authenticatedRequest } from "@/core/api/authenticated-request";
import { authenticatedListRequest } from "@/core/api/paginated-request";
import { getMyProfiles } from "@/features/profiles/api/profiles-api";
import type { WorkspaceType } from "@/core/auth/types";

export type HomeworkItem = {
  id: string;
  subject: string;
  subject_name: string;
  section: string;
  section_name: string;
  teacher: string;
  teacher_name: string;
  title: string;
  description: string;
  assigned_date: string;
  due_date: string;
  max_score: string | number;
  is_active: boolean;
};

export type HomeworkSubmission = {
  id: string;
  homework: string;
  student: string;
  student_name: string;
  submission_text: string;
  attachment_name: string;
  attachment_available: boolean;
  submitted_at: string;
  status: "submitted" | "late" | "graded" | "resubmit" | string;
  score: string | number | null;
  teacher_feedback: string;
  graded_at: string | null;
  attempts: {
    id: string;
    attempt_number: number;
    submission_text: string;
    attachment_name: string;
    submitted_at: string;
    status: string;
  }[];
};

export type GradeRecord = {
  id: string;
  student: string;
  student_name: string;
  subject: string;
  subject_name: string;
  academic_term: string | null;
  academic_term_name: string | null;
  assessment_type: string | null;
  homework: string | null;
  assessment_title: string;
  score: string | number;
  max_score: string | number;
  teacher_feedback: string;
  graded_at: string | null;
  workflow_status: "draft" | "submitted" | "approved" | "published" | string;
  is_published: boolean;
};

type StudentProfileSummary = {
  id: string;
  section: string;
  full_name: string;
};

type GuardianChildrenResponse = {
  guardian_id: string;
  results: { id: string }[];
};

type TeacherAssignmentSummary = {
  id: string;
  section: string;
  subject: string;
  teacher: string;
};

export type AcademicWorkspaceData = {
  homeworks: HomeworkItem[];
  submissions: HomeworkSubmission[];
  grades: GradeRecord[];
};

async function fetchAllAcademicRecords() {
  return Promise.all([
    authenticatedListRequest<HomeworkItem>("app/homework/"),
    authenticatedListRequest<HomeworkSubmission>("app/homework-submissions/"),
    authenticatedListRequest<GradeRecord>("app/gradebook/"),
  ]);
}

function onlyPublishedGrades(grades: GradeRecord[]) {
  return grades.filter(
    (item) => item.is_published && item.workflow_status === "published",
  );
}

export async function loadAcademicWorkspaceData(
  workspace: WorkspaceType,
): Promise<AcademicWorkspaceData> {
  const [homeworks, submissions, grades] = await fetchAllAcademicRecords();

  if (workspace === "student") {
    const profiles = await getMyProfiles();
    const ownStudent = profiles.students[0];
    if (!ownStudent) {
      return { homeworks: [], submissions: [], grades: [] };
    }

    // Read APIs can union results for every role on a multi-role account.
    // Keep this student workspace scoped to the exact linked student file.
    return {
      homeworks: homeworks.filter((item) => item.section === ownStudent.section_id),
      submissions: submissions.filter((item) => item.student === ownStudent.id),
      grades: onlyPublishedGrades(grades).filter((item) => item.student === ownStudent.id),
    };
  }

  if (workspace === "guardian") {
    const children = await authenticatedRequest<GuardianChildrenResponse>(
      "app/my/children/",
    );
    const childIds = new Set(children.results.map((child) => child.id));

    // The guardian-children response intentionally omits section IDs. Fetch
    // each linked child using the API's guardian-scoped detail permission so
    // homework lists can be restricted to the actual children, even when the
    // same account is also a student or teacher.
    const childProfiles = await Promise.all(
      children.results.map((child) =>
        authenticatedRequest<StudentProfileSummary>(
          "students/" + encodeURIComponent(child.id) + "/",
        ),
      ),
    );
    const sectionIds = new Set(childProfiles.map((child) => child.section));

    return {
      homeworks: homeworks.filter((item) => sectionIds.has(item.section)),
      submissions: submissions.filter((item) => childIds.has(item.student)),
      grades: onlyPublishedGrades(grades).filter((item) => childIds.has(item.student)),
    };
  }

  if (workspace === "teacher") {
    const profiles = await getMyProfiles();
    const teacher = profiles.teachers[0];
    if (!teacher) return { homeworks: [], submissions: [], grades: [] };

    const assignments = await authenticatedListRequest<TeacherAssignmentSummary>(
      "app/teacher-assignments/",
    );
    const assignmentPairs = new Set(
      assignments.map((item) => item.section + ":" + item.subject),
    );
    const sectionIds = new Set(assignments.map((item) => item.section));
    const teacherStudents = await authenticatedListRequest<StudentProfileSummary>(
      "students/",
    );
    const teacherStudentIds = new Set(
      teacherStudents
        .filter((student) => sectionIds.has(student.section))
        .map((student) => student.id),
    );
    const studentSections = new Map(
      teacherStudents.map((student) => [student.id, student.section]),
    );

    return {
      homeworks: homeworks.filter((item) => item.teacher === teacher.id),
      submissions: submissions.filter((item) => teacherStudentIds.has(item.student)),
      grades: grades.filter((item) => {
        const sectionId = studentSections.get(item.student);
        return Boolean(
          sectionId &&
          teacherStudentIds.has(item.student) &&
          assignmentPairs.has(sectionId + ":" + item.subject),
        );
      }),
    };
  }

  if (workspace === "management") {
    return { homeworks, submissions, grades };
  }

  return { homeworks: [], submissions: [], grades: [] };
}

export async function submitHomework(
  homeworkId: string,
  submissionText: string,
): Promise<HomeworkSubmission> {
  const form = new FormData();
  form.append("homework_id", homeworkId);
  form.append("submission_text", submissionText);

  return authenticatedRequest<HomeworkSubmission>(
    "app/homework-submissions/submit/",
    { method: "POST", body: form },
  );
}

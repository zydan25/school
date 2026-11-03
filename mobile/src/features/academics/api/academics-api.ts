import { authenticatedRequest } from "@/core/api/authenticated-request";
import { authenticatedListRequest } from "@/core/api/paginated-request";
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

export type AcademicWorkspaceData = {
  homeworks: HomeworkItem[];
  submissions: HomeworkSubmission[];
  grades: GradeRecord[];
};

export async function loadAcademicWorkspaceData(
  workspace: WorkspaceType,
): Promise<AcademicWorkspaceData> {
  const [homeworks, submissions, grades] = await Promise.all([
    authenticatedListRequest<HomeworkItem>("app/homework/"),
    authenticatedListRequest<HomeworkSubmission>("app/homework-submissions/"),
    authenticatedListRequest<GradeRecord>("app/gradebook/"),
  ]);

  // The API enforces the actual visibility rules for each role. The extra
  // filters below ensure guardian/student UI only renders records tied to
  // their own linked profile IDs even when multiple roles coexist.
  if (workspace === "student") {
    return {
      homeworks,
      submissions,
      grades: grades.filter((item) => item.is_published && item.workflow_status === "published"),
    };
  }

  if (workspace === "guardian") {
    const profiles = await authenticatedRequest<{
      guardians: { id: string }[];
      students: { id: string }[];
    }>("app/account/profiles/");
    const children = await authenticatedRequest<{
      guardian_id: string;
      results: { id: string }[];
    }>("app/my/children/");
    const childIds = new Set(children.results.map((child) => child.id));
    return {
      homeworks,
      submissions: submissions.filter((item) => childIds.has(item.student)),
      grades: grades.filter(
        (item) => childIds.has(item.student) && item.is_published && item.workflow_status === "published",
      ),
    };
  }

  return { homeworks, submissions, grades };
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

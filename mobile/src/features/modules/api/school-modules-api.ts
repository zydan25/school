import { authenticatedRequest } from "@/core/api/authenticated-request";
import { toResults, type ApiPage } from "@/core/api/api-response";
import type { WorkspaceType } from "@/core/auth/types";

export type AttendanceRow = {
  id: string;
  student_id: string;
  student_name: string;
  section: string;
  date: string;
  session_type: string;
  status: string;
  late_minutes: number;
  notes: string;
  recorded_at?: string | null;
};

export type AttendanceResponse = {
  children: { id: string; student_number: string; name: string; section?: string | null }[];
  results: AttendanceRow[];
  count: number;
};

export type AttendanceScore = {
  id: string;
  student_id: string;
  student_name: string;
  academic_term_id: string;
  academic_term: string;
  subject_id?: string | null;
  subject?: string | null;
  raw_score: string;
  unexcused_absence_count: number;
  excused_absence_count: number;
  late_count: number;
  deduction_total: string;
  final_score: string;
  calculated_at?: string | null;
};

export type AttendanceExcuse = {
  id: string;
  student: string;
  student_name: string;
  request_type: string;
  start_date: string;
  end_date: string;
  reason: string;
  status: string;
  review_notes: string;
  created_at: string;
};

export type HomeworkItem = {
  id: string;
  title: string;
  description: string;
  subject: string;
  subject_name?: string;
  section: string;
  section_name?: string;
  teacher_name?: string;
  assigned_date: string;
  due_date: string;
  max_score: string;
  is_active: boolean;
};

export type HomeworkAttempt = {
  id: string;
  attempt_number: number;
  submission_text: string;
  attachment_name: string;
  submitted_at: string;
  status: string;
};

export type HomeworkSubmission = {
  id: string;
  homework: string;
  student: string;
  student_name: string;
  submission_text: string;
  attachment_name?: string;
  attachment_available?: boolean;
  submitted_at: string;
  status: string;
  score?: string | null;
  teacher_feedback: string;
  attempts: HomeworkAttempt[];
};

export type GradeEntry = {
  id: string;
  student: string;
  student_name?: string;
  subject: string;
  subject_name?: string;
  academic_term: string;
  academic_term_name?: string;
  assessment_type?: string | null;
  score: string;
  max_score: string;
  graded_at?: string | null;
  workflow_status: string;
  is_published: boolean;
};

export type OnlineExam = {
  id: string;
  title: string;
  subject: string;
  subject_name: string;
  academic_term: string;
  grade_level: string;
  section?: string | null;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  total_marks: string;
  passing_marks: string;
  instructions: string;
  is_published: boolean;
};

export type ExamQuestion = {
  id: string;
  question_text: string;
  question_type: "mcq" | "true_false" | "short_answer" | "essay" | string;
  difficulty?: string;
  default_marks: string;
  options_json: { id: string; text: string }[];
};

export type ExamPaper = {
  exam: {
    id: string;
    title: string;
    duration_minutes: number;
    start_time: string;
    end_time: string;
    total_marks: string;
    instructions: string;
  };
  questions: ExamQuestion[];
};

export type ExamStartResult = {
  submission_id: string;
  started_at: string;
  status: string;
  deadline: string;
  reconnected: boolean;
};

export type FeeStatement = {
  student: {
    id: string;
    student_id_number: string;
    name: string;
    credit_balance: string | number;
  };
  as_of: string;
  summary: {
    total_invoiced: string | number;
    total_discounts: string | number;
    total_paid: string | number;
    total_due: string | number;
    credit_balance: string | number;
    credit_ledger_balance: string | number;
    credit_balance_matches_ledger: boolean;
  };
  aging: Record<string, string | number>;
  invoices: {
    id: string;
    invoice_number: string;
    academic_year_name: string;
    issue_date: string;
    due_date: string;
    total_amount: string | number;
    discount_amount: string | number;
    paid_amount: string | number;
    remaining_balance: string | number;
    status: string;
  }[];
  receipts: {
    id: string;
    receipt_number: string;
    invoice_number?: string | null;
    amount: string | number;
    payment_method_display: string;
    paid_at: string;
    is_cancelled: boolean;
  }[];
  installment_plans: {
    id: string;
    plan_name: string;
    total_amount: string | number;
    installments: {
      id: string;
      installment_number: number;
      title: string;
      due_date: string;
      amount: string | number;
      paid_amount: string | number;
      remaining_amount: string | number;
      status: string;
    }[];
  }[];
  credit_transactions: {
    id: string;
    transaction_type: string;
    transaction_type_display: string;
    amount: string | number;
    balance_before: string | number;
    balance_after: string | number;
    is_reversed: boolean;
    created_at: string;
    notes: string;
  }[];
};

export type UserNotification = {
  id: string;
  title: string;
  body: string;
  category: string;
  channel: string;
  action_url: string;
  is_read: boolean;
  created_at: string;
  read_at?: string | null;
};

export type NotificationsResponse = {
  unread_count: number;
  notifications: UserNotification[];
};

export type Conversation = {
  id: string;
  subject: string;
  conversation_type: string;
  student?: string | null;
  status: "open" | "closed" | string;
  last_message_at?: string | null;
  unread_count: number;
  created_at: string;
  participants: {
    id: string;
    user: string;
    user_name: string;
    phone: string;
    role: string;
    is_active: boolean;
    is_muted: boolean;
    last_read_at?: string | null;
  }[];
};

export type ConversationMessage = {
  id: string;
  conversation: string;
  sender: string | null;
  sender_name: string;
  message_type: string;
  body: string;
  attachment_available: boolean;
  attachment_name: string;
  attachment_size: number;
  reply_to?: string | null;
  created_at: string;
  edited_at?: string | null;
  is_deleted: boolean;
};

export type ConversationMessagesResponse = {
  results: ConversationMessage[];
  has_more: boolean;
};

type ListResult<T> = T[] | ApiPage<T>;

export async function getAttendanceRecords(studentId?: string) {
  const query = studentId ? "?student_id=" + encodeURIComponent(studentId) : "";
  return authenticatedRequest<AttendanceResponse>("attendance/me/children/records/" + query);
}

export async function getAttendanceScores(studentId?: string) {
  const query = studentId ? "?student_id=" + encodeURIComponent(studentId) : "";
  return authenticatedRequest<{ results: AttendanceScore[]; count: number }>(
    "attendance/me/children/scores/" + query,
  );
}

export async function getAttendanceExcuses() {
  const result = await authenticatedRequest<ListResult<AttendanceExcuse>>(
    "attendance/excuses/",
  );
  return toResults(result);
}

export async function createAttendanceExcuse(input: {
  student: string;
  request_type: string;
  start_date: string;
  end_date: string;
  reason: string;
}) {
  return authenticatedRequest<AttendanceExcuse>("attendance/excuses/", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function getHomeworkList() {
  const result = await authenticatedRequest<ListResult<HomeworkItem>>("app/homework/");
  return toResults(result);
}

export async function getHomeworkSubmissions(homeworkId?: string) {
  const query = homeworkId ? "?homework_id=" + encodeURIComponent(homeworkId) : "";
  const result = await authenticatedRequest<ListResult<HomeworkSubmission>>(
    "app/homework-submissions/" + query,
  );
  return toResults(result);
}

export async function submitHomework(homeworkId: string, submissionText: string) {
  return authenticatedRequest<HomeworkSubmission>("app/homework-submissions/submit/", {
    method: "POST",
    body: JSON.stringify({ homework_id: homeworkId, submission_text: submissionText }),
  });
}

export async function gradeHomework(submissionId: string, score: string, feedback: string) {
  return authenticatedRequest<HomeworkSubmission>(
    "app/homework-submissions/" + submissionId + "/grade/",
    { method: "POST", body: JSON.stringify({ score, teacher_feedback: feedback }) },
  );
}

export async function requestHomeworkResubmission(submissionId: string, reason: string) {
  return authenticatedRequest<HomeworkSubmission>(
    "app/homework-submissions/" + submissionId + "/request-resubmission/",
    { method: "POST", body: JSON.stringify({ reason }) },
  );
}

export async function getGradeEntries() {
  const result = await authenticatedRequest<ListResult<GradeEntry>>("app/gradebook/");
  return toResults(result);
}

export async function getOnlineExams() {
  const result = await authenticatedRequest<ListResult<OnlineExam>>("app/online-exams/");
  return toResults(result);
}

export async function getExamPaper(examId: string) {
  return authenticatedRequest<ExamPaper>("app/online-exams/" + examId + "/paper/");
}

export async function startOnlineExam(examId: string) {
  return authenticatedRequest<ExamStartResult>(
    "app/online-exams/" + examId + "/start/",
    { method: "POST", body: JSON.stringify({}) },
  );
}

export async function submitOnlineExam(examId: string, answers: Record<string, string>) {
  return authenticatedRequest<{ submission_id: string; status: string; auto_score: string }>(
    "app/online-exams/" + examId + "/submit/",
    { method: "POST", body: JSON.stringify({ answers }) },
  );
}

export async function getFeeStatement(studentId: string) {
  return authenticatedRequest<FeeStatement>(
    "fees/students/" + encodeURIComponent(studentId) + "/statement/",
  );
}

export async function getUserNotifications() {
  return authenticatedRequest<NotificationsResponse>("notifications/");
}

export async function markNotificationRead(notificationId: string) {
  return authenticatedRequest<{ status: string; id: string; is_read: boolean }>(
    "notifications/" + notificationId + "/read/",
    { method: "POST", body: JSON.stringify({}) },
  );
}

export async function markAllNotificationsRead() {
  return authenticatedRequest<{ status: string; marked_read_count: number }>(
    "notifications/",
    { method: "POST", body: JSON.stringify({}) },
  );
}

export async function getConversations() {
  const result = await authenticatedRequest<ListResult<Conversation>>("app/conversations/");
  return toResults(result);
}

export async function getConversationMessages(conversationId: string) {
  return authenticatedRequest<ConversationMessagesResponse>(
    "app/conversations/" + conversationId + "/messages/",
  );
}

export async function sendConversationMessage(conversationId: string, body: string) {
  return authenticatedRequest<ConversationMessage>(
    "app/conversations/" + conversationId + "/messages/",
    { method: "POST", body: JSON.stringify({ body }) },
  );
}

export async function markConversationRead(conversationId: string) {
  return authenticatedRequest<{ conversation_id: string; last_read_at: string }>(
    "app/conversations/" + conversationId + "/read/",
    { method: "POST", body: JSON.stringify({}) },
  );
}

export async function setConversationMuted(conversationId: string, muted: boolean) {
  return authenticatedRequest<{ conversation_id: string; is_muted: boolean }>(
    "app/conversations/" + conversationId + "/mute/",
    { method: "POST", body: JSON.stringify({ muted }) },
  );
}


export type TeacherAttendanceAssignment = {
  id: string;
  section: string;
  section_name: string;
  subject: string;
  subject_name: string;
  academic_year: string;
  academic_year_name: string;
};

export type AttendanceStatusOption = {
  id: string;
  code: string;
  name: string;
  category: string;
  color_code: string;
  is_active: boolean;
  display_order: number;
};

export type AttendanceRegister = {
  id: string;
  academic_year: string;
  section: string;
  section_name: string;
  date: string;
  session_type: string;
  status: string;
  student_records: {
    id: string;
    student: string;
    student_name: string;
    student_id_number: string;
    status_category: string;
    late_minutes: number;
    notes: string;
  }[];
};

export type AttendanceStudent = {
  id: string;
  student_id_number: string;
  full_name: string;
  section: string;
  section_name: string;
};

export async function getTeacherAssignmentsForAttendance() {
  const result = await authenticatedRequest<ListResult<TeacherAttendanceAssignment>>(
    "app/teacher-assignments/",
  );
  return toResults(result);
}

export async function getAttendanceStatusTypes() {
  const result = await authenticatedRequest<ListResult<AttendanceStatusOption>>(
    "attendance/status-types/",
  );
  return toResults(result).filter((status) => status.is_active);
}

export async function getStudentsForAttendance(sectionId: string, academicYearId: string) {
  const query =
    "?section=" + encodeURIComponent(sectionId) +
    "&academic_year=" + encodeURIComponent(academicYearId);
  const result = await authenticatedRequest<ListResult<AttendanceStudent>>("students/" + query);
  return toResults(result);
}

export async function getAttendanceRegister(sectionId: string, date: string) {
  const query = "?section_id=" + encodeURIComponent(sectionId) + "&date=" + encodeURIComponent(date);
  const result = await authenticatedRequest<ListResult<AttendanceRegister>>(
    "attendance/registers/" + query,
  );
  return toResults(result)[0] ?? null;
}

export async function openAttendanceRegister(
  academicYearId: string,
  sectionId: string,
  date: string,
) {
  return authenticatedRequest<AttendanceRegister>("attendance/registers/open/", {
    method: "POST",
    body: JSON.stringify({
      academic_year_id: academicYearId,
      section_id: sectionId,
      date,
      session_type: "daily_morning",
    }),
  });
}

export async function recordAttendanceBulk(
  registerId: string,
  records: { student_id: string; status_category: string; late_minutes?: number; notes?: string }[],
) {
  return authenticatedRequest<{ message: string; updated_records: number }>(
    "attendance/registers/" + registerId + "/bulk-record/",
    { method: "POST", body: JSON.stringify({ records }) },
  );
}

export async function submitAttendanceRegister(registerId: string) {
  return authenticatedRequest<AttendanceRegister>(
    "attendance/registers/" + registerId + "/submit/",
    { method: "POST", body: JSON.stringify({}) },
  );
}

export function workspaceSupportsAcademicModules(workspace: WorkspaceType) {
  return ["student", "guardian", "teacher", "management"].includes(workspace);
}

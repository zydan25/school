import { authenticatedRequest } from "@/core/api/authenticated-request";
import { authenticatedListRequest } from "@/core/api/paginated-request";

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
  guardian?: string;
  guardian_name?: string;
  request_type: string;
  start_date: string;
  end_date: string;
  reason: string;
  attachment?: string | null;
  status: string;
  review_notes: string;
  created_at: string;
  reviewed_at?: string | null;
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
    number_of_installments: number;
    installments: {
      id: string;
      installment_number: number;
      title: string;
      due_date: string;
      amount: string | number;
      paid_amount: string | number;
      remaining_amount: string | number;
      status: string;
      paid_date?: string | null;
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

export type NotificationPreference = {
  id: string;
  school: string | null;
  category: string;
  channel: string;
  is_enabled: boolean;
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
  counts_as_present: boolean;
  counts_as_absent: boolean;
  is_excused: boolean;
  is_default: boolean;
  is_active: boolean;
  display_order: number;
};

export type AttendanceRegister = {
  id: string;
  academic_year: string;
  academic_term?: string | null;
  section: string;
  section_name: string;
  grade_name?: string;
  date: string;
  session_type: string;
  status: "open" | "submitted" | "approved" | "locked" | string;
  submitted_at?: string | null;
  approved_at?: string | null;
  locked_at?: string | null;
  student_records: {
    id: string;
    student: string;
    student_name: string;
    student_id_number: string;
    status_type: string | null;
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

export async function getAttendanceExcuses(status?: string) {
  const query = status ? "?status=" + encodeURIComponent(status) : "";
  return authenticatedListRequest<AttendanceExcuse>("attendance/excuses/" + query);
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

export async function getOnlineExams() {
  return authenticatedListRequest<OnlineExam>("app/online-exams/");
}

export async function getExamPaper(examId: string) {
  return authenticatedRequest<ExamPaper>("app/online-exams/" + encodeURIComponent(examId) + "/paper/");
}

export async function startOnlineExam(examId: string) {
  return authenticatedRequest<ExamStartResult>(
    "app/online-exams/" + encodeURIComponent(examId) + "/start/",
    { method: "POST", body: JSON.stringify({}) },
  );
}

export async function submitOnlineExam(examId: string, answers: Record<string, string>) {
  return authenticatedRequest<{ submission_id: string; status: string; auto_score: string }>(
    "app/online-exams/" + encodeURIComponent(examId) + "/submit/",
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
    "notifications/" + encodeURIComponent(notificationId) + "/read/",
    { method: "POST", body: JSON.stringify({}) },
  );
}

export async function markAllNotificationsRead() {
  return authenticatedRequest<{ status: string; marked_read_count: number }>(
    "notifications/",
    { method: "POST", body: JSON.stringify({}) },
  );
}

export async function getNotificationPreferences() {
  return authenticatedRequest<NotificationPreference[]>("app/notification-preferences/");
}

export async function updateNotificationPreference(id: string, isEnabled: boolean) {
  return authenticatedRequest<NotificationPreference>(
    "app/notification-preferences/" + encodeURIComponent(id) + "/",
    { method: "PATCH", body: JSON.stringify({ is_enabled: isEnabled }) },
  );
}

export async function getConversations() {
  return authenticatedListRequest<Conversation>("app/conversations/");
}

export async function getConversationMessages(conversationId: string, before?: string) {
  const query = before ? "?before=" + encodeURIComponent(before) : "";
  return authenticatedRequest<ConversationMessagesResponse>(
    "app/conversations/" + encodeURIComponent(conversationId) + "/messages/" + query,
  );
}

export async function sendConversationMessage(conversationId: string, body: string) {
  return authenticatedRequest<ConversationMessage>(
    "app/conversations/" + encodeURIComponent(conversationId) + "/messages/",
    { method: "POST", body: JSON.stringify({ body }) },
  );
}

export async function markConversationRead(conversationId: string) {
  return authenticatedRequest<{ conversation_id: string; last_read_at: string }>(
    "app/conversations/" + encodeURIComponent(conversationId) + "/read/",
    { method: "POST", body: JSON.stringify({}) },
  );
}

export async function setConversationMuted(conversationId: string, muted: boolean) {
  return authenticatedRequest<{ conversation_id: string; is_muted: boolean }>(
    "app/conversations/" + encodeURIComponent(conversationId) + "/mute/",
    { method: "POST", body: JSON.stringify({ muted }) },
  );
}

export async function getTeacherAssignmentsForAttendance() {
  return authenticatedListRequest<TeacherAttendanceAssignment>("app/teacher-assignments/");
}

export async function getAttendanceStatusTypes() {
  const result = await authenticatedListRequest<AttendanceStatusOption>("attendance/status-types/");
  return result.filter((item) => item.is_active);
}

export async function getStudentsForAttendance(sectionId: string, academicYearId: string) {
  const query =
    "?section=" + encodeURIComponent(sectionId) +
    "&academic_year=" + encodeURIComponent(academicYearId);
  return authenticatedListRequest<AttendanceStudent>("students/" + query);
}

export async function getAttendanceRegister(sectionId: string, date: string) {
  const query = "?section_id=" + encodeURIComponent(sectionId) + "&date=" + encodeURIComponent(date);
  const result = await authenticatedListRequest<AttendanceRegister>("attendance/registers/" + query);
  return result[0] ?? null;
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
    "attendance/registers/" + encodeURIComponent(registerId) + "/bulk-record/",
    { method: "POST", body: JSON.stringify({ records }) },
  );
}

export async function submitAttendanceRegister(registerId: string) {
  return authenticatedRequest<AttendanceRegister>(
    "attendance/registers/" + encodeURIComponent(registerId) + "/submit/",
    { method: "POST", body: JSON.stringify({}) },
  );
}

export async function getAttendanceRegisters(date?: string) {
  const query = date ? "?date=" + encodeURIComponent(date) : "";
  return authenticatedListRequest<AttendanceRegister>("attendance/registers/" + query);
}

export async function approveAttendanceRegister(registerId: string) {
  return authenticatedRequest<AttendanceRegister>(
    "attendance/registers/" + encodeURIComponent(registerId) + "/approve/",
    { method: "POST", body: JSON.stringify({}) },
  );
}

export type AttendanceReopenRequest = {
  id: string;
  register: string;
  register_date: string;
  section_name: string;
  requested_by: string;
  requested_by_name: string;
  reason: string;
  status: "pending" | "approved" | "rejected" | string;
  reviewed_by?: string | null;
  reviewed_by_name?: string | null;
  reviewed_at?: string | null;
  review_notes: string;
  created_at: string;
};

export type AttendanceAuditLog = {
  id: string;
  register: string;
  student_record?: string | null;
  student_name?: string | null;
  action: string;
  performed_by?: string | null;
  performed_by_name?: string | null;
  timestamp: string;
  old_value?: unknown;
  new_value?: unknown;
  reason: string;
};

export async function lockAttendanceRegister(registerId: string) {
  return authenticatedRequest<AttendanceRegister>(
    "attendance/registers/" + encodeURIComponent(registerId) + "/lock/",
    { method: "POST", body: JSON.stringify({}) },
  );
}

export async function requestAttendanceRegisterReopen(registerId: string, reason: string) {
  return authenticatedRequest<{ message: string; request_id: string }>(
    "attendance/registers/" + encodeURIComponent(registerId) + "/reopen-request/",
    { method: "POST", body: JSON.stringify({ reason }) },
  );
}

export async function getAttendanceReopenRequests(status?: string, registerId?: string) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (registerId) params.set("register_id", registerId);
  const query = params.toString();
  return authenticatedListRequest<AttendanceReopenRequest>(
    "attendance/reopen-requests/" + (query ? "?" + query : ""),
  );
}

export async function reviewAttendanceRegisterReopen(
  registerId: string,
  isApproved: boolean,
  reviewNotes = "",
) {
  return authenticatedRequest<{ message: string }>(
    "attendance/registers/" + encodeURIComponent(registerId) + "/review-reopen/",
    {
      method: "POST",
      body: JSON.stringify({ is_approved: isApproved, review_notes: reviewNotes }),
    },
  );
}

export async function getAttendanceAuditLogs(filters: {
  registerId?: string;
  studentId?: string;
  action?: string;
  from?: string;
  to?: string;
} = {}) {
  const params = new URLSearchParams();
  if (filters.registerId) params.set("register_id", filters.registerId);
  if (filters.studentId) params.set("student_id", filters.studentId);
  if (filters.action) params.set("action", filters.action);
  if (filters.from) params.set("from", filters.from);
  if (filters.to) params.set("to", filters.to);
  const query = params.toString();
  return authenticatedListRequest<AttendanceAuditLog>(
    "attendance/audit-logs/" + (query ? "?" + query : ""),
  );
}

export async function reviewAttendanceExcuse(
  excuseId: string,
  approved: boolean,
  reviewNotes: string,
) {
  return authenticatedRequest<AttendanceExcuse>(
    "attendance/excuses/" + encodeURIComponent(excuseId) + "/review/",
    {
      method: "POST",
      body: JSON.stringify({ is_approved: approved, review_notes: reviewNotes }),
    },
  );
}

export type WorkspaceType =
  | "student"
  | "guardian"
  | "teacher"
  | "employee"
  | "management";

export type AuthUser = {
  id: string;
  phone: string;
  full_name: string;
  email?: string | null;
  is_platform_admin: boolean;
  phone_verified?: boolean;
  avatar?: string | null;
};

export type SchoolOption = {
  id: string;
  code: string;
  name: string;
  roles: string[];
  isDefault: boolean;
};

export type AuthSession = {
  accessToken: string;
  sessionId: string;
  expiresAt: string;
  deviceId: string;
  user: AuthUser;
  schools: SchoolOption[];
  activeSchoolId: string | null;
  activeWorkspace: WorkspaceType | null;
};

export type ProfileCollection = {
  teachers: { id: string; employee_number?: string; specialization?: string }[];
  guardians: { id: string; relationship_type?: string; children_count: number }[];
  students: { id: string; student_id_number: string; full_name: string; section_id: string }[];
  staff: { id: string; employee_number?: string; job_title?: string; role?: string }[];
};

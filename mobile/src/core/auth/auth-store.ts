import { Platform } from "react-native";
import { create } from "zustand";

import { ApiError, apiRequest } from "@/core/api/api-client";
import {
  clearStoredSession,
  getOrCreateDeviceId,
  readStoredSession,
  writeStoredSession,
} from "@/core/auth/session-storage";
import type { AuthSession, AuthUser, SchoolOption, WorkspaceType } from "@/core/auth/types";

type LoginResponse = {
  access_token?: string;
  token?: string;
  session_id: string;
  expires_at: string;
  device_id?: string;
  user: AuthUser;
  schools?: {
    school_id?: string;
    id?: string;
    school_code?: string;
    code?: string;
    school_name?: string;
    name?: string;
    roles?: string[];
    is_default?: boolean;
  }[];
};

type SchoolListResponse = {
  results?: {
    id?: string;
    school_id?: string;
    code?: string;
    school_code?: string;
    name?: string;
    school_name?: string;
    is_default?: boolean;
  }[];
};

type RefreshResponse = {
  access_token?: string;
  token?: string;
  session_id?: string;
  expires_at?: string;
};

type AuthState = {
  session: AuthSession | null;
  hasHydrated: boolean;
  isBusy: boolean;
  login: (phone: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  hydrate: () => Promise<void>;
  chooseSchool: (schoolId: string) => Promise<void>;
  chooseWorkspace: (workspace: WorkspaceType) => Promise<void>;
  refreshAccessToken: () => Promise<string | null>;
  clearSession: () => Promise<void>;
};

function normalizeSchoolList(
  rows: NonNullable<LoginResponse["schools"]>,
): SchoolOption[] {
  return rows.flatMap((row) => {
    const id = row.school_id ?? row.id;
    if (!id) return [];
    return [{
      id,
      code: row.school_code ?? row.code ?? "",
      name: row.school_name ?? row.name ?? "مدرسة",
      roles: Array.isArray(row.roles) ? row.roles : [],
      isDefault: Boolean(row.is_default),
    }];
  });
}

function mergeAvailableSchools(
  response: SchoolListResponse | undefined,
  existing: SchoolOption[],
): SchoolOption[] {
  const rows = response?.results;
  if (!Array.isArray(rows)) return existing;

  return rows.flatMap((row) => {
    const id = row.id ?? row.school_id;
    if (!id) return [];
    const previous = existing.find((school) => school.id === id);
    return [{
      id,
      code: row.code ?? row.school_code ?? previous?.code ?? "",
      name: row.name ?? row.school_name ?? previous?.name ?? "مدرسة",
      roles: previous?.roles ?? [],
      isDefault: Boolean(row.is_default ?? previous?.isDefault),
    }];
  });
}

async function persistSession(session: AuthSession | null) {
  if (session) await writeStoredSession(session);
  else await clearStoredSession();
}

let hydrationTask: Promise<void> | null = null;
let refreshTask: Promise<string | null> | null = null;

export const useAuthStore = create<AuthState>((set, get) => ({
  session: null,
  hasHydrated: false,
  isBusy: false,

  clearSession: async () => {
    await clearStoredSession();
    set({ session: null, isBusy: false });
  },

  hydrate: async () => {
    if (get().hasHydrated) return;
    if (hydrationTask) return hydrationTask;

    hydrationTask = (async () => {
      try {
        let session = await readStoredSession();
        if (!session) {
          set({ session: null });
          return;
        }
        set({ session });

        if (session.expiresAt && Date.parse(session.expiresAt) <= Date.now() + 60_000) {
          const token = await get().refreshAccessToken();
          session = get().session;
          if (!token || !session) return;
        }

        try {
          const user = await apiRequest<Partial<AuthUser> & { is_platform_admin?: boolean }>(
            "me/",
            {},
            { accessToken: session.accessToken },
          );
          session = {
            ...session,
            user: { ...session.user, ...user, id: user.id ?? session.user.id,
              full_name: user.full_name ?? session.user.full_name,
              is_platform_admin: Boolean(user.is_platform_admin ?? session.user.is_platform_admin) },
          };
          const schools = await apiRequest<SchoolListResponse>(
            "schools/",
            {},
            { accessToken: session.accessToken },
          );
          session.schools = mergeAvailableSchools(schools, session.schools);
          if (session.activeSchoolId && !session.schools.some((item) => item.id === session.activeSchoolId)) {
            session.activeSchoolId = null;
            session.activeWorkspace = null;
          }
          if (!session.activeSchoolId && session.schools.length === 1) {
            session.activeSchoolId = session.schools[0].id;
          }
          await persistSession(session);
          set({ session });
        } catch (error) {
          if (error instanceof ApiError && error.status === 401) {
            await clearStoredSession();
            set({ session: null });
          }
          // On temporary network failures, retain the encrypted session and let
          // the destination screen show its normal connection error.
        }
      } finally {
        set({ hasHydrated: true });
        hydrationTask = null;
      }
    })();
    return hydrationTask;
  },

  login: async (phone, password) => {
    set({ isBusy: true });
    try {
      const deviceId = await getOrCreateDeviceId();
      const payload = await apiRequest<LoginResponse>("auth/login/", {
        method: "POST",
        headers: { "X-Device-ID": deviceId },
        body: JSON.stringify({
          phone: phone.trim(),
          password,
          device_id: deviceId,
          device_name: Platform.OS === "android" ? "هاتف Android" : "هاتف iOS",
        }),
      });

      const accessToken = payload.access_token ?? payload.token;
      if (!accessToken || !payload.session_id || !payload.user) {
        throw new Error("استجابة تسجيل الدخول من الخادم غير مكتملة.");
      }

      const schools = normalizeSchoolList(payload.schools ?? []);
      let mergedSchools = schools;
      try {
        const remote = await apiRequest<SchoolListResponse>(
          "schools/",
          {},
          { accessToken },
        );
        mergedSchools = mergeAvailableSchools(remote, schools);
      } catch {
        // The login response already contains the caller's active memberships.
      }

      const session: AuthSession = {
        accessToken,
        sessionId: payload.session_id,
        expiresAt: payload.expires_at,
        deviceId: payload.device_id ?? deviceId,
        user: payload.user,
        schools: mergedSchools,
        activeSchoolId: mergedSchools.length === 1 ? mergedSchools[0].id : null,
        activeWorkspace: null,
      };

      await persistSession(session);
      set({ session });
    } finally {
      set({ isBusy: false });
    }
  },

  logout: async () => {
    const session = get().session;
    set({ isBusy: true });
    try {
      if (session?.accessToken) {
        await apiRequest("auth/logout/", {
          method: "POST",
        }, { accessToken: session.accessToken });
      }
    } catch {
      // The local session must still be removed when the network is unavailable.
    } finally {
      await clearStoredSession();
      set({ session: null, isBusy: false });
    }
  },

  chooseSchool: async (schoolId) => {
    const current = get().session;
    if (!current?.schools.some((school) => school.id === schoolId)) {
      throw new Error("هذه المدرسة غير موجودة ضمن المدارس المتاحة لحسابك.");
    }
    const session = { ...current, activeSchoolId: schoolId, activeWorkspace: null };
    await persistSession(session);
    set({ session });
  },

  chooseWorkspace: async (workspace) => {
    const current = get().session;
    if (!current?.activeSchoolId) throw new Error("اختر المدرسة أولاً.");
    const session = { ...current, activeWorkspace: workspace };
    await persistSession(session);
    set({ session });
  },

  refreshAccessToken: async () => {
    const current = get().session;
    if (!current?.accessToken) return null;
    if (refreshTask) return refreshTask;

    refreshTask = (async () => {
      try {
        const result = await apiRequest<RefreshResponse>("auth/sessions/refresh/", {
          method: "POST",
        }, { accessToken: current.accessToken });
        const token = result.access_token ?? result.token;
        if (!token) return null;
        const latest = get().session;
        if (!latest) return null;
        const next: AuthSession = {
          ...latest,
          accessToken: token,
          sessionId: result.session_id ?? latest.sessionId,
          expiresAt: result.expires_at ?? latest.expiresAt,
        };
        await persistSession(next);
        set({ session: next });
        return token;
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          await clearStoredSession();
          set({ session: null });
        }
        return null;
      } finally {
        refreshTask = null;
      }
    })();
    return refreshTask;
  },
}));

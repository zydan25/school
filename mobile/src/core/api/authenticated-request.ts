import { ApiError, apiRequest } from "@/core/api/api-client";
import { useAuthStore } from "@/core/auth/auth-store";

export async function authenticatedRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const initial = useAuthStore.getState().session;
  if (!initial?.accessToken) {
    throw new ApiError("انتهت جلسة الدخول. سجل الدخول مجدداً.", 401, null);
  }

  try {
    return await apiRequest<T>(path, init, {
      accessToken: initial.accessToken,
      schoolId: initial.activeSchoolId ?? undefined,
    });
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401) throw error;

    const latest = useAuthStore.getState().session;
    let accessToken = latest?.accessToken;
    if (!latest || !accessToken) throw error;

    if (accessToken === initial.accessToken) {
      accessToken = await useAuthStore.getState().refreshAccessToken();
    }

    const refreshed = useAuthStore.getState().session;
    if (!accessToken || !refreshed) throw error;

    return apiRequest<T>(path, init, {
      accessToken,
      schoolId: refreshed.activeSchoolId ?? undefined,
    });
  }
}

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
    if (!latest?.accessToken) throw error;
    let accessToken: string = latest.accessToken;

    if (accessToken === initial.accessToken) {
      const rotatedToken = await useAuthStore.getState().refreshAccessToken();
      if (!rotatedToken) throw error;
      accessToken = rotatedToken;
    }

    const refreshed = useAuthStore.getState().session;
    if (!refreshed) throw error;

    return apiRequest<T>(path, init, {
      accessToken,
      schoolId: refreshed.activeSchoolId ?? undefined,
    });
  }
}

export type ApiContext = {
  accessToken?: string;
  schoolId?: string;
};

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly payload: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function readErrorMessage(payload: unknown): string {
  if (payload && typeof payload === "object") {
    const record = payload as Record<string, unknown>;
    if (typeof record.detail === "string") return record.detail;
    if (typeof record.error === "string") return record.error;
  }

  return "تعذر إكمال الطلب. حاول مجدداً.";
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  context: ApiContext = {},
): Promise<T> {
  const baseUrl = process.env.EXPO_PUBLIC_API_BASE_URL?.trim();

  if (!baseUrl) {
    throw new Error("EXPO_PUBLIC_API_BASE_URL غير مضبوط في ملف البيئة.");
  }

  const normalizedBase = baseUrl.endsWith("/") ? baseUrl : baseUrl + "/";
  const normalizedPath = path.replace(/^\/+/, "");
  const url = new URL(normalizedPath, normalizedBase);
  const headers = new Headers(init.headers);

  headers.set("Accept", "application/json");

  if (context.accessToken) {
    headers.set("Authorization", "Bearer " + context.accessToken);
  }

  if (context.schoolId) {
    headers.set("X-School-ID", context.schoolId);
  }

  const isFormData =
    typeof FormData !== "undefined" && init.body instanceof FormData;

  if (init.body != null && !isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(url.toString(), {
    ...init,
    headers,
  });

  const rawBody = await response.text();
  let payload: unknown = null;

  if (rawBody) {
    try {
      payload = JSON.parse(rawBody) as unknown;
    } catch {
      payload = rawBody;
    }
  }

  if (!response.ok) {
    throw new ApiError(
      readErrorMessage(payload),
      response.status,
      payload,
    );
  }

  return payload as T;
}

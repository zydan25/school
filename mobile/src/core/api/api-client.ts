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

function valueToMessage(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) return value.trim();
  if (Array.isArray(value)) {
    for (const item of value) {
      const message = valueToMessage(item);
      if (message) return message;
    }
  }
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    for (const key of ["detail", "error", "message", "non_field_errors"]) {
      const message = valueToMessage(record[key]);
      if (message) return message;
    }
    for (const [key, nested] of Object.entries(record)) {
      const message = valueToMessage(nested);
      if (message) return key + ": " + message;
    }
  }
  return null;
}

export function getApiErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return valueToMessage(error.payload) ?? error.message;
  }
  if (error instanceof Error) return error.message;
  return "تعذر إكمال الطلب. حاول مجدداً.";
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  context: ApiContext = {},
): Promise<T> {
  const baseUrl = process.env.EXPO_PUBLIC_API_BASE_URL?.trim();

  if (!baseUrl) {
    throw new Error("عنوان الخادم غير مضبوط. تحقق من EXPO_PUBLIC_API_BASE_URL في ملف البيئة.");
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

  let response: Response;
  try {
    response = await fetch(url.toString(), { ...init, headers });
  } catch {
    throw new Error("تعذر الاتصال بالخادم. تحقق من اتصال الإنترنت وحاول مجدداً.");
  }

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
    const message = valueToMessage(payload) ?? "تعذر إكمال الطلب. حاول مجدداً.";
    throw new ApiError(message, response.status, payload);
  }

  return payload as T;
}

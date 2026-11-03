import { authenticatedRequest } from "@/core/api/authenticated-request";
import type { ApiPage } from "@/core/api/api-response";

type ListResponse<T> = T[] | ApiPage<T>;

const MAX_LIST_PAGES = 50;

/**
 * Fetch a paginated DRF list without losing records after the first page.
 * Pagination links are accepted only from the configured School API origin
 * and base path, so the bearer token is never sent to an arbitrary host.
 */
export async function authenticatedListRequest<T>(path: string): Promise<T[]> {
  const configuredBase = process.env.EXPO_PUBLIC_API_BASE_URL?.trim();
  if (!configuredBase) {
    throw new Error("عنوان الخادم غير مضبوط.");
  }

  const normalizedBase = configuredBase.endsWith("/")
    ? configuredBase
    : configuredBase + "/";
  const baseUrl = new URL(normalizedBase);
  let pageUrl: URL | null = new URL(path.replace(/^\/+/, ""), normalizedBase);
  const results: T[] = [];

  for (let page = 0; page < MAX_LIST_PAGES && pageUrl; page += 1) {
    if (
      pageUrl.origin !== baseUrl.origin ||
      !pageUrl.pathname.startsWith(baseUrl.pathname)
    ) {
      throw new Error("رفض التطبيق رابط صفحة خارج نطاق API المدرسة.");
    }

    const response: ListResponse<T> = await authenticatedRequest<ListResponse<T>>(pageUrl.toString());
    if (Array.isArray(response)) {
      results.push(...response);
      return results;
    }

    if (!response || !Array.isArray(response.results)) {
      throw new Error("استجابة القائمة من الخادم غير صحيحة.");
    }

    results.push(...response.results);
    pageUrl = response.next ? new URL(response.next, pageUrl) : null;
  }

  if (pageUrl) {
    throw new Error("قائمة الخادم تحتوي على صفحات أكثر من الحد المسموح للتحميل.");
  }

  return results;
}

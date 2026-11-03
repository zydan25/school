export type ApiPage<T> = {
  count?: number;
  next?: string | null;
  previous?: string | null;
  results: T[];
};

export function toResults<T>(value: T[] | ApiPage<T> | null | undefined): T[] {
  if (Array.isArray(value)) return value;
  if (value && Array.isArray(value.results)) return value.results;
  return [];
}

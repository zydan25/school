import { useAuthStore } from "@/core/auth/auth-store";

export function useModuleQueryScope() {
  const session = useAuthStore((state) => state.session);
  return [
    session?.user.id ?? "anonymous",
    session?.sessionId ?? "no-session",
    session?.activeSchoolId ?? "no-school",
  ] as const;
}

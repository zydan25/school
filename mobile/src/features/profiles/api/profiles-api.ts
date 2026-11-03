import { authenticatedRequest } from "@/core/api/authenticated-request";
import type { ProfileCollection } from "@/core/auth/types";

export async function getMyProfiles(): Promise<ProfileCollection> {
  return authenticatedRequest<ProfileCollection>("app/account/profiles/");
}

import * as SecureStore from "expo-secure-store";

import type { AuthSession } from "@/core/auth/types";

const SESSION_KEY = "school.mobile.auth.session.v1";
const DEVICE_ID_KEY = "school.mobile.device.id.v1";

export async function readStoredSession(): Promise<AuthSession | null> {
  const raw = await SecureStore.getItemAsync(SESSION_KEY);
  if (!raw) return null;

  try {
    const value = JSON.parse(raw) as AuthSession;
    if (
      !value ||
      typeof value.accessToken !== "string" ||
      typeof value.sessionId !== "string" ||
      !value.user?.id ||
      !Array.isArray(value.schools)
    ) {
      await SecureStore.deleteItemAsync(SESSION_KEY);
      return null;
    }
    return value;
  } catch {
    await SecureStore.deleteItemAsync(SESSION_KEY);
    return null;
  }
}

export async function writeStoredSession(session: AuthSession): Promise<void> {
  await SecureStore.setItemAsync(SESSION_KEY, JSON.stringify(session));
}

export async function clearStoredSession(): Promise<void> {
  await SecureStore.deleteItemAsync(SESSION_KEY);
}

export async function getOrCreateDeviceId(): Promise<string> {
  const current = await SecureStore.getItemAsync(DEVICE_ID_KEY);
  if (current) return current;

  const generated = [
    "school",
    Date.now().toString(36),
    Math.random().toString(36).slice(2, 12),
  ].join("-");
  await SecureStore.setItemAsync(DEVICE_ID_KEY, generated);
  return generated;
}

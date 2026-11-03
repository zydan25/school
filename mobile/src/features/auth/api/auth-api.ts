import { apiRequest } from "@/core/api/api-client";

export type RegistrationInput = {
  phone: string;
  first_name: string;
  middle_name?: string;
  last_name: string;
  email?: string;
  password: string;
  password_confirm: string;
};

export type RegistrationResponse = {
  message: string;
  phone: string;
  account_status: string;
  expires_in_seconds: number;
};

export async function registerWithPhone(input: RegistrationInput) {
  return apiRequest<RegistrationResponse>("auth/register/", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function verifyPhone(phone: string, code: string) {
  return apiRequest<{ message: string; phone_verified: boolean; account_status: string }>(
    "auth/phone/verify/",
    { method: "POST", body: JSON.stringify({ phone, code }) },
  );
}

export async function resendPhoneCode(phone: string) {
  return apiRequest<{ message: string }>(
    "auth/phone/resend/",
    { method: "POST", body: JSON.stringify({ phone }) },
  );
}

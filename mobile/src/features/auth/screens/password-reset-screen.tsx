import { useState } from "react";
import { KeyboardAvoidingView, Platform, StyleSheet, View } from "react-native";
import { Button, Text, TextInput } from "react-native-paper";
import { router } from "expo-router";

import { AppBrand } from "@/shared/components/app-brand";
import { AppNotice } from "@/shared/components/app-notice";
import { AppScreen } from "@/shared/components/app-screen";
import { confirmPasswordReset, requestPasswordReset } from "@/features/auth/api/auth-api";
import { getApiErrorMessage } from "@/core/api/api-client";
import { useAuthStore } from "@/core/auth/auth-store";
import { palette, spacing } from "@/core/theme/tokens";

export function PasswordResetScreen() {
  const clearSession = useAuthStore((state) => state.clearSession);
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [step, setStep] = useState<"phone" | "code">("phone");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function sendCode() {
    setError("");
    setMessage("");
    if (!phone.trim()) {
      setError("أدخل رقم الهاتف المرتبط بحسابك.");
      return;
    }
    setBusy(true);
    try {
      const result = await requestPasswordReset(phone.trim());
      setStep("code");
      setMessage(result.message);
    } catch (reason) {
      setError(getApiErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function resetPassword() {
    setError("");
    setMessage("");
    if (!/^\d{6}$/.test(code.trim())) {
      setError("أدخل رمز التحقق المكون من ستة أرقام.");
      return;
    }
    if (!password || password !== confirm) {
      setError("أدخل كلمة المرور الجديدة وتأكد من تطابقها.");
      return;
    }
    setBusy(true);
    try {
      const result = await confirmPasswordReset(phone.trim(), code.trim(), password, confirm);
      setMessage(result.message);
      await clearSession();
      router.replace("/login" as never);
    } catch (reason) {
      setError(getApiErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppScreen>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.keyboard}>
        <AppBrand title="استعادة كلمة المرور" subtitle="استعد الوصول إلى حسابك بأمان" />
        <View style={styles.form}>
          <Text style={styles.heading}>{step === "phone" ? "أرسل رمز الاستعادة" : "تعيين كلمة مرور جديدة"}</Text>
          {error ? <AppNotice message={error} /> : null}
          {message ? <AppNotice tone="success" message={message} /> : null}

          <TextInput
            mode="outlined"
            label="رقم الهاتف"
            value={phone}
            onChangeText={setPhone}
            keyboardType="phone-pad"
            editable={step === "phone"}
            style={styles.input}
            contentStyle={styles.inputText}
          />

          {step === "code" ? (
            <>
              <TextInput
                mode="outlined"
                label="رمز الاستعادة"
                value={code}
                onChangeText={(value) => setCode(value.replace(/\D/g, "").slice(0, 6))}
                keyboardType="number-pad"
                maxLength={6}
                style={styles.input}
                contentStyle={styles.code}
              />
              <TextInput
                mode="outlined"
                label="كلمة المرور الجديدة"
                value={password}
                onChangeText={setPassword}
                secureTextEntry
                autoCapitalize="none"
                style={styles.input}
                contentStyle={styles.inputText}
              />
              <TextInput
                mode="outlined"
                label="تأكيد كلمة المرور الجديدة"
                value={confirm}
                onChangeText={setConfirm}
                secureTextEntry
                autoCapitalize="none"
                style={styles.input}
                contentStyle={styles.inputText}
              />
              <Button mode="contained" onPress={() => void resetPassword()} loading={busy} disabled={busy} buttonColor={palette.primary} contentStyle={styles.buttonContent}>
                تغيير كلمة المرور
              </Button>
              <Button mode="text" onPress={() => void sendCode()} disabled={busy} textColor={palette.secondary}>إعادة إرسال الرمز</Button>
            </>
          ) : (
            <Button mode="contained" onPress={() => void sendCode()} loading={busy} disabled={busy} buttonColor={palette.primary} contentStyle={styles.buttonContent}>
              إرسال رمز الاستعادة
            </Button>
          )}
          <Button mode="text" onPress={() => router.replace("/login" as never)} textColor={palette.muted}>العودة لتسجيل الدخول</Button>
        </View>
      </KeyboardAvoidingView>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  keyboard: { flex: 1, justifyContent: "center", gap: spacing.lg },
  form: { backgroundColor: palette.surface, borderRadius: 20, borderWidth: 1, borderColor: palette.border, padding: spacing.lg, gap: spacing.md },
  heading: { color: palette.primary, fontSize: 18, fontWeight: "800", textAlign: "right" },
  input: { backgroundColor: palette.surface },
  inputText: { textAlign: "right" },
  code: { textAlign: "center", letterSpacing: 7, fontSize: 21, fontWeight: "800" },
  buttonContent: { minHeight: 48 },
});

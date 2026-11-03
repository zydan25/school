import { useState } from "react";
import { StyleSheet, View } from "react-native";
import { Button, Text, TextInput } from "react-native-paper";
import { router, useLocalSearchParams } from "expo-router";

import { AppBrand } from "@/shared/components/app-brand";
import { AppNotice } from "@/shared/components/app-notice";
import { AppScreen } from "@/shared/components/app-screen";
import { verifyPhone, resendPhoneCode } from "@/features/auth/api/auth-api";
import { getApiErrorMessage } from "@/core/api/api-client";
import { palette, spacing } from "@/core/theme/tokens";

export function VerifyPhoneScreen() {
  const params = useLocalSearchParams<{ phone?: string }>();
  const phone = typeof params.phone === "string" ? params.phone : "";
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function submit() {
    setError("");
    setMessage("");
    if (!phone || !/^\d{6}$/.test(code.trim())) {
      setError("أدخل رقم الهاتف ورمز التحقق المكون من ستة أرقام.");
      return;
    }
    setBusy(true);
    try {
      const result = await verifyPhone(phone, code.trim());
      setMessage(result.message);
      router.replace("/login" as never);
    } catch (reason) {
      setError(getApiErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    setError("");
    setMessage("");
    setBusy(true);
    try {
      const result = await resendPhoneCode(phone);
      setMessage(result.message);
    } catch (reason) {
      setError(getApiErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppScreen compact>
      <AppBrand title="توثيق رقم الهاتف" subtitle="أدخل الرمز المرسل إلى هاتفك" />
      <View style={styles.form}>
        {error ? <AppNotice message={error} /> : null}
        {message ? <AppNotice tone="success" message={message} /> : null}
        <Text style={styles.phone}>{phone || "رقم الهاتف غير محدد"}</Text>
        <TextInput
          mode="outlined"
          label="رمز التحقق"
          value={code}
          onChangeText={(value) => setCode(value.replace(/\D/g, "").slice(0, 6))}
          keyboardType="number-pad"
          maxLength={6}
          style={styles.input}
          contentStyle={styles.code}
          outlineColor={palette.border}
          activeOutlineColor={palette.secondary}
        />
        <Button mode="contained" onPress={() => void submit()} loading={busy} disabled={busy} buttonColor={palette.primary} contentStyle={styles.buttonContent}>تأكيد الرمز</Button>
        <Button mode="text" onPress={() => void resend()} disabled={busy || !phone} textColor={palette.secondary}>إعادة إرسال الرمز</Button>
        <Button mode="text" onPress={() => router.replace("/login" as never)} textColor={palette.muted}>العودة لتسجيل الدخول</Button>
      </View>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  form: { backgroundColor: palette.surface, borderRadius: 20, borderWidth: 1, borderColor: palette.border, padding: spacing.lg, gap: spacing.md },
  phone: { color: palette.muted, fontSize: 13, textAlign: "center" },
  input: { backgroundColor: palette.surface },
  code: { textAlign: "center", letterSpacing: 8, fontSize: 22, fontWeight: "800" },
  buttonContent: { minHeight: 48 },
});

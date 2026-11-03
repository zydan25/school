import { useState } from "react";
import { KeyboardAvoidingView, Platform, StyleSheet, View } from "react-native";
import { Button, Text, TextInput } from "react-native-paper";
import { router } from "expo-router";

import { AppBrand } from "@/shared/components/app-brand";
import { AppNotice } from "@/shared/components/app-notice";
import { AppScreen } from "@/shared/components/app-screen";
import { registerWithPhone } from "@/features/auth/api/auth-api";
import { getApiErrorMessage } from "@/core/api/api-client";
import { palette, spacing } from "@/core/theme/tokens";

export function RegisterScreen() {
  const [firstName, setFirstName] = useState("");
  const [middleName, setMiddleName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    setError("");
    if (!firstName.trim() || !lastName.trim() || !phone.trim() || !password) {
      setError("أكمل الاسم الأول واسم العائلة ورقم الهاتف وكلمة المرور.");
      return;
    }
    if (password !== confirm) {
      setError("كلمتا المرور غير متطابقتين.");
      return;
    }
    setBusy(true);
    try {
      const result = await registerWithPhone({
        first_name: firstName.trim(),
        middle_name: middleName.trim(),
        last_name: lastName.trim(),
        phone: phone.trim(),
        email: email.trim(),
        password,
        password_confirm: confirm,
      });
      router.replace(("/verify-phone?phone=" + encodeURIComponent(result.phone)) as never);
    } catch (reason) {
      setError(getApiErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppScreen>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.keyboard}>
        <AppBrand title="حساب جديد" subtitle="أنشئ حسابك ثم وثّق رقم الهاتف" />
        <View style={styles.form}>
          <Text style={styles.heading}>التسجيل برقم الهاتف</Text>
          {error ? <AppNotice message={error} /> : null}
          <TextInput mode="outlined" label="الاسم الأول" value={firstName} onChangeText={setFirstName} style={styles.input} contentStyle={styles.inputText} />
          <TextInput mode="outlined" label="اسم الأب / الاسم الأوسط (اختياري)" value={middleName} onChangeText={setMiddleName} style={styles.input} contentStyle={styles.inputText} />
          <TextInput mode="outlined" label="اسم العائلة" value={lastName} onChangeText={setLastName} style={styles.input} contentStyle={styles.inputText} />
          <TextInput mode="outlined" label="رقم الهاتف" value={phone} onChangeText={setPhone} keyboardType="phone-pad" autoComplete="tel" style={styles.input} contentStyle={styles.inputText} />
          <TextInput mode="outlined" label="البريد الإلكتروني (اختياري)" value={email} onChangeText={setEmail} keyboardType="email-address" autoCapitalize="none" style={styles.input} contentStyle={styles.inputText} />
          <TextInput mode="outlined" label="كلمة المرور" value={password} onChangeText={setPassword} secureTextEntry autoCapitalize="none" style={styles.input} contentStyle={styles.inputText} />
          <TextInput mode="outlined" label="تأكيد كلمة المرور" value={confirm} onChangeText={setConfirm} secureTextEntry autoCapitalize="none" style={styles.input} contentStyle={styles.inputText} />
          <Text style={styles.note}>إنشاء الحساب لا يمنحك عضوية مدرسة تلقائياً؛ يجب أن تربطك المدرسة بدور وملف معتمد.</Text>
          <Button mode="contained" onPress={() => void submit()} loading={busy} disabled={busy} buttonColor={palette.primary} contentStyle={styles.buttonContent} labelStyle={styles.buttonLabel}>إرسال رمز التحقق</Button>
          <Button mode="text" onPress={() => router.replace("/login" as never)} textColor={palette.secondary}>لديك حساب؟ تسجيل الدخول</Button>
        </View>
      </KeyboardAvoidingView>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  keyboard: { flex: 1, gap: spacing.md },
  form: { backgroundColor: palette.surface, borderRadius: 20, borderWidth: 1, borderColor: palette.border, padding: spacing.lg, gap: spacing.sm },
  heading: { color: palette.primary, fontWeight: "800", fontSize: 18, textAlign: "right", marginBottom: spacing.xs },
  input: { backgroundColor: palette.surface },
  inputText: { textAlign: "right" },
  note: { color: palette.muted, fontSize: 11, lineHeight: 18, textAlign: "right" },
  buttonContent: { minHeight: 48 },
  buttonLabel: { fontWeight: "800" },
});

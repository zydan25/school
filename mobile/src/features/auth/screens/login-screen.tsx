import { useState } from "react";
import { KeyboardAvoidingView, Platform, StyleSheet, View } from "react-native";
import { Button, HelperText, Text, TextInput } from "react-native-paper";
import { router } from "expo-router";

import { AppBrand } from "@/shared/components/app-brand";
import { AppNotice } from "@/shared/components/app-notice";
import { AppScreen } from "@/shared/components/app-screen";
import { palette, spacing } from "@/core/theme/tokens";
import { getApiErrorMessage } from "@/core/api/api-client";
import { useAuthStore } from "@/core/auth/auth-store";

export function LoginScreen() {
  const login = useAuthStore((state) => state.login);
  const isBusy = useAuthStore((state) => state.isBusy);
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    setError("");
    if (!phone.trim() || !password) {
      setError("أدخل رقم الهاتف وكلمة المرور.");
      return;
    }
    try {
      await login(phone, password);
      router.replace("/");
    } catch (reason) {
      setError(getApiErrorMessage(reason));
    }
  }

  return (
    <AppScreen>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.keyboard}>
        <AppBrand title="مرحباً بك" subtitle="سجل الدخول إلى حسابك لمتابعة مدرستك" />
        <View style={styles.form}>
          <Text style={styles.heading}>تسجيل الدخول</Text>
          <Text style={styles.description}>استخدم رقم الهاتف المسجل في حسابك.</Text>

          {error ? <AppNotice message={error} /> : null}

          <TextInput
            mode="outlined"
            label="رقم الهاتف"
            value={phone}
            onChangeText={setPhone}
            keyboardType="phone-pad"
            autoComplete="tel"
            textContentType="telephoneNumber"
            autoCapitalize="none"
            style={styles.input}
            contentStyle={styles.inputText}
            outlineColor={palette.border}
            activeOutlineColor={palette.secondary}
            left={<TextInput.Icon icon="phone" />}
          />
          <TextInput
            mode="outlined"
            label="كلمة المرور"
            value={password}
            onChangeText={setPassword}
            secureTextEntry={!showPassword}
            autoComplete="password"
            textContentType="password"
            autoCapitalize="none"
            style={styles.input}
            contentStyle={styles.inputText}
            outlineColor={palette.border}
            activeOutlineColor={palette.secondary}
            left={<TextInput.Icon icon="lock-outline" />}
            right={<TextInput.Icon icon={showPassword ? "eye-off" : "eye"} onPress={() => setShowPassword((value) => !value)} />}
            onSubmitEditing={() => void submit()}
            returnKeyType="go"
          />
          <Button
            mode="contained"
            onPress={() => void submit()}
            loading={isBusy}
            disabled={isBusy}
            contentStyle={styles.primaryButton}
            buttonColor={palette.primary}
            labelStyle={styles.primaryLabel}
          >
            دخول
          </Button>

          <View style={styles.links}>
            <Button mode="text" compact onPress={() => router.push("/register" as never)} textColor={palette.secondary}>
              إنشاء حساب جديد
            </Button>
          </View>
          <HelperText type="info" visible style={styles.helper}>
            بعد الدخول ستظهر المدارس والأدوار المرتبطة بحسابك فقط.
          </HelperText>
        </View>
      </KeyboardAvoidingView>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  keyboard: { flex: 1, justifyContent: "center", gap: spacing.lg },
  form: { backgroundColor: palette.surface, borderRadius: 20, borderWidth: 1, borderColor: palette.border, padding: spacing.lg, gap: spacing.md },
  heading: { color: palette.primary, fontSize: 19, fontWeight: "800", textAlign: "right" },
  description: { color: palette.muted, fontSize: 12, textAlign: "right", lineHeight: 19 },
  input: { backgroundColor: palette.surface },
  inputText: { textAlign: "right" },
  primaryButton: { minHeight: 48 },
  primaryLabel: { fontWeight: "800", fontSize: 14 },
  links: { flexDirection: "row", justifyContent: "center" },
  helper: { textAlign: "right", lineHeight: 18 },
});

import { useState } from "react";
import { router } from "expo-router";
import { StyleSheet, View } from "react-native";
import { Button, Text, TextInput } from "react-native-paper";
import { TicketCheck } from "lucide-react-native";

import { useAuthStore } from "@/core/auth/auth-store";
import { getApiErrorMessage } from "@/core/api/api-client";
import { AppBrand } from "@/shared/components/app-brand";
import { AppNotice } from "@/shared/components/app-notice";
import { AppScreen } from "@/shared/components/app-screen";
import { palette, spacing } from "@/core/theme/tokens";

export function AcceptInvitationScreen() {
  const acceptInvitation = useAuthStore((state) => state.acceptInvitation);
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    setError("");
    if (!token.trim()) {
      setError("أدخل رمز الدعوة الذي أرسلته المدرسة إلى هاتفك أو بريدك.");
      return;
    }
    setBusy(true);
    try {
      await acceptInvitation(token.trim());
      router.replace("/workspace" as never);
    } catch (reason) {
      setError(getApiErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppScreen compact>
      <AppBrand title="الانضمام إلى مدرسة" subtitle="استخدم رمز الدعوة المرسل من إدارة المدرسة" />
      <View style={styles.form}>
        {error ? <AppNotice message={error} /> : null}
        <View style={styles.icon}><TicketCheck color={palette.secondary} size={28} /></View>
        <Text style={styles.title}>قبول دعوة المدرسة</Text>
        <Text style={styles.description}>
          أدخل الرمز كما وصلك تماماً. يتحقق الخادم من صلاحية الدعوة وتطابق رقم هاتفك أو بريدك الموثق قبل تفعيل العضوية.
        </Text>
        <TextInput
          mode="outlined"
          label="رمز الدعوة"
          value={token}
          onChangeText={setToken}
          autoCapitalize="none"
          autoCorrect={false}
          multiline
          numberOfLines={3}
          style={styles.input}
          contentStyle={styles.tokenInput}
          outlineColor={palette.border}
          activeOutlineColor={palette.secondary}
        />
        <Button
          mode="contained"
          onPress={() => void submit()}
          loading={busy}
          disabled={busy}
          buttonColor={palette.primary}
          contentStyle={styles.button}
          labelStyle={styles.buttonLabel}
        >
          قبول الدعوة
        </Button>
        <Button mode="text" onPress={() => router.replace("/schools" as never)} disabled={busy} textColor={palette.muted}>
          العودة إلى المدارس
        </Button>
      </View>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  form: { backgroundColor: palette.surface, borderRadius: 20, borderWidth: 1, borderColor: palette.border, padding: spacing.lg, gap: spacing.md },
  icon: { width: 56, height: 56, alignSelf: "center", borderRadius: 18, backgroundColor: palette.secondaryTint, alignItems: "center", justifyContent: "center" },
  title: { color: palette.primary, fontSize: 18, fontWeight: "900", textAlign: "center" },
  description: { color: palette.muted, fontSize: 12, lineHeight: 20, textAlign: "center" },
  input: { backgroundColor: palette.surface },
  tokenInput: { textAlign: "left", minHeight: 76 },
  button: { minHeight: 48 },
  buttonLabel: { fontWeight: "800" },
});

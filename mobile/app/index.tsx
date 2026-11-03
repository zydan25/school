import { useEffect } from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";
import { router } from "expo-router";
import { Text } from "react-native-paper";

import { useAuthStore } from "@/core/auth/auth-store";
import { palette } from "@/core/theme/tokens";

export default function IndexRoute() {
  const session = useAuthStore((state) => state.session);
  const hasHydrated = useAuthStore((state) => state.hasHydrated);
  const hydrate = useAuthStore((state) => state.hydrate);

  useEffect(() => {
    void hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (!hasHydrated) return;
    if (!session) {
      router.replace("/login" as never);
    } else if (!session.activeSchoolId) {
      router.replace("/schools" as never);
    } else if (!session.activeWorkspace) {
      router.replace("/workspace" as never);
    } else {
      router.replace("/home" as never);
    }
  }, [hasHydrated, session]);

  return (
    <View style={styles.container}>
      <ActivityIndicator color={palette.secondary} size="large" />
      <Text style={styles.label}>جارٍ تجهيز تطبيق School...</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: palette.background, alignItems: "center", justifyContent: "center", gap: 12 },
  label: { color: palette.muted, fontSize: 12 },
});

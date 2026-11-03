import type { PropsWithChildren } from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { palette, spacing } from "@/core/theme/tokens";

type Props = PropsWithChildren<{
  scroll?: boolean;
  compact?: boolean;
}>;

export function AppScreen({ children, scroll = true, compact = false }: Props) {
  const content = (
    <View style={[styles.content, compact && styles.compact]}>
      {children}
    </View>
  );

  return (
    <SafeAreaView style={styles.safeArea} edges={["top", "right", "bottom", "left"]}>
      {scroll ? (
        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {content}
        </ScrollView>
      ) : (
        <View style={styles.scrollContent}>{content}</View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: palette.background, direction: "rtl" },
  scroll: { flex: 1 },
  scrollContent: { flexGrow: 1 },
  content: { flex: 1, width: "100%", maxWidth: 560, alignSelf: "center", padding: spacing.lg, gap: spacing.md, direction: "rtl" },
  compact: { justifyContent: "center" },
});

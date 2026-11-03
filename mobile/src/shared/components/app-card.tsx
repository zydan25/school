import type { PropsWithChildren } from "react";
import { StyleSheet, View } from "react-native";
import { Card } from "react-native-paper";

import { palette, radius } from "@/core/theme/tokens";

type AppCardProps = PropsWithChildren<{
  padding?: number;
}>;

export function AppCard({ children, padding = 16 }: AppCardProps) {
  return (
    <Card mode="contained" style={styles.card}>
      <View style={{ padding }}>{children}</View>
    </Card>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: palette.surface,
    borderRadius: radius.lg,
    borderColor: palette.border,
    borderWidth: StyleSheet.hairlineWidth,
    elevation: 0,
    overflow: "hidden",
  },
});

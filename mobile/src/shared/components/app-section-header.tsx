import { StyleSheet, View } from "react-native";
import { Text } from "react-native-paper";
import { palette, spacing } from "@/core/theme/tokens";

type Props = { title: string; trailing?: string; subtitle?: string };

export function AppSectionHeader({ title, trailing, subtitle }: Props) {
  return (
    <View style={styles.container}>
      <View style={styles.textGroup}>
        <Text style={styles.title}>{title}</Text>
        {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
      </View>
      {trailing ? <Text style={styles.trailing}>{trailing}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm, marginTop: spacing.xs },
  textGroup: { flex: 1, alignItems: "flex-start", gap: 3 },
  title: { color: palette.primary, fontSize: 16, fontWeight: "800", textAlign: "right" },
  subtitle: { color: palette.muted, fontSize: 11, textAlign: "right" },
  trailing: { color: palette.muted, fontSize: 12, textAlign: "left" },
});

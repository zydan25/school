import { StyleSheet, View } from "react-native";
import { Text } from "react-native-paper";
import type { LucideIcon } from "lucide-react-native";
import { palette, radius, spacing } from "@/core/theme/tokens";
import { AppIcon } from "@/shared/components/app-icon";

type Props = { icon: LucideIcon; value: string; label: string; color?: string; tint?: string };

export function AppStatCard({ icon, value, label, color = palette.secondary, tint = palette.secondaryTint }: Props) {
  return (
    <View style={styles.card}>
      <View style={[styles.iconWrap, { backgroundColor: tint }]}><AppIcon icon={icon} size={19} color={color} /></View>
      <Text style={styles.value}>{value}</Text>
      <Text style={styles.label}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { flex: 1, minWidth: 0, alignItems: "center", justifyContent: "center", gap: spacing.xs, paddingVertical: 13, paddingHorizontal: 5, backgroundColor: palette.surface, borderRadius: radius.md, borderWidth: 1, borderColor: palette.border },
  iconWrap: { width: 34, height: 34, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  value: { color: palette.primary, fontSize: 19, fontWeight: "800" },
  label: { color: palette.muted, fontSize: 11, textAlign: "center" },
});

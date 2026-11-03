import { Pressable, StyleSheet, View } from "react-native";
import { Text } from "react-native-paper";
import type { LucideIcon } from "lucide-react-native";
import { palette, radius, spacing } from "@/core/theme/tokens";
import { AppIcon } from "@/shared/components/app-icon";

type Props = { icon: LucideIcon; label: string; onPress: () => void; tint?: string; color?: string; accessibilityHint?: string };

export function AppActionTile({ icon, label, onPress, tint = palette.secondaryTint, color = palette.secondary, accessibilityHint }: Props) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={label} accessibilityHint={accessibilityHint}
      style={({ pressed }) => [styles.tile, pressed && styles.pressed]}>
      <View style={[styles.iconWrap, { backgroundColor: tint }]}><AppIcon icon={icon} size={23} color={color} /></View>
      <Text style={styles.label}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  tile: { width: "48%", minHeight: 88, flexGrow: 1, flexBasis: "46%", alignItems: "center", justifyContent: "center", gap: spacing.sm, padding: spacing.sm, backgroundColor: palette.surface, borderRadius: radius.md, borderWidth: 1, borderColor: palette.border },
  pressed: { opacity: 0.76, transform: [{ scale: 0.98 }] },
  iconWrap: { width: 40, height: 40, borderRadius: 13, alignItems: "center", justifyContent: "center" },
  label: { color: palette.primary, fontSize: 12, fontWeight: "700", textAlign: "center" },
});

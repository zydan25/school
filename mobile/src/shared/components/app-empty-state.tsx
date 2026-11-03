import { StyleSheet, View } from "react-native";
import { Button, Text } from "react-native-paper";
import type { LucideIcon } from "lucide-react-native";
import { palette, radius, spacing } from "@/core/theme/tokens";
import { AppIcon } from "@/shared/components/app-icon";

type Props = { icon: LucideIcon; title: string; description: string; actionLabel?: string; onAction?: () => void };

export function AppEmptyState({ icon, title, description, actionLabel, onAction }: Props) {
  return (
    <View style={styles.container}>
      <View style={styles.iconWrap}><AppIcon icon={icon} size={30} color={palette.secondary} /></View>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.description}>{description}</Text>
      {actionLabel && onAction ? <Button mode="outlined" onPress={onAction} compact style={styles.button} labelStyle={styles.buttonLabel}>{actionLabel}</Button> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignItems: "center", justifyContent: "center", paddingHorizontal: spacing.lg, paddingVertical: spacing.xl, backgroundColor: palette.surface, borderRadius: radius.lg, borderWidth: 1, borderColor: palette.border, gap: spacing.sm },
  iconWrap: { width: 58, height: 58, borderRadius: 20, backgroundColor: "#E8F5F2", alignItems: "center", justifyContent: "center" },
  title: { color: palette.primary, fontSize: 15, fontWeight: "800", textAlign: "center" },
  description: { color: palette.muted, fontSize: 12, lineHeight: 19, textAlign: "center" },
  button: { marginTop: spacing.xs, borderColor: palette.secondary },
  buttonLabel: { color: palette.primary, fontWeight: "700" },
});

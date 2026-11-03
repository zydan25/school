import { Pressable, StyleSheet, View } from "react-native";
import { Text } from "react-native-paper";
import { CheckCircle2, Info, X } from "lucide-react-native";
import { palette, radius, spacing } from "@/core/theme/tokens";
import { AppIcon } from "@/shared/components/app-icon";

type Props = { message: string; tone?: "info" | "success"; onDismiss?: () => void };

export function AppNotice({ message, tone = "info", onDismiss }: Props) {
  const icon = tone === "success" ? CheckCircle2 : Info;
  const color = tone === "success" ? palette.success : palette.info;
  const background = tone === "success" ? palette.successTint : palette.infoTint;
  return (
    <View style={[styles.container, { backgroundColor: background, borderColor: color }]}>
      <AppIcon icon={icon} color={color} size={19} />
      <Text style={styles.message}>{message}</Text>
      {onDismiss ? <Pressable onPress={onDismiss} accessibilityRole="button" accessibilityLabel="إغلاق الرسالة" hitSlop={8}><AppIcon icon={X} color={palette.muted} size={17} /></Pressable> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flexDirection: "row", alignItems: "center", gap: spacing.sm, padding: spacing.md, borderRadius: radius.md, borderWidth: 1 },
  message: { flex: 1, color: palette.text, fontSize: 12, lineHeight: 19, textAlign: "right" },
});

import { StyleSheet, View } from "react-native";
import { Text } from "react-native-paper";
import { GraduationCap } from "lucide-react-native";

import { palette, radius, spacing } from "@/core/theme/tokens";
import { AppIcon } from "@/shared/components/app-icon";

type Props = { title?: string; subtitle?: string };

export function AppBrand({ title = "School", subtitle = "منصة المدرسة في هاتفك" }: Props) {
  return (
    <View style={styles.container}>
      <View style={styles.logo}><AppIcon icon={GraduationCap} size={30} color={palette.white} /></View>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.subtitle}>{subtitle}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignItems: "center", gap: spacing.xs, paddingVertical: spacing.md },
  logo: { width: 66, height: 66, borderRadius: radius.xl, backgroundColor: palette.primary, alignItems: "center", justifyContent: "center", marginBottom: spacing.xs },
  title: { color: palette.primary, fontSize: 25, fontWeight: "900" },
  subtitle: { color: palette.muted, fontSize: 12, textAlign: "center" },
});

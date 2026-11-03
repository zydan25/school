import { Pressable, StyleSheet, View } from "react-native";
import { Text } from "react-native-paper";
import { Bell, GraduationCap } from "lucide-react-native";
import { palette, radius, spacing } from "@/core/theme/tokens";
import { AppAvatar } from "@/shared/components/app-avatar";
import { AppIcon } from "@/shared/components/app-icon";

type Props = { schoolName?: string; userName: string; onNotificationsPress: () => void };

export function DashboardHeader({ schoolName = "مدرستي", userName, onNotificationsPress }: Props) {
  return (
    <View style={styles.header}>
      <View style={styles.brand}>
        <View style={styles.logo}><AppIcon icon={GraduationCap} size={24} color={palette.white} /></View>
        <View style={styles.brandText}>
          <Text style={styles.schoolName}>{schoolName}</Text>
          <Text style={styles.schoolCaption}>منصة School التعليمية</Text>
        </View>
      </View>
      <View style={styles.actions}>
        <Pressable onPress={onNotificationsPress} accessibilityRole="button" accessibilityLabel="فتح الإشعارات"
          style={({ pressed }) => [styles.notificationButton, pressed && styles.pressed]}>
          <AppIcon icon={Bell} color={palette.primary} size={21} />
          <View style={styles.notificationDot} />
        </Pressable>
        <AppAvatar name={userName} size={42} backgroundColor={palette.infoTint} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm },
  brand: { flexDirection: "row", alignItems: "center", gap: spacing.sm, flex: 1 },
  logo: { width: 44, height: 44, borderRadius: radius.md, backgroundColor: palette.primary, alignItems: "center", justifyContent: "center" },
  brandText: { alignItems: "flex-start" },
  schoolName: { color: palette.primary, fontSize: 16, fontWeight: "800", textAlign: "right" },
  schoolCaption: { color: palette.muted, fontSize: 10, textAlign: "right" },
  actions: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  notificationButton: { width: 42, height: 42, borderRadius: radius.md, backgroundColor: palette.surface, borderColor: palette.border, borderWidth: 1, alignItems: "center", justifyContent: "center" },
  notificationDot: { position: "absolute", top: 8, right: 9, width: 7, height: 7, borderRadius: 4, backgroundColor: palette.secondary },
  pressed: { opacity: 0.72 },
});

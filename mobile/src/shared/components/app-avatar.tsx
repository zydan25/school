import { StyleSheet, View } from "react-native";
import { Text } from "react-native-paper";
import { palette } from "@/core/theme/tokens";

type AppAvatarProps = { name: string; size?: number; backgroundColor?: string; color?: string };

export function AppAvatar({ name, size = 48, backgroundColor = palette.primaryTint, color = palette.primary }: AppAvatarProps) {
  const initial = Array.from(name.trim())[0] || "؟";
  return (
    <View accessible accessibilityLabel={"الصورة الشخصية: " + name}
      style={[styles.avatar, { width: size, height: size, borderRadius: size / 2, backgroundColor }]}>
      <Text style={[styles.initial, { color, fontSize: Math.max(15, size * 0.38) }]}>{initial}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  avatar: { alignItems: "center", justifyContent: "center", overflow: "hidden" },
  initial: { fontWeight: "800", textAlign: "center" },
});

import { Pressable, StyleSheet, View } from "react-native";
import { Text } from "react-native-paper";
import { palette, radius } from "@/core/theme/tokens";

export type PreviewPersona = "guardian" | "teacher" | "student";

const personas: { value: PreviewPersona; label: string; subtitle: string }[] = [
  { value: "guardian", label: "ولي الأمر", subtitle: "متابعة الأبناء" },
  { value: "teacher", label: "المعلم", subtitle: "الشعب والطلاب" },
  { value: "student", label: "الطالب", subtitle: "الدراسة والواجبات" },
];

type Props = { value: PreviewPersona; onChange: (persona: PreviewPersona) => void };

export function PersonaSwitcher({ value, onChange }: Props) {
  return (
    <View style={styles.container} accessibilityRole="tablist">
      {personas.map((persona) => {
        const selected = value === persona.value;
        return (
          <Pressable key={persona.value} onPress={() => onChange(persona.value)}
            accessibilityRole="tab" accessibilityState={{ selected }}
            style={({ pressed }) => [styles.item, selected && styles.itemSelected, pressed && styles.pressed]}>
            <Text style={[styles.label, selected && styles.labelSelected]}>{persona.label}</Text>
            <Text style={[styles.subtitle, selected && styles.subtitleSelected]}>{persona.subtitle}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flexDirection: "row", gap: 6, padding: 4, borderRadius: radius.lg, backgroundColor: "#E8EDF3" },
  item: { flex: 1, minHeight: 54, justifyContent: "center", alignItems: "center", paddingHorizontal: 4, paddingVertical: 7, borderRadius: radius.md },
  itemSelected: { backgroundColor: palette.surface, borderWidth: 1, borderColor: palette.border },
  label: { color: palette.muted, fontSize: 12, fontWeight: "700" },
  labelSelected: { color: palette.primary },
  subtitle: { color: palette.muted, fontSize: 9, marginTop: 2 },
  subtitleSelected: { color: palette.secondary },
  pressed: { opacity: 0.75 },
});

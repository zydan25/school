import type { PropsWithChildren } from "react";
import { StyleSheet, View } from "react-native";
import { Text } from "react-native-paper";

import { AppCard } from "@/shared/components/app-card";
import { palette, spacing } from "@/core/theme/tokens";

export function ModuleHeader({
  title,
  subtitle,
  trailing,
}: {
  title: string;
  subtitle: string;
  trailing?: string;
}) {
  return (
    <View style={styles.header}>
      <View style={styles.headerRow}>
        <Text style={styles.title}>{title}</Text>
        {trailing ? <Text style={styles.trailing}>{trailing}</Text> : null}
      </View>
      <Text style={styles.subtitle}>{subtitle}</Text>
    </View>
  );
}

export function ModuleCard({ children }: PropsWithChildren) {
  return <AppCard padding={14}>{children}</AppCard>;
}

export function ModuleEmpty({ title, body }: { title: string; body: string }) {
  return (
    <AppCard padding={16}>
      <Text style={styles.emptyTitle}>{title}</Text>
      <Text style={styles.emptyBody}>{body}</Text>
    </AppCard>
  );
}

export function ValueLine({ label, value, emphasize = false }: {
  label: string;
  value: string;
  emphasize?: boolean;
}) {
  return (
    <View style={styles.valueLine}>
      <Text style={styles.valueLabel}>{label}</Text>
      <Text style={[styles.value, emphasize && styles.emphasize]}>{value || "—"}</Text>
    </View>
  );
}

export function formatAmount(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return String(value);
  return new Intl.NumberFormat("ar", { maximumFractionDigits: 2 }).format(parsed);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value.length === 10 ? value + "T12:00:00" : value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ar", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date);
}

export function StatusPill({ value, labels = {} }: {
  value: string;
  labels?: Record<string, string>;
}) {
  const label = labels[value] ?? value;
  const isGood = ["present", "approved", "paid", "graded", "published", "read", "active", "completed"].includes(value);
  const isBad = ["absent_unexcused", "rejected", "cancelled", "late", "failed", "unpaid"].includes(value);
  return (
    <View style={[
      styles.pill,
      isGood && styles.goodPill,
      isBad && styles.badPill,
    ]}>
      <Text style={[
        styles.pillText,
        isGood && styles.goodText,
        isBad && styles.badText,
      ]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  header: { gap: 5, paddingVertical: spacing.sm },
  headerRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm },
  title: { color: palette.primary, fontSize: 21, fontWeight: "900", textAlign: "right" },
  trailing: { color: palette.secondary, fontSize: 11, fontWeight: "700" },
  subtitle: { color: palette.muted, fontSize: 11, textAlign: "right", lineHeight: 18 },
  emptyTitle: { color: palette.primary, fontWeight: "800", fontSize: 14, textAlign: "right" },
  emptyBody: { color: palette.muted, fontSize: 11, lineHeight: 19, textAlign: "right", marginTop: 5 },
  valueLine: { flexDirection: "row", justifyContent: "space-between", gap: spacing.md, paddingVertical: 7, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: palette.border },
  valueLabel: { color: palette.muted, fontSize: 11 },
  value: { color: palette.text, fontSize: 11, fontWeight: "700", textAlign: "left", flexShrink: 1 },
  emphasize: { color: palette.primary, fontSize: 14, fontWeight: "900" },
  pill: { alignSelf: "flex-start", paddingHorizontal: 8, paddingVertical: 4, borderRadius: 50, backgroundColor: palette.neutralTint },
  pillText: { color: palette.muted, fontSize: 10, fontWeight: "700" },
  goodPill: { backgroundColor: palette.successTint },
  goodText: { color: palette.success },
  badPill: { backgroundColor: palette.roseTint },
  badText: { color: palette.danger },
});

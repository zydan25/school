import { ActivityIndicator, StyleSheet, View } from "react-native";
import { Button, Switch, Text } from "react-native-paper";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CheckCheck } from "lucide-react-native";

import {
  getNotificationPreferences,
  getUserNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  updateNotificationPreference,
  type NotificationPreference,
  type UserNotification,
} from "@/features/modules/api/school-modules-api";
import { getApiErrorMessage } from "@/core/api/api-client";
import { AppNotice } from "@/shared/components/app-notice";
import { AppScreen } from "@/shared/components/app-screen";
import { useModuleQueryScope } from "@/features/modules/hooks/use-module-query-scope";
import { AppIcon } from "@/shared/components/app-icon";
import { palette, spacing } from "@/core/theme/tokens";
import {
  formatDate,
  ModuleCard,
  ModuleEmpty,
  ModuleHeader,
  StatusPill,
} from "@/features/modules/components/module-primitives";

export function NotificationsScreen() {
  const client = useQueryClient();
  const queryScope = useModuleQueryScope();
  const query = useQuery({
    queryKey: ["module", "notifications", ...queryScope],
    queryFn: getUserNotifications,
    refetchInterval: 30_000,
  });
  const readMutation = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: async () => client.invalidateQueries({ queryKey: ["module", "notifications"] }),
  });
  const allMutation = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: async () => client.invalidateQueries({ queryKey: ["module", "notifications"] }),
  });
  const data = query.data;
  const preferencesQuery = useQuery({
    queryKey: ["module", "notification-preferences", ...queryScope],
    queryFn: getNotificationPreferences,
  });
  const preferenceMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      updateNotificationPreference(id, enabled),
    onSuccess: async () => client.invalidateQueries({ queryKey: ["module", "notification-preferences"] }),
  });

  return (
    <AppScreen>
      <ModuleHeader title="الإشعارات" subtitle="تنبيهات الحساب ورسائل المدرسة ومتابعة آخر المستجدات" trailing={String(data?.unread_count ?? 0) + " غير مقروء"} />
      <View style={styles.actions}>
        <Button mode="outlined" icon={CheckCheck} textColor={palette.secondary}
          loading={allMutation.isPending}
          disabled={allMutation.isPending || !data?.unread_count}
          onPress={() => allMutation.mutate()}>
          تحديد الكل كمقروء
        </Button>
      </View>
      {query.isLoading ? <ActivityIndicator color={palette.secondary} /> : null}
      {query.isError ? <AppNotice message={getApiErrorMessage(query.error)} /> : null}
      {!query.isLoading && !data?.notifications.length ? (
        <ModuleEmpty title="لا توجد إشعارات" body="ستظهر هنا إشعارات المدرسة والمحادثات والحساب." />
      ) : null}
      {(data?.notifications ?? []).map((notification) => (
        <NotificationCard
          key={notification.id}
          notification={notification}
          busy={readMutation.isPending}
          onRead={() => readMutation.mutate(notification.id)}
        />
      ))}
      {allMutation.isError ? <AppNotice message={getApiErrorMessage(allMutation.error)} /> : null}
      {readMutation.isError ? <AppNotice message={getApiErrorMessage(readMutation.error)} /> : null}

      <View style={styles.preferenceHeader}>
        <Text style={styles.preferenceTitle}>تفضيلات الإشعارات</Text>
        <Text style={styles.preferenceDescription}>
          هذه الخيارات تعرض التفضيلات المسجلة لحسابك. لا تنشئ فئات أو قنوات جديدة من التطبيق.
        </Text>
      </View>
      {preferencesQuery.isLoading ? <ActivityIndicator color={palette.secondary} /> : null}
      {preferencesQuery.isError ? <AppNotice message={getApiErrorMessage(preferencesQuery.error)} /> : null}
      {!preferencesQuery.isLoading && !preferencesQuery.isError && !preferencesQuery.data?.length ? (
        <ModuleEmpty title="لا توجد تفضيلات مخصصة" body="لم تسجل المدرسة أو الحساب تفضيلات خاصة. ستستمر الإعدادات الافتراضية التي يديرها الخادم." />
      ) : null}
      {(preferencesQuery.data ?? []).map((preference) => (
        <PreferenceCard
          key={preference.id}
          preference={preference}
          busy={preferenceMutation.isPending}
          onChange={(enabled) => preferenceMutation.mutate({ id: preference.id, enabled })}
        />
      ))}
      {preferenceMutation.isError ? <AppNotice message={getApiErrorMessage(preferenceMutation.error)} /> : null}
      <AppNotice message="ملاحظة: ظهور الإشعارات داخل التطبيق يعمل عبر الخادم. أما إرسال إشعار Push إلى شاشة الهاتف فيتطلب استكمال خدمة الإرسال الخلفية وإعداد مزود المنصة." />
    </AppScreen>
  );
}


const channelLabels: Record<string, string> = {
  in_app: "داخل التطبيق",
  email: "البريد الإلكتروني",
  sms: "رسائل SMS",
  whatsapp: "واتساب",
  push: "إشعار Push",
};

function PreferenceCard({ preference, busy, onChange }: {
  preference: NotificationPreference;
  busy: boolean;
  onChange: (enabled: boolean) => void;
}) {
  return (
    <ModuleCard>
      <View style={styles.preferenceRow}>
        <View style={styles.preferenceText}>
          <Text style={styles.preferenceCategory}>{preference.category}</Text>
          <Text style={styles.preferenceChannel}>
            {channelLabels[preference.channel] ?? preference.channel}
            {preference.school ? " · إعداد المدرسة" : " · إعداد عام"}
          </Text>
        </View>
        <Switch value={preference.is_enabled} disabled={busy} onValueChange={onChange} color={palette.secondary} />
      </View>
    </ModuleCard>
  );
}

function NotificationCard({ notification, busy, onRead }: {
  notification: UserNotification;
  busy: boolean;
  onRead: () => void;
}) {
  return (
    <ModuleCard>
      <View style={styles.cardTop}>
        <View style={styles.icon}><AppIcon icon={Bell} color={notification.is_read ? palette.muted : palette.secondary} size={19} /></View>
        <View style={styles.titleBlock}>
          <Text style={styles.title}>{notification.title}</Text>
          <Text style={styles.date}>{formatDate(notification.created_at)}</Text>
        </View>
        <StatusPill value={notification.is_read ? "read" : "unread"} labels={{ read: "مقروء", unread: "جديد" }} />
      </View>
      <Text style={styles.body}>{notification.body}</Text>
      {!notification.is_read ? (
        <Button mode="text" compact disabled={busy} onPress={onRead} textColor={palette.secondary}>تحديد كمقروء</Button>
      ) : null}
    </ModuleCard>
  );
}

const styles = StyleSheet.create({
  actions: { alignItems: "flex-start", paddingBottom: spacing.sm },
  cardTop: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  icon: { width: 38, height: 38, borderRadius: 12, backgroundColor: palette.secondaryTint, alignItems: "center", justifyContent: "center" },
  titleBlock: { flex: 1, alignItems: "flex-start", gap: 3 },
  title: { color: palette.primary, fontSize: 12, fontWeight: "800", textAlign: "right" },
  date: { color: palette.muted, fontSize: 10 },
  body: { color: palette.text, fontSize: 11, lineHeight: 19, textAlign: "right", marginTop: spacing.sm },
  preferenceHeader: { gap: 4, paddingTop: spacing.lg },
  preferenceTitle: { color: palette.primary, fontSize: 14, fontWeight: "900", textAlign: "right" },
  preferenceDescription: { color: palette.muted, fontSize: 10, lineHeight: 17, textAlign: "right" },
  preferenceRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  preferenceText: { flex: 1, alignItems: "flex-start", gap: 4 },
  preferenceCategory: { color: palette.primary, fontSize: 12, fontWeight: "800" },
  preferenceChannel: { color: palette.muted, fontSize: 10 },
});

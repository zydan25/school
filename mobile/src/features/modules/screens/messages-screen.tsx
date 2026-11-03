import { useEffect, useState } from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { ActivityIndicator, Button, Text, TextInput } from "react-native-paper";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, MessageCircle, Send } from "lucide-react-native";

import {
  getConversationMessages,
  getConversations,
  markConversationRead,
  sendConversationMessage,
  setConversationMuted,
  type Conversation,
  type ConversationMessage,
} from "@/features/modules/api/school-modules-api";
import { getApiErrorMessage } from "@/core/api/api-client";
import { AppNotice } from "@/shared/components/app-notice";
import { AppScreen } from "@/shared/components/app-screen";
import { AppIcon } from "@/shared/components/app-icon";
import { palette, spacing } from "@/core/theme/tokens";
import {
  formatDate,
  ModuleCard,
  ModuleEmpty,
  ModuleHeader,
  StatusPill,
} from "@/features/modules/components/module-primitives";

export function MessagesScreen() {
  const client = useQueryClient();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [body, setBody] = useState("");
  const conversationsQuery = useQuery({
    queryKey: ["module", "conversations"],
    queryFn: getConversations,
    refetchInterval: 30_000,
  });
  const activeConversation = conversationsQuery.data?.find((item) => item.id === activeId);
  const messagesQuery = useQuery({
    queryKey: ["module", "conversation-messages", activeId],
    queryFn: () => getConversationMessages(activeId!),
    enabled: Boolean(activeId),
    refetchInterval: activeId ? 15_000 : false,
  });
  const readMutation = useMutation({
    mutationFn: markConversationRead,
    onSuccess: async () => client.invalidateQueries({ queryKey: ["module", "conversations"] }),
  });
  const sendMutation = useMutation({
    mutationFn: ({ id, text }: { id: string; text: string }) => sendConversationMessage(id, text),
    onSuccess: async () => {
      setBody("");
      await client.invalidateQueries({ queryKey: ["module", "conversation-messages", activeId] });
      await client.invalidateQueries({ queryKey: ["module", "conversations"] });
    },
  });
  const muteMutation = useMutation({
    mutationFn: ({ id, muted }: { id: string; muted: boolean }) => setConversationMuted(id, muted),
    onSuccess: async () => client.invalidateQueries({ queryKey: ["module", "conversations"] }),
  });

  useEffect(() => {
    if (activeId) readMutation.mutate(activeId);
  }, [activeId]);

  return (
    <AppScreen>
      {activeId ? (
        <>
          <View style={styles.titleBar}>
            <Button compact mode="text" icon={ArrowRight} onPress={() => setActiveId(null)} textColor={palette.secondary}>المحادثات</Button>
            <Text style={styles.activeTitle}>{activeConversation?.subject ?? "المحادثة"}</Text>
          </View>
          <View style={styles.conversationTools}>
            <StatusPill value={activeConversation?.status ?? "open"} labels={{ open: "مفتوحة", closed: "مغلقة" }} />
            {activeConversation?.status === "open" ? (
              <Button compact mode="text" textColor={palette.muted}
                onPress={() => muteMutation.mutate({ id: activeId, muted: !activeConversation.participants.find((p) => p.is_active)?.is_muted })}>
                كتم / إلغاء الكتم
              </Button>
            ) : null}
          </View>
          {messagesQuery.isLoading ? <ActivityIndicator color={palette.secondary} /> : null}
          {messagesQuery.isError ? <AppNotice message={getApiErrorMessage(messagesQuery.error)} /> : null}
          <ScrollView style={styles.messages} contentContainerStyle={styles.messageList}>
            {(messagesQuery.data?.results ?? []).map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            {messagesQuery.data?.has_more ? (
              <Text style={styles.footnote}>توجد رسائل أقدم؛ يعرض الخادم أحدث 100 رسالة في هذا الطلب.</Text>
            ) : null}
          </ScrollView>
          {activeConversation?.status === "open" ? (
            <View style={styles.composer}>
              <TextInput mode="outlined" value={body} onChangeText={setBody} placeholder="اكتب رسالتك..."
                multiline style={styles.input} contentStyle={styles.inputText} />
              <Button mode="contained" icon={Send} buttonColor={palette.primary}
                loading={sendMutation.isPending} disabled={sendMutation.isPending || !body.trim()}
                onPress={() => sendMutation.mutate({ id: activeId, text: body.trim() })}>
                إرسال
              </Button>
              {sendMutation.isError ? <AppNotice message={getApiErrorMessage(sendMutation.error)} /> : null}
            </View>
          ) : <AppNotice message="هذه المحادثة مغلقة ولا تقبل رسائل جديدة." />}
        </>
      ) : (
        <>
          <ModuleHeader title="المحادثات" subtitle="مراسلاتك مع المدرسة والمشاركين المرتبطين بحسابك" trailing={String(conversationsQuery.data?.length ?? 0) + " محادثات"} />
          {conversationsQuery.isLoading ? <ActivityIndicator color={palette.secondary} /> : null}
          {conversationsQuery.isError ? <AppNotice message={getApiErrorMessage(conversationsQuery.error)} /> : null}
          {!conversationsQuery.isLoading && !conversationsQuery.data?.length ? (
            <ModuleEmpty title="لا توجد محادثات" body="ستظهر المحادثات التي أضافتك إليها المدرسة أو بدأتها من قناة مصرح بها. لا يتيح التطبيق اختيار مستخدمين عشوائياً لبدء محادثة." />
          ) : null}
          {(conversationsQuery.data ?? []).map((conversation) => (
            <ConversationCard key={conversation.id} conversation={conversation} onPress={() => setActiveId(conversation.id)} />
          ))}
        </>
      )}
    </AppScreen>
  );
}

function ConversationCard({ conversation, onPress }: { conversation: Conversation; onPress: () => void }) {
  return (
    <PressableConversation onPress={onPress}>
      <View style={styles.conversationRow}>
        <View style={styles.avatar}><AppIcon icon={MessageCircle} color={palette.secondary} size={21} /></View>
        <View style={styles.conversationText}>
          <Text style={styles.conversationTitle}>{conversation.subject}</Text>
          <Text style={styles.conversationMeta}>{conversation.participants.map((p) => p.user_name).filter(Boolean).slice(0, 3).join("، ")}</Text>
          {conversation.last_message_at ? <Text style={styles.conversationDate}>{formatDate(conversation.last_message_at)}</Text> : null}
        </View>
        {conversation.unread_count > 0 ? <View style={styles.unread}><Text style={styles.unreadText}>{conversation.unread_count}</Text></View> : null}
      </View>
    </PressableConversation>
  );
}

function PressableConversation({ children, onPress }: { children: React.ReactNode; onPress: () => void }) {
  const { Pressable } = require("react-native") as typeof import("react-native");
  return <Pressable onPress={onPress} style={styles.conversationSurface}>{children}</Pressable>;
}

function MessageBubble({ message }: { message: ConversationMessage }) {
  return (
    <View style={styles.messageBubble}>
      <Text style={styles.sender}>{message.sender_name}</Text>
      {message.body ? <Text style={styles.messageBody}>{message.body}</Text> : null}
      {message.attachment_available ? <Text style={styles.attachment}>مرفق: {message.attachment_name}</Text> : null}
      <Text style={styles.messageDate}>{formatDate(message.created_at)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  titleBar: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  activeTitle: { color: palette.primary, fontSize: 16, fontWeight: "900", flex: 1, textAlign: "right" },
  conversationTools: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  messages: { maxHeight: 440, minHeight: 170, backgroundColor: palette.surfaceSoft, borderRadius: 14, padding: 8 },
  messageList: { gap: 8, padding: 4 },
  messageBubble: { alignSelf: "stretch", maxWidth: "92%", borderRadius: 12, backgroundColor: palette.surface, borderWidth: 1, borderColor: palette.border, padding: 10, gap: 5 },
  sender: { color: palette.secondary, fontSize: 10, fontWeight: "800", textAlign: "right" },
  messageBody: { color: palette.text, fontSize: 12, lineHeight: 19, textAlign: "right" },
  attachment: { color: palette.info, fontSize: 10, textAlign: "right" },
  messageDate: { color: palette.muted, fontSize: 9, textAlign: "left" },
  footnote: { color: palette.muted, fontSize: 10, textAlign: "center", padding: 8 },
  composer: { gap: spacing.sm },
  input: { backgroundColor: palette.surface, maxHeight: 110 },
  inputText: { textAlign: "right" },
  conversationSurface: { backgroundColor: palette.surface, borderRadius: 14, borderWidth: 1, borderColor: palette.border, padding: 12 },
  conversationRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  avatar: { width: 42, height: 42, borderRadius: 14, backgroundColor: palette.secondaryTint, alignItems: "center", justifyContent: "center" },
  conversationText: { flex: 1, alignItems: "flex-start", gap: 4 },
  conversationTitle: { color: palette.primary, fontSize: 12, fontWeight: "800" },
  conversationMeta: { color: palette.muted, fontSize: 10, lineHeight: 15, textAlign: "right" },
  conversationDate: { color: palette.muted, fontSize: 9 },
  unread: { minWidth: 22, height: 22, borderRadius: 12, backgroundColor: palette.secondary, alignItems: "center", justifyContent: "center", paddingHorizontal: 5 },
  unreadText: { color: palette.white, fontWeight: "800", fontSize: 10 },
});

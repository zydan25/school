import { useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { ActivityIndicator, Text } from "react-native-paper";
import { useQuery } from "@tanstack/react-query";

import { useAuthStore } from "@/core/auth/auth-store";
import { authenticatedRequest } from "@/core/api/authenticated-request";
import { getFeeStatement } from "@/features/modules/api/school-modules-api";
import { getMyProfiles } from "@/features/profiles/api/profiles-api";
import { getApiErrorMessage } from "@/core/api/api-client";
import { AppNotice } from "@/shared/components/app-notice";
import { AppScreen } from "@/shared/components/app-screen";
import { palette, spacing } from "@/core/theme/tokens";
import {
  formatAmount,
  formatDate,
  ModuleCard,
  ModuleEmpty,
  ModuleHeader,
  StatusPill,
  ValueLine,
} from "@/features/modules/components/module-primitives";

type Child = { id: string; student_id_number: string; name: string; grade: string; section: string };

const invoiceLabels: Record<string, string> = {
  unpaid: "غير مسددة",
  partially_paid: "مسددة جزئياً",
  paid: "مسددة بالكامل",
  cancelled: "ملغاة",
};

export function FeesScreen() {
  const workspace = useAuthStore((state) => state.session?.activeWorkspace);
  const isGuardian = workspace === "guardian";
  const isStudent = workspace === "student";
  const childrenQuery = useQuery({
    queryKey: ["module", "fees-children"],
    queryFn: () => authenticatedRequest<{ results: Child[] }>("app/my/children/"),
    enabled: isGuardian,
  });
  const profilesQuery = useQuery({
    queryKey: ["module", "fees-profiles"],
    queryFn: getMyProfiles,
    enabled: isStudent,
  });
  const [selectedChildId, setSelectedChildId] = useState("");
  const children = childrenQuery.data?.results ?? [];
  const studentProfiles = profilesQuery.data?.students ?? [];
  const studentId = isGuardian
    ? (children.find((item) => item.id === selectedChildId) ?? children[0])?.id
    : studentProfiles[0]?.id;
  const statementQuery = useQuery({
    queryKey: ["module", "fee-statement", studentId],
    queryFn: () => getFeeStatement(studentId!),
    enabled: Boolean(studentId),
    staleTime: 30_000,
  });
  const statement = statementQuery.data;

  if (!isGuardian && !isStudent) {
    return (
      <AppScreen>
        <ModuleHeader title="الملف المالي" subtitle="الفواتير والأقساط والسندات والرصيد" />
        <ModuleEmpty title="الملف المالي للطالب وولي الأمر" body="هذه الشاشة مخصصة للطالب وولي الأمر لقراءة كشف الحساب. عمليات إنشاء الفواتير وتسجيل القبض وعكس السندات تبقى للموظفين الماليين المخولين." />
      </AppScreen>
    );
  }

  return (
    <AppScreen>
      <ModuleHeader title="الملف المالي" subtitle="كشف حساب الطالب وفواتيره ومدفوعاته ورصيده الدائن" />
      {isGuardian ? (
        <View style={styles.childChips}>
          {children.map((child) => {
            const selected = child.id === (studentId ?? selectedChildId);
            return (
              <Pressable key={child.id} onPress={() => setSelectedChildId(child.id)}
                style={[styles.childChip, selected && styles.selectedChip]}>
                <Text style={[styles.childChipText, selected && styles.selectedChipText]}>{child.name}</Text>
              </Pressable>
            );
          })}
        </View>
      ) : null}
      {statementQuery.isLoading || (isGuardian && childrenQuery.isLoading) || (isStudent && profilesQuery.isLoading) ? (
        <ActivityIndicator color={palette.secondary} />
      ) : null}
      {childrenQuery.isError ? <AppNotice message={getApiErrorMessage(childrenQuery.error)} /> : null}
      {profilesQuery.isError ? <AppNotice message={getApiErrorMessage(profilesQuery.error)} /> : null}
      {statementQuery.isError ? <AppNotice message={getApiErrorMessage(statementQuery.error)} /> : null}
      {!studentId && !statementQuery.isLoading ? (
        <ModuleEmpty title="لا يوجد ملف طالب مالي" body="لم يرجع الخادم ملف طالب مرتبطاً بالحساب في المدرسة النشطة." />
      ) : null}

      {statement ? (
        <>
          <ModuleCard>
            <Text style={styles.studentName}>{statement.student.name}</Text>
            <Text style={styles.studentNumber}>الرقم المدرسي: {statement.student.student_id_number}</Text>
            <View style={styles.summaryGrid}>
              <SummaryValue label="إجمالي الفواتير" value={statement.summary.total_invoiced} />
              <SummaryValue label="الخصومات" value={statement.summary.total_discounts} />
              <SummaryValue label="المدفوع" value={statement.summary.total_paid} />
              <SummaryValue label="المتبقي" value={statement.summary.total_due} important />
              <SummaryValue label="الرصيد الدائن" value={statement.summary.credit_balance} />
              <SummaryValue label="رصيد دفتر الأستاذ" value={statement.summary.credit_ledger_balance} />
            </View>
            {!statement.summary.credit_balance_matches_ledger ? (
              <AppNotice message="يوجد اختلاف بين رصيد الطالب وآخر رصيد في سجل الحركات. راجع الإدارة المالية؛ التطبيق لا يصحح الأرصدة محلياً." />
            ) : null}
          </ModuleCard>

          <Text style={styles.sectionTitle}>الفواتير ({statement.invoices.length})</Text>
          {statement.invoices.length ? statement.invoices.map((invoice) => (
            <ModuleCard key={invoice.id}>
              <View style={styles.cardTop}>
                <Text style={styles.invoiceNumber}>{invoice.invoice_number}</Text>
                <StatusPill value={invoice.status} labels={invoiceLabels} />
              </View>
              <ValueLine label="السنة" value={invoice.academic_year_name} />
              <ValueLine label="تاريخ الإصدار" value={formatDate(invoice.issue_date)} />
              <ValueLine label="موعد الاستحقاق" value={formatDate(invoice.due_date)} />
              <ValueLine label="الإجمالي" value={formatAmount(invoice.total_amount)} />
              <ValueLine label="الخصم" value={formatAmount(invoice.discount_amount)} />
              <ValueLine label="المدفوع" value={formatAmount(invoice.paid_amount)} />
              <ValueLine label="المتبقي" value={formatAmount(invoice.remaining_balance)} emphasize />
            </ModuleCard>
          )) : <ModuleEmpty title="لا توجد فواتير" body="لا توجد مطالبات مالية لهذا الطالب في المدرسة." />}

          <Text style={styles.sectionTitle}>الأقساط</Text>
          {statement.installment_plans.map((plan) => (
            <ModuleCard key={plan.id}>
              <Text style={styles.invoiceNumber}>{plan.plan_name}</Text>
              <ValueLine label="إجمالي الخطة" value={formatAmount(plan.total_amount)} />
              {plan.installments.map((item) => (
                <View key={item.id} style={styles.installment}>
                  <View style={styles.cardTop}>
                    <Text style={styles.normal}>{item.title || "القسط " + item.installment_number}</Text>
                    <StatusPill value={item.status} />
                  </View>
                  <ValueLine label="الاستحقاق" value={formatDate(item.due_date)} />
                  <ValueLine label="المبلغ" value={formatAmount(item.amount)} />
                  <ValueLine label="المدفوع" value={formatAmount(item.paid_amount)} />
                  <ValueLine label="المتبقي" value={formatAmount(item.remaining_amount)} />
                </View>
              ))}
            </ModuleCard>
          ))}
          {!statement.installment_plans.length ? <ModuleEmpty title="لا توجد خطط أقساط" body="لا توجد خطة تقسيط مسجلة على الفواتير." /> : null}

          <Text style={styles.sectionTitle}>سندات القبض</Text>
          {statement.receipts.map((receipt) => (
            <ModuleCard key={receipt.id}>
              <View style={styles.cardTop}>
                <Text style={styles.invoiceNumber}>{receipt.receipt_number}</Text>
                {receipt.is_cancelled ? <StatusPill value="cancelled" labels={{ cancelled: "معكوس" }} /> : <StatusPill value="paid" labels={{ paid: "مسجل" }} />}
              </View>
              <ValueLine label="التاريخ" value={formatDate(receipt.paid_at)} />
              <ValueLine label="طريقة الدفع" value={receipt.payment_method_display} />
              <ValueLine label="الفاتورة" value={receipt.invoice_number ?? "رصيد دائن"} />
              <ValueLine label="المبلغ" value={formatAmount(receipt.amount)} emphasize />
            </ModuleCard>
          ))}
          {!statement.receipts.length ? <ModuleEmpty title="لا توجد سندات قبض" body="لم تسجل سندات قبض لهذا الطالب بعد." /> : null}

          <Text style={styles.sectionTitle}>حركات الرصيد الدائن</Text>
          {statement.credit_transactions.map((transaction) => (
            <ModuleCard key={transaction.id}>
              <View style={styles.cardTop}>
                <Text style={styles.normal}>{transaction.transaction_type_display}</Text>
                {transaction.is_reversed ? <StatusPill value="cancelled" labels={{ cancelled: "معكوسة" }} /> : null}
              </View>
              <ValueLine label="التاريخ" value={formatDate(transaction.created_at)} />
              <ValueLine label="المبلغ" value={formatAmount(transaction.amount)} />
              <ValueLine label="الرصيد بعد الحركة" value={formatAmount(transaction.balance_after)} emphasize />
              {transaction.notes ? <ValueLine label="البيان" value={transaction.notes} /> : null}
            </ModuleCard>
          ))}
          {!statement.credit_transactions.length ? <ModuleEmpty title="لا توجد حركات رصيد" body="لا يوجد سجل حركات رصيد دائن لهذا الطالب." /> : null}
        </>
      ) : null}
    </AppScreen>
  );
}

function SummaryValue({ label, value, important = false }: { label: string; value: string | number; important?: boolean }) {
  return (
    <View style={styles.summaryCell}>
      <Text style={styles.summaryLabel}>{label}</Text>
      <Text style={[styles.summaryValue, important && styles.important]}>{formatAmount(value)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  childChips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  childChip: { borderWidth: 1, borderColor: palette.border, borderRadius: 30, paddingVertical: 8, paddingHorizontal: 12 },
  selectedChip: { backgroundColor: palette.primary, borderColor: palette.primary },
  childChipText: { color: palette.primary, fontSize: 11, fontWeight: "700" },
  selectedChipText: { color: palette.white },
  studentName: { color: palette.primary, fontWeight: "900", fontSize: 16, textAlign: "right" },
  studentNumber: { color: palette.muted, fontSize: 10, textAlign: "right", marginTop: 4 },
  summaryGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: spacing.md },
  summaryCell: { width: "48%", flexGrow: 1, borderRadius: 12, backgroundColor: palette.surfaceSoft, borderWidth: 1, borderColor: palette.border, padding: 10, gap: 4 },
  summaryLabel: { color: palette.muted, fontSize: 10, textAlign: "right" },
  summaryValue: { color: palette.primary, fontSize: 14, fontWeight: "900", textAlign: "right" },
  important: { color: palette.danger, fontSize: 16 },
  sectionTitle: { color: palette.primary, fontSize: 14, fontWeight: "900", textAlign: "right", marginTop: spacing.md },
  agingTitle: { color: palette.primary, fontSize: 11, fontWeight: "800", textAlign: "right", marginTop: spacing.md },
  agingGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 8 },
  cardTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm },
  invoiceNumber: { color: palette.primary, fontSize: 13, fontWeight: "900" },
  installment: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: palette.border, marginTop: spacing.sm, paddingTop: spacing.sm },
  normal: { color: palette.primary, fontSize: 12, fontWeight: "800" },
});

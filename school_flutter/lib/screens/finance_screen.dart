import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/api_service.dart';
import '../core/theme.dart';

class FinanceScreen extends StatefulWidget {
  final ApiService api;
  const FinanceScreen({super.key, required this.api});

  @override
  State<FinanceScreen> createState() => _FinanceScreenState();
}

class _FinanceScreenState extends State<FinanceScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  void _showJaibPaymentSheet() {
    final remaining = widget.api.tuitionRemaining;
    if (remaining <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('تم سداد كافة الرسوم الدراسية المقررة بالكامل!', style: GoogleFonts.cairo()),
          backgroundColor: AppTheme.screenshotGreen,
        ),
      );
      return;
    }

    double selectedAmount = remaining >= 50000 ? 50000 : remaining;
    final customAmountController = TextEditingController(text: selectedAmount.toInt().toString());

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setModalState) {
          return Container(
            padding: EdgeInsets.only(
              bottom: MediaQuery.of(context).viewInsets.bottom + 20,
              top: 20,
              left: 20,
              right: 20,
            ),
            decoration: const BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Container(
                    width: 40,
                    height: 4,
                    decoration: BoxDecoration(
                      color: const Color(0xFFE2E8F0),
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                ),
                const SizedBox(height: 14),

                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: const Color(0xFFFFF1F2),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: const Icon(Icons.account_balance_wallet_rounded, color: AppTheme.jaibRed, size: 22),
                        ),
                        const SizedBox(width: 10),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'سداد فوري عبر محفظة جيب',
                              style: GoogleFonts.cairo(fontSize: 15, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                            ),
                            Text(
                              'رقم الحساب: ${widget.api.userPhone}',
                              style: GoogleFonts.cairo(fontSize: 11, color: AppTheme.jaibRed, fontWeight: FontWeight.w600),
                            ),
                          ],
                        ),
                      ],
                    ),
                    IconButton(
                      icon: const Icon(Icons.close_rounded, size: 20),
                      onPressed: () => Navigator.pop(ctx),
                    ),
                  ],
                ),

                const Divider(height: 20),

                Text(
                  'اختر المبلغ المراد سداده:',
                  style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold, color: const Color(0xFF64748B)),
                ),
                const SizedBox(height: 8),

                Wrap(
                  spacing: 8,
                  children: [
                    _buildAmountChip('20,000 ريال', 20000, selectedAmount, (amt) {
                      setModalState(() {
                        selectedAmount = amt;
                        customAmountController.text = amt.toInt().toString();
                      });
                    }),
                    _buildAmountChip('50,000 ريال', 50000, selectedAmount, (amt) {
                      setModalState(() {
                        selectedAmount = amt;
                        customAmountController.text = amt.toInt().toString();
                      });
                    }),
                    _buildAmountChip('المتبقي (${remaining.toInt()} ريال)', remaining, selectedAmount, (amt) {
                      setModalState(() {
                        selectedAmount = amt;
                        customAmountController.text = amt.toInt().toString();
                      });
                    }),
                  ],
                ),

                const SizedBox(height: 14),

                TextField(
                  controller: customAmountController,
                  keyboardType: TextInputType.number,
                  style: GoogleFonts.cairo(fontSize: 15, fontWeight: FontWeight.bold),
                  decoration: InputDecoration(
                    labelText: 'مبلغ السداد (ريال)',
                    labelStyle: GoogleFonts.cairo(fontSize: 12, color: const Color(0xFF64748B)),
                    prefixIcon: const Icon(Icons.payments_outlined, color: AppTheme.jaibRed, size: 20),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: const BorderSide(color: AppTheme.jaibRed, width: 1.5),
                    ),
                  ),
                  onChanged: (val) {
                    final p = double.tryParse(val) ?? 0;
                    setModalState(() => selectedAmount = p);
                  },
                ),

                const SizedBox(height: 18),

                SizedBox(
                  width: double.infinity,
                  height: 46,
                  child: ElevatedButton(
                    onPressed: selectedAmount <= 0
                        ? null
                        : () {
                            Navigator.pop(ctx);
                            _executePayment(selectedAmount);
                          },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.jaibRed,
                      foregroundColor: Colors.white,
                      elevation: 0,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    child: Text(
                      'تأكيد سداد ${selectedAmount.toInt()} ريال الآن',
                      style: GoogleFonts.cairo(fontSize: 13, fontWeight: FontWeight.bold),
                    ),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildAmountChip(String label, double amount, double currentSelected, Function(double) onSelect) {
    final isSelected = currentSelected == amount;
    return ChoiceChip(
      label: Text(
        label,
        style: GoogleFonts.cairo(
          fontSize: 11,
          fontWeight: FontWeight.bold,
          color: isSelected ? Colors.white : const Color(0xFF0F172A),
        ),
      ),
      selected: isSelected,
      selectedColor: AppTheme.jaibRed,
      backgroundColor: const Color(0xFFF1F5F9),
      onSelected: (_) => onSelect(amount),
    );
  }

  void _executePayment(double amount) {
    widget.api.payViaJaibWallet(amount);

    showDialog(
      context: context,
      builder: (ctx) => Dialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  color: AppTheme.screenshotGreen.withValues(alpha: 0.12),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.check_circle_rounded, color: AppTheme.screenshotGreen, size: 32),
              ),
              const SizedBox(height: 10),
              Text(
                'تمت عملية السداد بنجاح',
                style: GoogleFonts.cairo(fontSize: 16, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
              ),
              Text(
                'سند قبض رقم #${widget.api.paymentReceipts.first['id']}',
                style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF64748B)),
              ),
              const SizedBox(height: 14),

              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFF8FAFC),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: const Color(0xFFE2E8F0)),
                ),
                child: Column(
                  children: [
                    _buildReceiptRow('المبلغ المسدد', '${amount.toInt()} ريال'),
                    _buildReceiptRow('وسيلة الدفع', 'محفظة جيب الإلكترونية'),
                    _buildReceiptRow('المتبقي بعد السداد', '${widget.api.tuitionRemaining.toInt()} ريال'),
                    _buildReceiptRow('الحالة', 'معتمد فورياً'),
                  ],
                ),
              ),

              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: () => Navigator.pop(ctx),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF1E60FF),
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  child: Text('حسناً', style: GoogleFonts.cairo(fontWeight: FontWeight.bold)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildReceiptRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF64748B))),
          Text(value, style: GoogleFonts.cairo(fontSize: 11, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A))),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.api,
      builder: (context, _) {
        final total = widget.api.tuitionTotal;
        final paid = widget.api.tuitionPaid;
        final remaining = widget.api.tuitionRemaining;
        final progress = (paid / total).clamp(0.0, 1.0);

        return Scaffold(
          backgroundColor: const Color(0xFFF8FAFC),
          appBar: AppBar(
            backgroundColor: Colors.white,
            elevation: 0,
            title: Text(
              'الرسوم والأقساط الدراسية',
              style: GoogleFonts.cairo(fontSize: 16, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
            ),
            leading: IconButton(
              icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18, color: Color(0xFF0F172A)),
              onPressed: () => Navigator.pop(context),
            ),
          ),
          body: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            physics: const BouncingScrollPhysics(),
            child: Column(
              children: [
                // 1. Compact, Human-Crafted Financial Summary Card (Not bulky!)
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: const Color(0xFFE2E8F0)),
                    boxShadow: AppTheme.softShadow,
                  ),
                  child: Column(
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'المتبقي للسداد (${widget.api.currentStudent?.fullName.split(' ').first ?? 'الطالب'})',
                                style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF64748B)),
                              ),
                              Row(
                                crossAxisAlignment: CrossAxisAlignment.baseline,
                                textBaseline: TextBaseline.alphabetic,
                                children: [
                                  Text(
                                    '${remaining.toInt()}',
                                    style: GoogleFonts.cairo(
                                      fontSize: 26,
                                      fontWeight: FontWeight.w900,
                                      color: remaining > 0 ? AppTheme.jaibRed : AppTheme.screenshotGreen,
                                    ),
                                  ),
                                  const SizedBox(width: 4),
                                  Text('ريال', style: GoogleFonts.cairo(fontSize: 12, color: const Color(0xFF64748B))),
                                ],
                              ),
                            ],
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: remaining == 0 ? AppTheme.screenshotGreen.withValues(alpha: 0.1) : AppTheme.jaibRed.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(
                              remaining == 0 ? 'مسدد بالكامل' : 'قيد الاستحقاق',
                              style: GoogleFonts.cairo(
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                                color: remaining == 0 ? AppTheme.screenshotGreen : AppTheme.jaibRed,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      // Progress bar
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text('نسبة الإنجاز: ${(progress * 100).toInt()}%', style: GoogleFonts.cairo(fontSize: 10, color: const Color(0xFF64748B))),
                          Text('المسدد: ${paid.toInt()} / ${total.toInt()} ريال', style: GoogleFonts.cairo(fontSize: 10, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A))),
                        ],
                      ),
                      const SizedBox(height: 4),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          value: progress,
                          backgroundColor: const Color(0xFFF1F5F9),
                          valueColor: AlwaysStoppedAnimation<Color>(remaining == 0 ? AppTheme.screenshotGreen : AppTheme.jaibRed),
                          minHeight: 6,
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 12),

                // 2. Jaib Wallet Action Button (Standard Compact Height)
                SizedBox(
                  width: double.infinity,
                  height: 46,
                  child: ElevatedButton.icon(
                    onPressed: _showJaibPaymentSheet,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.jaibRed,
                      foregroundColor: Colors.white,
                      elevation: 0,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    icon: const Icon(Icons.account_balance_wallet_rounded, size: 18),
                    label: Text(
                      'سداد فوري عبر محفظة جيب الإلكترونية',
                      style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold),
                    ),
                  ),
                ),

                const SizedBox(height: 16),

                // 3. Tab Bar
                Container(
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: const Color(0xFFE2E8F0)),
                  ),
                  child: TabBar(
                    controller: _tabController,
                    labelColor: AppTheme.screenshotBlue,
                    unselectedLabelColor: const Color(0xFF64748B),
                    labelStyle: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold),
                    indicatorColor: AppTheme.screenshotBlue,
                    indicatorSize: TabBarIndicatorSize.tab,
                    tabs: const [
                      Tab(text: 'بنود الرسوم المقررة'),
                      Tab(text: 'سندات القبض المعتمدة'),
                    ],
                  ),
                ),

                const SizedBox(height: 12),

                // 4. Tab View
                SizedBox(
                  height: 380,
                  child: TabBarView(
                    controller: _tabController,
                    children: [
                      // Sub Tab 1: Fees breakdown
                      ListView(
                        physics: const BouncingScrollPhysics(),
                        children: [
                          _buildFeeItem('القسط الدراسي الأول', '120,000 ريال', paid >= 120000),
                          _buildFeeItem('رسوم الكتب المدرسية والمناهج', '35,000 ريال', paid >= 155000),
                          _buildFeeItem('رسوم الأنشطة والمختبرات', '15,000 ريال', paid >= 170000),
                          _buildFeeItem('رسوم البطاقة والمنظومة الذكية', '10,000 ريال', paid >= 180000),
                        ],
                      ),

                      // Sub Tab 2: Payment receipts
                      ListView.builder(
                        physics: const BouncingScrollPhysics(),
                        itemCount: widget.api.paymentReceipts.length,
                        itemBuilder: (context, index) {
                          final rec = widget.api.paymentReceipts[index];
                          return Container(
                            margin: const EdgeInsets.only(bottom: 8),
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(14),
                              border: Border.all(color: const Color(0xFFE2E8F0)),
                              boxShadow: AppTheme.softShadow,
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.receipt_long_rounded, color: AppTheme.screenshotGreen, size: 24),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        rec['title'],
                                        style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
                                      ),
                                      Text(
                                        '${rec['id']} • ${rec['method']}',
                                        style: GoogleFonts.cairo(fontSize: 10, color: const Color(0xFF64748B)),
                                      ),
                                    ],
                                  ),
                                ),
                                Text(
                                  '${(rec['amount'] as double).toInt()} ر.ي',
                                  style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.screenshotGreen),
                                ),
                              ],
                            ),
                          );
                        },
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildFeeItem(String title, String amount, bool isPaid) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFE2E8F0)),
        boxShadow: AppTheme.softShadow,
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.bold, color: const Color(0xFF0F172A)),
              ),
              Text(
                amount,
                style: GoogleFonts.cairo(fontSize: 11, color: const Color(0xFF64748B)),
              ),
            ],
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              color: isPaid ? AppTheme.screenshotGreen.withValues(alpha: 0.1) : AppTheme.jaibRed.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(
              isPaid ? 'مسدد' : 'متبقي',
              style: GoogleFonts.cairo(
                fontSize: 10,
                fontWeight: FontWeight.bold,
                color: isPaid ? AppTheme.screenshotGreen : AppTheme.jaibRed,
              ),
            ),
          ),
        ],
      ),
    );
  }
}



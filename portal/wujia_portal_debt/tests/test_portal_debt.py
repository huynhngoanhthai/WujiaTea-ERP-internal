"""Test module Công nợ portal — wire backend thật (Sprint 48, BA Tasks!STT9).

Chạy: `--test-tags wujia_debt`.

  1. `TestPortalDebtWired` — seam đọc account.move/account.payment thật: scope franchise
     (isolation), credit note giảm nợ, overdue, payment history lọc trạng thái, bank info,
     badge store.
  2. `TestPortalDebtRules` — cụm C2: trạng thái tuần == trạng thái dòng, dư có, đa tệ,
     tuần mặc định + hạn thanh toán.
  3. `TestPortalDebtAccess` — controller chặn Staff, cho Owner/Manager, empty khi chưa
     chọn cửa hàng, và cụm C3: trang thanh toán (bank chưa cấu hình, 2 shell, gỡ QR).

⚠️ KHÔNG import `odoo.addons.account.tests.common` — chuỗi import của nó kéo theo
`base.tests.test_date_utils` dùng `freeze_time(as_kwarg=...)`, vỡ với freezegun cũ trong
env. Dựng fixture kế toán bằng ORM thuần trên chart `generic_coa` đã cài sẵn.
"""

from datetime import date, timedelta

from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase

from .common import load_vi

SUMMARY_KEYS = {
    'franchise_id', 'franchise_code', 'week_key', 'week_label', 'week_number',
    'week_short', 'weeks', 'state', 'total', 'paid', 'remaining', 'invoice_count',
    'has_overdue', 'overdue_count', 'nearest_due', 'confirmed_date', 'invoices',
    'amount_due', 'credit_amount', 'payment_due_date', 'payment_due_label',
}
INVOICE_KEYS = {'name', 'date', 'due', 'status', 'amount'}
# PC (STT10) mở rộng additive: bảng cần 3 số/hoá đơn.
PC_INVOICE_KEYS = {'total', 'paid', 'remaining'}
PAYMENT_KEYS = {'ref', 'date', 'time', 'method', 'trace', 'amount', 'state',
                'currency_symbol', 'currency_decimals', 'amount_label'}


@tagged('post_install', '-at_install', 'wujia_debt')
class TestPortalDebtWired(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.debt = cls.env['wujia.portal.debt']
        cls.company = cls.env.company
        cls.income = cls.env['account.account'].search(
            [('account_type', '=', 'income'), ('company_ids', 'in', cls.company.id)], limit=1) \
            or cls.env['account.account'].search([('account_type', '=', 'income')], limit=1)
        cls.sale_journal = cls.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', cls.company.id)], limit=1)
        cls.bank_journal = cls.env['account.journal'].search(
            [('type', 'in', ('bank', 'cash')), ('company_id', '=', cls.company.id)], limit=1)
        cls.customer = cls.env['res.partner'].create({'name': 'Debt Test Customer'})

        Partner = cls.env['res.partner']
        Franchise = cls.env['wujia.franchise.management']
        cls.franchise = Franchise.create({
            'code': 'HDEBT1', 'name': 'Debt store 1', 'franchise_end_date': '2030-01-01',
            'partner_id': Partner.create({'name': 'HDEBT1 partner'}).id})
        cls.other = Franchise.create({
            'code': 'HDEBT2', 'name': 'Debt store 2', 'franchise_end_date': '2030-01-01',
            'partner_id': Partner.create({'name': 'HDEBT2 partner'}).id})

        # Tuần thử: Mon 2026-07-13 → Sun 2026-07-19; "hôm nay" của logic tuần = 2026-07-15.
        cls.week_today = date(2026, 7, 15)

        cls.inv_overdue = cls._move('out_invoice', cls.franchise, date(2026, 7, 14),
                                    date(2026, 7, 14), 1_000_000)   # due < 07-15 → overdue
        cls.inv_open = cls._move('out_invoice', cls.franchise, date(2026, 7, 16),
                                 date(2026, 7, 25), 2_000_000)      # chưa tới hạn trong tuần
        cls.credit = cls._move('out_refund', cls.franchise, date(2026, 7, 16),
                               date(2026, 7, 16), 500_000)           # credit note giảm nợ
        cls._move('out_invoice', cls.other, date(2026, 7, 16),      # cửa hàng khác — KHÔNG lọt
                  date(2026, 7, 25), 9_000_000)

        cls.pay_ok = cls._payment(4_150_000, date(2026, 7, 10), cls.franchise, post=True)
        cls.pay_draft = cls._payment(999_000, date(2026, 7, 12), cls.franchise, post=False)

    @classmethod
    def _move(cls, move_type, franchise, inv_date, due, amount):
        move = cls.env['account.move'].create({
            'move_type': move_type,
            'partner_id': cls.customer.id,
            'invoice_date': inv_date,
            'journal_id': cls.sale_journal.id,
            'franchise_id': franchise.id,
            'invoice_payment_term_id': False,
            'invoice_line_ids': [(0, 0, {
                'name': 'line', 'quantity': 1, 'price_unit': amount,
                'account_id': cls.income.id, 'tax_ids': [(6, 0, [])],
            })],
        })
        move.action_post()
        move.invoice_date_due = due   # sau post → payment term không tính đè
        return move

    @classmethod
    def _payment(cls, amount, pay_date, franchise, post):
        payment = cls.env['account.payment'].create({
            'amount': amount, 'date': pay_date, 'payment_type': 'inbound',
            'partner_type': 'customer', 'partner_id': cls.customer.id,
            'journal_id': cls.bank_journal.id,
        })
        if post:
            payment.action_post()
        payment.franchise_id = franchise
        return payment

    def _summary(self):
        return self.debt.get_summary(self.franchise.id, week='2026-W29', today=self.week_today)

    # ---- summary -----------------------------------------------------
    def test_summary_keys_and_types(self):
        s = self._summary()
        self.assertTrue(SUMMARY_KEYS.issubset(set(s)))
        self.assertEqual(s['invoice_count'], len(s['invoices']))
        for inv in s['invoices']:
            self.assertTrue(INVOICE_KEYS.issubset(set(inv)))
            self.assertIsInstance(inv['date'], date)   # template gọi .strftime
            self.assertIsInstance(inv['due'], date)
            self.assertIn(inv['status'], ('overdue', 'unpaid', 'partial', 'credit', 'paid'))

    # ---- PC (STT10): invoice enrichment total/paid/remaining --------
    def test_invoice_enrichment_total_paid_remaining(self):
        s = self._summary()
        for inv in s['invoices']:
            self.assertTrue(PC_INVOICE_KEYS.issubset(set(inv)),
                            'thiếu key PC total/paid/remaining trên hoá đơn')
            # Bất biến bảng PC: Tổng = Đã trả + Còn phải trả (giữ cả với credit note âm).
            self.assertAlmostEqual(inv['total'], inv['paid'] + inv['remaining'], places=2)
        # Tổng 3 cột khớp tổng tuần (credit note out_refund vẫn âm nhất quán).
        self.assertAlmostEqual(sum(i['total'] for i in s['invoices']), s['total'], places=2)
        self.assertAlmostEqual(sum(i['remaining'] for i in s['invoices']), s['remaining'], places=2)
        by_name = {i['name']: i for i in s['invoices']}
        ov = by_name[self.inv_overdue.name]                 # chưa trả đồng nào
        self.assertEqual((ov['total'], ov['paid'], ov['remaining']), (1_000_000, 0, 1_000_000))
        cn = by_name[self.credit.name]                       # credit note giữ dấu âm
        self.assertEqual(cn['total'], -500_000)
        self.assertEqual(cn['paid'], 0)

    def test_credit_note_reduces_debt_and_totals_consistent(self):
        s = self._summary()
        self.assertEqual(s['total'], 2_500_000)        # 1,000,000 + 2,000,000 − 500,000
        self.assertEqual(s['remaining'], 2_500_000)
        self.assertEqual(s['paid'] + s['remaining'], s['total'])
        self.assertEqual(s['invoice_count'], 3)

    def test_overdue_within_week(self):
        s = self._summary()
        self.assertTrue(s['has_overdue'])
        self.assertEqual(s['overdue_count'], 1)        # chỉ inv_overdue trong tuần
        self.assertEqual(s['state'], 'outstanding')
        self.assertEqual(s['nearest_due'], date(2026, 7, 14))

    def test_franchise_isolation(self):
        s = self._summary()
        self.assertEqual(s['total'], 2_500_000)        # 9tr của cửa hàng khác không cộng vào
        other_name = self.env['account.move'].search(
            [('franchise_id', '=', self.other.id)], limit=1).name
        self.assertNotIn(other_name, {inv['name'] for inv in s['invoices']})

    def test_no_franchise_returns_empty(self):
        s = self.debt.get_summary(False, today=self.week_today)
        self.assertEqual(s['state'], 'empty')
        self.assertEqual(s['invoices'], [])
        self.assertTrue(SUMMARY_KEYS.issubset(set(s)))

    def test_invalid_week_falls_back(self):
        default = self.debt.get_summary(self.franchise.id, today=self.week_today)
        for bad in (None, '', 'abc', '9999-W99', 0, False):
            self.assertEqual(
                self.debt.get_summary(self.franchise.id, week=bad, today=self.week_today)['week_key'],
                default['week_key'])

    # ---- payment history --------------------------------------------
    def test_payment_history_excludes_draft(self):
        h = self.debt.get_payments(self.franchise.id, today=date(2026, 7, 31))
        self.assertEqual(h['date_from'], date(2026, 7, 1))
        refs = {p['ref'] for p in h['payments']}
        self.assertIn(self.pay_ok.name, refs)
        self.assertNotIn(self.pay_draft.name, refs)    # draft bị loại
        self.assertEqual(h['total'], 4_150_000)
        for p in h['payments']:
            self.assertTrue(PAYMENT_KEYS.issubset(set(p)))
            self.assertIsInstance(p['date'], date)

    def test_payment_history_franchise_isolation(self):
        other_pay = self._payment(7_000_000, date(2026, 7, 5), self.other, post=True)
        h = self.debt.get_payments(self.franchise.id, today=date(2026, 7, 31))
        self.assertNotIn(other_pay.name, {p['ref'] for p in h['payments']})

    # ---- PC (STT10): keyword filter (mã payment / nội dung) ---------
    def test_payment_history_keyword_filters(self):
        base = self.debt.get_payments(self.franchise.id, today=date(2026, 7, 31))
        self.assertIn(self.pay_ok.name, {p['ref'] for p in base['payments']})
        # Khớp theo mã payment → còn giao dịch; không khớp → rỗng.
        hit = self.debt.get_payments(self.franchise.id, today=date(2026, 7, 31),
                                     keyword=self.pay_ok.name)
        self.assertIn(self.pay_ok.name, {p['ref'] for p in hit['payments']})
        miss = self.debt.get_payments(self.franchise.id, today=date(2026, 7, 31),
                                      keyword='ZZ-KHONG-KHOP-QWERTY')
        self.assertEqual(miss['payments'], [])
        # keyword rỗng/None ⇒ không đổi hành vi (mobile không truyền).
        for empty in (None, '', '   '):
            self.assertEqual(len(self.debt.get_payments(
                self.franchise.id, today=date(2026, 7, 31), keyword=empty)['payments']),
                len(base['payments']))

    # ---- bank info ---------------------------------------------------
    def test_bank_info_picks_smallest_sequence_enabled(self):
        Bank = self.env['res.partner.bank']
        partner = self.company.partner_id
        # Như test kế bên: DB giống UAT có thể đã bật sẵn 1 TK portal, và nếu nó cùng
        # `sequence` thì `id` nhỏ hơn thắng ⇒ tắt trước cho tất định.
        Bank.search([('id', 'in', self.company.bank_ids.ids)]).portal_payment_enabled = False
        Bank.create({'acc_number': 'ACC-DISABLED', 'partner_id': partner.id,
                     'sequence': 1, 'portal_payment_enabled': False})
        Bank.create({'acc_number': 'ACC-WIN', 'partner_id': partner.id,
                     'sequence': 5, 'portal_payment_enabled': True})
        Bank.create({'acc_number': 'ACC-LATE', 'partner_id': partner.id,
                     'sequence': 9, 'portal_payment_enabled': True})
        bank = self.debt.get_bank_info(self.franchise.id, 2_500_000, 29)
        self.assertTrue(bank['configured'])
        self.assertEqual(bank['account'], 'ACC-WIN')          # enabled + sequence nhỏ nhất
        self.assertEqual(bank['memo'], 'HDEBT1 K29 2500000')  # backend tự tính nội dung CK

    def test_bank_info_not_configured_flag(self):
        # DB thật có thể đã bật sẵn 1 TK portal → tắt trong transaction test cho tất định.
        self.env['res.partner.bank'].search(
            [('id', 'in', self.company.bank_ids.ids)]).portal_payment_enabled = False
        bank = self.debt.get_bank_info(self.franchise.id, 100, 29)
        # WJ-DEBT-002: cờ tường minh + KHÔNG trường rỗng nào mang chữ (template tự rẽ).
        self.assertFalse(bank['configured'])
        self.assertEqual([bank['name'], bank['holder'], bank['account'], bank['memo']],
                         ['', '', '', ''])

    # ---- PC (STT10): tách empty → empty_week / no_debt (rule 10c/10d) ----
    def test_empty_substate(self):
        # Cửa hàng còn công nợ ở kỳ khác → 'empty_week'.
        self.franchise.invalidate_recordset(['portal_debt_remaining'])
        self.assertGreater(self.franchise.portal_debt_remaining, 0)
        self.assertEqual(self.debt._empty_substate(self.franchise.id), 'empty_week')
        # Cửa hàng không phát sinh gì → hết nợ mọi kỳ → 'no_debt'.
        clean = self.env['wujia.franchise.management'].create({
            'code': 'HDEBT0', 'name': 'Debt store empty', 'franchise_end_date': '2030-01-01',
            'partner_id': self.env['res.partner'].create({'name': 'HDEBT0 partner'}).id})
        self.assertEqual(clean.portal_debt_remaining or 0, 0)
        self.assertEqual(self.debt._empty_substate(clean.id), 'no_debt')
        # Chưa chọn cửa hàng → 'no_debt' (không raise).
        self.assertEqual(self.debt._empty_substate(False), 'no_debt')

    # ---- badge store (perf) -----------------------------------------
    def test_badge_aggregates_stored(self):
        self.franchise.invalidate_recordset(
            ['portal_overdue_invoice_count', 'portal_debt_remaining'])
        # Badge quá hạn theo NGÀY THẬT: cả 2 hoá đơn (due 07-14 & 07-25) đều đã qua hạn.
        self.assertEqual(self.franchise.portal_overdue_invoice_count, 2)
        self.assertEqual(self.franchise.portal_debt_remaining, 2_500_000)


@tagged('post_install', '-at_install', 'wujia_debt')
class TestPortalDebtRules(TransactionCase):
    """Cụm C2 — WJ-DEBT-001/004/007/010: trạng thái, đa tệ, dư có, tuần mặc định."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.debt = cls.env['wujia.portal.debt']
        cls.company = cls.env.company
        cls.income = cls.env['account.account'].search(
            [('account_type', '=', 'income')], limit=1)
        cls.sale_journal = cls.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', cls.company.id)], limit=1)
        cls.bank_journal = cls.env['account.journal'].search(
            [('type', 'in', ('bank', 'cash')), ('company_id', '=', cls.company.id)], limit=1)
        cls.customer = cls.env['res.partner'].create({'name': 'C2 customer'})
        Partner = cls.env['res.partner']
        Franchise = cls.env['wujia.franchise.management']
        cls.f_unpaid = Franchise.create({
            'code': 'HC201', 'name': 'C2 unpaid', 'franchise_end_date': '2030-01-01',
            'partner_id': Partner.create({'name': 'HC201 partner'}).id})
        cls.f_credit = Franchise.create({
            'code': 'HC202', 'name': 'C2 credit', 'franchise_end_date': '2030-01-01',
            'partner_id': Partner.create({'name': 'HC202 partner'}).id})
        cls.f_week = Franchise.create({
            'code': 'HC203', 'name': 'C2 weeks', 'franchise_end_date': '2030-01-01',
            'partner_id': Partner.create({'name': 'HC203 partner'}).id})

        # Tuần thử: Mon 2026-07-13 → Sun 2026-07-19, "hôm nay" = 2026-07-15.
        cls.today = date(2026, 7, 15)
        cls.week = '2026-W29'
        cls.inv_unpaid = cls._move('out_invoice', cls.f_unpaid, date(2026, 7, 14),
                                   date(2026, 7, 25), 72_450)      # chưa trả, chưa tới hạn

    @classmethod
    def _move(cls, move_type, franchise, inv_date, due, amount, currency=None):
        vals = {
            'move_type': move_type, 'partner_id': cls.customer.id, 'invoice_date': inv_date,
            'journal_id': cls.sale_journal.id, 'franchise_id': franchise.id,
            'invoice_payment_term_id': False,
            'invoice_line_ids': [(0, 0, {
                'name': 'line', 'quantity': 1, 'price_unit': amount,
                'account_id': cls.income.id, 'tax_ids': [(6, 0, [])]})],
        }
        if currency:
            vals['currency_id'] = currency.id
        move = cls.env['account.move'].create(vals)
        move.action_post()
        move.invoice_date_due = due
        return move

    @classmethod
    def _payment(cls, amount, pay_date, franchise, currency=None):
        vals = {'amount': amount, 'date': pay_date, 'payment_type': 'inbound',
                'partner_type': 'customer', 'partner_id': cls.customer.id,
                'journal_id': cls.bank_journal.id}
        if currency:
            vals['currency_id'] = currency.id
        payment = cls.env['account.payment'].create(vals)
        payment.action_post()
        payment.franchise_id = franchise
        return payment

    @classmethod
    def _reconcile(cls, move, payment):
        lines = (move.line_ids + payment.move_id.line_ids).filtered(
            lambda line: line.account_id.account_type == 'asset_receivable'
            and not line.reconciled)
        lines.reconcile()

    # ---- WJ-DEBT-001: card tổng quan == dòng hoá đơn ------------------
    def test_unpaid_week_matches_invoice_line(self):
        s = self.debt.get_summary(self.f_unpaid.id, week=self.week, today=self.today)
        self.assertEqual(s['state'], 'unpaid')          # KHÔNG còn 'partial' khi paid == 0
        self.assertEqual(s['paid'], 0)
        self.assertEqual(s['remaining'], self.inv_unpaid.amount_residual)
        self.assertEqual([i['status'] for i in s['invoices']], ['unpaid'])
        from odoo.addons.wujia_portal_debt.models.wujia_portal_debt import (
            INVOICE_BADGE, STATE_BADGE,
        )
        # Nhãn là `_lt` (J-V5) — so câu gốc, `==` trên lazy bị Odoo cấm.
        self.assertEqual(STATE_BADGE[s['state']][0]._source, INVOICE_BADGE['unpaid'][0]._source)

    def test_partial_only_when_something_paid(self):
        pay = self._payment(30_000, date(2026, 7, 15), self.f_unpaid)
        self._reconcile(self.inv_unpaid, pay)
        s = self.debt.get_summary(self.f_unpaid.id, week=self.week, today=self.today)
        self.assertEqual(s['state'], 'partial')
        self.assertEqual(s['paid'], 30_000)
        self.assertEqual([i['status'] for i in s['invoices']], ['partial'])

    # ---- WJ-DEBT-007: dư có -------------------------------------------
    def test_credit_balance_week(self):
        inv = self._move('out_invoice', self.f_credit, date(2026, 7, 14),
                         date(2026, 7, 25), 72_450)
        self._reconcile(inv, self._payment(72_450, date(2026, 7, 15), self.f_credit))
        self._move('out_refund', self.f_credit, date(2026, 7, 16), date(2026, 7, 16), 72_450)
        s = self.debt.get_summary(self.f_credit.id, week=self.week, today=self.today)
        self.assertEqual(s['remaining'], -72_450)
        self.assertEqual(s['state'], 'credit')
        self.assertEqual(s['amount_due'], 0)             # UI không bao giờ in số âm
        self.assertEqual(s['credit_amount'], 72_450)
        statuses = {i['name']: i['status'] for i in s['invoices']}
        self.assertNotIn('unpaid', statuses.values())    # credit note KHÔNG phải khoản nợ
        self.assertIn('credit', statuses.values())

    def test_memo_never_negative(self):
        self.env['res.partner.bank'].create({
            'acc_number': 'ACC-C2', 'partner_id': self.company.partner_id.id,
            'sequence': 1, 'portal_payment_enabled': True})
        bank = self.debt.get_bank_info(self.f_credit.id, -72_450, 33)
        self.assertNotIn('-', bank['memo'])
        self.assertTrue(bank['memo'].endswith(' 0'))

    # ---- WJ-DEBT-004: đa tệ -------------------------------------------
    def test_payment_history_per_currency(self):
        other = self.env.ref('base.EUR')     # khác currency công ty (USD trên UAT)
        other.active = True
        self.assertNotEqual(other, self.company.currency_id)
        self._payment(30_000, date(2026, 7, 3), self.f_week, currency=other)
        self._payment(1_000, date(2026, 7, 4), self.f_week)      # currency công ty
        h = self.debt.get_payments(self.f_week.id, today=date(2026, 7, 31))
        self.assertEqual(len({p['ref'] for p in h['payments']}), 2)
        symbols = {p['currency_symbol'] for p in h['payments']}
        self.assertIn(other.symbol, symbols)
        self.assertIn(self.company.currency_id.symbol, symbols)
        for pay in h['payments']:
            self.assertIn(pay['currency_symbol'], pay['amount_label'])
        # Mỗi loại tiền MỘT dòng tổng, không cộng chéo, không quy đổi.
        self.assertEqual(len(h['totals']), 2)
        self.assertEqual({t['symbol'] for t in h['totals']}, symbols)
        self.assertEqual({t['amount'] for t in h['totals']}, {30_000, 1_000})
        self.assertEqual(h['total'], 0)                  # nhiều currency ⇒ không có 1 tổng

    def test_payment_history_single_currency_keeps_total(self):
        self._payment(500, date(2026, 7, 6), self.f_unpaid)
        h = self.debt.get_payments(self.f_unpaid.id, today=date(2026, 7, 31))
        self.assertEqual(len(h['totals']), 1)
        self.assertEqual(h['total'], h['totals'][0]['amount'])

    # ---- WJ-DEBT-010: tuần mặc định + hạn thanh toán -------------------
    def test_default_week_prefers_oldest_overdue(self):
        today = date(2026, 8, 13)                        # thứ Năm, tuần W33
        self._move('out_invoice', self.f_week, date(2026, 7, 28),   # W31 — quá hạn cũ nhất
                   date(2026, 8, 6), 1_000)
        self._move('out_invoice', self.f_week, date(2026, 8, 4),    # W32 — cũng quá hạn
                   date(2026, 8, 10), 2_000)
        s = self.debt.get_summary(self.f_week.id, today=today)
        self.assertEqual(s['week_key'], '2026-W31')
        # ?week= hợp lệ vẫn thắng mặc định.
        self.assertEqual(self.debt.get_summary(
            self.f_week.id, week='2026-W33', today=today)['week_key'], '2026-W33')

    def test_default_week_previous_then_current(self):
        today = date(2026, 8, 13)
        # Không có gì quá hạn: hoá đơn tuần liền trước (W32), hạn còn xa.
        self._move('out_invoice', self.f_credit, date(2026, 8, 5), date(2026, 8, 20), 1_000)
        self.assertEqual(self.debt.get_summary(
            self.f_credit.id, today=today)['week_key'], '2026-W32')
        # Cửa hàng không có chứng từ nào trong 6 tuần → tuần hiện tại.
        clean = self.env['wujia.franchise.management'].create({
            'code': 'HC204', 'name': 'C2 clean', 'franchise_end_date': '2030-01-01',
            'partner_id': self.env['res.partner'].create({'name': 'HC204 partner'}).id})
        self.assertEqual(self.debt.get_summary(clean.id, today=today)['week_key'], '2026-W33')

    def test_payment_due_is_thursday_next_week(self):
        s = self.debt.get_summary(self.f_unpaid.id, week=self.week, today=self.today)
        self.assertEqual(s['payment_due_date'], date(2026, 7, 23))   # thứ Năm tuần kế
        self.assertEqual(s['payment_due_date'].weekday(), 3)
        self.assertEqual(s['payment_due_label'], '23/07/2026')
        empty = self.debt.get_summary(self.f_unpaid.id, week='2026-W27', today=self.today)
        self.assertEqual(empty['state'], 'empty')
        self.assertEqual(empty['payment_due_label'], '-')
        self.assertEqual(empty['remaining'], 0)


@tagged('post_install', '-at_install', 'wujia_debt')
class TestPortalDebtAccess(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Assert chữ tiếng Việt ⇒ user vi_VN + .po đã nạp (J-V5).
        load_vi(cls.env)
        cls.franchise = cls.env['wujia.franchise.management'].create({
            'code': 'HACC1', 'name': 'Access store', 'franchise_end_date': '2030-01-01',
            'partner_id': cls.env['res.partner'].create({'name': 'HACC1 partner'}).id})
        cls.owner = cls._portal_user('debt_owner', 'owner')
        cls.staff = cls._portal_user('debt_staff', 'staff')

        # Một hoá đơn chưa trả trong tuần hiện tại → trang /portal/debt/pay mới render
        # (C2 chặn route khi amount_due <= 0).
        today = date.today()
        cls.due_week = '%04d-W%02d' % today.isocalendar()[:2]
        cls.empty_week = '%04d-W%02d' % (today - timedelta(weeks=3)).isocalendar()[:2]
        invoice = cls.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': cls.env['res.partner'].create({'name': 'HACC1 customer'}).id,
            'invoice_date': today,
            'journal_id': cls.env['account.journal'].search(
                [('type', '=', 'sale'), ('company_id', '=', cls.env.company.id)], limit=1).id,
            'franchise_id': cls.franchise.id,
            'invoice_payment_term_id': False,
            'invoice_line_ids': [(0, 0, {
                'name': 'line', 'quantity': 1, 'price_unit': 1_500_000,
                'account_id': cls.env['account.account'].search(
                    [('account_type', '=', 'income')], limit=1).id,
                'tax_ids': [(6, 0, [])]})],
        })
        invoice.action_post()
        invoice.invoice_date_due = today + timedelta(days=7)

    @classmethod
    def _portal_user(cls, login, role):
        user = cls.env['res.users'].create({
            'name': login, 'login': login, 'password': login, 'lang': 'vi_VN',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        cls.env['wujia.franchise.member'].create({
            'user_id': user.id, 'franchise_id': cls.franchise.id, 'role': role})
        return user

    def test_owner_can_view(self):
        self.authenticate('debt_owner', 'debt_owner')
        res = self.url_open('/portal/debt', timeout=30)
        self.assertEqual(res.status_code, 200)
        self.assertIn('wj-debt', res.text)
        self.assertNotIn('Không có quyền xem', res.text)

    def test_owner_pc_blocks_render(self):
        """Khối desktop STT10 render không lỗi (500 sẽ trượt): tab strip + filter PC."""
        self.authenticate('debt_owner', 'debt_owner')
        res = self.url_open('/portal/debt', timeout=30)
        self.assertEqual(res.status_code, 200)
        self.assertIn('wj-debt-pc', res.text)          # wrapper desktop
        self.assertIn('wj-debt-pc-tabs', res.text)     # tab Công nợ / Lịch sử
        self.assertIn('wj-debt-pc-filter', res.text)   # filter row PC

    def test_payment_history_pc_keyword_renders(self):
        """PC lịch sử + tham số tìm kiếm ?q= render 200 (ô search hiện đúng)."""
        self.authenticate('debt_owner', 'debt_owner')
        res = self.url_open('/portal/debt/payment-history?q=abc', timeout=30)
        self.assertEqual(res.status_code, 200)
        self.assertIn('wj-debt-pc', res.text)
        self.assertIn('Tìm mã thanh toán', res.text)   # placeholder ô search PC

    def _post_payments(self, n):
        journal = self.env['account.journal'].search(
            [('type', '=', 'bank'), ('company_id', '=', self.env.company.id)], limit=1)
        if not journal:
            journal = self.env['account.journal'].create(
                {'name': 'HACC1 bank', 'type': 'bank', 'code': 'HAB'})
        partner = self.env['res.partner'].create({'name': 'HACC1 payer'})
        for i in range(n):
            pay = self.env['account.payment'].create({
                'amount': 100_000 + i, 'date': date.today(), 'payment_type': 'inbound',
                'partner_type': 'customer', 'partner_id': partner.id, 'journal_id': journal.id})
            pay.action_post()
            pay.franchise_id = self.franchise

    def test_payment_history_mobile_paginated_like_pc(self):
        """Retest UI-DATALIST-001: 12 giao dịch → mobile 10 thẻ + nút trang (cả 2 kênh);
        trang 2 còn 2 thẻ; 50/trang → 12 thẻ và không còn nút trang."""
        self._post_payments(12)
        self.authenticate('debt_owner', 'debt_owner')
        res = self.url_open('/portal/debt/payment-history', timeout=30)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.text.count('wj-debt-pay '), 10)
        self.assertEqual(res.text.count('wj-pagination__nav'), 2)
        res = self.url_open('/portal/debt/payment-history?page=2', timeout=30)
        self.assertEqual(res.text.count('wj-debt-pay '), 2)
        res = self.url_open('/portal/debt/payment-history?page_size=50', timeout=30)
        self.assertEqual(res.text.count('wj-debt-pay '), 12)
        self.assertNotIn('wj-pagination__nav', res.text)

    def test_pay_page_blocked_when_nothing_due(self):
        """WJ-DEBT-007: hết nợ → về trang công nợ kèm thông báo, không dựng QR/STK."""
        self.authenticate('debt_owner', 'debt_owner')
        res = self.url_open('/portal/debt/pay?week=%s' % self.empty_week, timeout=30)
        self.assertEqual(res.status_code, 200)
        self.assertIn('/portal/debt', res.url)
        self.assertNotIn('/portal/debt/pay', res.url)
        self.assertNotIn('SỐ TIỀN CẦN CHUYỂN', res.text)
        self.assertIn('không còn khoản cần thanh toán', res.text)

    # ---- cụm C3: trang thanh toán ------------------------------------
    def _pay_page(self):
        """Trang pay của tuần có nợ thật (route tự chặn khi amount_due <= 0 — C2)."""
        self.authenticate('debt_owner', 'debt_owner')
        return self.url_open(
            '/portal/debt/pay?week=%s' % self.due_week, timeout=30)

    def test_pay_page_without_bank_shows_single_empty_state(self):
        """WJ-DEBT-002: chưa cấu hình TK → 1 thông báo, không nút copy, không trường rỗng."""
        self.env['res.partner.bank'].search(
            [('id', 'in', self.env.company.bank_ids.ids)]).portal_payment_enabled = False
        self.env.flush_all()
        res = self._pay_page()
        self.assertEqual(res.status_code, 200)
        self.assertIn('Chưa cấu hình tài khoản nhận thanh toán', res.text)
        self.assertNotIn('data-wj-debt="copy"', res.text)
        self.assertNotIn('THÔNG TIN CHUYỂN KHOẢN', res.text)

    def test_pay_page_with_bank_has_both_shells_and_copy(self):
        """WJ-DEBT-003/005: mobile d-lg-none + khối PC, nút copy có ô phản hồi."""
        self.env['res.partner.bank'].search(
            [('id', 'in', self.env.company.bank_ids.ids)]).portal_payment_enabled = False
        self.env['res.partner.bank'].create({
            'acc_number': 'C3-ACC-0001', 'partner_id': self.env.company.partner_id.id,
            'acc_holder_name': 'NGO GIA C3', 'sequence': 1, 'portal_payment_enabled': True})
        self.env.flush_all()
        res = self._pay_page()
        self.assertEqual(res.status_code, 200)
        self.assertIn('wj-debt--pay d-lg-none', res.text)   # khối mobile chỉ dưới 992
        self.assertIn('wj-debt-pc', res.text)               # khối desktop
        self.assertIn('C3-ACC-0001', res.text)
        self.assertEqual(res.text.count('data-wj-debt="copy"'), 4)   # 2 mobile + 2 PC
        self.assertIn('wj-debt-copy-msg', res.text)

    def test_no_qr_markup_left(self):
        """WJ-DEBT-008: gỡ hẳn khối QR ở cả trang pay và modal PC."""
        self.env['res.partner.bank'].search(
            [('id', 'in', self.env.company.bank_ids.ids)]).portal_payment_enabled = False
        self.env['res.partner.bank'].create({
            'acc_number': 'C3-ACC-0002', 'partner_id': self.env.company.partner_id.id,
            'sequence': 1, 'portal_payment_enabled': True})
        self.env.flush_all()
        for text in (self._pay_page().text,
                     self.url_open('/portal/debt', timeout=30).text):
            for dead in ('wj-debt-qr', 'wj-debt-pc-qr', 'QR minh họa',
                         'Quét QR để chuyển khoản', 'Tải mã QR'):
                self.assertNotIn(dead, text)

    def test_staff_is_denied(self):
        self.authenticate('debt_staff', 'debt_staff')
        for url in ('/portal/debt', '/portal/debt/payment-history', '/portal/debt/pay'):
            res = self.url_open(url, timeout=30)
            self.assertEqual(res.status_code, 403)
            self.assertIn('Không có quyền xem', res.text)

    def test_admin_without_store_gets_empty_not_error(self):
        self.authenticate('admin', 'admin')
        for url in ('/portal/debt', '/portal/debt/payment-history', '/portal/debt/pay'):
            res = self.url_open(url, timeout=30)
            self.assertEqual(res.status_code, 200)
            self.assertIn('wj-debt', res.text)


@tagged('post_install', '-at_install', 'wujia_debt')
class TestShortAmountSigned(TransactionCase):
    """UI-MOB-HOME-004 — ô KPI Công nợ rộng ~64px ở 360px, chuỗi in ra phải NGẮN.

    Số âm (trả thừa / credit note) từng rớt qua cả hai bậc rút gọn nên in nguyên
    `-72449 $` rồi bị bẻ thành `-7244` / `9 $` trên ảnh BA. Guard giữ QUAN HỆ: mọi số
    tiền, dấu nào, độ lớn nào, đều ra chuỗi ≤ 7 ký tự.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Hậu tố tỷ/tr/k là bản dịch vi_VN của câu gốc EN (J-V5).
        cls.env_vi = load_vi(cls.env)

    def _f(self, amount, env=None):
        from odoo.addons.wujia_portal_debt.models.wujia_portal_debt import _short_amount
        return _short_amount(amount, '$', self.env_vi if env is None else env)

    def test_negative_amounts_are_shortened_like_positive_ones(self):
        for value, expected in ((-72449, '-72k'), (-1000, '-1k'),
                                (-12650000, '-12,7tr'), (-2500000000, '-2,5tỷ')):
            with self.subTest(value=value):
                self.assertEqual(self._f(value), expected)
                self.assertEqual(self._f(-value), expected.lstrip('-'))

    def test_worst_case_string_stays_short_enough_for_the_tile(self):
        # BA yêu cầu retest đúng giá trị này; 64px ở cỡ chữ chung 22px ≈ 7 ký tự.
        self.assertEqual(self._f(-999999999), '-1tỷ')
        for value in (-999999999, 999999999, -2500000000, -12650000, -999, 0):
            with self.subTest(value=value):
                self.assertLessEqual(len(self._f(value)), 7)

    def test_currency_symbol_only_on_the_unabbreviated_tier(self):
        self.assertEqual(self._f(0), '0 $')
        self.assertEqual(self._f(-999), '-999 $')
        for value in (1000, -1000, 10 ** 6, -10 ** 9):
            with self.subTest(value=value):
                self.assertNotIn('$', self._f(value))

    def test_tier_boundaries_do_not_print_a_full_next_tier(self):
        # Làm tròn 1 chữ số đẩy 999.999.999 thành '1000' ⇒ phải lên bậc, không in '1000tr'.
        self.assertEqual(self._f(999949999), '999,9tr')
        self.assertEqual(self._f(999950000), '1tỷ')
        self.assertEqual(self._f(999999), '999k')
        self.assertEqual(self._f(10 ** 6), '1tr')

    def test_english_suffixes_and_decimal_point(self):
        """J-V5: en_US dùng hậu tố + dấu thập phân của tiếng Anh; vi_VN giữ y chữ cũ."""
        env_en = self.env(context=dict(self.env.context, lang='en_US'))
        for value, en, vi in ((12650000, '12.7M', '12,7tr'), (-2500000000, '-2.5B', '-2,5tỷ'),
                              (999950000, '1B', '1tỷ'), (72449, '72K', '72k'), (999, '999 $', '999 $')):
            with self.subTest(value=value):
                self.assertEqual(self._f(value, env_en), en)
                self.assertEqual(self._f(value), vi)

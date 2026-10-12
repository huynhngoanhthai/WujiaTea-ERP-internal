"""J-V5 — câu gốc của Công nợ là tiếng Anh; user vi_VN phải thấy y chữ trước phiên.

Bảng VN dưới đây chép nguyên từ source TRƯỚC J-V5 (HEAD a6f97309) — chốt chặn khi ai đó đổi
câu EN mà quên glossary/.po (mutation "bỏ load_vi" không bắt được vì DB đo đã nạp .po).
"""

import os
import re
from datetime import date, timedelta

from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase

from odoo.addons.wujia_portal_base.tests.common import legacy_vn_badge

from .common import load_vi

# Nhãn badge viết cứng trước J-V5.
STATE_VI = {
    'outstanding': 'Có quá hạn', 'partial': 'Thanh toán một phần', 'unpaid': 'Chưa thanh toán',
    'credit': 'Dư có', 'paid': 'Đã thanh toán',
}
INVOICE_VI = {
    'overdue': 'Quá hạn', 'unpaid': 'Chưa thanh toán', 'partial': 'Một phần',
    'credit': 'Giấy báo có', 'paid': 'Đã thanh toán',
}
# Câu JS nút sao chép trước J-V5 (portal_debt.js).
JS_VI = {
    'copy-empty': 'Chưa có giá trị để sao chép.',
    'copied': 'Đã sao chép',
    'copy-failed': 'Không sao chép được — chạm giữ vào giá trị để copy thủ công.',
}
JS_EN = {
    'copy-empty': 'Nothing to copy yet.',
    'copied': 'Copied',
    'copy-failed': "Couldn't copy — press and hold the value to copy it manually.",
}
def _text(html):
    """Chữ hiển thị thô: bỏ thẻ, gộp khoảng trắng."""
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))


def _strip_comments(arch):
    return re.sub(r'<!--.*?-->', '', arch, flags=re.S)


MODULE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@tagged('post_install', '-at_install', 'wujia_debt', 'wujia_jv5')
class TestJv5Labels(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env_vi = load_vi(cls.env)
        cls.env_en = cls.env(context=dict(cls.env.context, lang='en_US'))

    def test_badge_labels_vi_unchanged_and_same_colour(self):
        from odoo.addons.wujia_portal_debt.models.wujia_portal_debt import (
            INVOICE_BADGE, STATE_BADGE, translated_badges,
        )
        for table, vi_table in ((STATE_BADGE, STATE_VI), (INVOICE_BADGE, INVOICE_VI)):
            vi = translated_badges(self.env_vi, table)
            en = translated_badges(self.env_en, table)
            for key, old in vi_table.items():
                with self.subTest(key=key):
                    lazy, css = table[key]
                    self.assertEqual(vi[key][0], old)
                    self.assertEqual(en[key][0], lazy._source)
                    self.assertNotEqual(en[key][0], old)
                    # Màu không đổi so với nhãn VN cũ (không rơi về neutral).
                    self.assertEqual(css, legacy_vn_badge(old))
                    self.assertEqual(vi[key][1], css)

    def test_fallback_bank_and_method_follow_env_lang(self):
        from odoo.addons.wujia_portal_debt.models import wujia_portal_debt as mod
        src = open(mod.__file__, encoding='utf-8').read()
        self.assertIn("self.env._('Bank')", src)
        self.assertIn("self.env._('Bank transfer')", src)
        self.assertEqual(self.env_vi._('Bank'), 'Ngân hàng')
        self.assertEqual(self.env_vi._('Bank transfer'), 'Chuyển khoản')

    def test_pager_item_labels(self):
        from odoo.addons.wujia_portal_debt.controllers import portal as ctrl
        src = open(ctrl.__file__, encoding='utf-8').read()
        self.assertIn("item_label=_lt('invoices')", src)
        self.assertIn("item_label=_lt('transactions')", src)
        self.assertEqual(self.env_vi._(ctrl._lt('invoices')), 'hóa đơn')
        self.assertEqual(self.env_vi._(ctrl._lt('transactions')), 'giao dịch')

    def test_view_names_and_labels_in_arch(self):
        """Arch vi_VN của 4 template chính vẫn chứa chữ cũ; en_US là câu gốc EN."""
        cases = {
            'wujia_portal_debt.portal_debt_overview': ('Công nợ', 'Hóa đơn trong tuần', 'Thanh toán số còn lại',
                                                       'Không phát sinh', 'Đã trả', 'Được trừ', 'Còn lại'),
            'wujia_portal_debt.portal_debt_payment_history': ('Lịch sử thanh toán', 'Thời gian thanh toán',
                                                              'Kỳ được chọn chưa có khoản thanh toán nào được xác nhận.'),
            'wujia_portal_debt.portal_debt_pay': ('SỐ TIỀN CẦN CHUYỂN', 'Về trang công nợ'),
            'wujia_portal_debt.wj_debt_pc_bank_block': tuple(JS_VI.values()),
        }
        for xmlid, words in cases.items():
            view = self.env.ref(xmlid)
            # Comment XML (ghi chú dev, không hiển thị) không dịch ⇒ bỏ trước khi so.
            arch_vi = _strip_comments(view.with_env(self.env_vi).arch)
            arch_en = _strip_comments(view.with_env(self.env_en).arch)
            for word in words:
                with self.subTest(view=xmlid, word=word):
                    self.assertIn(word, arch_vi)
                    self.assertNotIn(word, arch_en)


@tagged('post_install', '-at_install', 'wujia_debt', 'wujia_jv5')
class TestJv5JsMessages(TransactionCase):
    """Mọi key `copyMsg(btn, '<key>'` trong portal_debt.js có `data-wj-msg-<key>` trên CẢ hai
    khối ngân hàng (PC dùng chung + mobile trang pay), và fallback trong .js là tiếng Anh."""

    def _read(self, rel):
        with open(os.path.join(MODULE_DIR, rel), encoding='utf-8') as fh:
            return fh.read()

    def test_every_js_key_has_an_attribute_on_both_roots(self):
        js = self._read('static/src/js/portal_debt.js')
        keys = set(re.findall(r"copyMsg\(btn, '([\w-]+)'", js))
        self.assertEqual(keys, set(JS_EN))
        xml = self._read('views/portal_debt.xml')
        self.assertEqual(xml.count('t-att="_debt_copy_msgs"'), 2)
        for key in keys:
            with self.subTest(key=key):
                self.assertEqual(xml.count("'data-wj-msg-%s'" % key), 2)
        for key, en in JS_EN.items():
            self.assertIn(en, js)
            self.assertIn(en, xml)

    def test_no_vietnamese_left_in_js(self):
        js = self._read('static/src/js/portal_debt.js')
        code = re.sub(r'/\*.*?\*/|//[^\n]*', '', js, flags=re.S)
        for vi in JS_VI.values():
            self.assertNotIn(vi, code)


@tagged('post_install', '-at_install', 'wujia_debt', 'wujia_jv5')
class TestJv5PortalByLang(HttpCase):
    """User vi_VN thấy chữ cũ, en_US thấy câu gốc EN — cùng dữ liệu, cùng route."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_vi(cls.env)
        Partner = cls.env['res.partner']
        cls.franchise = cls.env['wujia.franchise.management'].create({
            'code': 'HJV5', 'name': 'JV5 store', 'franchise_end_date': '2030-01-01',
            'partner_id': Partner.create({'name': 'HJV5 partner'}).id})
        for login, lang in (('jv5_vi', 'vi_VN'), ('jv5_en', 'en_US')):
            user = cls.env['res.users'].create({
                'name': login, 'login': login, 'password': login, 'lang': lang,
                'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
            })
            cls.env['wujia.franchise.member'].create({
                'user_id': user.id, 'franchise_id': cls.franchise.id, 'role': 'owner'})
        # Đúng MỘT hoá đơn chưa trả tuần này ⇒ kiểm luôn số ít EN ("1 invoice").
        today = date.today()
        cls.week = '%04d-W%02d' % today.isocalendar()[:2]
        invoice = cls.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': Partner.create({'name': 'HJV5 customer'}).id,
            'invoice_date': today, 'franchise_id': cls.franchise.id, 'invoice_payment_term_id': False,
            'journal_id': cls.env['account.journal'].search(
                [('type', '=', 'sale'), ('company_id', '=', cls.env.company.id)], limit=1).id,
            'invoice_line_ids': [(0, 0, {
                'name': 'line', 'quantity': 1, 'price_unit': 1_500_000, 'tax_ids': [(6, 0, [])],
                'account_id': cls.env['account.account'].search(
                    [('account_type', '=', 'income')], limit=1).id})],
        })
        invoice.action_post()
        invoice.invoice_date_due = today + timedelta(days=7)
        cls.env['res.partner.bank'].search(
            [('id', 'in', cls.env.company.bank_ids.ids)]).portal_payment_enabled = False
        cls.env['res.partner.bank'].create({
            'acc_number': 'JV5-ACC', 'partner_id': cls.env.company.partner_id.id,
            'acc_holder_name': 'NGO GIA JV5', 'sequence': 1, 'portal_payment_enabled': True})

    def _get(self, login, url):
        self.authenticate(login, login)
        res = self.url_open(url, timeout=30)
        self.assertEqual(res.status_code, 200)
        return res.text

    def test_overview_vi_and_en(self):
        url = '/portal/debt?week=%s' % self.week
        vi = self._get('jv5_vi', url)
        for word in ('Công nợ', 'Tuần hóa đơn', 'Chưa thanh toán', 'Hóa đơn trong tuần',
                     'Tổng giá trị hóa đơn', 'Thanh toán số còn lại'):
            self.assertIn(word, vi)
        en = self._get('jv5_en', url)
        for word in ('Debts', 'Invoice week', 'Unpaid', 'Invoices this week', 'Total invoice value',
                     'Pay remaining balance'):
            self.assertIn(word, en)
        # Số ít: đúng 1 hoá đơn ⇒ "1 invoice", không "1 invoices"; vi vẫn "1 hóa đơn".
        text_en = _text(en)
        self.assertRegex(text_en, r'\b1 invoice\b')
        self.assertNotRegex(text_en, r'\b1 invoices\b')
        self.assertIn('1 hóa đơn', _text(vi))
        for word in ('Tuần hóa đơn', 'Chưa thanh toán', 'Hóa đơn trong tuần'):
            self.assertNotIn(word, en)

    def test_pay_page_js_messages_follow_lang(self):
        url = '/portal/debt/pay?week=%s' % self.week
        vi = self._get('jv5_vi', url)
        en = self._get('jv5_en', url)
        for key in JS_VI:
            with self.subTest(key=key):
                # 2 khối: mobile + PC.
                self.assertEqual(vi.count('data-wj-msg-%s=' % key), 2)
                self.assertEqual(en.count('data-wj-msg-%s=' % key), 2)
        self.assertIn('data-wj-msg-copied="Đã sao chép"', vi)
        self.assertIn('data-wj-msg-copied="Copied"', en)
        self.assertIn('SỐ TIỀN CẦN CHUYỂN', vi)
        self.assertIn('AMOUNT TO TRANSFER', en)

    def test_history_empty_state_vi_and_en(self):
        vi = self._get('jv5_vi', '/portal/debt/payment-history')
        en = self._get('jv5_en', '/portal/debt/payment-history')
        self.assertIn('Kỳ được chọn chưa có khoản thanh toán nào được xác nhận.', vi)
        self.assertIn('The selected period has no confirmed payments.', en)
        self.assertIn('0 giao dịch', _text(vi))
        self.assertIn('0 transactions', _text(en))

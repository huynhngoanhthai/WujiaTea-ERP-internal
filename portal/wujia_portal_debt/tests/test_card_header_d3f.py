"""D3f — CardHeader trên màn Công nợ.

F5b dời khỏi `wujia_portal_layout`: khung không được biết màn nào. Chín call site của
D3f đều PHẢI kèm một rule scope trả dáng — bỏ rule đi thì component áp 18px và card
52px/142px của Figma vỡ ngay mà build vẫn xanh.
"""
import os

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'wujia_card_header_d3')
class TestCardHeaderDebtD3f(TransactionCase):

    CALL_SITES = {
        'wujia_portal_debt.portal_debt_overview': 2,          # __head S43 + "Hóa đơn trong tuần"
        'wujia_portal_debt.portal_debt_payment_history': 1,
        'wujia_portal_debt.portal_debt_pay': 2,               # nhãn hint 11.5px + bank eyebrow (F4)
    }

    def _arch(self, xmlid):
        return self.env.ref(xmlid).arch_db

    def _css(self, module, name):
        path = os.path.join(os.path.dirname(__file__), '..', '..', module,
                            'static', 'src', 'css', name)
        with open(path, encoding='utf-8') as fh:
            return fh.read()

    def test_call_sites_use_component(self):
        for xmlid, count in self.CALL_SITES.items():
            with self.subTest(view=xmlid):
                self.assertEqual(
                    self._arch(xmlid).count('wujia_portal_layout.wj_card_header'), count)

    def test_debt_summary_keeps_its_head_wrapper(self):
        # Hai rule hình học Figma S43 bám `.wj-debt-summary__head`: hàng 15px và
        # badge `position:absolute`. Gỡ div bọc là badge rơi xuống thành flex item.
        arch = self._arch('wujia_portal_debt.portal_debt_overview')
        self.assertIn('wj-debt-summary__head', arch)
        css = self._css('wujia_portal_debt', 'portal_debt.css')
        self.assertRegex(css, r'\.wj-debt-summary__head\s*\{[^}]*height:\s*15px')
        self.assertRegex(
            css,
            r'\.wj-debt-summary__head \.wj-status-badge\s*\{[^}]*position:\s*absolute')

    def test_debt_card_labels_use_the_eyebrow_variant(self):
        # F4: nhãn 11px viết hoa trong thẻ số liệu (tổng "CÒN PHẢI TRẢ" + "THÔNG TIN
        # CHUYỂN KHOẢN") về biến thể chung `wj-card-header--eyebrow`; module không
        # còn tự khai cỡ chữ tiêu đề.
        path = os.path.join(os.path.dirname(__file__), '..', '..', 'wujia_portal_debt',
                            'views', 'portal_debt.xml')
        with open(path, encoding='utf-8') as fh:
            xml = fh.read()
        self.assertIn("'wj-card-header--flush wj-card-header--eyebrow wj-debt-summary__hb'", xml)
        # J-V5: thẻ mang thêm `t-att` (câu JS) ⇒ chỉ khớp phần mở thẻ.
        bank = xml[xml.index('<section class="wj-debt-bank"'):]
        bank = bank[:bank.index('</section>')]
        self.assertIn('wujia_portal_layout.wj_card_header', bank)
        self.assertNotIn('wj_section_header', bank)
        self.assertIn("'wj-card-header--eyebrow'", bank)
        css = self._css('wujia_portal_debt', 'portal_debt.css')
        self.assertNotRegex(css, r'wj-debt-summary__hb\s+\.wj-card-header__title\s*\{')
        self.assertNotIn('.wj-debt-bank .wj-section-header', css)

    def test_debt_hint_label_stays_smaller_than_card_title(self):
        # Hộp hint chỉ cao 52px; lấy 18px của component là tràn.
        self.assertRegex(
            self._css('wujia_portal_debt', 'portal_debt.css'),
            r'\.wj-debt-hint \.wj-card-header\.wj-debt-hint-head'
            r'\s+\.wj-card-header__title\s*\{[^}]*font-size:\s*11\.5px\s*!important')

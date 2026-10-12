"""C8 (quét nhiều module) — call site của SectionHeader CMP-SH-001.

F5b dời khỏi `wujia_portal_layout`: khung không được biết màn nào. Hợp đồng render của
component vẫn ở layout.
"""
from lxml import html

from odoo.tests import TransactionCase, tagged

from .common import load_vi, need


@tagged('post_install', '-at_install', 'wujia_section_header_c8')
class TestSectionHeaderCallSites(TransactionCase):
    """Các call site C8a phải dùng component + đúng rule đếm của spec."""

    def _arch(self, xmlid, env=None):
        need(self, xmlid)
        return (env or self.env).ref(xmlid).arch_db

    # Header nằm trong sub-template render thật (fragment của wj_ajax_list),
    # không phải view gốc `portal_*` — bám đúng id có t-call.
    CALL_SITES = {
        'wujia_portal_base.portal_home_page': 8,
        'wujia_portal_sale.portal_order_catalog_results_part': 2,
        'wujia_portal_sale.mcart_panel': 1,
        'wujia_portal_purchase_history.portal_history_results_part': 1,
        'wujia_portal_delivery.portal_delivery_results_part': 1,
        # C8b
        'wujia_portal_debt.portal_debt_overview': 1,
        'wujia_portal_debt.portal_debt_payment_history': 1,
        # F4: nhãn "THÔNG TIN CHUYỂN KHOẢN" nằm trong thẻ ⇒ sang CardHeader --eyebrow.
        'wujia_portal_debt.portal_debt_pay': 0,
        'wujia_portal_exam.portal_exam_register': 1,
        'wujia_portal_exam.portal_exam_registration_detail': 1,
        'wujia_portal_return.portal_return_list': 1,
    }

    # Class rời đã bị component thay; còn sót là có màn tự dựng lại tiêu đề riêng.
    # KHÔNG liệt `wujia-mdash-title`: return/support còn dùng nó làm nhãn TRONG card
    # (CardHeader, ngoài scope CMP-SH-001).
    RETIRED_CLASSES = (
        'wujia-mhist-listhead', 'wujia-morder-listhead', 'wujia-mcart-listhead',
        'wujia-mexam-sectitle', 'wj-debt-section__title',
    )

    def test_call_sites_use_component(self):
        for xmlid, count in self.CALL_SITES.items():
            with self.subTest(view=xmlid):
                self.assertEqual(
                    self._arch(xmlid).count('wujia_portal_layout.wj_section_header'),
                    count)

    def test_retired_heading_classes_are_gone(self):
        views = self.env['ir.ui.view'].search(
            [('arch_db', '!=', False), ('type', '=', 'qweb')])
        for cls in self.RETIRED_CLASSES:
            with self.subTest(css_class=cls):
                self.assertEqual(
                    [v.xml_id for v in views if cls in (v.arch_db or '')], [])

    def _sh_metas(self, xmlid, env=None):
        """Nội dung mọi slot meta của SectionHeader trong view (bỏ qua meta của
        PageHeader `wj-page-header__meta` — đó là CMP-PG-001, ngoài scope C8)."""
        root = html.fromstring(f'<div>{self._arch(xmlid, env)}</div>')
        return [m.text_content()
                for m in root.xpath('.//*[@class="wj-section-header__meta"]')]

    def test_count_uses_full_word_not_abbreviation(self):
        # Spec: "5 sản phẩm", KHÔNG "5 SP". J-V4: câu gốc tiếng Anh ("products"), tiếng Việt qua
        # .po của wujia_portal_sale ⇒ đọc arch ở vi_VN để giữ assert.
        xmlid = 'wujia_portal_sale.portal_order_catalog_results_part'
        need(self, xmlid)
        env_vi = load_vi(self.env)
        env_vi['ir.module.module'].search([
            ('name', '=', 'wujia_portal_sale'), ('state', '=', 'installed'),
        ])._update_translations(['vi_VN'])
        for env, word in ((self.env(context=dict(self.env.context, lang='en_US')), 'products'),
                          (env_vi, 'sản phẩm')):
            metas = self._sh_metas(xmlid, env)
            self.assertEqual(len(metas), 2)
            for m in metas:
                self.assertIn(word, m)
                self.assertNotRegex(m, r'\bSP\b')

    def test_count_not_hidden_when_zero(self):
        # Meta đếm không được bọc trong t-if="products" — 0 vẫn phải hiện.
        arch = self._arch('wujia_portal_sale.portal_order_catalog_results_part')
        root = html.fromstring(f'<div>{arch}</div>')
        for m in root.xpath('.//*[@class="wj-section-header__meta"]'):
            for node in [m] + m.xpath('.//*'):
                self.assertNotIn('products', node.get('t-if') or '')

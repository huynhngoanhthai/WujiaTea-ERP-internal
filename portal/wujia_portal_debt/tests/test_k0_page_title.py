"""PageHeader Lịch sử thanh toán: PC và mobile cùng một tên màn."""
from lxml import etree

from odoo.tests import TransactionCase, tagged
from odoo.addons.wujia_portal_layout.tests.src_paths import src


@tagged('post_install', '-at_install', 'wujia_page_header')
class TestDebtPageTitle(TransactionCase):

    def _titles(self, template_id):
        with open(src('wujia_portal_debt', 'views', 'portal_debt.xml'), 'rb') as fh:
            root = etree.fromstring(fh.read())
        tmpl = root.xpath('//template[@id="%s"]' % template_id)[0]
        return ([t.text for t in tmpl.xpath('.//t[@t-set="ph_title"]')],
                tmpl.xpath('.//t[@t-set="title"]')[0].text)

    def test_lich_su_thanh_toan_mot_ten_o_ca_hai_kho(self):
        headers, page_title = self._titles('portal_debt_payment_history')
        self.assertEqual(headers, ['Payment history', 'Payment history'])
        self.assertEqual(page_title, 'Payment history')

    def test_hai_man_con_lai_cung_mot_ten_o_ca_hai_kho(self):
        for template_id in ('portal_debt_overview', 'portal_debt_pay'):
            with self.subTest(view=template_id):
                headers, _page_title = self._titles(template_id)
                self.assertEqual(len(headers), 2)
                self.assertEqual(len(set(headers)), 1)

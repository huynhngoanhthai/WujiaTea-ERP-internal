"""Báo cáo đặt hàng + export chỉ theo MỘT cửa hàng đang chọn.

Chạy: `--test-tags wujia_scope_i4a`.

Quyền Chủ/Quản lý/Nhân viên KHÔNG đổi ở đây (I5 #153) — user test là Chủ cả hai cửa hàng.
"""
import io
import zipfile
from datetime import date

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_portal_base.controllers.portal import ACTIVE_FRANCHISE_COOKIE

PROMPT_NEED_PICK = 'data-store-scope="need_pick"'
YEAR = '?date_from=%d-01-01&date_to=%s' % (date.today().year, date.today().isoformat())


@tagged('post_install', '-at_install', 'wujia_scope_i4a')
class TestReportStoreScope(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Partner, Franchise = env['res.partner'], env['wujia.franchise.management']
        cls.store_a, cls.store_b = (Franchise.create({
            'code': code, 'name': 'I4a report %s' % code, 'franchise_end_date': '2030-01-01',
            'partner_id': Partner.create({'name': 'I4a rep partner %s' % code}).id,
        }) for code in ('I4RA', 'I4RB'))
        # Mỗi cửa hàng một sản phẩm riêng ⇒ bảng top sản phẩm lộ ngay nếu gộp.
        cls.prod_a, cls.prod_b = (env['product.product'].create({
            'name': name, 'type': 'consu', 'list_price': 10_000}) for name in ('I4RA-ONLY', 'I4RB-ONLY'))
        cls.so_a = cls._order(cls.store_a, cls.prod_a)
        cls.so_b = cls._order(cls.store_b, cls.prod_b)
        user = env['res.users'].create({
            'name': 'i4a_rep', 'login': 'i4a_rep', 'password': 'i4a_rep',
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])]})
        for store in (cls.store_a, cls.store_b):
            env['wujia.franchise.member'].create({
                'user_id': user.id, 'franchise_id': store.id, 'role': 'owner'})

    @classmethod
    def _order(cls, store, product):
        so = cls.env['sale.order'].create({
            'partner_id': store.partner_id.id, 'franchise_id': store.id,
            'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 3})]})
        so.action_confirm()
        return so

    def _open(self, url, store=None):
        self.authenticate('i4a_rep', 'i4a_rep')
        if store is not None:
            self.opener.cookies.set(ACTIVE_FRANCHISE_COOKIE, str(store.id))
        return self.url_open(url, timeout=30, allow_redirects=False)

    @staticmethod
    def _xlsx_text(content):
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            return ''.join(z.read(n).decode() for n in z.namelist() if n.startswith('xl/'))

    def test_not_selected_page_prompts_without_data(self):
        res = self._open('/portal/reports/orders' + YEAR)
        self.assertEqual(res.status_code, 200)
        self.assertIn(PROMPT_NEED_PICK, res.text)
        self.assertNotIn('I4RA-ONLY', res.text)
        self.assertNotIn('I4RB-ONLY', res.text)
        self.assertNotIn('id="wj-rep-pc-body"', res.text, 'chưa chọn ⇒ không KPI/biểu đồ')

    def test_not_selected_export_redirects_to_page(self):
        res = self._open('/portal/reports/orders/export.xlsx' + YEAR)
        self.assertEqual(res.status_code, 303)
        self.assertTrue(res.headers['Location'].endswith('/portal/reports/orders'), res.headers['Location'])

    def test_selected_a_page_only_a(self):
        html = self._open('/portal/reports/orders' + YEAR, self.store_a).text
        self.assertNotIn(PROMPT_NEED_PICK, html)
        self.assertIn('I4RA-ONLY', html)
        self.assertNotIn('I4RB-ONLY', html)

    def test_switch_b_page_only_b(self):
        html = self._open('/portal/reports/orders' + YEAR, self.store_b).text
        self.assertIn('I4RB-ONLY', html)
        self.assertNotIn('I4RA-ONLY', html)

    def test_selected_a_export_only_a(self):
        res = self._open('/portal/reports/orders/export.xlsx' + YEAR, self.store_a)
        self.assertEqual(res.status_code, 200)
        text = self._xlsx_text(res.content)
        self.assertIn(self.so_a.name, text)
        self.assertNotIn(self.so_b.name, text)

    def test_store_param_cannot_widen_scope(self):
        """Tham số request (franchise_id/franchise_ids) không mở rộng phạm vi ra ngoài cửa hàng đang chọn."""
        res = self._open('/portal/reports/orders/export.xlsx' + YEAR
                         + '&franchise_id=%d&franchise_ids=%d' % (self.store_b.id, self.store_b.id), self.store_a)
        text = self._xlsx_text(res.content)
        self.assertNotIn(self.so_b.name, text)

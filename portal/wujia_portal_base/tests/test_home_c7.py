"""Cụm C7 — Home mobile (WJ-HOME-001/002/006/007/008).

Chạy: `--test-tags wujia_home_c7`.

Home render qua `request` nên test đi đường người dùng đi (HttpCase); phần đo pixel
(nhãn KPI, mã đơn không bị cắt) thuộc harness Playwright, không phải test Python.
"""

import re
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_portal_base.controllers.portal import HOME_PREVIEW_LIMIT


@tagged('post_install', '-at_install', 'wujia_home_c7')
class TestHomePreview(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.franchise = env['wujia.franchise.management'].create({
            'code': 'HC7A', 'name': 'C7 store', 'franchise_end_date': '2030-01-01',
            'partner_id': env['res.partner'].create({'name': 'C7 partner'}).id})
        cls.product = env['product.product'].create({
            'name': 'C7 product', 'type': 'consu', 'list_price': 50_000})
        now = fields.Datetime.now()
        # 4 đơn, mới → cũ: orders[0] mới nhất.
        cls.orders = env['sale.order'].browse()
        for i in range(4):
            cls.orders |= env['sale.order'].create({
                'partner_id': cls.franchise.partner_id.id,
                'franchise_id': cls.franchise.id,
                'date_order': now - timedelta(days=i),
                'order_line': [(0, 0, {'product_id': cls.product.id, 'product_uom_qty': 1})],
            })
        cls.user = env['res.users'].create({
            'name': 'c7_owner', 'login': 'c7_owner', 'password': 'c7_owner',
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])]})
        env['wujia.franchise.member'].create({
            'user_id': cls.user.id, 'franchise_id': cls.franchise.id, 'role': 'owner'})

    def _home(self):
        self.authenticate('c7_owner', 'c7_owner')
        res = self.url_open('/portal', timeout=30)
        self.assertEqual(res.status_code, 200)
        return res.text

    @staticmethod
    def _orders_block(html):
        # rindex: khối desktop in "Đơn hàng gần đây" trước, cụm này chỉ nói về mobile.
        start = html.rindex('Đơn hàng gần đây')
        return html[start:html.index('Bài viết / Kiến thức mới', start)]

    # ---- WJ-HOME-006 ---------------------------------------------------
    def test_orders_block_shows_two_newest(self):
        block = self._orders_block(self._home())
        shown = [o for o in self.orders if o.name in block]
        self.assertEqual(len(shown), HOME_PREVIEW_LIMIT)
        self.assertEqual(shown, list(self.orders[:HOME_PREVIEW_LIMIT]))
        self.assertIn('/portal/purchase-history', block)  # "Xem tất cả" vẫn còn

    # ---- WJ-HOME-007 ---------------------------------------------------
    def test_no_row_level_chevron(self):
        self.assertNotIn('wujia-mdash-chev', self._home())

    # ---- WJ-HOME-008 ---------------------------------------------------
    def test_list_block_uses_single_card(self):
        block = self._orders_block(self._home())
        self.assertEqual(len(re.findall(r'wujia-mdash-card', block)), 1)

    def test_no_card_per_record_layout(self):
        html = self._home()
        for dead in ('wujia-mdash-item', 'wujia-mdash-stack', 'wujia-mhome-noti-row'):
            self.assertNotIn(dead, html)

    # ---- WJ-HOME-002 ---------------------------------------------------
    def test_order_code_rendered_in_full(self):
        block = self._orders_block(self._home())
        self.assertIn('is-code', block)
        self.assertIn(self.orders[0].name, block)

"""CMP-SN-001 (E8b) — module này sở hữu mục menu của màn mình (ADR-027: khung không biết route).

Gỡ module ⇒ view `layout_sidenav_delivery` biến mất ⇒ mục "Giao hàng" biến mất khỏi sidebar.
Danh sách vàng (thứ tự, nhóm, active theo route, quyền) nằm ở `wujia_portal_base`
(`test_f5_menu_ownership.py`) vì phép kiểm đó đụng nhiều module cùng lúc.
"""
from lxml import etree

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'wujia_f5')
class TestNavItemDelivery(TransactionCase):

    def _env_vi(self):
        self.env['res.lang']._activate_lang('vi_VN')
        self.env['ir.module.module'].search([('name', '=', 'wujia_portal_delivery')])._update_translations(['vi_VN'])
        return self.env(context=dict(self.env.context, lang='vi_VN'))

    def test_item_is_declared_by_this_module(self):
        view = self.env.ref('wujia_portal_delivery.layout_sidenav_delivery')
        self.assertEqual(view.inherit_id, self.env.ref('wujia_portal_layout.layout_sidenav'))
        arch = view.arch
        self.assertIn('<li', arch)
        self.assertIn('id="nav_item_delivery"', arch)
        self.assertIn('t-value="\'/portal/delivery\'"', arch)
        # J-V8a: câu gốc EN; chữ VN cũ nằm ở vi_VN.po ⇒ assert ở vi_VN, không xoá assert.
        self.assertIn('<t t-set="ni_label">Delivery</t>', view.with_context(lang='en_US').arch)
        self.assertIn('<t t-set="ni_label">Giao hàng</t>', view.with_env(self._env_vi()).arch)
        # Nhóm theo BA: chèn trước neo của nhóm kế tiếp.
        self.assertIn("//li[@id='nav_header_finance']", arch)
        # Cùng điều kiện sáng truyền vào wj_nav_item để có aria-current.
        self.assertIn('t-set="ni_active"', arch)

    def test_item_lands_in_the_shell(self):
        """Mục thật sự nằm trong arch tổng của khung (xpath neo còn khớp)."""
        xml = etree.tostring(
            self.env.ref('wujia_portal_layout.layout_sidenav')._get_combined_arch(),
            encoding='unicode')
        self.assertIn('id="nav_item_delivery"', xml)

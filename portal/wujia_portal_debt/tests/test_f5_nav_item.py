"""CMP-SN-001 (E8b) — module này sở hữu mục menu của màn mình (ADR-027: khung không biết route).

Gỡ module ⇒ view `layout_sidenav_debt` biến mất ⇒ mục "Công nợ & thanh toán" biến mất khỏi sidebar.
Danh sách vàng (thứ tự, nhóm, active theo route, quyền) nằm ở `wujia_portal_base`
(`test_f5_menu_ownership.py`) vì phép kiểm đó đụng nhiều module cùng lúc.
"""
from lxml import etree

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from .common import load_vi


@tagged('post_install', '-at_install', 'wujia_f5')
class TestNavItemDebt(TransactionCase):

    def test_item_is_declared_by_this_module(self):
        view = self.env.ref('wujia_portal_debt.layout_sidenav_debt')
        self.assertEqual(view.inherit_id, self.env.ref('wujia_portal_layout.layout_sidenav'))
        arch = view.arch
        self.assertIn('<li', arch)
        self.assertIn('id="nav_item_debt"', arch)
        self.assertIn('t-value="\'/portal/debt\'"', arch)
        # J-V5: câu gốc tiếng Anh, user vi_VN vẫn thấy nhãn cũ.
        self.assertIn('<t t-set="ni_label">Debts &amp; payments</t>', arch)
        self.assertIn('<t t-set="ni_label">Công nợ &amp; thanh toán</t>',
                      view.with_env(load_vi(self.env)).arch)
        # Nhóm theo BA: chèn trước neo của nhóm kế tiếp.
        self.assertIn("//li[@id='nav_header_ops']", arch)
        # Cùng điều kiện sáng truyền vào wj_nav_item để có aria-current.
        self.assertIn('t-set="ni_active"', arch)
        # Quyền = điều kiện của _debt_access: Owner/Manager của cửa hàng đang chọn.
        self.assertIn('t-if="not _wujia_active_fid or _nav_store_admin"', arch)

    def test_item_lands_in_the_shell(self):
        """Mục thật sự nằm trong arch tổng của khung (xpath neo còn khớp)."""
        xml = etree.tostring(
            self.env.ref('wujia_portal_layout.layout_sidenav')._get_combined_arch(),
            encoding='unicode')
        self.assertIn('id="nav_item_debt"', xml)

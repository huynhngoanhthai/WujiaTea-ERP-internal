"""CMP-SN-001 (E8b) — module này sở hữu mục menu của màn mình (ADR-027: khung không biết route).

Gỡ module ⇒ view `layout_sidenav_knowledge` biến mất ⇒ mục "Kiến thức" biến mất khỏi sidebar.
Danh sách vàng (thứ tự, nhóm, active theo route, quyền) nằm ở `wujia_portal_base`
(`test_f5_menu_ownership.py`) vì phép kiểm đó đụng nhiều module cùng lúc.
"""
from lxml import etree

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.wujia_knowledge.tests.common import load_vi


@tagged('post_install', '-at_install', 'wujia_f5')
class TestNavItemKnowledge(TransactionCase):

    def test_item_is_declared_by_this_module(self):
        view = self.env.ref('wujia_portal_knowledge.layout_sidenav_knowledge')
        self.assertEqual(view.inherit_id, self.env.ref('wujia_portal_layout.layout_sidenav'))
        arch = view.arch
        # J-V7: câu gốc EN; chữ VN cũ nằm ở vi_VN.po ⇒ assert ở vi_VN, không xoá assert.
        arch_vi = view.with_env(load_vi(self.env, ('wujia_portal_knowledge',))).arch
        self.assertIn('<t t-set="ni_label">Knowledge</t>', view.with_context(lang='en_US').arch)
        self.assertIn('<li', arch)
        self.assertIn('id="nav_item_knowledge"', arch)
        self.assertIn('t-value="\'/portal/knowledge\'"', arch)
        self.assertIn('<t t-set="ni_label">Kiến thức</t>', arch_vi)
        # Nhóm theo BA: chèn trước neo của nhóm kế tiếp.
        self.assertIn("//li[@id='nav_end']", arch)
        # Cùng điều kiện sáng truyền vào wj_nav_item để có aria-current.
        self.assertIn('t-set="ni_active"', arch)

    def test_item_lands_in_the_shell(self):
        """Mục thật sự nằm trong arch tổng của khung (xpath neo còn khớp)."""
        xml = etree.tostring(
            self.env.ref('wujia_portal_layout.layout_sidenav')._get_combined_arch(),
            encoding='unicode')
        self.assertIn('id="nav_item_knowledge"', xml)

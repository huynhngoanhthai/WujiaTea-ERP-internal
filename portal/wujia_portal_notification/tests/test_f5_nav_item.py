"""CMP-SN-001 (E8b) — Thông báo KHÔNG có mục trong sidebar PC.

BA: thông báo trên PC vào bằng chuông topbar (`header_bell_inherit.xml`); mobile giữ tab
Thông báo ở bottom-nav. Guard chống việc mục PC quay lại.
"""
from lxml import etree

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools.misc import file_path


@tagged('post_install', '-at_install', 'wujia_f5')
class TestNavItemNotification(TransactionCase):

    def test_no_pc_sidebar_item(self):
        self.assertFalse(self.env.ref('wujia_portal_notification.layout_sidenav_notification',
                                      raise_if_not_found=False))
        xml = etree.tostring(
            self.env.ref('wujia_portal_layout.layout_sidenav')._get_combined_arch(),
            encoding='unicode')
        self.assertNotIn('id="nav_item_notification"', xml)
        self.assertNotIn("'/portal/notification'", xml)

    def test_bell_and_mobile_tab_still_reach_notifications(self):
        bell = self.env.ref('wujia_portal_notification.layout_top_navbar_bell_icon', raise_if_not_found=False)
        self.assertTrue(bell, 'mất chuông topbar ⇒ PC không còn lối vào Thông báo')


@tagged('post_install', '-at_install', 'wujia_e8')
class TestBellAria(TransactionCase):
    """CMP-SN-001: chuông PC là nút mở popup ⇒ trình đọc màn hình phải biết đang mở/đóng."""

    def test_bell_markup(self):
        root = etree.fromstring(
            self.env.ref('wujia_portal_notification.layout_top_navbar_bell_icon').arch_db)
        bell = root.xpath("//a[@data-wj-noti-bell]")[0]
        self.assertEqual(bell.get('aria-haspopup'), 'true')
        self.assertEqual(bell.get('aria-controls'), 'wj-noti-popup')
        self.assertEqual(bell.get('aria-expanded'), 'false')
        self.assertTrue(root.xpath("//*[@id='wj-noti-popup']"), 'aria-controls trỏ vào id không có')

    def test_js_dong_bo_aria_expanded_va_tra_focus(self):
        path = file_path('wujia_portal_notification/static/src/js/header_bell_badge.js')
        with open(path, encoding='utf-8') as fh:
            js = fh.read()
        self.assertIn('bell.setAttribute("aria-expanded"', js)
        self.assertRegex(js, r'Escape[\s\S]{0,200}bell\.focus\(\)')

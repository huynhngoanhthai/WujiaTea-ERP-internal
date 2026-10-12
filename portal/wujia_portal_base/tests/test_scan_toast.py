"""Quét nhiều module — thông báo nổi chỉ có một implementation: `wjToast` của khung
(`wujia_portal_layout/static/assets/js/wj_toast.js`, hợp đồng ở `test_toast.py` của khung).

Trước đây giỏ hàng, trang đặt hàng và trang thông báo PC mỗi nơi tự dựng một ô `position:fixed`
bằng style inline: ô của giỏ ghim `top:20px; right:20px` nên đè lên header mobile.
"""
import glob
import re

from odoo.tests import TransactionCase, tagged

from odoo.addons.wujia_portal_base.tests.css_probe import src, src_modules, src_rel

CALLERS = (('wujia_portal_sale', 'portal_cart_sync.js'),
           ('wujia_portal_sale', 'portal_order.js'),
           ('wujia_portal_notification', 'portal_notification_pc.js'))


@tagged('post_install', '-at_install', 'wujia_toast')
class TestScanToast(TransactionCase):

    def test_no_screen_builds_its_own_floating_box(self):
        files = [f for mod in src_modules() if mod.startswith('wujia_portal_')
                 for f in glob.glob(src(mod, 'static', 'src', 'js', '*.js'))]
        self.assertGreater(len(files), 10)
        bad = []
        for path in files:
            with open(path, encoding='utf-8') as fh:
                if re.search(r'position\s*:\s*fixed', fh.read()):
                    bad.append(src_rel(path))
        self.assertFalse(bad, 'JS tự dựng ô position:fixed — dùng window.wjToast: %s' % bad)

    def test_callers_use_shared_toast(self):
        for module, name in CALLERS:
            with self.subTest(file=name):
                with open(src(module, 'static', 'src', 'js', name), encoding='utf-8') as fh:
                    self.assertIn('window.wjToast(', fh.read())

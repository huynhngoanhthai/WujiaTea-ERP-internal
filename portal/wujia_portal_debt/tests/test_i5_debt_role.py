from odoo.tests import tagged

from odoo.addons.wujia_portal_base.tests.test_i5_store_role import NO_PERMISSION, I5Common

DEBT_URLS = ('/portal/debt', '/portal/debt/payment-history', '/portal/debt/pay')


@tagged('post_install', '-at_install', 'wujia_role_i5')
class TestDebtRole(I5Common):

    def test_admin_at_selected_store(self):
        for login in ('i5.mix', 'i5.mgr'):
            for url in DEBT_URLS:
                res = self._open(url, self.store_a, login, allow_redirects=False)
                self.assertIn(res.status_code, (200, 303), url)
                self.assertNotIn(NO_PERMISSION, res.text)

    def test_owner_elsewhere_is_staff_here(self):
        for url in DEBT_URLS:
            res = self._open(url, self.store_b)
            self.assertEqual(res.status_code, 403, url)
            self.assertIn(NO_PERMISSION, res.text)

    def test_menu_and_home_follow_backend(self):
        html_a = self._open('/portal', self.store_a).text
        self.assertIn('id="nav_item_debt"', html_a)
        self.assertIn('wujia-msheet-item--debt', html_a)
        html_b = self._open('/portal', self.store_b).text
        for marker in ('id="nav_item_debt"', 'wujia-msheet-item--debt', 'href="/portal/debt"'):
            self.assertNotIn(marker, html_b)

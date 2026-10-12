from odoo.tests import tagged

from odoo.addons.wujia_portal_base.tests.test_i5_store_role import NO_PERMISSION, I5Common


@tagged('post_install', '-at_install', 'wujia_role_i5')
class TestReportRole(I5Common):

    def test_admin_at_selected_store(self):
        for login in ('i5.mix', 'i5.mgr'):
            res = self._open('/portal/reports/orders', self.store_a, login)
            self.assertEqual(res.status_code, 200, login)
            self.assertNotIn(NO_PERMISSION, res.text)
        export = self._open('/portal/reports/orders/export.xlsx', self.store_a)
        self.assertIn('spreadsheetml', export.headers.get('Content-Type', ''))

    def test_owner_elsewhere_is_staff_here(self):
        res = self._open('/portal/reports/orders', self.store_b)
        self.assertEqual(res.status_code, 403)
        self.assertIn(NO_PERMISSION, res.text)
        export = self._open('/portal/reports/orders/export.xlsx', self.store_b, allow_redirects=False)
        self.assertIn(export.status_code, (302, 303))
        self.assertTrue(export.headers['Location'].endswith('/portal/reports/orders'))

    def test_menu_follows_backend(self):
        self.assertIn('id="nav_item_report"', self._open('/portal', self.store_a).text)
        html_b = self._open('/portal', self.store_b).text
        self.assertNotIn('id="nav_item_report"', html_b)
        self.assertNotIn('/portal/reports/orders', html_b)

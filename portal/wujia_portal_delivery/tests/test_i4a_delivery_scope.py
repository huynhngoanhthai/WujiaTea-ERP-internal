"""Giao hàng chỉ theo MỘT cửa hàng đang chọn.

Chạy: `--test-tags wujia_scope_i4a`.

Ma trận route × (chưa chọn / chọn A / chọn B): list, fragment AJAX `/results`, chi tiết, `.ics`.
Sửa ID chuyến sang chuyến của cửa hàng kia ⇒ không đọc được.
"""
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_portal_base.controllers.portal import ACTIVE_FRANCHISE_COOKIE
from odoo.addons.wujia_portal_delivery.tests.test_delivery_c5 import DeliveryFixture

PROMPT_NEED_PICK = 'data-store-scope="need_pick"'


@tagged('post_install', '-at_install', 'wujia_scope_i4a')
class TestDeliveryStoreScope(HttpCase, DeliveryFixture):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_delivery_data()
        user = cls.env['res.users'].create({
            'name': 'i4a_dlv', 'login': 'i4a_dlv', 'password': 'i4a_dlv',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])]})
        for store in (cls.franchise, cls.other):
            cls.env['wujia.franchise.member'].create({
                'user_id': user.id, 'franchise_id': store.id, 'role': 'owner'})

    def _open(self, url, store=None):
        self.authenticate('i4a_dlv', 'i4a_dlv')
        if store is not None:
            self.opener.cookies.set(ACTIVE_FRANCHISE_COOKIE, str(store.id))
        return self.url_open(url, timeout=30, allow_redirects=False)

    def _assert_redirect_list(self, res):
        self.assertEqual(res.status_code, 303)
        self.assertTrue(res.headers['Location'].endswith('/portal/delivery'), res.headers['Location'])

    # ---- chưa chọn --------------------------------------------------------
    def test_not_selected_list_and_fragment_prompt(self):
        for url in ('/portal/delivery', '/portal/delivery/results'):
            res = self._open(url)
            self.assertEqual(res.status_code, 200, url)
            self.assertNotIn(self.batch_soon.name, res.text, url)
            self.assertNotIn(self.batch_other.name, res.text, url)
        self.assertIn(PROMPT_NEED_PICK, self._open('/portal/delivery').text)

    def test_not_selected_detail_and_ics_blocked(self):
        self._assert_redirect_list(self._open('/portal/delivery/%d' % self.batch_soon.id))
        self.assertEqual(self._open('/portal/delivery/%d.ics' % self.batch_other.id).status_code, 404)

    # ---- chọn A / B -------------------------------------------------------
    def test_selected_a_only_a(self):
        for url in ('/portal/delivery', '/portal/delivery/results'):
            html = self._open(url, self.franchise).text
            self.assertIn(self.batch_soon.name, html, url)
            self.assertNotIn(self.batch_other.name, html, url)
        self.assertEqual(self._open('/portal/delivery/%d' % self.batch_soon.id, self.franchise).status_code, 200)

    def test_selected_b_only_b(self):
        html = self._open('/portal/delivery', self.other).text
        self.assertIn(self.batch_other.name, html)
        self.assertNotIn(self.batch_soon.name, html)

    def test_foreign_id_blocked(self):
        """Đang chọn A, sửa URL sang chuyến của B ⇒ không đọc được (và ngược lại)."""
        self._assert_redirect_list(self._open('/portal/delivery/%d' % self.batch_other.id, self.franchise))
        self.assertEqual(self._open('/portal/delivery/%d.ics' % self.batch_other.id, self.franchise).status_code, 404)
        self._assert_redirect_list(self._open('/portal/delivery/%d' % self.batch_soon.id, self.other))
        self.assertEqual(self._open('/portal/delivery/%d.ics' % self.batch_soon.id, self.franchise).status_code, 200)

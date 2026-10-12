"""Thông báo theo MỘT cửa hàng đang chọn; chưa chọn ⇒ chỉ thông báo toàn hệ + khối nhắc chọn.

Chạy: `--test-tags wujia_scope_i4b`.
"""
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_notification.tests.test_portal_rules import NotificationCommon
from odoo.addons.wujia_portal_base.controllers.portal import ACTIVE_FRANCHISE_COOKIE

PROMPT_NEED_PICK = 'data-store-scope="need_pick"'


@tagged('post_install', '-at_install', 'wujia_scope_i4b')
class TestNotificationStoreScope(NotificationCommon, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_notification(login='i4b.noti')
        for store in (cls.store_a, cls.store_b):
            cls.env['wujia.franchise.member'].create({
                'user_id': cls.user.id, 'franchise_id': store.id, 'role': 'owner'})
        cls.only_a = cls._noti('I4B riêng A', cls.live.published_date, stores=cls.store_a)
        cls.file_b = cls.env['ir.attachment'].create({'name': 'i4b-b.txt', 'raw': b'b'})
        cls.other_store.attachment_ids = [(4, cls.file_b.id)]

    def _login(self, store=None):
        self.authenticate('i4b.noti', 'i4b.noti')
        if store is not None:
            self.opener.cookies.set(ACTIVE_FRANCHISE_COOKIE, str(store.id))

    def _open(self, url, store=None):
        self._login(store)
        return self.url_open(url, timeout=30, allow_redirects=False)

    def _rpc(self, url, store=None, **params):
        self._login(store)
        return self.make_jsonrpc_request(url, params)

    def _assert_redirect_list(self, res):
        self.assertEqual(res.status_code, 303)
        self.assertTrue(res.headers['Location'].endswith('/portal/notification'), res.headers['Location'])

    def test_not_selected_only_system_wide(self):
        res = self._open('/portal/notification')
        self.assertIn(PROMPT_NEED_PICK, res.text)
        self.assertIn(self.live.name, res.text)
        self.assertNotIn(self.only_a.name, res.text)
        self.assertNotIn(self.other_store.name, res.text)
        popup = {n['id'] for n in self._rpc('/portal/notification/recent')['notifications']}
        self.assertNotIn(self.only_a.id, popup)
        self.assertNotIn(self.other_store.id, popup)
        self.assertEqual(self._rpc('/portal/notification/unread-count')['count'],
                         self.Noti._portal_unread_count(self.user, (), False))
        self.assertEqual(self._open('/portal/notification/%d' % self.live.id).status_code, 200)
        self._assert_redirect_list(self._open('/portal/notification/%d' % self.only_a.id))

    def test_selected_a_and_switch_b(self):
        html = self._open('/portal/notification', self.store_a).text
        self.assertNotIn(PROMPT_NEED_PICK, html)
        self.assertIn(self.live.name, html)
        self.assertIn(self.only_a.name, html)
        self.assertNotIn(self.other_store.name, html)
        html = self._open('/portal/notification', self.store_b).text
        self.assertIn(self.other_store.name, html)
        self.assertNotIn(self.only_a.name, html)

    def test_foreign_ids_blocked(self):
        self._assert_redirect_list(self._open('/portal/notification/%d' % self.other_store.id, self.store_a))
        self.assertEqual(self._open('/portal/notification/%d/attachment/%d' % (
            self.other_store.id, self.file_b.id), self.store_a).status_code, 404)
        res = self._rpc('/portal/notification/mark-read', self.store_a, notification_ids=[self.other_store.id])
        self.assertEqual(res['created'], 0)
        self.assertEqual(self._open('/portal/notification/%d/attachment/%d' % (
            self.other_store.id, self.file_b.id), self.store_b).status_code, 200)

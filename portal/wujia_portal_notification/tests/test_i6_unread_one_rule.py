"""I6 — WJ-NOTI-001: Home, chuông, hộp chuông, lọc "Chưa đọc", "Đánh dấu tất cả" cùng một số.

Chạy: `--test-tags wujia_noti_i6`.
"""
import re

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_notification.tests.test_portal_rules import NotificationCommon
from odoo.addons.wujia_portal_base.controllers.portal import ACTIVE_FRANCHISE_COOKIE

HOME_KPI = re.compile(r'icon-bell"></i></div>\s*<div class="wujia-kpi-content">.*?wujia-kpi-value">(\d+)<', re.S)


@tagged('post_install', '-at_install', 'wujia_noti_i6')
class TestI6UnreadOneRule(NotificationCommon, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_notification(login='i6.noti')
        cls.user.lang = 'en_US'  # câu tooltip assert bằng bản gốc
        for store in (cls.store_a, cls.store_b):
            cls.env['wujia.franchise.member'].create({
                'user_id': cls.user.id, 'franchise_id': store.id, 'role': 'owner'})
        cls.only_a = cls._noti('I6 riêng A', cls.live.published_date, stores=cls.store_a)
        cls.mine |= cls.only_a

    def _login(self, store=None):
        self.authenticate('i6.noti', 'i6.noti')
        if store is not None:
            self.opener.cookies.set(ACTIVE_FRANCHISE_COOKIE, str(store.id))

    def _rpc(self, url, store=None, **params):
        self._login(store)
        return self.make_jsonrpc_request(url, params)

    def _html(self, url, store=None):
        self._login(store)
        res = self.url_open(url, timeout=30)
        self.assertEqual(res.status_code, 200, url)
        return res.text

    def _expected(self, store=None):
        ids = (store.id,) if store else ()
        return self.Noti._portal_unread_count(self.user, ids, store and store.id)

    def _counts(self, store):
        """Số chưa đọc ở mọi vị trí (cửa hàng đã chọn)."""
        home = HOME_KPI.search(self._html('/portal', store))
        recent = self._rpc('/portal/notification/recent', store)
        return {
            'home': int(home.group(1)) if home else None,
            'badge': self._rpc('/portal/notification/unread-count', store)['count'],
            'popup': recent['total_unread'],
        }

    def test_all_positions_same_number(self):
        for store in (self.store_a, self.store_b):
            expected = self._expected(store)
            self.assertEqual(self._counts(store), dict.fromkeys(('home', 'badge', 'popup'), expected), store.code)
        # Lọc "Chưa đọc" = đúng các bài chưa đọc của domain chung (trong phần của test).
        html = self._html('/portal/notification?read_status=unread&limit=50', self.store_a)
        for noti in self.mine:
            should = noti in (self.live | self.only_a)
            self.assertEqual(noti.name in html, should, noti.name)

    def test_broadcast_read_once_across_stores(self):
        before_b = self._expected(self.store_b)
        self._html('/portal/notification/%d' % self.live.id, self.store_a)
        self.assertEqual(self._counts(self.store_b)['badge'], before_b - 1)
        html = self._html('/portal/notification?read_status=unread&limit=50', self.store_b)
        self.assertNotIn(self.live.name, html)
        html = self._html('/portal/notification?read_status=read&limit=50', self.store_b)
        self.assertIn(self.live.name, html)

    def test_mark_all_matches_count(self):
        expected = self._expected(self.store_a)
        res = self._rpc('/portal/notification/mark-all-read', self.store_a)
        self.assertTrue(res['success'])
        self.assertEqual(res['updated_count'], expected)
        self.assertEqual(res['unread_count'], 0)
        self.assertEqual(self._counts(self.store_a), dict.fromkeys(('home', 'badge', 'popup'), 0))
        # B: bài toàn hệ đã đọc, bài riêng của B vẫn chưa đọc.
        self.assertEqual(self._expected(self.store_b), self.Noti.search_count(
            self.Noti._portal_unread_domain(self.user, (self.store_b.id,), self.store_b.id)))
        self.assertIn(self.other_store.id, self.Noti.search(
            self.Noti._portal_unread_domain(self.user, (self.store_b.id,), self.store_b.id)).ids)

    def test_not_selected_marks_only_broadcast(self):
        expected = self._expected()
        self.assertEqual(self._rpc('/portal/notification/unread-count')['count'], expected)
        self.assertEqual(self._rpc('/portal/notification/recent')['total_unread'], expected)
        res = self._rpc('/portal/notification/mark-all-read')
        self.assertTrue(res['success'])
        self.assertEqual(res['updated_count'], expected)
        rows = self.Read.search([('user_id', '=', self.user.id)])
        self.assertFalse(rows.franchise_id, 'chỉ dấu toàn hệ (franchise NULL)')
        self.assertNotIn(self.only_a, rows.notification_id)
        # Sang A: bài toàn hệ vẫn đã đọc, chỉ còn bài riêng của A.
        self.assertEqual(self._expected(self.store_a), self.Noti.search_count(
            self.Noti._portal_effective_domain((self.store_a.id,)) + [('franchise_ids', '!=', False)]))

    def test_mark_all_tooltip_follows_scope(self):
        self.assertIn('all-store notifications only', self._html('/portal/notification'))
        self.assertIn('the store you are working in', self._html('/portal/notification', self.store_a))

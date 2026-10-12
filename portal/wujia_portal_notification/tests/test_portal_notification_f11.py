"""F11 — route portal + Home gọi luật model: đếm chưa đọc, danh sách Home, ghi đã đọc, tải đính kèm.
Chạy: `--test-tags wujia_notification`. Luật model test ở `wujia_notification`."""
import re

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_notification.tests.test_portal_rules import NotificationCommon


@tagged('post_install', '-at_install', 'wujia_notification')
class TestPortalNotificationF11(NotificationCommon, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_notification(login='f11.portal')
        # Một cửa hàng ⇒ portal tự chọn cửa hàng A.
        cls.env['wujia.franchise.member'].create({
            'user_id': cls.user.id, 'franchise_id': cls.store_a.id, 'role': 'owner'})
        Att = cls.env['ir.attachment']
        cls.own_file = Att.create({'name': 'f11-own.txt', 'raw': b'own'})
        cls.other_file = Att.create({'name': 'f11-other.txt', 'raw': b'other'})
        cls.live.attachment_ids = [(4, cls.own_file.id)]
        cls.other_store.attachment_ids = [(4, cls.other_file.id)]

    def setUp(self):
        super().setUp()
        self.authenticate('f11.portal', 'f11.portal')

    def _rows(self):
        return self.Read.search([('user_id', '=', self.user.id)])

    def _home_kpis(self):
        html = self.url_open('/portal', timeout=30).text
        # G3a (142): nhãn PC "Thông báo chưa đọc" → "Thông báo" như mobile (mockup V4).
        pc = re.search(r'Thông báo</p>\s*<div class="wujia-kpi-value">(\d+)<', html)
        mobile = re.search(r'Thông báo</span>\s*<span class="wujia-mhome-kpi-value">(\d+)<', html)
        return int(pc.group(1)), int(mobile.group(1))

    def test_home_kpi_matches_bell_badge(self):
        # Luật cũ của Home đếm cả bài hẹn giờ + hết hạn ⇒ lệch badge chuông.
        badge = self.make_jsonrpc_request('/portal/notification/unread-count')['count']
        self.assertEqual(self._home_kpis(), (badge, badge))
        self.url_open('/portal/notification/%s' % self.live.id)
        self.assertEqual(self._home_kpis(), (badge - 1, badge - 1))

    def test_home_lists_only_effective_notifications(self):
        html = self.url_open('/portal', timeout=30).text
        self.assertIn('F11 còn hiệu lực', html)
        for hidden in ('F11 hẹn giờ', 'F11 hết hạn', 'F11 cửa hàng khác'):
            self.assertNotIn(hidden, html)

    def test_detail_reopen_keeps_first_read_date(self):
        self.url_open('/portal/notification/%s' % self.live.id)
        row = self._rows()
        self.assertEqual(len(row), 1)
        self.assertFalse(row.franchise_id, 'Toàn hệ: dấu theo user (WJ-NOTI-001).')
        first = row.read_date
        self.assertTrue(row.last_open_date)
        self.url_open('/portal/notification/%s' % self.live.id)
        row.invalidate_recordset()
        self.assertEqual(len(self._rows()), 1)
        self.assertEqual(row.read_date, first)

    def test_mark_read_only_accessible_ids(self):
        res = self.make_jsonrpc_request('/portal/notification/mark-read', {
            'notification_ids': self.mine.ids})
        self.assertEqual(res, {'success': True, 'created': 2})
        self.assertEqual(self._rows().mapped('notification_id'), self.live | self.expired)

    def test_attachment_download_only_own_files(self):
        base = '/portal/notification/%s/attachment/%s'
        self.assertEqual(self.url_open(base % (self.live.id, self.own_file.id)).status_code, 200)
        self.assertEqual(self.url_open(base % (self.live.id, self.other_file.id)).status_code, 403)
        self.assertEqual(self.url_open(base % (self.other_store.id, self.other_file.id)).status_code, 404)
        self.assertEqual(self.url_open(base % (self.scheduled.id, self.own_file.id)).status_code, 404)

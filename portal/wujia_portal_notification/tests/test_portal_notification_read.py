"""Ghi đã đọc qua portal. WJ-NOTI-001 (BA 02/10/2026) thay NOTI-02 bước 1: chưa chọn cửa hàng vẫn ghi
đã đọc cho thông báo toàn hệ (theo user, franchise NULL)."""

from odoo import fields
from odoo.tests.common import HOST, HttpCase, tagged

ACTIVE_FRANCHISE_COOKIE = 'wujia_active_franchise_id'
PORTAL_PASSWORD = 'wujia@test123'


@tagged('post_install', '-at_install', 'wujia_notification')
class TestPortalNotificationRead(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Read = cls.env['wujia.notification.read']
        # 2 cửa hàng → user multi-store, chưa chọn thì get_active_franchise_id() trả False
        # (nhánh auto-pick chỉ chạy khi user có đúng 1 cửa hàng).
        cls.franchise_a, cls.franchise_b = [cls._make_franchise(code) for code in ('WJT01', 'WJT02')]
        cls.portal_user = cls.env['res.users'].create({
            'name': 'Portal Noti Tester',
            'login': 'wj_noti_read_tester',
            'password': PORTAL_PASSWORD,
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        Member = cls.env['wujia.franchise.member']
        for franchise in (cls.franchise_a, cls.franchise_b):
            Member.create({
                'user_id': cls.portal_user.id,
                'franchise_id': franchise.id,
                'role': 'staff',
            })
        cls.noti = cls.env['wujia.notification'].create({
            'name': 'Lịch nghỉ Tết 2026',
            'type_id': cls.env['wujia.notification.type'].create({
                'name': 'Chính sách', 'code': 'TEST_READ_POLICY',
            }).id,
            'content': '<p>Nghỉ từ 25 tháng Chạp.</p>',
        })
        cls.noti.action_publish()

    @classmethod
    def _make_franchise(cls, code):
        return cls.env['wujia.franchise.management'].create({
            'code': code,
            'name': 'Cửa hàng %s' % code,
            'partner_id': cls.env['res.partner'].create({'name': 'Partner %s' % code}).id,
            'franchise_start_date': fields.Date.today(),
            'franchise_end_date': fields.Date.add(fields.Date.today(), years=1),
        })

    def setUp(self):
        super().setUp()
        self.authenticate(self.portal_user.login, PORTAL_PASSWORD)

    def _read_rows(self):
        return self.Read.search([('notification_id', '=', self.noti.id),
                                 ('user_id', '=', self.portal_user.id)])

    def _select_store(self, franchise):
        self.opener.cookies.set(ACTIVE_FRANCHISE_COOKIE, str(franchise.id), domain=HOST)

    # ---------------- chưa chọn cửa hàng → vẫn ghi dấu toàn hệ ----------------
    def test_mark_all_read_without_store_marks_broadcast(self):
        res = self.make_jsonrpc_request('/portal/notification/mark-all-read')
        self.assertTrue(res.get('success'))
        rows = self._read_rows()
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows.franchise_id, 'Thông báo toàn hệ ghi theo user (không cửa hàng).')

    def test_mark_read_without_store_marks_broadcast(self):
        res = self.make_jsonrpc_request(
            '/portal/notification/mark-read', {'notification_ids': [self.noti.id]})
        self.assertEqual(res.get('created'), 1)
        self.assertFalse(self._read_rows().franchise_id)

    def test_detail_without_store_records_read(self):
        response = self.url_open('/portal/notification/%s' % self.noti.id)
        self.assertEqual(response.status_code, 200)
        rows = self._read_rows()
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows.last_open_date)

    # ---------------- đã chọn cửa hàng → ghi bình thường ----------------
    def test_mark_all_read_with_store_is_idempotent(self):
        # DB local có sẵn thông báo seed → không assert số tuyệt đối, chỉ soi record của test.
        self._select_store(self.franchise_a)
        first = self.make_jsonrpc_request('/portal/notification/mark-all-read')
        self.assertTrue(first.get('success'))
        self.assertGreaterEqual(first.get('updated_count'), 1)
        self.assertEqual(first.get('unread_count'), 0)
        rows = self._read_rows()
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows.franchise_id, 'Thông báo toàn hệ: dấu theo user, hiệu lực mọi cửa hàng.')
        self.assertFalse(rows.last_open_date, 'mark-all không được giả lập thời điểm mở detail.')

        second = self.make_jsonrpc_request('/portal/notification/mark-all-read')
        self.assertEqual(second.get('updated_count'), 0, 'Gọi lại phải idempotent.')
        self.assertEqual(len(self._read_rows()), 1)

        # Sang cửa hàng B: thông báo toàn hệ vẫn đã đọc, không tạo thêm dấu.
        self._select_store(self.franchise_b)
        third = self.make_jsonrpc_request('/portal/notification/mark-all-read')
        self.assertNotIn(self.noti.id, self._read_rows().filtered('franchise_id').notification_id.ids)
        self.assertEqual(len(self._read_rows()), 1)
        self.assertEqual(third.get('unread_count'), 0)

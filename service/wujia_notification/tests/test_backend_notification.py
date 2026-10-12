"""Sprint 41 — backend quản lý thông báo nhượng quyền (BA spec phần F)."""

from datetime import timedelta

from psycopg2 import IntegrityError

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install', 'wujia_notification')
class TestBackendNotification(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Noti = cls.env['wujia.notification']
        cls.ntype = cls.env['wujia.notification.type'].create({
            'name': 'Chính sách', 'code': 'TEST_POLICY',
        })
        cls.draft = cls.Noti.create({
            'name': 'Lịch nghỉ Tết 2026',
            'type_id': cls.ntype.id,
            'content': '<p>Nghỉ từ 25 tháng Chạp.</p>',
        })

    # ---------------- code + mặc định ----------------
    def test_code_auto_sequence(self):
        self.assertTrue(self.draft.code.startswith('ANN/'),
                        'code phải sinh từ ir.sequence ANN/<năm>/<số>')
        other = self.Noti.create({'name': 'Khác', 'type_id': self.ntype.id})
        self.assertNotEqual(self.draft.code, other.code)

    def test_default_state_draft_not_on_portal(self):
        self.assertEqual(self.draft.state, 'draft')
        self.assertFalse(self.draft.is_published_portal)

    @mute_logger('odoo.sql_db')
    def test_code_unique(self):
        with self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                self.Noti.create({
                    'name': 'Trùng mã', 'type_id': self.ntype.id,
                    'code': self.draft.code,
                })

    # ---------------- publish ----------------
    def test_publish_requires_content(self):
        noti = self.Noti.create({'name': 'Thiếu nội dung', 'type_id': self.ntype.id})
        with self.assertRaises(UserError):
            noti.action_publish()
        self.assertEqual(noti.state, 'draft')

    def test_publish_requires_active_category(self):
        self.ntype.active = False
        with self.assertRaises(UserError):
            self.draft.action_publish()

    def test_publish_rejects_past_expired_date(self):
        # Nháp soạn từ 10 ngày trước, hạn hiệu lực đã qua → không cho gửi hôm nay.
        now = fields.Datetime.now()
        self.draft.write({
            'published_date': now - timedelta(days=10),
            'expired_date': now - timedelta(days=1),
        })
        with self.assertRaises(UserError):
            self.draft.action_publish()
        self.assertEqual(self.draft.state, 'draft')

    @mute_logger('odoo.sql_db')
    def test_expired_date_before_published_date_blocked(self):
        # Spec F §8.7 — chặn ngay ở tầng DB kèm message nghiệp vụ.
        with self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                self.draft.expired_date = fields.Datetime.now() - timedelta(days=1)
                self.env.flush_all()

    def test_publish_sets_metadata_and_portal_flag(self):
        self.draft.action_publish()
        self.assertEqual(self.draft.state, 'published')
        self.assertTrue(self.draft.published_date)
        self.assertEqual(self.draft.published_by_id, self.env.user)
        self.assertTrue(self.draft.is_published_portal)

    def test_portal_visible_off_hides_from_portal(self):
        self.draft.action_publish()
        self.draft.portal_visible = False
        self.assertFalse(self.draft.is_published_portal)

    def test_inactive_hides_from_portal(self):
        self.draft.action_publish()
        self.draft.active = False
        self.assertFalse(self.draft.is_published_portal)

    # ---------------- state machine (spec F §4) ----------------
    def test_archived_is_dead_end(self):
        self.draft.action_publish()
        self.draft.action_archive_notification()
        self.assertEqual(self.draft.state, 'archived')
        self.assertFalse(self.draft.is_published_portal)
        with self.assertRaises(UserError):
            self.draft.state = 'published'

    def test_published_cannot_return_to_draft(self):
        self.draft.action_publish()
        with self.assertRaises(UserError):
            self.draft.state = 'draft'

    def test_publish_twice_blocked(self):
        self.draft.action_publish()
        with self.assertRaises(UserError):
            self.draft.action_publish()

    def test_published_without_category_blocked(self):
        with self.assertRaises(ValidationError):
            self.Noti.create({
                'name': 'Không loại', 'content': '<p>x</p>',
                'state': 'published',
            })

    # ---------------- archive / delete (spec F §17) ----------------
    def test_unlink_published_blocked_draft_allowed(self):
        self.draft.action_publish()
        with self.assertRaises(UserError):
            self.draft.unlink()
        temp = self.Noti.create({'name': 'Nháp bỏ', 'type_id': self.ntype.id})
        temp.unlink()

    # ---------------- thống kê đọc (spec F §15) ----------------
    def test_unread_count_zero_when_expired(self):
        self.draft.action_publish()
        self.draft.expired_date = fields.Datetime.now() - timedelta(hours=1)
        self.assertTrue(self.draft.is_expired)
        self.assertEqual(self.draft.unread_count, 0)
        # Hết hiệu lực vẫn còn trong lịch sử portal.
        self.assertTrue(self.draft.is_published_portal)

    def test_read_count_counts_distinct_rows(self):
        self.draft.action_publish()
        self.env['wujia.notification.read'].create({
            'notification_id': self.draft.id,
            'user_id': self.env.user.id,
        })
        self.assertEqual(self.draft.read_count, 1)

    @mute_logger('odoo.sql_db')
    def test_read_row_unique_per_user_store(self):
        Read = self.env['wujia.notification.read']
        vals = {'notification_id': self.draft.id, 'user_id': self.env.user.id}
        Read.create(vals)
        with self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                Read.create(vals)

    # ---------------- quyền portal (spec F §16/§17.1) ----------------
    def test_portal_user_cannot_write_backend_models(self):
        portal_user = self.env['res.users'].create({
            'name': 'Portal Tester', 'login': 'wj_portal_tester',
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        Noti = self.Noti.with_user(portal_user)
        with self.assertRaises(AccessError):
            Noti.create({'name': 'Portal tự tạo'})
        self.draft.action_publish()
        with self.assertRaises(AccessError):
            self.draft.with_user(portal_user).write({'name': 'Sửa trộm'})
        with self.assertRaises(AccessError):
            self.env['wujia.notification.type'].with_user(portal_user).create({
                'name': 'Loại lậu', 'code': 'HACK',
            })

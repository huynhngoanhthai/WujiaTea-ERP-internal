"""Chọn đối tượng nhận thông báo — target_mode all / filter / manual.

Chủ dự án chốt 31/07/2026 (ghi chú cột L phần F, dòng 741-746): tiêu chí chỉ là CÁCH CHỌN,
kết quả chốt vào franchise_ids tại thời điểm publish nên portal/ir.rule không đổi.
"""

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

PORTAL_PASSWORD = 'wujia@test123'


@tagged('post_install', '-at_install', 'wujia_notification')
class TestNotificationTargeting(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Noti = cls.env['wujia.notification']
        cls.Franchise = cls.env['wujia.franchise.management']
        cls.area_north = cls.env['res.area'].create({'code': 'KV-BAC', 'name': 'Miền Bắc'})
        cls.area_south = cls.env['res.area'].create({'code': 'KV-NAM', 'name': 'Miền Nam'})
        cls.type = cls.env['wujia.notification.type'].create({
            'name': 'Chính sách', 'code': 'TEST_TARGET_POLICY',
        })
        cls.north_a = cls._make_franchise('TGT-N1', cls.area_north)
        cls.north_b = cls._make_franchise('TGT-N2', cls.area_north)
        cls.south_a = cls._make_franchise('TGT-S1', cls.area_south)
        cls.north_closed = cls._make_franchise('TGT-N3', cls.area_north, status='closed')

    @classmethod
    def _make_franchise(cls, code, area, status='active'):
        return cls.Franchise.create({
            'code': code,
            'name': 'Cửa hàng %s' % code,
            'partner_id': cls.env['res.partner'].create({'name': 'Partner %s' % code}).id,
            'area_id': area.id,
            'status': status,
            'franchise_start_date': fields.Date.today(),
            'franchise_end_date': fields.Date.add(fields.Date.today(), years=1),
        })

    def _make_noti(self, **vals):
        base = {'name': 'Lịch nghỉ Tết 2026', 'type_id': self.type.id,
                'content': '<p>Nghỉ từ 25 tháng Chạp.</p>'}
        base.update(vals)
        return self.Noti.create(base)

    # ---------------- mặc định: gửi hết ----------------
    def test_default_mode_is_all_and_stays_broadcast(self):
        noti = self._make_noti()
        self.assertEqual(noti.target_mode, 'all')
        noti.action_publish()
        self.assertFalse(noti.franchise_ids, 'Gửi tất cả thì không ghi dòng franchise nào.')

    def test_switching_to_all_clears_selected_stores(self):
        noti = self._make_noti(target_mode='manual',
                               franchise_ids=[fields.Command.set(self.north_a.ids)])
        noti.write({'target_mode': 'all'})
        self.assertFalse(noti.franchise_ids)

    # ---------------- theo tiêu chí ----------------
    def test_filter_by_area_resolves_on_publish(self):
        noti = self._make_noti(target_mode='filter',
                               target_area_ids=[fields.Command.set(self.area_north.ids)])
        self.assertFalse(noti.franchise_ids, 'Chưa gửi thì chưa chốt danh sách.')
        self.assertEqual(noti.target_preview_count, 2, 'Miền Bắc có 2 cửa hàng đang hoạt động.')
        noti.action_publish()
        self.assertEqual(noti.franchise_ids, self.north_a | self.north_b)

    def test_filter_skips_inactive_store_unless_any_status(self):
        noti = self._make_noti(target_mode='filter',
                               target_area_ids=[fields.Command.set(self.area_north.ids)])
        self.assertNotIn(self.north_closed, noti._resolve_target_franchises())
        noti.target_status = 'any'
        self.assertIn(self.north_closed, noti._resolve_target_franchises())

    def test_filter_excludes_listed_stores(self):
        noti = self._make_noti(
            target_mode='filter',
            target_area_ids=[fields.Command.set(self.area_north.ids)],
            target_exclude_franchise_ids=[fields.Command.set(self.north_b.ids)],
        )
        noti.action_publish()
        self.assertEqual(noti.franchise_ids, self.north_a)

    def test_new_store_does_not_join_published_notification(self):
        noti = self._make_noti(target_mode='filter',
                               target_area_ids=[fields.Command.set(self.area_north.ids)])
        noti.action_publish()
        newcomer = self._make_franchise('TGT-N9', self.area_north)
        self.assertNotIn(newcomer, noti.franchise_ids,
                         'Cửa hàng mở sau ngày gửi không tự nhận thông báo cũ.')
        noti.action_refresh_recipients()
        self.assertIn(newcomer, noti.franchise_ids, 'Cập nhật danh sách thì mới thêm vào.')

    # ---------------- ràng buộc ----------------
    def test_filter_without_criteria_is_blocked(self):
        with self.assertRaises(ValidationError):
            self._make_noti(target_mode='filter')

    def test_publish_blocked_when_filter_matches_nothing(self):
        empty_area = self.env['res.area'].create({'code': 'KV-TRONG', 'name': 'Khu vực trống'})
        noti = self._make_noti(target_mode='filter',
                               target_area_ids=[fields.Command.set(empty_area.ids)])
        with self.assertRaises(UserError):
            noti.action_publish()

    def test_publish_blocked_when_manual_has_no_store(self):
        noti = self._make_noti(target_mode='manual')
        with self.assertRaises(UserError):
            noti.action_publish()

    def test_refresh_rejected_outside_filter_mode(self):
        noti = self._make_noti()
        with self.assertRaises(UserError):
            noti.action_refresh_recipients()

    # ---------------- portal chỉ thấy thông báo của mình ----------------
    def test_portal_user_outside_target_cannot_see_notification(self):
        user = self.env['res.users'].create({
            'name': 'Portal Target Tester',
            'login': 'wj_noti_target_tester',
            'password': PORTAL_PASSWORD,
            'group_ids': [fields.Command.set([self.env.ref('base.group_portal').id])],
        })
        self.env['wujia.franchise.member'].create({
            'user_id': user.id, 'franchise_id': self.south_a.id, 'role': 'staff',
        })
        self.env.registry.clear_cache()

        targeted = self._make_noti(name='Chỉ miền Bắc', target_mode='filter',
                                   target_area_ids=[fields.Command.set(self.area_north.ids)])
        targeted.action_publish()
        broadcast = self._make_noti(name='Toàn hệ thống')
        broadcast.action_publish()

        visible = self.Noti.with_user(user).search([('id', 'in', (targeted | broadcast).ids)])
        self.assertNotIn(targeted, visible, 'Cửa hàng miền Nam không được thấy thông báo miền Bắc.')
        self.assertIn(broadcast, visible, 'Thông báo gửi tất cả thì mọi cửa hàng vẫn thấy.')

    def test_recipient_count_counts_only_targeted_stores(self):
        # 2 người ở Miền Bắc, 1 người ở Miền Nam — thông báo chỉ gửi north_a thì đếm 1.
        for idx, franchise in enumerate((self.north_a, self.north_b, self.south_a)):
            user = self.env['res.users'].create({
                'name': 'Portal Count %s' % idx,
                'login': 'wj_noti_count_%s' % idx,
                'group_ids': [fields.Command.set([self.env.ref('base.group_portal').id])],
            })
            self.env['wujia.franchise.member'].create({
                'user_id': user.id, 'franchise_id': franchise.id, 'role': 'staff',
            })
        targeted = self._make_noti(target_mode='manual',
                                   franchise_ids=[fields.Command.set(self.north_a.ids)])
        broadcast = self._make_noti()
        self.assertEqual(targeted.recipient_count, 1)
        # DB local/CI có sẵn membership khác → chỉ khẳng định broadcast rộng hơn.
        self.assertGreater(broadcast.recipient_count, targeted.recipient_count)

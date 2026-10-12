"""I6 — WJ-NOTI-001: phạm vi dấu đã đọc + một luật số chưa đọc + migration dấu cũ."""
import importlib.util
from datetime import timedelta
from pathlib import Path

from odoo import fields
from odoo.tests.common import TransactionCase, tagged

from .test_portal_rules import NotificationCommon


@tagged('post_install', '-at_install', 'wujia_notification', 'wujia_noti_i6')
class TestI6ReadScope(NotificationCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_notification(login='i6_reader')
        cls.store_c = cls._store('F11C')
        now = fields.Datetime.now()
        cls.both = cls._noti('I6 gửi A và B', now - timedelta(minutes=1), stores=cls.store_a | cls.store_b)
        cls.mine |= cls.both

    def _unread(self, store=None):
        """Bài chưa đọc trong phần thông báo của test (DB có thông báo seed)."""
        ids = [store.id] if store else []
        dom = self.Noti._portal_unread_domain(self.user, ids, store and store.id)
        return self.Noti.search(dom + [('id', 'in', self.mine.ids)])

    def _count(self, store=None):
        ids = [store.id] if store else []
        others = self.Noti._portal_unread_domain(self.user, ids, store and store.id) + [
            ('id', 'not in', self.mine.ids)]
        return (self.Noti._portal_unread_count(self.user, ids, store and store.id)
                - self.Noti.search_count(others))

    def _rows(self):
        return self.Read.search([('user_id', '=', self.user.id), ('notification_id', 'in', self.mine.ids)])

    # GIVEN 1 — toàn hệ đọc ở bất kỳ trạng thái chọn cửa hàng nào ⇒ cửa hàng khác vẫn Đã đọc.
    def test_broadcast_read_follows_user(self):
        self.assertEqual(self._unread(self.store_a), self.live | self.both)
        self.Read._mark_read(self.user, False, self.live)
        for store in (None, self.store_a, self.store_b):
            self.assertNotIn(self.live, self._unread(store))
            self.assertIn(self.live.id, self.Noti._portal_read_ids(
                self.user, self.mine.ids, store and store.id))
        self.assertEqual(self._count(self.store_b), 2, 'B còn bài riêng + bài A,B')
        self.assertEqual(len(self._rows()), 1)
        self.assertFalse(self._rows().franchise_id)
        # Đọc lại ở cửa hàng khác không tạo thêm dấu.
        self.assertEqual(self.Read._mark_read(self.user, self.store_b.id, self.live, opened=True), 0)

    # GIVEN 2 — bài chỉ định đọc ở A ⇒ B vẫn chưa đọc, không tạo dấu cho B.
    def test_targeted_read_stays_in_store(self):
        self.Read._mark_read(self.user, self.store_a.id, self.both)
        self.assertNotIn(self.both, self._unread(self.store_a))
        self.assertIn(self.both, self._unread(self.store_b))
        self.assertEqual(self._rows().franchise_id, self.store_a)
        # Cửa hàng không nhận ⇒ không ghi dấu (không tạo dấu sai phạm vi).
        self.assertEqual(self.Read._mark_read(self.user, self.store_c.id, self.both | self.other_store), 0)
        self.assertEqual(self.Read._mark_read(self.user, False, self.both), 0)
        self.assertEqual(len(self._rows()), 1)

    # GIVEN 3 — chưa chọn cửa hàng: chỉ toàn hệ; đánh dấu tất cả chỉ áp dụng toàn hệ còn hiệu lực.
    def test_no_store_only_broadcast(self):
        history = self.Noti.search(self.Noti._portal_history_domain(()) + [('id', 'in', self.mine.ids)])
        self.assertEqual(history, self.live | self.expired)
        unread = self._unread()
        self.assertEqual(unread, self.live)
        self.assertEqual(self.Read._mark_read(self.user, False, unread), 1)
        self.assertFalse(self._unread())
        self.assertEqual(self._rows().notification_id, self.live)
        self.assertEqual(self._unread(self.store_b), self.other_store | self.both)

    # GIVEN 4 — hẹn giờ / hết hạn không tính chưa đọc; hết hạn vẫn mở được từ lịch sử.
    def test_unread_excludes_scheduled_and_expired(self):
        for store in (None, self.store_a, self.store_b):
            unread = self._unread(store)
            self.assertNotIn(self.scheduled, unread)
            self.assertNotIn(self.expired, unread)
        history = self.Noti.search(self.Noti._portal_history_domain([self.store_a.id]))
        self.assertIn(self.expired, history)
        self.assertNotIn(self.scheduled, history)

    # Một số chưa đọc: đếm = số dòng của domain chung.
    def test_count_equals_domain(self):
        self.Read._mark_read(self.user, self.store_a.id, self.live | self.both)
        for store in (None, self.store_a, self.store_b):
            self.assertEqual(self._count(store), len(self._unread(store)))

    # Dữ liệu lệch phạm vi (dấu cũ) không bao giờ được tính là đã đọc.
    def test_stale_rows_do_not_count(self):
        self.Read.create([
            {'notification_id': self.both.id, 'user_id': self.user.id},
            {'notification_id': self.live.id, 'user_id': self.user.id, 'franchise_id': self.store_a.id},
        ])
        self.assertEqual(self._unread(self.store_a), self.live | self.both)
        self.assertEqual(self._unread(), self.live)
        self.assertFalse(self.Noti._portal_read_ids(self.user, self.mine.ids, self.store_a.id))

    def test_read_stats_scope(self):
        Member = self.env['wujia.franchise.member']
        other = self.env['res.users'].create({
            'name': 'I6 Other', 'login': 'i6_other',
            'group_ids': [fields.Command.set([self.env.ref('base.group_portal').id])],
        })
        for user, store in ((self.user, self.store_a), (self.user, self.store_b), (other, self.store_a)):
            Member.create({'user_id': user.id, 'franchise_id': store.id, 'role': 'staff'})
        self.Read._mark_read(self.user, self.store_a.id, self.live | self.both)
        self.Read._mark_read(other, self.store_a.id, self.live)
        self.Read.create({'notification_id': self.both.id, 'user_id': other.id})  # lệch phạm vi
        self.live.invalidate_recordset(['read_count', 'recipient_count'])
        pairs = Member.sudo()._read_group([('is_currently_valid', '=', True)], groupby=['user_id'])
        self.assertEqual(self.live.recipient_count, len(pairs), 'toàn hệ: đếm user, không đếm cặp')
        self.assertEqual(self.live.read_count, 2)
        self.assertEqual(self.both.recipient_count, 3, 'A,B: user@A, user@B, other@A')
        self.assertEqual(self.both.read_count, 1)


@tagged('post_install', '-at_install', 'wujia_notification', 'wujia_noti_i6')
class TestI6Migration(NotificationCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_notification(login='i6_migrate')
        cls.both = cls._noti('I6 mig A,B', fields.Datetime.now(), stores=cls.store_a | cls.store_b)

    def _migrate(self):
        path = Path(__file__).parents[1] / 'migrations' / '19.0.3.0.0' / 'post-migrate.py'
        spec = importlib.util.spec_from_file_location('wj_noti_i6_post_migrate', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.env.flush_all()
        mod.migrate(self.env.cr, '19.0.2.0.0')
        self.env.invalidate_all()

    def test_migration_scopes_old_marks(self):
        uid, a, b = self.user.id, self.store_a.id, self.store_b.id
        t1, t2, t3 = '2026-06-01 01:00:00', '2026-06-05 01:00:00', '2026-06-10 02:00:00'
        rows = [
            # Toàn hệ: đọc ở 2 cửa hàng ⇒ gộp 1 dòng NULL, mốc sớm/muộn nhất.
            (self.live.id, a, t2, None), (self.live.id, b, t1, t3),
            # Toàn hệ: đã có NULL + dòng cửa hàng ⇒ giữ NULL, lấy read_date sớm nhất.
            (self.expired.id, None, t2, None), (self.expired.id, a, t1, None),
            # Chỉ định: đúng cửa hàng giữ; NULL và sai cửa hàng xoá.
            (self.both.id, a, t1, None), (self.both.id, None, t1, None),
            (self.other_store.id, a, t1, None),
        ]
        for noti, store, read, opened in rows:
            self.env.cr.execute("""
                INSERT INTO wujia_notification_read (notification_id, user_id, franchise_id, read_date, last_open_date)
                VALUES (%s, %s, %s, %s, %s)""", (noti, uid, store, read, opened))
        self._migrate()
        got = {(r.notification_id.id, r.franchise_id.id or None): r
               for r in self.Read.search([('user_id', '=', uid)])}
        self.assertEqual(set(got), {
            (self.live.id, None), (self.expired.id, None), (self.both.id, a)})
        self.assertEqual(fields.Datetime.to_string(got[(self.live.id, None)].read_date), t1)
        self.assertEqual(fields.Datetime.to_string(got[(self.live.id, None)].last_open_date), t3)
        self.assertEqual(fields.Datetime.to_string(got[(self.expired.id, None)].read_date), t1)
        # Chạy lại không đổi gì.
        self._migrate()
        self.assertEqual(len(self.Read.search([('user_id', '=', uid)])), 3)

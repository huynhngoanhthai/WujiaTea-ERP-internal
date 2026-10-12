"""F11 — luật portal dùng chung ở model: phạm vi lịch sử / còn hiệu lực, đếm chưa đọc, ghi đã đọc."""
from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


class NotificationCommon:
    """Fixture dùng chung với test portal: 2 cửa hàng, 4 thông báo (còn hiệu lực, hết hạn, hẹn giờ, cửa hàng B)."""

    @classmethod
    def _setup_notification(cls, login='f11_reader'):
        cls.Noti = cls.env['wujia.notification'].sudo()
        cls.Read = cls.env['wujia.notification.read'].sudo()
        cls.store_a, cls.store_b = [cls._store(code) for code in ('F11A', 'F11B')]
        cls.user = cls.env['res.users'].create({
            'name': 'F11 Reader', 'login': login, 'password': login,
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        cls.ntype = cls.env['wujia.notification.type'].create({'name': 'F11', 'code': 'F11_TYPE'})
        now = fields.Datetime.now()
        # Ghim cả 4 để lọt top Home dù DB có thông báo seed: lọt ra là do luật, không do thứ tự.
        cls.live = cls._noti('F11 còn hiệu lực', now - timedelta(minutes=1))
        cls.expired = cls._noti('F11 hết hạn', now - timedelta(minutes=3), expired=now - timedelta(minutes=2))
        cls.scheduled = cls._noti('F11 hẹn giờ', now + timedelta(days=2))
        cls.other_store = cls._noti('F11 cửa hàng khác', now - timedelta(minutes=1), stores=cls.store_b)
        cls.mine = cls.live | cls.expired | cls.scheduled | cls.other_store

    @classmethod
    def _store(cls, code):
        return cls.env['wujia.franchise.management'].create({
            'code': code, 'name': 'Cửa hàng %s' % code,
            'partner_id': cls.env['res.partner'].create({'name': code}).id,
            'franchise_start_date': fields.Date.today(),
            'franchise_end_date': fields.Date.add(fields.Date.today(), years=1),
        })

    @classmethod
    def _noti(cls, name, published, expired=False, stores=None):
        return cls.env['wujia.notification'].create({
            'name': name, 'type_id': cls.ntype.id, 'content': '<p>%s</p>' % name,
            'state': 'published', 'published_date': published, 'expired_date': expired,
            'is_pinned': True,
            'target_mode': 'manual' if stores else 'all',
            'franchise_ids': [fields.Command.set(stores.ids)] if stores else False,
        })


@tagged('post_install', '-at_install', 'wujia_notification')
class TestPortalRules(NotificationCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_notification()

    def _found(self, domain):
        return self.Noti.search(domain + [('id', 'in', self.mine.ids)])

    def _broadcast_unread(self, store):
        """Đếm chưa đọc chỉ trên phần thông báo của test (DB có sẵn thông báo seed)."""
        others = self.Noti._portal_effective_domain([store.id]) + [('id', 'not in', self.mine.ids)]
        return self.Noti._portal_unread_count(self.user, [store.id], store.id) - self.Noti.search_count(others)

    def test_history_and_effective_domains(self):
        history = self._found(self.Noti._portal_history_domain([self.store_a.id]))
        self.assertEqual(history, self.live | self.expired)
        effective = self._found(self.Noti._portal_effective_domain([self.store_a.id]))
        self.assertEqual(effective, self.live)
        self.assertIn(self.other_store, self._found(self.Noti._portal_effective_domain([self.store_b.id])))

    def test_unread_count_broadcast_once_per_user(self):
        """WJ-NOTI-001: thông báo toàn hệ đọc 1 lần theo user, hiệu lực mọi cửa hàng."""
        self.assertEqual(self._broadcast_unread(self.store_a), 1)
        self.Read._mark_read(self.user, self.store_a.id, self.live)
        self.assertEqual(self._broadcast_unread(self.store_a), 0)
        self.assertEqual(self._broadcast_unread(self.store_b), 1, 'chỉ còn bài riêng của B')
        # Đọc thông báo hết hạn không làm âm số chưa đọc.
        self.Read._mark_read(self.user, self.store_b.id, self.expired)
        self.assertEqual(self._broadcast_unread(self.store_b), 1)

    def test_mark_read_modes(self):
        rows = lambda: self.Read.search([('user_id', '=', self.user.id)])
        # Chưa chọn cửa hàng: bài toàn hệ vẫn ghi (dòng NULL); bài chỉ định bỏ qua.
        self.assertEqual(self.Read._mark_read(self.user, False, self.live | self.other_store), 1)
        self.assertEqual(rows().franchise_id, self.env['wujia.franchise.management'])
        # mark-all: không giả lập thời điểm mở; bài toàn hệ đã có dấu ⇒ chỉ tạo bài hết hạn.
        self.assertEqual(self.Read._mark_read(self.user, self.store_a.id, self.live | self.expired), 1)
        self.assertFalse(any(rows().mapped('last_open_date')))
        self.assertEqual(self.Read._mark_read(self.user, self.store_b.id, self.live | self.expired), 0)
        # mark-read theo id: dòng mới có last_open_date, dòng cũ giữ nguyên.
        self.assertEqual(self.Read._mark_read(self.user, self.store_b.id, self.other_store, opened=True), 1)
        row_b = rows().filtered(lambda r: r.franchise_id == self.store_b)
        self.assertTrue(row_b.last_open_date)
        row_live = rows().filtered(lambda r: r.notification_id == self.live)
        self.Read._mark_read(self.user, self.store_a.id, self.live, opened=True)
        self.assertFalse(row_live.last_open_date)
        # mở chi tiết lại: đổi last_open_date, giữ read_date.
        first_read = row_live.read_date
        self.Read._mark_read(self.user, self.store_a.id, self.live, opened=True, touch=True)
        self.assertTrue(row_live.last_open_date)
        self.assertEqual(row_live.read_date, first_read)
        self.assertEqual(len(rows()), 3)

    def test_get_attachment_only_own_files(self):
        Att = self.env['ir.attachment']
        own = Att.create({'name': 'own.txt', 'raw': b'a', 'res_model': 'wujia.notification', 'res_id': self.live.id})
        other = Att.create({'name': 'other.txt', 'raw': b'b', 'res_model': 'wujia.notification',
                            'res_id': self.expired.id})
        self.live.attachment_ids = [fields.Command.link(own.id)]
        self.expired.attachment_ids = [fields.Command.link(other.id)]
        self.assertEqual(self.live._portal_get_attachment(own.id), own)
        self.assertFalse(self.live._portal_get_attachment(other.id))

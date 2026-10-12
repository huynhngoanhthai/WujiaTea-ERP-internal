from odoo import api, fields, models


class WujiaNotificationRead(models.Model):
    """Tracking đã đọc (WJ-NOTI-001, BA 02/10/2026).

    Thông báo toàn hệ ⇒ 1 dấu theo user (franchise_id NULL), hiệu lực ở mọi cửa hàng và cả khi
    chưa chọn cửa hàng. Thông báo chỉ định ⇒ dấu theo user + đúng cửa hàng nhận đang chọn.
    Luật đếm/đọc dùng chung ở `wujia.notification._portal_read_scope`."""

    _name = 'wujia.notification.read'
    _description = 'Wujia Notification Read Tracking'
    _order = 'read_date desc'

    notification_id = fields.Many2one(
        'wujia.notification', string='Notification',
        required=True, ondelete='cascade', index=True,
    )
    user_id = fields.Many2one(
        'res.users', string='Reader',
        required=True, index=True, ondelete='cascade',
    )
    franchise_id = fields.Many2one(
        'wujia.franchise.management', string='Store',
        index=True, ondelete='cascade',
    )
    member_id = fields.Many2one(
        'wujia.franchise.member', string='Membership',
        index=True, ondelete='set null',
        help='Membership snapshot at the store when the read was recorded (spec F §7).',
    )
    read_date = fields.Datetime(
        string='First read', default=fields.Datetime.now, required=True,
    )
    last_open_date = fields.Datetime(string='Last opened')

    _uniq_noti_user_store = models.Constraint(
        'unique(notification_id, user_id, franchise_id)',
        'Each user can record a read only once per notification and store.',
    )
    # unique() coi mọi NULL là khác nhau → session chưa chọn cửa hàng vẫn tạo được row trùng.
    # Partial index bịt nốt nhánh đó (spec F §8.9 — mark-read phải idempotent).
    _uniq_noti_user_no_store = models.UniqueIndex(
        '(notification_id, user_id) WHERE franchise_id IS NULL',
        'Each user can record a read only once per notification when no store is selected.',
    )

    @api.model
    def _mark_read(self, user, franchise_id, notifications, opened=False, touch=False):
        """Ghi "đã đọc" cho `notifications` theo đúng phạm vi — idempotent, trả số dòng tạo mới.

        Toàn hệ ⇒ dòng franchise_id NULL (ghi cả khi chưa chọn cửa hàng). Chỉ định ⇒ dòng
        `franchise_id` chỉ khi cửa hàng đang chọn là cửa hàng nhận; ngoài ra bỏ qua (không tạo
        dấu sai phạm vi).
        opened: người dùng thật sự mở nội dung ⇒ dòng mới có `last_open_date`.
        touch: dòng đã có đổi `last_open_date` (mở lại trang chi tiết), `read_date` giữ nguyên.
        """
        broadcast = notifications.filtered(lambda n: not n.franchise_ids)
        targeted = (notifications - broadcast).filtered(
            lambda n: franchise_id and franchise_id in n.franchise_ids.ids)
        now = fields.Datetime.now()
        vals = []
        for store_id, batch in ((False, broadcast), (franchise_id, targeted)):
            if not batch:
                continue
            existing = self.search([
                ('user_id', '=', user.id),
                ('notification_id', 'in', batch.ids),
                ('franchise_id', '=', store_id),
            ])
            if touch and existing:
                existing.last_open_date = now
            done = set(existing.mapped('notification_id').ids)
            vals += [
                dict({'notification_id': nid, 'user_id': user.id,
                      'franchise_id': store_id, 'read_date': now},
                     **({'last_open_date': now} if opened else {}))
                for nid in batch.ids if nid not in done
            ]
        if vals:
            self.create(vals)
        return len(vals)

import re
from html import unescape

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)


# Spec F §5 (sheet "1. Model/ Field"): 3 technical key, nhãn hiển thị
# "Thông thường / Quan trọng / Cần làm". FE không hardcode label — đọc priority_label backend trả.
PRIORITY_SELECTION = [
    ('normal', 'Regular'),
    ('important', 'Important'),
    ('urgent', 'Action required'),
]

# Spec F §3 — vòng đời do HQ điều khiển (expired_date KHÔNG tự đổi state).
STATE_SELECTION = [
    ('draft', 'Draft'),
    ('published', 'Submitted'),
    ('archived', 'Archived'),
]

# Spec F §4 — ma trận chuyển trạng thái. archived = ngõ cụt trong MVP.
STATE_TRANSITIONS = {
    'draft': ('published', 'archived'),
    'published': ('archived',),
    'archived': (),
}

# Chủ dự án chốt 31/07/2026 — ghi chú bổ sung cột L phần F, dòng 741-746:
# thông báo được chọn đối tượng nhận, mặc định `all` = gửi toàn hệ thống (giữ hành vi MVP).
# Tiêu chí chỉ là CÁCH CHỌN; kết quả luôn được chốt vào `franchise_ids` để portal/ir.rule
# đọc như cũ (không đổi tầng phân quyền, giữ index cho 1500 user).
TARGET_MODE_SELECTION = [
    ('all', 'All stores'),
    ('filter', 'By criteria'),
    ('manual', 'Manual selection'),
]

# Spec F §18 — message nghiệp vụ, không lộ lỗi kỹ thuật. `_lt` ⇒ dịch lúc raise bằng `self.env._`.
MSG_PUBLISH_VALIDATION = _lt(
    'Please enter the title, content, type and severity of the notification; '
    'the expiry date cannot be earlier than the sent date.'
)
MSG_TARGET_NO_CRITERIA = _lt(
    'With "By criteria", choose at least one criterion: area, province/city '
    'or excluded store.'
)
MSG_TARGET_EMPTY = _lt('The criteria do not match any store. Please adjust them before sending.')
MSG_TARGET_MANUAL_EMPTY = _lt('Please select at least one recipient store.')
MSG_TARGET_ALL_HAS_STORES = _lt('When sending to "All stores", recipient stores must be left empty.')


class WujiaNotification(models.Model):
    """Thông báo HQ → cửa hàng nhượng quyền. Backend HQ soạn/publish/archive, portal chỉ đọc.

    franchise_ids empty = broadcast cho tất cả cửa hàng đang hoạt động; `target_mode`
    quyết định field này được điền thế nào (tất cả / theo tiêu chí / chọn tay).
    Trạng thái đọc/chưa đọc lưu ở `wujia.notification.read` (table riêng để
    đếm unread nhanh — pattern v14); phạm vi dấu đọc xem `_portal_read_scope`."""

    # Mapping BA spec phần F (wujia.announcement) → model THẬT (giữ tên source, Sprint 41):
    #   title→name · name (ANN/2026/0001)→code · category_id→type_id · published_date→published_date
    #   (đã rename từ `date`) · wujia.announcement.category→wujia.notification.type.
    # `dispatch_number` = số công văn HQ nhập tay, KHÁC `code` (mã hệ thống auto).
    _name = 'wujia.notification'
    _description = 'Wujia Notification'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'published_date desc, id desc'

    code = fields.Char(
        string='Notification code', copy=False, readonly=True, index=True,
        help='System-generated code, e.g. ANN/2026/0001.',
    )
    name = fields.Char(string='Title', required=True, index=True, tracking=True)
    type_id = fields.Many2one(
        'wujia.notification.type', string='Type',
        index=True, ondelete='restrict', tracking=True,
    )
    dispatch_number = fields.Char(string='Document number', copy=False)
    published_date = fields.Datetime(
        string='Submission date', default=fields.Datetime.now,
        index=True, required=True, tracking=True,
    )
    content = fields.Html(string='Content', sanitize=True, translate=True)
    attachment_ids = fields.Many2many(
        'ir.attachment', 'wujia_notification_attachment_rel',
        'notification_id', 'attachment_id',
        string='Attachments',
    )
    franchise_ids = fields.Many2many(
        'wujia.franchise.management',
        'wujia_notification_franchise_rel',
        'notification_id', 'franchise_id',
        string='Recipient stores',
        help='Leave empty to broadcast to every store. The "By criteria" mode fills this field in when sending.',
    )
    target_mode = fields.Selection(
        TARGET_MODE_SELECTION, string='Send to', default='all',
        required=True, tracking=True,
        help="All = every store, nothing to select. By criteria = filter by area/province/status. Manual selection = tick each store yourself.",
    )
    target_area_ids = fields.Many2many(
        'res.area', 'wujia_notification_target_area_rel',
        'notification_id', 'area_id', string='Area',
    )
    target_state_ids = fields.Many2many(
        'res.country.state', 'wujia_notification_target_state_rel',
        'notification_id', 'state_id', string='Province',
    )
    target_status = fields.Selection(
        [('active', 'Active'), ('any', 'Any status')],
        string='Store status', default='active', required=True,
        help='By default only active stores are targeted; draft/locked/closed/expired ones are skipped.',
    )
    target_exclude_franchise_ids = fields.Many2many(
        'wujia.franchise.management', 'wujia_notification_target_exclude_rel',
        'notification_id', 'franchise_id', string='Excluded stores',
        help='Exclude a few specific stores from the filter result.',
    )
    target_preview_count = fields.Integer(
        string='Matching stores', compute='_compute_target_preview_count',
        help='Number of stores that would receive it if sent right now.',
    )
    state = fields.Selection(
        STATE_SELECTION, string='Status',
        default='draft', required=True, index=True, copy=False, tracking=True,
    )
    portal_visible = fields.Boolean(
        string='Show on portal', default=True,
        help='Turn it off to hide it from the portal without changing the state.',
    )
    is_published_portal = fields.Boolean(
        string='Live on portal',
        compute='_compute_is_published_portal', store=True, index=True,
        help="active + state = Sent + shown on portal. It does NOT exclude expired notifications, because the portal history must stay accessible.",
    )
    published_by_id = fields.Many2one(
        'res.users', string='Sent by', readonly=True, copy=False,
        help='The internal user who pressed Send notification.',
    )
    internal_note = fields.Text(
        string='Internal note',
        help='HQ only — not returned to the portal.',
    )
    priority = fields.Selection(
        PRIORITY_SELECTION, string='Severity',
        default='normal', required=True, index=True, tracking=True,
    )
    is_pinned = fields.Boolean(string='Pin to top', default=False)
    pin_expiry_date = fields.Datetime(string='Pinned until')
    expired_date = fields.Datetime(
        string='Expires on', index=True,
        help='Empty = never expires. After this moment it is hidden from the popup/badge but stays in history.',
    )
    is_expired = fields.Boolean(
        string='No longer valid', compute='_compute_is_expired',
    )
    priority_label = fields.Char(
        string='Priority label', compute='_compute_priority_label',
    )
    summary = fields.Text(
        string='Summary',
        help='Short description shown in the list/popup. Leave it empty and the portal excerpts the content.',
    )
    read_ids = fields.One2many(
        'wujia.notification.read', 'notification_id',
        string='Read status', readonly=True,
    )
    read_count = fields.Integer(
        string='Read', compute='_compute_read_stats',
        help='All stores: users who have read it. Targeted: user/store pairs that have read it at a recipient store.',
    )
    recipient_count = fields.Integer(
        string='Recipients', compute='_compute_read_stats',
        help='All stores: users holding a valid membership. Targeted: user/store pairs at the recipient stores.',
    )
    unread_count = fields.Integer(
        string='Unread', compute='_compute_read_stats',
        help='Zero once the notification has expired.',
    )
    active = fields.Boolean(string='Active', default=True)

    _uniq_code = models.Constraint(
        'unique(code)',
        'The notification code must be unique.',
    )
    _published_date_required = models.Constraint(
        "CHECK (state != 'published' OR published_date IS NOT NULL)",
        'A sent notification must have a sent date.',
    )
    _expired_after_published = models.Constraint(
        'CHECK (expired_date IS NULL OR published_date IS NULL'
        ' OR expired_date >= published_date)',
        'The expiry date cannot be earlier than the sent date.',
    )

    # -----------------------------------------------------------------
    # Compute
    # -----------------------------------------------------------------
    @api.depends('expired_date')
    def _compute_is_expired(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.is_expired = bool(rec.expired_date and rec.expired_date < now)

    @api.depends('priority')
    @api.depends_context('lang')
    def _compute_priority_label(self):
        for rec in self:
            rec.priority_label = dict(
                rec._fields['priority']._description_selection(rec.env)
            ).get(rec.priority, '')

    @api.depends('active', 'state', 'portal_visible')
    def _compute_is_published_portal(self):
        for rec in self:
            rec.is_published_portal = bool(
                rec.active and rec.state == 'published' and rec.portal_visible
            )

    @api.depends('target_mode', 'target_status', 'target_area_ids', 'target_state_ids',
                 'target_exclude_franchise_ids', 'franchise_ids')
    def _compute_target_preview_count(self):
        Franchise = self.env['wujia.franchise.management'].sudo()
        total = None
        for rec in self:
            if rec.target_mode == 'manual':
                rec.target_preview_count = len(rec.franchise_ids)
            elif rec.target_mode == 'filter':
                rec.target_preview_count = Franchise.search_count(rec._target_domain())
            else:
                # Broadcast: mọi cửa hàng đều thấy, kể cả không active — đếm 1 lần cho recordset.
                if total is None:
                    total = Franchise.search_count([])
                rec.target_preview_count = total

    def _compute_read_stats(self):
        """Spec F §15 + WJ-NOTI-001. Perf 1500 user: 2 query cho CẢ recordset.

        Cùng phạm vi dấu đọc với portal: toàn hệ đếm theo USER (người nhận = user còn membership
        hợp lệ, không trùng; đã đọc = dấu franchise NULL); chỉ định đếm cặp (user, cửa hàng nhận).
        Dòng lệch phạm vi không được tính."""
        reads = {}
        noti_ids = [nid for nid in self._origin.ids if nid]
        if noti_ids:
            for noti, franchise, count in self.env['wujia.notification.read'].sudo()._read_group(
                [('notification_id', 'in', noti_ids)],
                groupby=['notification_id', 'franchise_id'], aggregates=['__count'],
            ):
                reads.setdefault(noti.id, {})[franchise.id] = count
        pairs = self.env['wujia.franchise.member'].sudo()._read_group(
            [('is_currently_valid', '=', True)], groupby=['franchise_id', 'user_id'],
        )
        per_franchise = {}
        for franchise, _user in pairs:
            per_franchise[franchise.id] = per_franchise.get(franchise.id, 0) + 1
        total_users = len({user.id for _franchise, user in pairs})
        for rec in self:
            noti_reads = reads.get(rec._origin.id, {})
            fids = rec.franchise_ids.ids
            if fids:
                rec.recipient_count = sum(per_franchise.get(fid, 0) for fid in fids)
                rec.read_count = sum(noti_reads.get(fid, 0) for fid in fids)
            else:
                rec.recipient_count = total_users
                rec.read_count = noti_reads.get(False, 0)
            rec.unread_count = 0 if rec.is_expired else max(
                rec.recipient_count - rec.read_count, 0
            )

    # -----------------------------------------------------------------
    # Create / write / unlink
    # -----------------------------------------------------------------
    @api.onchange('target_mode')
    def _onchange_target_mode(self):
        # Đổi sang "Tất cả" thì bỏ hết cửa hàng đã chọn — tránh gửi nhầm phạm vi hẹp.
        if self.target_mode == 'all':
            self.franchise_ids = [fields.Command.clear()]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('target_mode') == 'all':
                vals['franchise_ids'] = [fields.Command.clear()]
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'wujia.notification'
                )
            if vals.get('state') == 'published':
                vals.setdefault('published_date', fields.Datetime.now())
                vals.setdefault('published_by_id', self.env.user.id)
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('target_mode') == 'all':
            vals.setdefault('franchise_ids', [fields.Command.clear()])
        new_state = vals.get('state')
        if new_state:
            states = dict(self._fields['state']._description_selection(self.env))
            for rec in self:
                if rec.state != new_state and new_state not in STATE_TRANSITIONS[rec.state]:
                    raise UserError(_(
                        'Cannot move notification "%(name)s" from "%(old)s" to "%(new)s".',
                        name=rec.name,
                        old=states[rec.state],
                        new=states[new_state],
                    ))
            if new_state == 'published':
                vals.setdefault('published_date', fields.Datetime.now())
                vals.setdefault('published_by_id', self.env.user.id)
        return super().write(vals)

    def unlink(self):
        # Spec F §17.2 — không xoá vật lý bản đã gửi, dùng Lưu trữ / bỏ active.
        blocked = self.filtered(lambda r: r.state != 'draft')
        if blocked:
            raise UserError(_(
                'Cannot delete sent notifications: %s. Use Archive instead.',
                ', '.join(blocked.mapped('name')),
            ))
        return super().unlink()

    @api.constrains('state', 'type_id')
    def _check_published_requirements(self):
        for rec in self:
            if rec.state == 'published' and not rec.type_id:
                raise ValidationError(self.env._(MSG_PUBLISH_VALIDATION))

    @api.constrains('target_mode', 'target_area_ids', 'target_state_ids',
                    'target_exclude_franchise_ids', 'franchise_ids')
    def _check_target(self):
        for rec in self:
            if rec.target_mode == 'filter' and not (
                rec.target_area_ids or rec.target_state_ids
                or rec.target_exclude_franchise_ids
            ):
                # Tiêu chí rỗng khớp toàn bộ cửa hàng — trùng ý nghĩa "Tất cả", chặn cho rõ ràng.
                raise ValidationError(self.env._(MSG_TARGET_NO_CRITERIA))
            if rec.target_mode == 'all' and rec.franchise_ids:
                raise ValidationError(self.env._(MSG_TARGET_ALL_HAS_STORES))

    # -----------------------------------------------------------------
    # Actions (backend HQ)
    # -----------------------------------------------------------------
    def action_publish(self):
        """Spec F §9 — validate rồi mới gửi. Fail → message nghiệp vụ §18."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft notifications can be sent.'))
            if not (rec.name and rec._has_content() and rec.priority):
                raise UserError(self.env._(MSG_PUBLISH_VALIDATION))
            if not rec.type_id or not rec.type_id.active:
                raise UserError(self.env._(MSG_PUBLISH_VALIDATION))
            now = fields.Datetime.now()
            if rec.expired_date and rec.expired_date < now:
                raise UserError(self.env._(MSG_PUBLISH_VALIDATION))
            vals = {
                'state': 'published',
                'published_date': now,
                'published_by_id': self.env.user.id,
            }
            # Chốt danh sách nhận tại thời điểm gửi (ghi chú cột L dòng 745): cửa hàng mở
            # sau ngày gửi KHÔNG nhận thông báo cũ; HQ dùng action_refresh_recipients nếu muốn.
            if rec.target_mode == 'filter':
                franchises = rec._resolve_target_franchises()
                if not franchises:
                    raise UserError(self.env._(MSG_TARGET_EMPTY))
                vals['franchise_ids'] = [fields.Command.set(franchises.ids)]
            elif rec.target_mode == 'manual' and not rec.franchise_ids:
                raise UserError(self.env._(MSG_TARGET_MANUAL_EMPTY))
            rec.write(vals)
        return True

    def action_preview_recipients(self):
        """Xem trước cửa hàng sẽ nhận — HQ kiểm tra trước khi gửi, không phải tick từng tiệm."""
        self.ensure_one()
        if self.target_mode == 'all':
            domain = []
        elif self.target_mode == 'filter':
            domain = self._target_domain()
        else:
            domain = [('id', 'in', self.franchise_ids.ids)]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Recipient stores'),
            'res_model': 'wujia.franchise.management',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {'create': False},
        }

    def action_refresh_recipients(self):
        """Chốt lại danh sách nhận theo tiêu chí hiện tại — dùng khi có cửa hàng mới mở."""
        for rec in self:
            if rec.target_mode != 'filter':
                raise UserError(_(
                    'Only notifications sent "By criteria" can refresh their recipient list.'
                ))
            franchises = rec._resolve_target_franchises()
            if not franchises:
                raise UserError(self.env._(MSG_TARGET_EMPTY))
            rec.franchise_ids = [fields.Command.set(franchises.ids)]
        return True

    def action_archive_notification(self):
        """Lưu trữ — ẩn khỏi portal, giữ lịch sử. Không xoá dữ liệu đọc."""
        for rec in self:
            if rec.state == 'archived':
                continue
            rec.state = 'archived'
        return True

    def action_view_read_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Read status'),
            'res_model': 'wujia.notification.read',
            'view_mode': 'list,form',
            'domain': [('notification_id', '=', self.id)],
            'context': {'create': False},
        }

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------
    def _target_domain(self):
        """Tiêu chí → domain trên wujia.franchise.management. OR trong nhóm, AND giữa nhóm."""
        self.ensure_one()
        domain = []
        if self.target_status == 'active':
            domain.append(('status', '=', 'active'))
        if self.target_area_ids:
            domain.append(('area_id', 'in', self.target_area_ids.ids))
        if self.target_state_ids:
            domain.append(('state_id', 'in', self.target_state_ids.ids))
        if self.target_exclude_franchise_ids:
            domain.append(('id', 'not in', self.target_exclude_franchise_ids.ids))
        return domain

    def _resolve_target_franchises(self):
        """Dịch tiêu chí thành danh sách cửa hàng thật. Mode khác `filter` giữ nguyên lựa chọn."""
        self.ensure_one()
        if self.target_mode != 'filter':
            return self.franchise_ids
        return self.env['wujia.franchise.management'].sudo().search(self._target_domain())

    def _has_content(self):
        self.ensure_one()
        return bool(self._html_to_text(self.content))

    @staticmethod
    def _html_to_text(html):
        text = re.sub(r'<[^>]+>', ' ', html or '')
        return re.sub(r'\s+', ' ', unescape(text)).strip()

    # -----------------------------------------------------------------
    # Portal — luật dùng chung cho mọi kênh. Gọi trên recordset sudo.
    # -----------------------------------------------------------------
    @api.model
    def _portal_history_domain(self, franchise_ids):
        """Lịch sử: mọi thông báo đã phát hành đúng đối tượng (gồm cả đã hết hiệu lực).
        Broadcast (franchise_ids trống) HOẶC target đúng cửa hàng đang thao tác."""
        ids = list(franchise_ids) if franchise_ids else [-1]
        return [
            ('is_published_portal', '=', True),
            '|', ('franchise_ids', '=', False), ('franchise_ids', 'in', ids),
            ('published_date', '<=', fields.Datetime.now()),
        ]

    @api.model
    def _portal_effective_domain(self, franchise_ids):
        """Còn hiệu lực: đã phát hành + chưa hết hạn — dùng cho popup, badge, đếm chưa đọc, Home."""
        return self._portal_history_domain(franchise_ids) + [
            '|', ('expired_date', '=', False), ('expired_date', '>=', fields.Datetime.now()),
        ]

    # Phạm vi dấu đọc (WJ-NOTI-001, BA 02/10/2026):
    #   toàn hệ (franchise_ids rỗng) ⇒ dấu theo user, franchise_id NULL, hiệu lực mọi cửa hàng;
    #   chỉ định ⇒ dấu theo user + đúng cửa hàng đang chọn.
    # Hai nhánh xét theo CHÍNH thông báo, nên dòng lệch phạm vi (dòng NULL của bài chỉ định,
    # dòng mang cửa hàng của bài toàn hệ) không bao giờ được tính là đã đọc.
    @api.model
    def _portal_read_scope(self, user, franchise_id):
        """(dấu đọc của bài toàn hệ, dấu đọc của bài chỉ định) — domain trên wujia.notification.read."""
        return (
            [('user_id', '=', user.id), ('franchise_id', '=', False)],
            [('user_id', '=', user.id), ('franchise_id', 'in', [franchise_id] if franchise_id else [])],
        )

    @api.model
    def _portal_read_domain(self, user, franchise_id):
        """Thông báo user ĐÃ đọc trong phạm vi cửa hàng đang chọn (domain trên wujia.notification)."""
        broadcast, targeted = self._portal_read_scope(user, franchise_id)
        return [
            '|',
            '&', ('franchise_ids', '=', False), ('read_ids', 'any', broadcast),
            '&', ('franchise_ids', '!=', False), ('read_ids', 'any', targeted),
        ]

    @api.model
    def _portal_unread_domain(self, user, franchise_ids, franchise_id):
        """MỘT luật chưa đọc cho Home, badge chuông, hộp chuông, lọc "Chưa đọc", "Đánh dấu tất cả":
        còn hiệu lực (đã phát hành, tới giờ, đúng đối tượng, chưa hết hạn) và chưa có dấu đúng phạm vi."""
        broadcast, targeted = self._portal_read_scope(user, franchise_id)
        return self._portal_effective_domain(franchise_ids) + [
            '|',
            '&', ('franchise_ids', '=', False), ('read_ids', 'not any', broadcast),
            '&', ('franchise_ids', '!=', False), ('read_ids', 'not any', targeted),
        ]

    @api.model
    def _portal_read_ids(self, user, notification_ids, franchise_id):
        """1 query — id thông báo (trong `notification_ids`) user đã đọc theo phạm vi trên."""
        if not notification_ids:
            return set()
        return set(self.search(
            [('id', 'in', list(notification_ids))] + self._portal_read_domain(user, franchise_id)
        ).ids)

    @api.model
    def _portal_unread_count(self, user, franchise_ids, franchise_id):
        """Số thông báo chưa đọc — 1 câu đếm (NOT EXISTS), không nạp id ra Python:
        badge chạy trên mọi trang portal, 1500 user."""
        return self.search_count(self._portal_unread_domain(user, franchise_ids, franchise_id))

    def _portal_get_attachment(self, attachment_id):
        """File đính kèm chỉ khi thuộc đúng thông báo này (đóng IDOR /web/content)."""
        self.ensure_one()
        return self.env['ir.attachment'].search([
            ('id', '=', attachment_id), ('id', 'in', self.attachment_ids.ids)], limit=1)

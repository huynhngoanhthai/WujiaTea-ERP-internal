from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


PRIORITIES = [
    ('normal', 'Normal'),
    ('urgent', 'Urgent'),
]

STATES = [
    ('new', 'New'),
    ('in_progress', 'In progress'),
    ('waiting_customer', 'Waiting customer'),
    ('resolved', 'Resolved'),
    ('closed', 'Closed'),
    ('cancelled', 'Cancelled'),
]

ROLES = [
    ('owner', 'Owner'),
    ('manager', 'Manager'),
    ('staff', 'Staff'),
]

LAST_RESPONSE_BY = [
    ('customer', 'Customer'),
    ('hq', 'HQ'),
    ('system', 'System'),
]


class WujiaSupportTicket(models.Model):
    """Support request from a franchise store — backend + portal.

    Uses mail.thread for chatter; analytics fields (last_message_date,
    need_customer_reply, …) maintained via message_post() override
    rather than a parallel franchise.support.ticket.message model
    (see ADR-016 in sprint log)."""

    _name = 'wujia.support.ticket'
    _description = 'Wujia Support Ticket'
    _order = 'create_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'title'

    # -----------------------------------------------------------------
    # Identity
    # -----------------------------------------------------------------
    name = fields.Char(string='Ticket code', readonly=True, copy=False, default='/')
    title = fields.Char(string='Title', required=True, tracking=True)
    description = fields.Html(string='Description', sanitize=True)

    # -----------------------------------------------------------------
    # Origin (store / user / role snapshot)
    # -----------------------------------------------------------------
    franchise_id = fields.Many2one(
        'wujia.franchise.management', string='Franchise',
        required=True, index=True, ondelete='restrict', tracking=True,
    )
    store_partner_id = fields.Many2one(
        'res.partner', string='Store partner',
        related='franchise_id.partner_id', store=True, index=True,
        help='Used for domain filtering linked sale orders / pickings.',
    )
    created_by_id = fields.Many2one(
        'res.users', string='Created by',
        default=lambda self: self.env.user, required=True, index=True,
    )
    created_by_role = fields.Selection(
        ROLES, string='Created by role',
        compute='_compute_created_by_role', store=True, readonly=True,
        help='Snapshot of franchise member role at creation time.',
    )

    # -----------------------------------------------------------------
    # Classification
    # -----------------------------------------------------------------
    category_id = fields.Many2one(
        'wujia.support.category', string='Category',
        required=True, index=True, ondelete='restrict', tracking=True,
    )
    priority = fields.Selection(
        PRIORITIES, string='Priority',
        default='normal', required=True, tracking=True,
    )
    state = fields.Selection(
        STATES, string='State',
        default='new', required=True, index=True, tracking=True, copy=False,
    )

    # -----------------------------------------------------------------
    # Related business records
    # -----------------------------------------------------------------
    sale_order_id = fields.Many2one(
        'sale.order', string='Related order',
        index=True,
        domain="[('partner_id', '=', store_partner_id)]",
    )
    picking_batch_id = fields.Many2one(
        'stock.picking.batch', string='Related delivery batch',
        index=True,
    )

    # -----------------------------------------------------------------
    # Assignment
    # -----------------------------------------------------------------
    assigned_user_id = fields.Many2one(
        'res.users', string='Assigned to',
        domain="[('share', '=', False)]",
        index=True, tracking=True,
    )
    assigned_team_id = fields.Many2one(
        'crm.team', string='Assigned team', tracking=True,
    )

    # -----------------------------------------------------------------
    # Analytics
    # -----------------------------------------------------------------
    last_message_date = fields.Datetime(
        string='Last message at', readonly=True, index=True, copy=False,
    )
    last_response_by = fields.Selection(
        LAST_RESPONSE_BY, string='Last response by', readonly=True, copy=False,
    )
    need_customer_reply = fields.Boolean(
        string='Need customer reply',
        readonly=True, index=True, copy=False,
        help='True when ticket is waiting_customer AND last response from HQ.',
    )
    message_count = fields.Integer(
        string='Messages', compute='_compute_message_count',
    )
    attachment_count = fields.Integer(
        string='Attachments', compute='_compute_attachment_count',
    )

    # -----------------------------------------------------------------
    # Dates
    # -----------------------------------------------------------------
    open_date = fields.Datetime(
        string='Open date', default=fields.Datetime.now,
        readonly=True, copy=False,
    )
    in_progress_date = fields.Datetime(string='In progress date', readonly=True, copy=False)
    resolved_date = fields.Datetime(string='Resolved date', readonly=True, copy=False)
    closed_date = fields.Datetime(string='Closed date', readonly=True, copy=False)

    # -----------------------------------------------------------------
    # Extra fields
    # -----------------------------------------------------------------
    cancel_reason = fields.Text(string='Cancel reason')
    internal_note = fields.Text(
        string='Internal note',
        help='HQ-only — not shown on portal.',
    )
    portal_visible = fields.Boolean(
        string='Visible on portal', default=True, index=True,
        help='Hide ticket from portal user even if they own it.',
    )
    active = fields.Boolean(string='Active', default=True)

    attachment_ids = fields.Many2many(
        'ir.attachment', 'wujia_support_ticket_attachment_rel',
        'ticket_id', 'attachment_id',
        string='Attachments (legacy)',
    )

    # -----------------------------------------------------------------
    # Compute
    # -----------------------------------------------------------------
    @api.depends('created_by_id', 'franchise_id')
    def _compute_created_by_role(self):
        Member = self.env['wujia.franchise.member'].sudo()
        for rec in self:
            if not rec.created_by_id or not rec.franchise_id:
                rec.created_by_role = False
                continue
            membership = Member.find_active_membership(
                rec.created_by_id.id, rec.franchise_id.id,
            )
            rec.created_by_role = membership.role if membership else False

    def _compute_message_count(self):
        # message_ids already prefetched via O2m from mail.thread.
        for rec in self:
            rec.message_count = len(rec.message_ids)

    def _compute_attachment_count(self):
        Attachment = self.env['ir.attachment'].sudo()
        groups = Attachment._read_group(
            [('res_model', '=', self._name), ('res_id', 'in', self.ids)],
            groupby=['res_id'], aggregates=['__count'],
        )
        mapping = {res_id: count for res_id, count in groups}
        for rec in self:
            rec.attachment_count = mapping.get(rec.id, 0) + len(rec.attachment_ids)

    # -----------------------------------------------------------------
    # Constraints
    # -----------------------------------------------------------------
    @api.constrains('state', 'cancel_reason')
    def _check_cancel_reason(self):
        for rec in self:
            if rec.state == 'cancelled' and not (rec.cancel_reason or '').strip():
                raise ValidationError(_(
                    "Ticket %s requires a cancel reason when state is 'cancelled'.",
                    rec.name or rec.title or '?',
                ))

    # -----------------------------------------------------------------
    # CRUD hooks
    # -----------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        Sequence = self.env['ir.sequence']
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = Sequence.next_by_code('wujia.support.ticket') or '/'
            vals.setdefault('open_date', fields.Datetime.now())
        return super().create(vals_list)

    def write(self, vals):
        # State transitions set timestamp fields atomically.
        if 'state' in vals:
            new_state = vals['state']
            now = fields.Datetime.now()
            if new_state == 'in_progress':
                vals.setdefault('in_progress_date', now)
            elif new_state == 'resolved':
                vals.setdefault('resolved_date', now)
            elif new_state == 'closed':
                vals.setdefault('closed_date', now)
        return super().write(vals)

    # -----------------------------------------------------------------
    # Messaging override — analytics atomic update.
    # -----------------------------------------------------------------
    def message_post(self, **kwargs):
        msg = super().message_post(**kwargs)
        if msg and msg.message_type == 'comment':
            self._update_response_analytics(msg)
        return msg

    def _update_response_analytics(self, msg):
        author = msg.author_id
        is_portal = bool(author.user_ids and author.user_ids[:1].share)
        vals = {'last_message_date': msg.date or fields.Datetime.now()}
        if is_portal:
            vals['last_response_by'] = 'customer'
            vals['need_customer_reply'] = False
        else:
            vals['last_response_by'] = 'hq'
            vals['need_customer_reply'] = self.state == 'waiting_customer'
        self.sudo().write(vals)

    # -----------------------------------------------------------------
    # Portal — luật dùng chung cho mọi kênh (ADR-027)
    # -----------------------------------------------------------------
    @api.model
    def _portal_scope_domain(self, user, franchise_ids):
        """Ticket do chính mình tạo, tại cửa hàng đang chọn, chưa bị HQ ẩn."""
        return [('created_by_id', '=', user.id), ('portal_visible', '=', True),
                ('franchise_id', 'in', list(franchise_ids) or [-1])]

    @api.model
    def create_from_portal(self, vals, franchise_ids, attach=None):
        """Kiểm → tạo → đính kèm (``attach(ticket)``) trong một savepoint.

        Trả ``(ticket, error)``; ``error`` là mã lỗi của form portal, ticket rỗng khi có lỗi.
        """
        if not vals.get('title') or not vals.get('franchise_id') or not vals.get('category_id'):
            return self.browse(), 'missing_fields'
        if vals['franchise_id'] not in franchise_ids:
            return self.browse(), 'invalid_franchise'
        category = self.env['wujia.support.category'].browse(vals['category_id']).exists()
        if not category.active:
            return self.browse(), 'invalid_input'
        vals = dict(vals)
        if vals.get('priority') not in dict(PRIORITIES):
            vals['priority'] = 'normal'
        with self.env.cr.savepoint() as sp:
            ticket = self.create(vals)
            try:
                if attach:
                    attach(ticket)
            except ValidationError:
                sp.close()
                return self.browse(), 'invalid_attachment'
        return ticket, None

    def _portal_reply(self, user, body):
        """Cửa hàng trả lời ticket; ``message_post`` cập nhật phân tích phản hồi."""
        self.ensure_one()
        body = (body or '').strip()
        if body:
            self.with_user(user).message_post(
                body=body, message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

    def _portal_messages(self):
        """Trao đổi cửa hàng được xem: bình luận, bỏ ghi chú nội bộ HQ (Log note)."""
        self.ensure_one()
        return self.message_ids.filtered(
            lambda m: m.message_type == 'comment'
            and not m.is_internal and not m.subtype_id.internal
        ).sorted('date')

    def _portal_attachments(self):
        """File cửa hàng được xem/tải: m2m cũ + file gắn res_model/res_id, trừ file của ghi chú nội bộ."""
        self.ensure_one()
        Attachment = self.env['ir.attachment'].sudo()
        linked = Attachment.search([('res_model', '=', self._name), ('res_id', '=', self.id)])
        public = self._portal_messages()
        internal = (self.message_ids - public).attachment_ids
        return (self.attachment_ids.sudo() | linked | public.attachment_ids.sudo()) - internal

    def _portal_get_attachment(self, att_id):
        """Attachment ``att_id`` nếu nằm trong ``_portal_attachments``, không thì rỗng."""
        self.ensure_one()
        return self._portal_attachments().filtered(lambda a: a.id == att_id)

    # -----------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------
    def action_set_in_progress(self):
        self.filtered(lambda t: t.state == 'new').write({'state': 'in_progress'})

    def action_set_waiting_customer(self):
        self.filtered(lambda t: t.state in ('new', 'in_progress')).write(
            {'state': 'waiting_customer'}
        )

    def action_set_resolved(self):
        self.filtered(
            lambda t: t.state in ('new', 'in_progress', 'waiting_customer')
        ).write({'state': 'resolved'})

    def action_set_closed(self):
        self.filtered(lambda t: t.state != 'closed').write({'state': 'closed'})

    def action_cancel(self):
        # Cancel reason set via wizard / dialog in view; constraint enforces.
        for rec in self.filtered(lambda t: t.state != 'cancelled'):
            if not (rec.cancel_reason or '').strip():
                raise ValidationError(_(
                    "Provide a cancel reason before cancelling ticket %s.",
                    rec.name or rec.title or '?',
                ))
            rec.state = 'cancelled'

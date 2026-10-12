from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_portal_order = fields.Boolean(
        string='Portal order',
        default=False,
        index=True,
        tracking=True,
        help='Marks an order created from the portal (as opposed to one created manually by admin).',
    )
    franchise_partner_id = fields.Many2one(
        'res.partner',
        string='Store partner',
        domain="[('is_franchise', '=', True)]",
        compute='_compute_franchise_partner_id',
        store=True,
        readonly=False,
        index=True,
        tracking=True,
        help='Partner representing the franchise store owning the order — required when is_portal_order=True.',
    )
    franchise_id = fields.Many2one(
        'wujia.franchise.management',
        string='Franchise store',
        compute='_compute_franchise_id',
        store=True,
        readonly=False,
        index=True,
        tracking=True,
        help='Store owning the order — required when is_portal_order=True. '
             'Derived from partner_id when the partner maps to exactly one store.',
    )
    portal_requester_user_id = fields.Many2one(
        'res.users',
        string='Created by (portal)',
        readonly=True,
        index=True,
        help='The portal user who pressed create. Set at creation time and never changed afterwards (audit trail).',
    )
    portal_member_id = fields.Many2one(
        'wujia.franchise.member',
        string='Ordering member',
        readonly=True,
        ondelete='restrict',
        help='Snapshot of the user × store membership at order creation time.',
    )
    area_id = fields.Many2one(
        'res.area',
        string='Area',
        related='franchise_id.area_id',
        store=True,
        readonly=True,
    )
    portal_delivery_street = fields.Char(string='Delivery address (portal)')
    portal_delivery_phone = fields.Char(string='Delivery phone (portal)')
    portal_note = fields.Text(string='Order note (portal)')

    is_return_order = fields.Boolean(
        string='Compensation orders',
        default=False,
        index=True,
        tracking=True,
        help='Marks an SO generated automatically by compensation/return management (Function K).',
    )

    # Weight aggregate
    total_planned_weight = fields.Float(
        string='Planned weight',
        compute='_compute_total_planned_weight',
        store=True,
        digits='Stock Weight',
        help="Total planned weight of the SO = sum(line.planned_weight). Early reference only, not the authoritative source for vehicle planning.",
    )

    batch_id = fields.Many2one(
        'stock.picking.batch',
        string='Delivery batch',
        compute='_compute_batch_id',
        store=True,
        index=True,
        help='Batch of the first non-cancelled delivery picking (id ASC). '
             'Auto-derived from picking_ids — null if SO has no picking yet.',
    )

    @api.depends('order_line.planned_weight')
    def _compute_total_planned_weight(self):
        for order in self:
            order.total_planned_weight = sum(order.order_line.mapped('planned_weight'))

    @api.depends('picking_ids.batch_id', 'picking_ids.state')
    def _compute_batch_id(self):
        # picking_ids đã prefetch sẵn qua O2m relation cache — sorted in-memory,
        # không gọi search() để tránh O(n) query khi compute trên list nhiều SO.
        for order in self:
            pickings = order.picking_ids.filtered(
                lambda p: p.state != 'cancel' and p.batch_id
            ).sorted('id')
            order.batch_id = pickings[:1].batch_id

    @api.constrains('is_portal_order', 'franchise_id', 'franchise_partner_id')
    def _check_portal_franchise_required(self):
        for order in self:
            if order.is_portal_order:
                if not order.franchise_id:
                    raise ValidationError(_(
                        "Portal order '%s' must have a franchise store (franchise_id).",
                        order.name or order.display_name,
                    ))
                if not order.franchise_partner_id:
                    raise ValidationError(_(
                        "Portal order '%s' must have a store partner (franchise_partner_id).",
                        order.name or order.display_name,
                    ))

    @api.constrains('portal_requester_user_id', 'franchise_id', 'portal_member_id')
    def _check_portal_franchise_membership(self):
        """Defense in depth: nếu có portal_requester_user_id thì user phải có
        membership active trong franchise_id (controller cũng đã check)."""
        Member = self.env['wujia.franchise.member'].sudo()
        for order in self:
            if not order.portal_requester_user_id:
                continue
            if not order.franchise_id:
                raise ValidationError(_(
                    "Order '%s' created from the portal must have a store (franchise_id).",
                    order.name or order.display_name,
                ))
            if order.portal_member_id:
                m = order.portal_member_id
                if (m.user_id != order.portal_requester_user_id
                        or m.franchise_id != order.franchise_id):
                    raise ValidationError(_(
                        "The member of order '%s' does not match the selected user/store.",
                        order.name or order.display_name,
                    ))
            else:
                membership = Member.find_active_membership(
                    order.portal_requester_user_id.id,
                    order.franchise_id.id,
                )
                if not membership:
                    raise ValidationError(_(
                        "User '%s' has no active membership in store '%s'.",
                        order.portal_requester_user_id.name,
                        order.franchise_id.display_name,
                    ))

    # ------------------------------------------------------------------
    # Franchise suy từ partner (WJ-FRANCHISE-001) — compute store để chạy cả ở
    # import/API, readonly=False cho phép admin chọn tay cửa hàng khác.
    # ------------------------------------------------------------------
    @api.depends('partner_id')
    def _compute_franchise_id(self):
        for order in self:
            # Partner không map / map nhiều: giữ nguyên giá trị đang có, không đoán.
            order.franchise_id = order.partner_id._wujia_unique_franchise() or order.franchise_id

    @api.depends('franchise_id')
    def _compute_franchise_partner_id(self):
        for order in self:
            order.franchise_partner_id = order.franchise_id.partner_id or order.franchise_partner_id

    @api.onchange('partner_id')
    def _onchange_partner_id_franchise_warning(self):
        return self.partner_id._wujia_multi_mapping_warning()

    def action_confirm(self):
        # WJ-FRANCHISE-002: chặn trước khi sinh picking/hoá đơn với franchise trống/lệch.
        for order in self:
            order.partner_id._wujia_assert_document_franchise(
                order.franchise_id, order.display_name,
            )
        return super().action_confirm()

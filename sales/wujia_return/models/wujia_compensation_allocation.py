from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class WujiaCompensationAllocation(models.Model):
    """Bản ghi phân bổ bù hàng — 1 request × 1 dòng SO bù (BA spec K).

    Persistent, hiển thị dưới dạng tab trong wujia.return.request (không menu
    riêng). Sprint K1 chỉ định nghĩa model; wizard tạo allocation + cập nhật
    delivered_qty từ picking = K2.
    """

    _name = 'wujia.compensation.allocation'
    _description = 'Wujia Compensation Allocation'
    _order = 'allocation_date desc, id desc'

    name = fields.Char(
        string='Allocation code', required=True, copy=False,
        readonly=True, default=lambda self: '/',
    )
    request_id = fields.Many2one(
        'wujia.return.request', string='Compensation request',
        required=True, ondelete='cascade', index=True,
    )
    franchise_id = fields.Many2one(
        'wujia.franchise.management', string='Store',
        related='request_id.franchise_id', store=True, readonly=True, index=True,
    )
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company, readonly=True, index=True,
    )
    sale_order_id = fields.Many2one(
        'sale.order', string='Compensation SO', readonly=True, ondelete='restrict', index=True,
    )
    sale_order_line_id = fields.Many2one(
        'sale.order.line', string='Compensation SO line', readonly=True, ondelete='restrict',
        index=True,
    )
    allocated_qty = fields.Float(
        string='Allocated qty', required=True, digits='Product Unit of Measure',
    )
    allocation_uom_id = fields.Many2one(
        'uom.uom', string='Allocation UoM', required=True,
    )
    delivered_qty = fields.Float(
        string='Delivered qty', default=0.0, digits='Product Unit of Measure',
    )
    released_qty = fields.Float(
        string='Returned qty', default=0.0, digits='Product Unit of Measure',
    )
    open_qty = fields.Float(
        string='Open qty', compute='_compute_open_qty', store=True,
        digits='Product Unit of Measure',
    )
    state = fields.Selection(
        [('allocated', 'Allocated'), ('partial', 'Partially delivered'),
         ('done', 'Delivered'), ('cancel', 'Voided')],
        string='Status', default='allocated', required=True,
    )
    allocation_date = fields.Datetime(
        string='Allocation date', default=fields.Datetime.now, readonly=True,
    )
    delivered_date = fields.Datetime(string='Delivery date', readonly=True)
    release_reason = fields.Text(string='Return reason')

    _check_allocated_positive = models.Constraint(
        'CHECK(allocated_qty > 0)',
        'Allocated qty must be greater than 0.',
    )
    _check_delivered_nonneg = models.Constraint(
        'CHECK(delivered_qty >= 0)',
        'Delivered qty cannot be negative.',
    )
    _check_released_nonneg = models.Constraint(
        'CHECK(released_qty >= 0)',
        'Returned qty cannot be negative.',
    )
    _check_delivered_released_le_allocated = models.Constraint(
        'CHECK(delivered_qty + released_qty <= allocated_qty)',
        'Delivered + returned cannot exceed the allocated qty.',
    )

    @api.depends('allocated_qty', 'delivered_qty', 'released_qty')
    def _compute_open_qty(self):
        for rec in self:
            rec.open_qty = rec.allocated_qty - rec.delivered_qty - rec.released_qty

    @api.constrains('allocated_qty', 'released_qty', 'request_id', 'state')
    def _check_not_over_approved(self):
        for rec in self.filtered(lambda a: a.state != 'cancel'):
            siblings = rec.request_id.allocation_ids.filtered(
                lambda a: a.state != 'cancel')
            total = sum(a.allocated_qty - a.released_qty for a in siblings)
            if total > rec.request_id.approved_qty + 1e-6:
                raise ValidationError(_(
                    "Total allocation of request '%s' exceeds the approved quantity.",
                    rec.request_id.name))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'wujia.compensation.allocation') or '/'
        return super().create(vals_list)

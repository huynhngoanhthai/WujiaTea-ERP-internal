from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    weight_per_unit = fields.Float(
        string='Weight per unit',
        digits='Stock Weight',
        readonly=True,
        copy=True,
        help="Snapshot of the weight of one product unit taken when the product is selected. Not user-editable; stored so historical data stays unchanged even if product.weight changes.",
    )
    planned_weight = fields.Float(
        string='Planned weight',
        compute='_compute_planned_weight',
        store=True,
        digits='Stock Weight',
        help='= product_uom_qty × weight_per_unit.',
    )

    wujia_is_gift = fields.Boolean(
        string='Is Gift',
        default=False,
        readonly=True,
        copy=False,
        help="Indicates whether this order line is a free gift product.",
    )

    @api.depends('product_uom_qty', 'weight_per_unit')
    def _compute_planned_weight(self):
        for line in self:
            line.planned_weight = (line.product_uom_qty or 0.0) * (line.weight_per_unit or 0.0)

    @api.depends('wujia_is_gift')
    def _compute_price_unit(self):
        super()._compute_price_unit()
        for line in self:
            if line.wujia_is_gift:
                line.price_unit = 0.0
                line.technical_price_unit = 0.0

    @api.depends('wujia_is_gift')
    def _compute_discount(self):
        super()._compute_discount()
        for line in self:
            if line.wujia_is_gift:
                line.discount = 0.0

    @api.onchange('product_id')
    def _onchange_product_id_snapshot_weight(self):
        if self.product_id:
            self.weight_per_unit = self.product_id.weight or 0.0

    @api.model_create_multi
    def create(self, vals_list):
        # Snapshot weight tại lúc create — cover cả flow API/import không qua onchange.
        for vals in vals_list:
            if vals.get('wujia_is_gift'):
                vals['price_unit'] = 0.0
                vals['technical_price_unit'] = 0.0
                vals['discount'] = 0.0
            if 'weight_per_unit' not in vals and vals.get('product_id'):
                product = self.env['product.product'].browse(vals['product_id'])
                vals['weight_per_unit'] = product.weight or 0.0
        return super().create(vals_list)

    def write(self, vals):
        if 'price_unit' in vals or 'discount' in vals:
            gift_lines = self.filtered('wujia_is_gift')
            if gift_lines:
                if len(gift_lines) == len(self):
                    vals = dict(vals, price_unit=0.0, technical_price_unit=0.0, discount=0.0)
                else:
                    non_gift = self - gift_lines
                    res1 = super(SaleOrderLine, non_gift).write(vals)
                    gift_vals = dict(vals, price_unit=0.0, technical_price_unit=0.0, discount=0.0)
                    res2 = super(SaleOrderLine, gift_lines).write(gift_vals)
                    return res1 and res2
        return super().write(vals)

    @api.constrains('product_id', 'product_uom_qty', 'order_id')
    def _check_min_max_qty_portal(self):
        """Luật min/bước/max của đơn portal — cùng nguồn `product._portal_qty_error`."""
        for line in self:
            if not line.order_id.is_portal_order or line.wujia_is_gift:
                continue
            product = line.product_id
            qty = line.product_uom_qty
            error = product._portal_qty_error(qty)
            if error and error[0] == 'MIN_QTY_NOT_CONFIGURED':
                error = ('QTY_ABOVE_MAX', product.max_qty) if 0 < product.max_qty < qty else None
            if not error:
                continue
            code, limit = error
            if code == 'QTY_BELOW_MIN':
                raise ValidationError(_(
                    "Product '%s' requires a minimum quantity of %s, ordered %s.",
                    product.name, limit, qty,
                ))
            if code == 'QTY_INVALID_STEP':
                raise ValidationError(_(
                    "The quantity of '%s' must be in steps of %s, ordered %s.",
                    product.name, limit, qty,
                ))
            raise ValidationError(_(
                "Product '%s' allows at most %s per order, ordered %s.",
                product.name, limit, qty,
            ))

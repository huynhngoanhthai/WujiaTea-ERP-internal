from odoo import _, api, fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    weight_per_unit = fields.Float(
        string='Weight per unit',
        digits='Stock Weight',
        readonly=True,
        help="Snapshot of weight_per_unit from sale.order.line when the move comes from an SO; falls back to product_id.weight for moves without an SO line.",
    )
    planned_weight = fields.Float(
        string='Planned weight',
        compute='_compute_planned_weight',
        store=True,
        digits='Stock Weight',
    )
    done_weight = fields.Float(
        string='Delivered weight',
        compute='_compute_done_weight',
        store=True,
        digits='Stock Weight',
        help='= quantity (delivered) × weight_per_unit. Odoo 19 uses the `quantity` field.',
    )

    @api.depends('product_uom_qty', 'weight_per_unit')
    def _compute_planned_weight(self):
        for move in self:
            move.planned_weight = (move.product_uom_qty or 0.0) * (move.weight_per_unit or 0.0)

    @api.depends('quantity', 'weight_per_unit')
    def _compute_done_weight(self):
        for move in self:
            move.done_weight = (move.quantity or 0.0) * (move.weight_per_unit or 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        # Snapshot weight_per_unit khi tạo move:
        # - Nếu có sale_line_id → lấy từ line.weight_per_unit.
        # - Nếu không → fallback product.weight.
        for vals in vals_list:
            if 'weight_per_unit' in vals:
                continue
            sale_line_id = vals.get('sale_line_id')
            if sale_line_id:
                line = self.env['sale.order.line'].browse(sale_line_id)
                vals['weight_per_unit'] = line.weight_per_unit or (
                    line.product_id.weight if line.product_id else 0.0
                )
            elif vals.get('product_id'):
                product = self.env['product.product'].browse(vals['product_id'])
                vals['weight_per_unit'] = product.weight or 0.0
        return super().create(vals_list)

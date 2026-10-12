from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductProduct(models.Model):
    """Cấu hình bù hàng ở mức sản phẩm (BA spec K — product.product extend).

    Dùng khi HQ duyệt yêu cầu bù: snapshot policy + ĐVT quyền lợi/giao bù vào
    request. compensation_unit_qty (hệ số quy đổi) nhập tại thời điểm duyệt.
    """

    _inherit = 'product.product'

    compensation_enabled = fields.Boolean(
        string='Compensation enabled',
        default=False,
        help='Allow this product to be compensated (creates a zero-value SO).',
    )
    compensation_policy = fields.Selection(
        [('exact', 'Exact quantity'),
         ('accumulate', 'Whole-pack accumulation')],
        string='Compensation policy',
        default='exact',
        help="exact: compensate exactly the missing quantity; accumulate: build up until a full delivery unit is reached (the remainder carries over to the next period).",
    )
    compensation_claim_uom_id = fields.Many2one(
        'uom.uom',
        string='Entitlement UoM',
        help='Unit in which the compensation entitlement is recorded (e.g. kg, stick).',
    )
    compensation_product_id = fields.Many2one(
        'product.product',
        string='Compensation product',
        help='Product actually put on the compensation SO. Leave empty to use this product.',
    )
    compensation_delivery_uom_id = fields.Many2one(
        'uom.uom',
        string='Compensation delivery UoM',
        help='Unit actually used on the compensation SO (e.g. bag, carton, stick).',
    )
    compensation_unit_qty = fields.Float(
        string='Entitlement qty per delivery unit',
        digits='Product Unit of Measure',
        help="Entitlement quantity for one compensation delivery unit (e.g. 1 bag = 10 kg). Used as the default suggestion when HQ approves a request.",
    )

    @api.constrains('compensation_enabled', 'compensation_policy',
                    'compensation_claim_uom_id', 'compensation_delivery_uom_id',
                    'compensation_unit_qty')
    def _check_compensation_config(self):
        for product in self:
            if not product.compensation_enabled:
                continue
            if not product.compensation_claim_uom_id:
                raise ValidationError(_(
                    "Product '%s' has compensation enabled and must have an entitlement UoM.",
                    product.display_name,
                ))
            if product.compensation_policy == 'accumulate':
                if not product.compensation_delivery_uom_id:
                    raise ValidationError(_(
                        "Product '%s' uses the accumulation policy and must have a compensation delivery UoM.",
                        product.display_name,
                    ))
                if product.compensation_unit_qty <= 0:
                    raise ValidationError(_(
                        "Product '%s' uses the accumulation policy and must have an entitlement qty per delivery unit > 0.",
                        product.display_name,
                    ))

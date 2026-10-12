from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductProduct(models.Model):
    _inherit = 'product.product'

    is_public_portal = fields.Boolean(
        string='Show on portal',
        default=False,
        index=True,
        help="Turn on to publish the product on the ordering portal (/portal/order). A published product must have a portal category and a minimum quantity > 0.",
    )
    min_qty = fields.Integer(
        string='Minimum quantity',
        default=0,
        help='Minimum order quantity. The portal steps up/down by this value.',
    )
    max_qty = fields.Integer(
        string='Maximum quantity',
        default=0,
        help='0 = unlimited. If > 0 it must be >= min and a multiple of min.',
    )
    # Đặt tiền tố wujia_: tên `description_ecommerce` trùng field Html dịch được của
    # website_sale trên product.template, đụng độ làm cột đổi sang jsonb (WJ-PROD-001).
    wujia_packaging = fields.Char(
        string='Packaging',
        help='Packaging shown on the portal, e.g. 10kg/bag, 120 pcs/carton.',
    )
    name_chinese = fields.Char(
        string='Chinese name',
        help='Displayed under the product name on the portal. Entered manually, never auto-translated.',
    )
    public_categ_id = fields.Many2one(
        'wujia.product.category',
        string='Portal category',
        index=True,
        ondelete='set null',
    )

    @api.model
    def _portal_orderable_domain(self):
        return [('is_public_portal', '=', True), ('active', '=', True),
                ('public_categ_id.active', '=', True)]

    def _portal_is_orderable(self):
        self.ensure_one()
        return bool(self.active and self.is_public_portal and self.public_categ_id.active)

    def _portal_qty_error(self, qty):
        """Luật đặt hàng portal (bước = min_qty, max 0 = không giới hạn) → None hoặc (mã, ngưỡng)."""
        self.ensure_one()
        step = self.min_qty
        if step <= 0:
            return 'MIN_QTY_NOT_CONFIGURED', 0
        if qty < step:
            return 'QTY_BELOW_MIN', step
        if qty % step:
            return 'QTY_INVALID_STEP', step
        if self.max_qty and qty > self.max_qty:
            return 'QTY_ABOVE_MAX', self.max_qty
        return None

    @api.constrains('is_public_portal', 'public_categ_id')
    def _check_portal_category(self):
        for product in self:
            if product.is_public_portal and not product.public_categ_id:
                raise ValidationError(_(
                    "Portal product '%s' must have a portal category before it can be published.",
                    product.display_name,
                ))

    @api.constrains('is_public_portal', 'min_qty', 'max_qty')
    def _check_portal_qty_rules(self):
        for product in self:
            if product.min_qty < 0 or product.max_qty < 0:
                raise ValidationError(_("Minimum/maximum quantity cannot be negative."))
            if product.is_public_portal and product.min_qty <= 0:
                raise ValidationError(_(
                    "Portal product '%s' must have a minimum quantity > 0 "
                    "(order step = minimum quantity).", product.display_name,
                ))
            if product.max_qty:
                if product.max_qty < product.min_qty:
                    raise ValidationError(_(
                        "Maximum quantity (%s) must be >= minimum quantity (%s).",
                        product.max_qty, product.min_qty,
                    ))
                if product.min_qty and product.max_qty % product.min_qty:
                    raise ValidationError(_(
                        "Maximum quantity (%s) must be a multiple of the minimum quantity (%s).",
                        product.max_qty, product.min_qty,
                    ))

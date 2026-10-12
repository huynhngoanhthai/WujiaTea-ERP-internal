from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class WujiaSaleOrderGiftWizard(models.TransientModel):
    _name = 'wujia.sale.order.gift.wizard'
    _description = "Add Bulk Gift Products to Sales Orders"

    product_id = fields.Many2one(
        'product.product',
        string="Gift Product",
        required=True,
        domain=[('sale_ok', '=', True), ('active', '=', True)],
        help="Select an active, saleable product to be gifted.",
    )
    quantity = fields.Float(
        string="Quantity",
        required=True,
        default=1.0,
        help="Quantity of the gift product to add to each sales order.",
    )
    uom_id = fields.Many2one(
        related='product_id.uom_id',
        string="Unit of Measure",
        readonly=True,
    )

    def action_apply_gift(self):
        self.ensure_one()
        if not self.env.user.has_group('sales_team.group_sale_manager'):
            raise AccessError(_("Only Sales Managers are allowed to add gift products in bulk."))

        if self.quantity <= 0.0:
            raise UserError(_("Quantity must be greater than zero."))

        if not self.product_id or not self.product_id.sale_ok or not self.product_id.active:
            raise UserError(_("Please select an active, saleable product."))

        active_ids = self.env.context.get('active_ids')
        if not active_ids:
            raise UserError(_("Please select at least one sales order."))

        orders = self.env['sale.order'].browse(active_ids).exists()
        if not orders:
            raise UserError(_("No sales orders found to process."))

        non_draft_orders = orders.filtered(lambda o: o.state != 'draft')
        if non_draft_orders:
            invalid_names = ", ".join(non_draft_orders.mapped('name'))
            raise UserError(_(
                "Selected list contains sales orders that are already confirmed or no longer in Draft status. Please select only Draft orders: %s",
                invalid_names,
            ))

        lines_to_create = []
        for order in orders:
            lines_to_create.append({
                'order_id': order.id,
                'product_id': self.product_id.id,
                'product_uom_qty': self.quantity,
                'product_uom_id': self.product_id.uom_id.id,
                'price_unit': 0.0,
                'technical_price_unit': 0.0,
                'discount': 0.0,
                'wujia_is_gift': True,
            })
        self.env['sale.order.line'].create(lines_to_create)

        body = _(
            "Added gift product: <b>%s</b> — Quantity: <b>%s %s</b> (Unit price: 0).",
            self.product_id.display_name,
            self.quantity,
            self.uom_id.name or '',
        )
        for order in orders:
            order.message_post(
                body=body,
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )

        return {'type': 'ir.actions.act_window_close'}

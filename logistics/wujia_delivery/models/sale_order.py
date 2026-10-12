from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _action_confirm(self):
        # Sau khi confirm, copy franchise_id từ SO xuống các picking sinh ra.
        # area_id của picking là related store từ franchise_id, nên không cần set tay.
        res = super()._action_confirm()
        for order in self:
            if not order.franchise_id:
                continue
            # SO là nguồn chân lý: picking nay tự suy franchise từ partner giao hàng nên
            # phải đè cả trường hợp lệch, không chỉ trường hợp trống.
            pickings_to_update = order.picking_ids.filtered(
                lambda p: p.franchise_id != order.franchise_id
            )
            if pickings_to_update:
                pickings_to_update.write({'franchise_id': order.franchise_id.id})
        return res

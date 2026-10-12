from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _prepare_invoice(self):
        """Propagate cửa hàng SO → hoá đơn (BA r1456: account.move.franchise_id lấy từ
        sale.order.franchise_id khi hoá đơn sinh từ đơn portal). Chỉ set thêm 1 key vào
        vals chuẩn, không đổi quy tắc hạch toán."""
        vals = super()._prepare_invoice()
        if self.franchise_id:
            vals['franchise_id'] = self.franchise_id.id
        return vals

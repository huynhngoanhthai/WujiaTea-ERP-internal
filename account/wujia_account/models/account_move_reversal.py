from odoo import models


class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    def _modify_default_reverse_values(self, origin_move):
        """WJ-DEBT-006 — nhánh "Đảo ngược và tạo hóa đơn": hoá đơn nháp mới sinh bằng
        copy_data() nên không đi qua _reverse_moves; gán cửa hàng của chứng từ gốc."""
        data = super()._modify_default_reverse_values(origin_move)
        if origin_move.franchise_id:
            data['franchise_id'] = origin_move.franchise_id.id
        return data

from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        info = super().session_info()
        # Tab trình duyệt backend khi chưa có action: tên thương hiệu thay "Odoo".
        info['wj_brand_name'] = self.env.company._wj_brand_info()['name']
        return info

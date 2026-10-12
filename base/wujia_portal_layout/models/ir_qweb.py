from odoo import models


class IrQweb(models.AbstractModel):
    _inherit = 'ir.qweb'

    def _prepare_environment(self, values):
        # `wj_brand` cho mọi template portal (tên, màu, cờ có ảnh): 1 lần/render, ormcache theo công ty.
        # Route portal không khai website=True ⇒ không đi nhánh _prepare_frontend_environment.
        if 'wj_brand' not in values:
            values['wj_brand'] = self.env.company._wj_brand_info()
        return super()._prepare_environment(values)

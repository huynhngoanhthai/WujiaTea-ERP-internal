from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    wj_brand_name = fields.Char(related='company_id.wj_brand_name', readonly=False)
    wj_primary_color = fields.Char(related='company_id.wj_primary_color', readonly=False)
    wj_logo = fields.Binary(related='company_id.logo', readonly=False)
    wj_logo_mobile = fields.Image(related='company_id.wj_logo_mobile', readonly=False)
    wj_favicon = fields.Image(related='company_id.wj_favicon', readonly=False)
    wj_login_background = fields.Image(related='company_id.wj_login_background', readonly=False)

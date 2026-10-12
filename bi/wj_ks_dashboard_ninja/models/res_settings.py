from odoo import fields, models


class ResConfig(models.TransientModel):
    _inherit = "res.config.settings"

    enable_chart_zoom = fields.Boolean(string="Enable Zooming for charts", store=True,
                             config_parameter='wj_ks_dashboard_ninja.enable_chart_zoom')

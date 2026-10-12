from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Chỉ admin (Settings) đọc/ghi được key; người dịch dùng qua wizard (sudo).
    wj_mt_provider = fields.Selection([('deepl', 'DeepL')], string='Machine translation provider', default='deepl',
                                      config_parameter='wujia_i18n.mt_provider')
    wj_deepl_api_key = fields.Char(string='DeepL API key', config_parameter='wujia_i18n.deepl_api_key',
                                   help='Free plan keys end with ":fx" (api-free.deepl.com); other keys use the Pro API.')

from odoo import models
from odoo.tools.sql import table_exists


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    def _update_translations(self, filter_lang=None, overwrite=False):
        # -u nạp lại .po (có thể đè bản sửa tay) ⇒ áp lại bản sửa tay của chính các module vừa nạp.
        res = super()._update_translations(filter_lang=filter_lang, overwrite=overwrite)
        if 'wujia.i18n.value' in self.env and table_exists(self.env.cr, 'wujia_i18n_value'):
            langs = filter_lang if isinstance(filter_lang, (list, tuple)) else ([filter_lang] if filter_lang else None)
            self.env['wujia.i18n.value']._wj_reapply_overrides(self.mapped('name'), langs)
        return res

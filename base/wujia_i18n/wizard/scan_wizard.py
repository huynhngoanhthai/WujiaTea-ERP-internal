from odoo import _, api, fields, models
from odoo.exceptions import UserError


class WujiaI18nScanWizard(models.TransientModel):
    _name = 'wujia.i18n.scan.wizard'
    _description = 'Scan translatable terms'

    module_ids = fields.Many2many(
        'ir.module.module', string='Modules', domain=[('state', '=', 'installed')],
        default=lambda self: self._default_modules(),
    )
    lang_ids = fields.Many2many(
        'res.lang', string='Languages', domain=[('active', '=', True), ('code', '!=', 'en_US')],
        default=lambda self: self.env['res.lang'].search([('code', '!=', 'en_US')]),
    )

    @api.model
    def _default_modules(self):
        Module = self.env['ir.module.module'].sudo()
        return Module.search([('state', '=', 'installed'), '|', ('name', '=like', 'wujia\\_%'), ('name', '=like', 'wj\\_%')])

    def action_scan(self):
        self.env['wujia.i18n.term'].check_access('create')
        if not self.module_ids or not self.lang_ids:
            raise UserError(_('Choose at least one module and one language.'))
        stats = self.env['wujia.i18n.term'].sudo()._wj_scan(self.module_ids.mapped('name'), self.lang_ids.mapped('code'))
        msg = _(
            '%(terms)s terms found (%(new_terms)s new, %(archived)s no longer found). '
            '%(new_values)s translations added, %(updated_values)s refreshed from modules. %(seconds)ss.',
            **stats,
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Scan finished'), 'message': msg, 'type': 'success', 'sticky': True,
                'next': self.env['ir.actions.act_window']._for_xml_id('wujia_i18n.action_wujia_i18n_value'),
            },
        }

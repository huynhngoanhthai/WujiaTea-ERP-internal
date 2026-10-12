import base64

from odoo import _, fields, models
from odoo.exceptions import UserError


class WujiaI18nTransferWizard(models.TransientModel):
    _name = 'wujia.i18n.transfer.wizard'
    _description = 'Import / export translations'

    mode = fields.Selection([('import', 'Import'), ('export', 'Export')], required=True, default='import')
    # Nhập
    file = fields.Binary(string='CSV file', attachment=False)
    filename = fields.Char()
    overwrite_edited = fields.Boolean(
        string='Overwrite edited translations',
        help='By default, translations edited in this tool are kept when the file has a different value.')
    src_mode = fields.Selection(
        [('missing', 'Only fill untranslated'), ('all', 'Update every match')],
        string='Rows without reference', required=True, default='missing',
        help='Rows with no "option" column (or whose reference is not found) are matched by source text in every module. '
             '"Only fill untranslated" leaves existing translations of those terms unchanged.')
    apply_now = fields.Boolean(string='Apply now', default=True,
                               help='Apply labels, menus and views immediately. Python/JavaScript strings need .po export + restart.')
    # Xuất
    export_format = fields.Selection([('csv', 'CSV glossary (key,option,VN,CN,TH)'), ('po_zip', 'Zip of .po + .pot per module')],
                                     string='Format', required=True, default='csv')
    module_ids = fields.Many2many(
        'ir.module.module', string='Modules', domain=[('state', '=', 'installed')],
        default=lambda self: self.env['wujia.i18n.scan.wizard']._default_modules(),
    )
    lang_ids = fields.Many2many(
        'res.lang', string='Languages', domain=[('active', '=', True), ('code', '!=', 'en_US')],
        default=lambda self: self.env['res.lang'].search([('code', '!=', 'en_US')]),
    )
    only_edited = fields.Boolean(string='Only edited terms')
    result_file = fields.Binary(readonly=True, attachment=False)
    result_filename = fields.Char(readonly=True)

    def action_import(self):
        self.ensure_one()
        if not self.file:
            raise UserError(_('Choose a CSV file.'))
        stats = self.env['wujia.i18n.transfer']._wj_import_csv(
            base64.b64decode(self.file), overwrite_edited=self.overwrite_edited, apply=self.apply_now,
            src_mode=self.src_mode)
        if not stats['languages']:
            raise UserError(_('No language column of the file is active (columns VN, CN, TH or language codes).'))
        msg = _(
            '%(rows)s rows: %(by_ref)s matched by reference, %(by_src)s by source text, %(unmatched)s not found. '
            '%(updated)s translations changed, %(unchanged)s already identical, %(kept)s existing ones kept.',
            rows=stats['rows'], by_ref=stats['matched_by_ref'], by_src=stats['matched_by_source'],
            unmatched=stats['unmatched'], updated=stats['updated'], unchanged=stats['unchanged'],
            kept=stats['kept_edited'] + stats['kept_translated'],
        )
        if stats['code_waiting_export']:
            msg += ' ' + _('%(n)s Python/JavaScript strings wait for .po export.', n=stats['code_waiting_export'])
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Import finished'), 'message': msg, 'type': 'success', 'sticky': True,
                'next': self.env['ir.actions.act_window']._for_xml_id('wujia_i18n.action_wujia_i18n_value'),
            },
        }

    def action_export(self):
        self.ensure_one()
        if not self.module_ids or not self.lang_ids:
            raise UserError(_('Choose at least one module and one language.'))
        Transfer = self.env['wujia.i18n.transfer']
        modules, langs = self.module_ids.mapped('name'), self.lang_ids.mapped('code')
        stamp = fields.Date.context_today(self).strftime('%Y%m%d')
        if self.export_format == 'csv':
            data, name = Transfer._wj_export_csv(modules, langs, self.only_edited), f'wujia_translations_{stamp}.csv'
        else:
            data, _notes = Transfer._wj_export_po_zip(modules, langs)
            name = f'wujia_i18n_po_{stamp}.zip'
        self.write({'result_file': base64.b64encode(data), 'result_filename': name})
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model={self._name}&id={self.id}&field=result_file'
                   f'&filename_field=result_filename&download=true',
            'target': 'self',
        }

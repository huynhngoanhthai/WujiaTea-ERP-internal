from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import TranslationImporter

from .i18n_term import DB_KINDS

STATES = [
    ('synced', 'From module'),
    ('override', 'Edited'),
    ('machine', 'Machine translated'),
    ('missing', 'Missing'),
]
# Bản đang dùng do tool đặt (người sửa / máy dịch): quét lại không làm mới, áp lại sau mỗi -u.
TOOL_STATES = ('override', 'machine')


class WujiaI18nValue(models.Model):
    _name = 'wujia.i18n.value'
    _description = 'Term translation'
    _order = 'module, term_id, lang'
    _rec_name = 'src'

    term_id = fields.Many2one('wujia.i18n.term', required=True, ondelete='cascade', index=True, readonly=True)
    lang = fields.Selection('_selection_lang', string='Language', required=True, readonly=True)
    value = fields.Text(string='Translation')
    state = fields.Selection(STATES, required=True, default='missing', readonly=True)
    pending = fields.Boolean(string='Waiting to apply', readonly=True,
                             help='Edited but not applied yet. Python/JavaScript strings: export .po, commit into the module, deploy, then restart.')
    module = fields.Char(related='term_id.module', store=True, index=True)
    kind = fields.Selection(related='term_id.kind', store=True)
    term_active = fields.Boolean(related='term_id.active', store=True, string='Term found')
    src = fields.Text(related='term_id.src', string='Source')
    name = fields.Char(related='term_id.name')
    res_id = fields.Char(related='term_id.res_id')
    mt_queued = fields.Boolean(string='In machine translation queue', readonly=True, index=True)
    mt_error = fields.Char(string='Machine translation error', readonly=True)

    _term_lang_uniq = models.Constraint('UNIQUE(term_id, lang)', 'One translation per term and language.')
    _lang_state_idx = models.Index('(lang, state)')

    @api.model
    def _selection_lang(self):
        return self.env['res.lang'].get_installed()

    def write(self, vals):
        # Người sửa tay ⇒ đánh dấu override + chờ áp dụng; lượt quét ghi qua context wj_i18n_scan.
        if 'value' in vals and not self.env.context.get('wj_i18n_scan'):
            vals = dict(vals, state='override' if vals['value'] else 'missing', pending=bool(vals['value']),
                        mt_queued=False, mt_error=False)
        return super().write(vals)

    def action_apply(self):
        self.check_access('write')
        todo = self.filtered(lambda v: v.state in TOOL_STATES and v.kind in DB_KINDS and v.value)
        todo._wj_apply()
        todo.with_context(wj_i18n_scan=True).write({'pending': False})
        skipped = len(self) - len(todo)
        msg = _('%(n)s translation(s) applied.', n=len(todo))
        if skipped:
            msg += ' ' + _('%(n)s skipped (code strings need .po export + restart, or nothing edited).', n=skipped)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'message': msg, 'type': 'success', 'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'}},
        }

    def action_mark_reviewed(self):
        """Duyệt bản dịch máy: giữ nguyên chữ, coi như người đã sửa (không bị dịch máy/nhập glossary đè)."""
        self.check_access('write')
        todo = self.filtered(lambda v: v.state == 'machine')
        todo.with_context(wj_i18n_scan=True).write({'state': 'override', 'mt_error': False})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'message': _('%(n)s machine translation(s) marked as reviewed.', n=len(todo)), 'type': 'success',
                       'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'}},
        }

    @api.model
    def action_apply_all_pending(self):
        return self.search([('pending', '=', True), ('kind', 'in', DB_KINDS)]).action_apply()

    @api.model
    def action_export_pending_code(self):
        """Mở wizard xuất .po cho các module có chuỗi Python/JS sửa tay đang chờ."""
        pending = self.search([('pending', '=', True), ('kind', 'not in', DB_KINDS)])
        if not pending:
            raise UserError(_('No Python/JavaScript string is waiting for export.'))
        modules = self.env['ir.module.module'].search([('name', 'in', list(set(pending.mapped('module'))))])
        langs = self.env['res.lang'].search([('code', 'in', list(set(pending.mapped('lang'))))])
        action = self.env['ir.actions.act_window']._for_xml_id('wujia_i18n.action_wujia_i18n_export_wizard')
        action['context'] = {
            'default_mode': 'export', 'default_export_format': 'po_zip',
            'default_module_ids': modules.ids, 'default_lang_ids': langs.ids,
        }
        return action

    def _wj_apply(self):
        """Ghi bản dịch vào DB bằng đúng đường Odoo import .po, ép ghi đè (kể cả bản ghi noupdate)."""
        if not self:
            return
        importer = TranslationImporter(self.env.cr, verbose=False)
        rows_by_lang = defaultdict(list)
        models_touched = set()
        for val in self:
            term = val.term_id
            imd_model = term.name.split(',')[0]
            module, imd_name = term.res_id.split('.', 1)
            models_touched.add(imd_model)
            rows_by_lang[val.lang].append({
                'type': term.kind, 'imd_model': imd_model, 'name': term.name, 'module': module,
                'imd_name': imd_name, 'src': term.src, 'value': val.value,
            })
        for lang, rows in rows_by_lang.items():
            importer._load(iter(rows), lang)
        importer.save(overwrite=True, force_overwrite=True)
        self.env.invalidate_all()
        # Nhãn field/selection nằm ở cache 'stable', view/QWeb ở 'templates', menu ở 'default'.
        caches = ['default']
        if 'ir.ui.view' in models_touched:
            caches.append('templates')
        if any(m.startswith('ir.model') for m in models_touched):
            caches.append('stable')
        self.env.registry.clear_cache(*caches)

    @api.model
    def _wj_reapply_overrides(self, module_names, langs=None):
        """Áp lại bản sửa tay + bản dịch máy sau khi module nạp .po (gọi từ ir.module.module._update_translations)."""
        domain = [('module', 'in', list(module_names)), ('state', 'in', TOOL_STATES),
                  ('kind', 'in', DB_KINDS), ('value', '!=', False)]
        if langs:
            domain.append(('lang', 'in', list(langs)))
        self.sudo().search(domain)._wj_apply()

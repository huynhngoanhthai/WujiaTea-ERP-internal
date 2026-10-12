from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.i18n_mt import PARAM_ERROR, PARAM_KEY
from ..tools import mt_deepl
from ..tools.po_writer import THAI_PREFIXES


class WujiaI18nMtWizard(models.TransientModel):
    _name = 'wujia.i18n.mt.wizard'
    _description = 'Machine translate'

    lang_id = fields.Many2one(
        'res.lang', string='Language', required=True, domain=[('code', '!=', 'en_US')],
        context={'active_test': False}, help='A language that is not active yet is enabled and scanned first.')
    lang_active = fields.Boolean(related='lang_id.active')
    module_ids = fields.Many2many(
        'ir.module.module', string='Modules', domain=[('state', '=', 'installed')],
        default=lambda self: self._default_modules(),
    )
    scope = fields.Selection(
        [('missing', 'Only untranslated'), ('refresh', 'Untranslated + translations from modules / machine')],
        required=True, default='missing',
        help='Translations edited by people are never replaced.')
    count = fields.Integer(string='Strings', compute='_compute_estimate')
    chars = fields.Integer(string='Characters', compute='_compute_estimate')
    queued = fields.Integer(string='Already in queue', compute='_compute_estimate')
    warning = fields.Text(compute='_compute_estimate')
    quota_info = fields.Char(string='DeepL quota', readonly=True)

    @api.model
    def _default_modules(self):
        modules = self.env['wujia.i18n.scan.wizard']._default_modules()
        return modules.filtered(lambda m: not m.name.startswith(THAI_PREFIXES))

    @api.depends('lang_id', 'module_ids', 'scope')
    def _compute_estimate(self):
        Value = self.env['wujia.i18n.value'].sudo()
        ICP = self.env['ir.config_parameter'].sudo()
        has_key = bool(ICP.get_param(PARAM_KEY))
        last_error = ICP.get_param(PARAM_ERROR)
        targets = Value._wj_mt_cached_targets()
        queued = Value.search_count([('mt_queued', '=', True)])
        for wiz in self:
            lines = []
            wiz.count = wiz.chars = 0
            wiz.queued = queued
            if not has_key:
                lines.append(_('No DeepL API key yet: an administrator enters it in Settings → Translation Tool.'))
            if last_error:
                lines.append(_('Last run stopped: %s', last_error))
            if wiz.lang_id and wiz.module_ids:
                code = wiz.lang_id.code
                if targets is not None and mt_deepl.deepl_target(code) not in targets:
                    lines.append(_('DeepL does not translate into %s.', wiz.lang_id.name))
                if not wiz.lang_id.active:
                    lines.append(_('%s is not active: it will be enabled and its strings scanned before translating.',
                                   wiz.lang_id.name))
                else:
                    values = Value.search(Value._wj_mt_domain(code, wiz.module_ids.mapped('name'), wiz.scope))
                    wiz.count = len(values)
                    wiz.chars = sum(len(src or '') for src in values.term_id.mapped('src'))
            wiz.warning = '\n'.join(lines)

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
            'view_mode': 'form', 'target': 'new', 'name': _('Machine translate'),
        }

    def action_check(self):
        """Hỏi DeepL: hạn mức còn lại + danh sách ngôn ngữ (lưu lại cho cảnh báo)."""
        self.ensure_one()
        Value = self.env['wujia.i18n.value'].sudo()
        client = Value._wj_mt_client()
        try:
            Value._wj_mt_capabilities(client, refresh=True)
            usage = client.usage()
        except mt_deepl.MTError as e:
            raise UserError(_('DeepL: %s', e)) from e
        left = max(usage['limit'] - usage['count'], 0)
        self.quota_info = _('%(used)s / %(limit)s characters used this period (%(left)s left, %(plan)s plan)',
                            used=f"{usage['count']:,}", limit=f"{usage['limit']:,}", left=f'{left:,}', plan=client.plan)
        return self._reopen()

    def action_translate(self):
        self.ensure_one()
        self.env['wujia.i18n.value'].check_access('write')
        if not self.module_ids:
            raise UserError(_('Choose at least one module.'))
        Value = self.env['wujia.i18n.value'].sudo()
        client = Value._wj_mt_client()
        try:
            caps = Value._wj_mt_capabilities(client)
        except mt_deepl.MTError as e:
            raise UserError(_('DeepL: %s', e)) from e
        lang = self.lang_id.code
        if mt_deepl.deepl_target(lang) not in caps['targets']:
            raise UserError(_('DeepL does not translate into %s.', self.lang_id.name))
        if not self.lang_id.active:
            self.env['res.lang'].sudo()._wj_enable_languages((lang,))
        modules = self.module_ids.mapped('name')
        # Quét trước để catalog có đủ chuỗi mới nhất của ngôn ngữ này (~3 s cho 29 module).
        self.env['wujia.i18n.term'].sudo()._wj_scan(modules, [lang])
        values = Value._wj_mt_enqueue(lang, modules, self.scope)
        if values:
            msg = _('%(n)s strings (%(chars)s characters) queued for %(lang)s. They are translated in the background; '
                    'labels, menus and views change as soon as each batch is done.',
                    n=len(values), chars=f"{sum(len(s) for s in values.mapped('src')):,}", lang=self.lang_id.name)
        else:
            msg = _('Nothing to translate for %s.', self.lang_id.name)
        action = self.env['ir.actions.act_window']._for_xml_id('wujia_i18n.action_wujia_i18n_value')
        action['context'] = {'search_default_mt_review': 1, 'search_default_current': 1}
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('Machine translation'), 'message': msg, 'type': 'success', 'sticky': True,
                       'next': action},
        }

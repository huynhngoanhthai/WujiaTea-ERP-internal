import hashlib
import json

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..tools.mt_deepl import deepl_glossary_lang


class WujiaI18nGlossary(models.Model):
    """Thuật ngữ cố định cho dịch máy: dịch đúng 1 cách (gửi kèm DeepL glossary) hoặc giữ nguyên (tên thương hiệu)."""
    _name = 'wujia.i18n.glossary'
    _description = 'Machine translation glossary'
    _order = 'src, lang'
    _rec_name = 'src'

    src = fields.Char(string='Term (English)', required=True)
    lang = fields.Selection('_selection_lang', string='Language', help='Empty = every language.')
    value = fields.Char(string='Translation')
    no_translate = fields.Boolean(string='Keep as is', help='Brand or product name: never translated.')
    note = fields.Char()

    _src_lang_uniq = models.Constraint('UNIQUE(src, lang)', 'This term already exists for this language.')

    @api.model
    def _selection_lang(self):
        return [(code, name) for code, name in self.env['res.lang'].get_installed() if code != 'en_US']

    @api.constrains('value', 'no_translate', 'src')
    def _check_value(self):
        for row in self:
            if not row.no_translate and not (row.value or '').strip():
                raise ValidationError(_('Term "%s": enter a translation or tick "Keep as is".', row.src))
            if any(c in (row.src or '') + (row.value or '') for c in '\t\n'):
                raise ValidationError(_('Term "%s": tabs and line breaks are not allowed.', row.src))

    @api.model
    def _wj_terms(self, lang):
        """→ (thuật ngữ giữ nguyên, {thuật ngữ: bản dịch}) cho `lang`; dòng riêng ngôn ngữ thắng dòng chung."""
        keep, mapping = set(), {}
        for row in self.sudo().search([('lang', 'in', (lang, False))]):
            src = row.src.strip()
            if row.no_translate:
                keep.add(src)
            elif row.value:
                if row.lang or src not in mapping:
                    mapping[src] = row.value.strip()
        return sorted(keep), mapping

    @api.model
    def _wj_deepl_glossary_id(self, client, lang, mapping):
        """Glossary DeepL EN → lang theo nội dung hiện tại; nội dung đổi ⇒ xoá bản cũ, tạo bản mới."""
        if not mapping:
            return None
        ICP = self.env['ir.config_parameter'].sudo()
        key = f'wujia_i18n.deepl_glossary.{lang}'
        digest = hashlib.md5(json.dumps(sorted(mapping.items())).encode()).hexdigest()[:12]
        old_digest, _sep, old_id = (ICP.get_param(key) or '').partition(':')
        if old_digest == digest and old_id:
            return old_id
        if old_id:
            client.delete_glossary(old_id)
        glossary_id = client.create_glossary(f'wujia_i18n {lang} {digest}', 'en', deepl_glossary_lang(lang), mapping)
        ICP.set_param(key, f'{digest}:{glossary_id}')
        return glossary_id

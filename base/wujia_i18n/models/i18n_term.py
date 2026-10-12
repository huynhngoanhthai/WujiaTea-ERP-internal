import hashlib
import logging
import time
from collections import defaultdict

from odoo import api, fields, models
from odoo.tools.translate import JAVASCRIPT_TRANSLATION_COMMENT, TranslationModuleReader

_logger = logging.getLogger(__name__)

KINDS = [
    ('model', 'Field value'),
    ('model_terms', 'View / template'),
    ('code_python', 'Python code'),
    ('code_js', 'JavaScript code'),
]
# Kind áp được ngay vào DB; chuỗi code chỉ đọc từ file .po (cần xuất + restart).
DB_KINDS = ('model', 'model_terms')


def term_key(kind, name, res_id, src):
    # Chuỗi code Odoo tra theo msgid trong module ⇒ khoá chỉ gồm src (số dòng đổi liên tục).
    parts = (kind, src) if kind not in DB_KINDS else (kind, name, res_id, src)
    return hashlib.md5('\x1f'.join(parts).encode()).hexdigest()


class WujiaI18nTerm(models.Model):
    _name = 'wujia.i18n.term'
    _description = 'Translatable term'
    _order = 'module, kind, id'
    _rec_name = 'src'

    module = fields.Char(required=True, index=True, readonly=True)
    kind = fields.Selection(KINDS, required=True, readonly=True)
    name = fields.Char(string='Reference', readonly=True,
                       help='Model,field (e.g. ir.ui.view,arch_db) or source file for code strings.')
    res_id = fields.Char(string='Record', readonly=True,
                         help='External ID of the record, or file:line for code strings.')
    src = fields.Text(string='Source', required=True, readonly=True)
    key_hash = fields.Char(required=True, readonly=True)
    active = fields.Boolean(default=True, readonly=True,
                            help='Archived when the term is no longer found by a scan (source text changed or removed).')
    value_ids = fields.One2many('wujia.i18n.value', 'term_id', string='Translations')

    _key_uniq = models.Constraint('UNIQUE(module, key_hash)', 'Term already exists in this module.')

    @api.model
    def _wj_scan(self, module_names, langs):
        """Quét chuỗi của các module cho các ngôn ngữ. Chỉ upsert; không đè bản sửa tay / dịch máy (override, machine)."""
        started = time.monotonic()
        self.env.flush_all()
        found = {}                        # (module, key) -> vals term
        found_values = defaultdict(dict)  # (module, key) -> {lang: value}
        for lang in langs:
            reader = TranslationModuleReader(self.env.cr, modules=list(module_names), lang=lang)
            for module, ttype, name, res_id, src, value, comments in reader:
                if ttype == 'code':
                    kind = 'code_js' if JAVASCRIPT_TRANSLATION_COMMENT in comments else 'code_python'
                    ref = f'{name}:{res_id}'
                else:
                    kind, ref = ttype, res_id
                key = term_key(kind, name, ref, src)
                found.setdefault((module, key), {
                    'module': module, 'kind': kind, 'name': name, 'res_id': ref, 'src': src, 'key_hash': key,
                })
                if value or lang not in found_values[(module, key)]:
                    found_values[(module, key)][lang] = value or ''

        Term = self.with_context(active_test=False)
        terms = {(t.module, t.key_hash): t for t in Term.search([('module', 'in', list(module_names))])}
        new_keys = [k for k in found if k not in terms]
        for term in Term.create([found[k] for k in new_keys]):
            terms[(term.module, term.key_hash)] = term
        gone = Term.browse([t.id for k, t in terms.items() if k not in found and t.active])
        back = Term.browse([t.id for k, t in terms.items() if k in found and not t.active])
        gone.write({'active': False})
        back.write({'active': True})

        Value = self.env['wujia.i18n.value'].with_context(wj_i18n_scan=True)
        term_ids = [terms[k].id for k in found]
        existing = {
            (v.term_id.id, v.lang): v
            for v in Value.search([('term_id', 'in', term_ids), ('lang', 'in', list(langs))])
        }
        to_create, updated = [], 0
        for k, per_lang in found_values.items():
            term_id = terms[k].id
            for lang in langs:
                db_value = per_lang.get(lang, '')
                state = 'synced' if db_value else 'missing'
                current = existing.get((term_id, lang))
                if not current:
                    to_create.append({'term_id': term_id, 'lang': lang, 'value': db_value, 'state': state})
                elif current.state not in ('override', 'machine') and (current.value or '') != db_value:
                    current.write({'value': db_value, 'state': state})
                    updated += 1
        Value.create(to_create)
        stats = {
            'terms': len(found), 'new_terms': len(new_keys), 'archived': len(gone), 'restored': len(back),
            'new_values': len(to_create), 'updated_values': updated,
            'seconds': round(time.monotonic() - started, 1),
        }
        _logger.info('wujia_i18n scan %s × %s: %s', sorted(module_names), list(langs), stats)
        return stats

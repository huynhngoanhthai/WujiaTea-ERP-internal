import io
import logging
import os
import time
import zipfile
from collections import defaultdict

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.modules.module import get_module_path
from odoo.tools.translate import TranslationModuleReader, trans_export

from ..tools import po_writer
from .i18n_term import DB_KINDS

_logger = logging.getLogger(__name__)

SAMPLE = 20
COUNTERS = ('matched_by_ref', 'matched_by_source', 'unmatched', 'unchanged', 'kept_edited', 'kept_translated',
            'updated', 'applied', 'code_waiting_export')


class WujiaI18nTransfer(models.AbstractModel):
    """Nhập/xuất bản dịch: dùng chung cho wizard backend và scripts/i18n_tool.py."""
    _name = 'wujia.i18n.transfer'
    _description = 'Translation import / export'

    @api.model
    def _wj_installed_langs(self):
        return [code for code, _name in self.env['res.lang'].get_installed()]

    # ------------------------------------------------------------------ import
    @api.model
    def _wj_import_csv(self, data, overwrite_edited=False, apply=True, src_mode='missing'):
        """Nạp glossary CSV vào catalog. Dòng có `option` khớp theo (ref, src), không thấy thì theo src.
        Bản dịch giống hiện tại ⇒ bỏ qua; khác ⇒ override + chờ áp dụng; bản đã sửa tay giữ nguyên trừ khi
        overwrite_edited. Dòng chỉ khớp theo src (không ref / ref cũ) mặc định chỉ điền chỗ chưa dịch: glossary chung
        không được đè bản vi_VN đã chốt riêng từng module (đo 07/10: 90 + 162 bản bị đổi nếu src_mode='all')."""
        Value = self.env['wujia.i18n.value']
        Value.check_access('write')
        Value.check_access('create')
        started = time.monotonic()
        try:
            rows = po_writer.read_glossary_rows(data)
        except (UnicodeDecodeError, ValueError) as e:
            raise UserError(_('Cannot read the CSV file: %s', e)) from e
        installed = set(self._wj_installed_langs())
        csv_langs = {lang for row in rows for lang in row['values']}
        langs = sorted(csv_langs & installed - {'en_US'})

        Term = self.env['wujia.i18n.term'].sudo()
        terms = Term.search_read([('src', 'in', list({r['key'] for r in rows}))], ['module', 'kind', 'name', 'res_id', 'src'])
        by_src, by_ref = defaultdict(list), {}
        for t in terms:
            by_src[t['src']].append(t)
            if t['kind'] in DB_KINDS:
                by_ref[(t['kind'], t['name'], t['res_id'], t['src'])] = t

        stats = dict.fromkeys(COUNTERS, 0)
        stats.update(rows=len(rows), languages=langs, skipped_languages=sorted(csv_langs - set(langs)))
        unmatched = []
        wanted = {}  # (term_id, lang) -> (value, exact)
        for row in rows:
            src, ref = row['key'], po_writer.parse_option(row['option'])
            matched, exact = [], False
            if ref:
                kind, name, res_id = ref
                if kind == 'code':
                    module = name.split('/')[1] if name.startswith('addons/') else None
                    matched = [t for t in by_src.get(src, ())
                               if t['kind'].startswith('code') and (not module or t['module'] == module)]
                else:
                    term = by_ref.get((kind, name, res_id, src))
                    matched = [term] if term else []
                exact = bool(matched)
            if not matched:
                matched = by_src.get(src, [])
            if not matched:
                stats['unmatched'] += 1
                if len(unmatched) < SAMPLE:
                    unmatched.append(src)
                continue
            stats['matched_by_ref' if exact else 'matched_by_source'] += 1
            for term in matched:
                for lang, value in row['values'].items():
                    if lang in langs:
                        prev = wanted.get((term['id'], lang))
                        # Dòng khớp đúng ref thắng dòng chỉ khớp theo src.
                        if not prev or (exact and not prev[1]):
                            wanted[(term['id'], lang)] = (value, exact)

        existing = {
            (v['term_id'][0], v['lang']): v
            for v in Value.search_read([('term_id', 'in', list({k[0] for k in wanted})), ('lang', 'in', langs)],
                                       ['term_id', 'lang', 'value', 'state'])
        }
        to_write, to_create = defaultdict(list), []
        for (term_id, lang), (value, exact) in wanted.items():
            cur = existing.get((term_id, lang))
            if not cur:
                to_create.append({'term_id': term_id, 'lang': lang, 'value': value, 'state': 'override', 'pending': True})
            elif (cur['value'] or '') == value:
                stats['unchanged'] += 1
            elif cur['state'] == 'override' and not overwrite_edited:
                stats['kept_edited'] += 1
            elif src_mode == 'missing' and not exact and cur['value'] and cur['state'] != 'machine':
                # Bản dịch máy coi như chưa có người dịch ⇒ glossary của người được điền đè (J-T5).
                stats['kept_translated'] += 1
            else:
                to_write[value].append(cur['id'])
        changed = Value.create(to_create)
        for value, ids in to_write.items():
            records = Value.browse(ids)
            records.write({'value': value})
            changed |= records
        stats['updated'] = len(changed)
        if apply:
            db_values = changed.filtered(lambda v: v.kind in DB_KINDS)
            db_values._wj_apply()
            db_values.with_context(wj_i18n_scan=True).write({'pending': False})
            stats['applied'] = len(db_values)
        stats['code_waiting_export'] = len(changed.filtered(lambda v: v.kind not in DB_KINDS))
        stats['unmatched_samples'] = unmatched
        stats['seconds'] = round(time.monotonic() - started, 1)
        _logger.info('wujia_i18n import: %s', {k: v for k, v in stats.items() if k != 'unmatched_samples'})
        return stats

    # ------------------------------------------------------------------ export CSV
    @api.model
    def _wj_export_csv(self, modules, langs, only_edited=False):
        Value = self.env['wujia.i18n.value']
        Value.check_access('read')
        langs = [lang for lang in langs if lang != 'en_US']
        terms = self.env['wujia.i18n.term'].search_read(
            [('module', 'in', list(modules))], ['module', 'kind', 'name', 'res_id', 'src'], order='module, kind, id')
        values = defaultdict(dict)
        edited = set()
        for v in Value.search_read([('term_id', 'in', [t['id'] for t in terms]), ('lang', 'in', langs)],
                                   ['term_id', 'lang', 'value', 'state']):
            if v['value']:
                values[v['term_id'][0]][v['lang']] = v['value']
            if v['state'] == 'override':
                edited.add(v['term_id'][0])
        rows = [
            (t['src'], po_writer.format_option(t['kind'], t['name'], t['res_id']), values.get(t['id'], {}))
            for t in terms if not only_edited or t['id'] in edited
        ]
        return po_writer.write_glossary_csv(rows, langs)

    # ------------------------------------------------------------------ export .po
    @api.model
    def _wj_export_po_zip(self, modules, langs):
        """Zip `<module>/i18n/<module>.pot` + `<module>/i18n/<lang>.po`.
        msgstr = bản sửa tay của tool > bản dịch máy > bản dịch đang chạy (DB / .po đã nạp) > msgstr .po trong source > rỗng."""
        Value = self.env['wujia.i18n.value']
        Value.check_access('read')
        langs = [lang for lang in langs if lang != 'en_US']
        overrides = defaultdict(dict)  # (module, lang) -> {msgid: value}
        machine = defaultdict(dict)
        conflicts = []
        for v in Value.search_read([('module', 'in', list(modules)), ('lang', 'in', langs),
                                    ('state', 'in', ('override', 'machine')),
                                    ('value', '!=', False), ('term_active', '=', True)],
                                   ['module', 'lang', 'src', 'value', 'state'], order='module, lang, id'):
            if v['state'] == 'machine':
                machine[(v['module'], v['lang'])].setdefault(v['src'], v['value'])
                continue
            seen = overrides[(v['module'], v['lang'])]
            if v['src'] in seen and seen[v['src']] != v['value']:
                conflicts.append(f"{v['module']} {v['lang']}: {v['src']!r} → kept {seen[v['src']]!r}, dropped {v['value']!r}")
                continue
            seen[v['src']] = v['value']

        buf = io.BytesIO()
        notes, files = [], 0
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for module in modules:
                pot = io.BytesIO()
                if not trans_export(None, [module], pot, 'po', self.env):
                    notes.append(f'{module}: no translatable strings, skipped')
                    continue
                pot_bytes = pot.getvalue()
                zf.writestr(f'{module}/i18n/{module}.pot', pot_bytes)
                files += 1
                mod_path = get_module_path(module, display_warning=False)
                for lang in langs:
                    keep = po_writer.existing_msgstr(mod_path and os.path.join(mod_path, 'i18n', f'{lang}.po'))
                    current = {
                        src: value
                        for _m, _t, _n, _r, src, value, _c in TranslationModuleReader(self.env.cr, [module], lang)
                        if value and value != src
                    }
                    edits = overrides.get((module, lang), {})
                    mt = machine.get((module, lang), {})
                    po = po_writer.fill_po(pot_bytes, lang,
                                           lambda m: edits.get(m) or mt.get(m) or current.get(m) or keep.get(m))
                    errs = po_writer.msgfmt_bytes_errors(po)
                    if errs:
                        notes.append(f'{module}/{lang}.po msgfmt: ' + ' | '.join(errs[:3]))
                    zf.writestr(f'{module}/i18n/{lang}.po', po)
                    files += 1
            readme = [
                'Translation export (wujia_i18n).',
                'Copy each <module>/i18n/ folder into the module source, commit, deploy, -u the module, then restart',
                '(Python/JavaScript strings are only read from .po files at startup).',
            ]
            if conflicts or notes:
                readme += ['', 'Notes:'] + conflicts + notes
            zf.writestr('README.txt', '\n'.join(readme) + '\n')
        # Chuỗi code đã nằm trong .po ⇒ hết "chờ"; còn phải commit + restart (ghi ở README).
        Value.search([('module', 'in', list(modules)), ('lang', 'in', langs), ('pending', '=', True),
                      ('kind', 'not in', DB_KINDS)]).with_context(wj_i18n_scan=True).write({'pending': False})
        _logger.info('wujia_i18n export .po: %s modules × %s, %s files, %s conflicts', len(modules), langs, files,
                     len(conflicts))
        return buf.getvalue(), conflicts + notes

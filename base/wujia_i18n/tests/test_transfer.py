import base64
import csv
import io
import os
import zipfile

from babel.messages.pofile import read_po

from odoo.exceptions import AccessError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.wujia_i18n.tools import po_writer

MOD = 'wujia_i18n'
LANG = 'zh_CN'


def csv_bytes(*rows, option=True):
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator='\n')
    writer.writerow(['key', 'option', 'VN', 'CN', 'TH'] if option else ['key', 'VN', 'CN', 'TH'])
    writer.writerows(rows)
    return buf.getvalue().encode()


@tagged('post_install', '-at_install', 'wujia_i18n')
class TestI18nTransfer(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.lang']._activate_lang(LANG)
        cls.env['res.lang']._activate_lang('vi_VN')
        cls.Term = cls.env['wujia.i18n.term']
        cls.Value = cls.env['wujia.i18n.value']
        cls.Transfer = cls.env['wujia.i18n.transfer']
        # DB đo có thể chứa catalog module khác (khớp theo câu nguồn sẽ chạm tới) ⇒ cô lập về MOD.
        cls.Term.with_context(active_test=False).search([('module', '!=', MOD)]).unlink()
        cls.Term._wj_scan([MOD], [LANG, 'vi_VN'])
        cls.menu = cls.env.ref('wujia_i18n.menu_wujia_i18n_term')

    def _value(self, domain, lang=LANG):
        val = self.Value.search([('module', '=', MOD), ('lang', '=', lang)] + domain, limit=1)
        self.assertTrue(val, domain)
        return val

    def _menu_value(self):
        return self._value([('res_id', '=', 'wujia_i18n.menu_wujia_i18n_term'), ('name', '=', 'ir.ui.menu,name')])

    def _code_value(self):
        return self._value([('kind', '=', 'code_python'), ('state', '=', 'missing')])

    def _import(self, *rows, option=True, **kw):
        return self.Transfer._wj_import_csv(csv_bytes(*rows, option=option), **kw)

    def test_option_roundtrip_matches_catalog(self):
        for kind in ('model', 'model_terms', 'code_python'):
            term = self.Term.search([('module', '=', MOD), ('kind', '=', kind)], limit=1)
            parsed = po_writer.parse_option(po_writer.format_option(term.kind, term.name, term.res_id))
            self.assertEqual(parsed, ('code' if kind.startswith('code') else kind, term.name, term.res_id))
        self.assertEqual(po_writer.parse_option('code:addons/x/a.js:12'), ('code', 'addons/x/a.js', 'addons/x/a.js:12'))
        self.assertIsNone(po_writer.parse_option('weird'))

    def test_import_by_reference_applies_now(self):
        val = self._menu_value()
        st = self._import((val.src, 'model:ir.ui.menu,name:wujia_i18n.menu_wujia_i18n_term', '', 'TERMS CSV', ''))
        self.assertEqual((st['matched_by_ref'], st['updated'], st['applied']), (1, 1, 1))
        self.assertEqual((val.value, val.state, val.pending), ('TERMS CSV', 'override', False))
        self.assertEqual(self.menu.with_context(lang=LANG).name, 'TERMS CSV')

    def test_identical_translation_is_noop(self):
        self.menu.update_field_translations('name', {LANG: 'TERMS SAME'})
        self.Term._wj_scan([MOD], [LANG])
        val = self._menu_value()
        st = self._import((val.src, 'model:ir.ui.menu,name:wujia_i18n.menu_wujia_i18n_term', '', 'TERMS SAME', ''))
        self.assertEqual((st['updated'], st['unchanged']), (0, 1))
        self.assertEqual(val.state, 'synced')

    def test_cell_equal_to_key_is_not_a_translation(self):
        val = self._code_value()
        st = self._import((val.src, '', '', val.src, val.src))
        self.assertEqual(st['updated'], 0)
        self.assertEqual((val.value or '', val.state), ('', 'missing'))

    def test_edited_translation_kept_unless_overwrite(self):
        val = self._menu_value()
        val.value = 'MANUAL'
        row = (val.src, 'model:ir.ui.menu,name:wujia_i18n.menu_wujia_i18n_term', '', 'FROM CSV', '')
        st = self._import(row)
        self.assertEqual((st['kept_edited'], st['updated'], val.value), (1, 0, 'MANUAL'))
        st = self._import(row, overwrite_edited=True)
        self.assertEqual((st['updated'], val.value), (1, 'FROM CSV'))

    def test_source_only_match_fills_missing_but_keeps_translated(self):
        self.menu.update_field_translations('name', {LANG: 'TERMS DONE'})
        self.Term._wj_scan([MOD], [LANG])
        menu_val, code_val = self._menu_value(), self._code_value()
        st = self._import((menu_val.src, '', 'TERMS GLOSSARY', ''), (code_val.src, '', 'CODE ZH', ''), option=False)
        self.assertEqual(st['matched_by_source'], 2)
        self.assertEqual((st['kept_translated'], menu_val.value, menu_val.state), (1, 'TERMS DONE', 'synced'))
        # Chuỗi code: vào tool, chờ xuất .po (không áp vào DB được).
        self.assertEqual((code_val.value, code_val.state, code_val.pending), ('CODE ZH', 'override', True))
        self.assertEqual(st['code_waiting_export'], 1)
        st = self._import((menu_val.src, '', 'TERMS GLOSSARY', ''), option=False, src_mode='all')
        self.assertEqual((st['updated'], menu_val.value), (1, 'TERMS GLOSSARY'))

    def test_unknown_rows_and_inactive_languages_reported(self):
        st = self._import(('No such source text xyz', '', '', 'X', ''))
        self.assertEqual((st['unmatched'], st['unmatched_samples']), (1, ['No such source text xyz']))
        data = b'key,option,ja_JP\n"Terms","","JP"\n'
        st = self.Transfer._wj_import_csv(data)
        self.assertEqual((st['languages'], st['skipped_languages']), ([], ['ja_JP']))

    def test_csv_export_reimport_is_noop(self):
        self._menu_value().value = 'EDITED'
        data = self.Transfer._wj_export_csv([MOD], [LANG, 'vi_VN'])
        self.assertTrue(data.startswith(b'key,option,CN,VN\n'))
        self.assertIn(b'EDITED', data)
        st = self.Transfer._wj_import_csv(data)
        self.assertEqual(st['updated'], 0)
        self.assertEqual(st['unmatched'], 0)
        only = self.Transfer._wj_export_csv([MOD], [LANG], only_edited=True)
        self.assertEqual(only.count(b'\n'), 2)

    def test_po_zip_carries_edits_and_keeps_existing(self):
        code_val = self._code_value()
        code_val.value = 'CODE ZH'
        # Bản sửa tay chưa áp phải thắng bản dịch đang có trong DB.
        self.menu.update_field_translations('name', {LANG: 'DB OLD'})
        menu_val = self._menu_value()
        menu_val.value = 'MENU EDIT'
        vi_keep = po_writer.existing_msgstr(os.path.join(get_module_path(MOD), 'i18n', 'vi_VN.po'))
        self.assertTrue(vi_keep)
        data, notes = self.Transfer._wj_export_po_zip([MOD], [LANG, 'vi_VN'])
        zf = zipfile.ZipFile(io.BytesIO(data))
        self.assertEqual(set(zf.namelist()), {
            f'{MOD}/i18n/{MOD}.pot', f'{MOD}/i18n/{LANG}.po', f'{MOD}/i18n/vi_VN.po', 'README.txt'})
        pot_raw = zf.read(f'{MOD}/i18n/{MOD}.pot')
        self.assertIn(b'#. odoo-python', pot_raw)
        self.assertFalse([m.id for m in read_po(io.BytesIO(pot_raw)) if m.id and m.string])
        zh = {m.id: m.string for m in read_po(io.BytesIO(zf.read(f'{MOD}/i18n/{LANG}.po'))) if m.id}
        self.assertEqual((zh[code_val.src], zh[menu_val.src]), ('CODE ZH', 'MENU EDIT'))
        vi = {m.id: m.string for m in read_po(io.BytesIO(zf.read(f'{MOD}/i18n/vi_VN.po'))) if m.id}
        lost = [m for m, s in vi_keep.items() if m in vi and not vi[m]]
        self.assertFalse(lost)
        self.assertFalse(code_val.pending)

    def test_po_zip_reports_conflicting_edits(self):
        a = self.Term.create({'module': MOD, 'kind': 'model', 'name': 'ir.ui.menu,name', 'res_id': 'wujia_i18n.a',
                              'src': 'Same source', 'key_hash': 'a' * 32})
        b = self.Term.create({'module': MOD, 'kind': 'model', 'name': 'ir.ui.menu,name', 'res_id': 'wujia_i18n.b',
                              'src': 'Same source', 'key_hash': 'b' * 32})
        self.Value.create([{'term_id': a.id, 'lang': LANG, 'value': 'ONE', 'state': 'override'},
                           {'term_id': b.id, 'lang': LANG, 'value': 'TWO', 'state': 'override'}])
        data, notes = self.Transfer._wj_export_po_zip([MOD], [LANG])
        self.assertTrue(any("'Same source'" in n and "'ONE'" in n for n in notes), notes)
        self.assertIn(b'Same source', zipfile.ZipFile(io.BytesIO(data)).read('README.txt'))

    def test_access_rights(self):
        user = new_test_user(self.env, login='wj_tr_user', groups='base.group_user')
        with self.assertRaises(AccessError):
            self.Transfer.with_user(user)._wj_import_csv(csv_bytes(('Terms', '', '', 'X', '')))
        with self.assertRaises(AccessError):
            self.Transfer.with_user(user)._wj_export_csv([MOD], [LANG])
        translator = new_test_user(self.env, login='wj_tr_ok', groups='base.group_user,wujia_i18n.group_wujia_translator')
        val = self._menu_value()
        st = self.Transfer.with_user(translator)._wj_import_csv(
            csv_bytes((val.src, 'model:ir.ui.menu,name:wujia_i18n.menu_wujia_i18n_term', '', 'BY TR', '')))
        self.assertEqual((st['updated'], val.value), (1, 'BY TR'))

    def test_wizard_import_and_export(self):
        val = self._menu_value()
        wiz = self.env['wujia.i18n.transfer.wizard'].create({
            'mode': 'import',
            'file': base64.b64encode(csv_bytes((val.src, 'model:ir.ui.menu,name:wujia_i18n.menu_wujia_i18n_term', '', 'WIZ', ''))),
        })
        self.assertEqual(wiz.action_import()['tag'], 'display_notification')
        self.assertEqual(self.menu.with_context(lang=LANG).name, 'WIZ')
        wiz = self.env['wujia.i18n.transfer.wizard'].create({
            'mode': 'export', 'export_format': 'po_zip',
            'module_ids': [(6, 0, self.env['ir.module.module']._get(MOD).ids)],
            'lang_ids': [(6, 0, self.env['res.lang']._lang_get(LANG).ids)],
        })
        action = wiz.action_export()
        self.assertIn('download=true', action['url'])
        self.assertTrue(wiz.result_filename.endswith('.zip'))
        self.assertTrue(zipfile.is_zipfile(io.BytesIO(base64.b64decode(wiz.result_file))))

    def test_export_pending_code_action(self):
        self._code_value().value = 'CODE ZH'
        action = self.Value.action_export_pending_code()
        self.assertEqual(action['context']['default_export_format'], 'po_zip')
        self.assertEqual(action['context']['default_module_ids'], self.env['ir.module.module']._get(MOD).ids)

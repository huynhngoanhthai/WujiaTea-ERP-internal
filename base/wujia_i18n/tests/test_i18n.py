from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged

MOD = 'wujia_i18n'
LANG = 'zh_CN'


@tagged('post_install', '-at_install', 'wujia_i18n')
class TestI18nTool(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.lang']._activate_lang(LANG)
        cls.Term = cls.env['wujia.i18n.term']
        cls.Value = cls.env['wujia.i18n.value']
        cls.stats = cls.Term._wj_scan([MOD], [LANG])

    def _value(self, domain):
        val = self.Value.search([('module', '=', MOD), ('lang', '=', LANG)] + domain, limit=1)
        self.assertTrue(val, domain)
        return val

    def test_scan_reads_db_and_code_terms(self):
        kinds = set(self.Term.search([('module', '=', MOD)]).mapped('kind'))
        self.assertTrue({'model', 'model_terms', 'code_python'} <= kinds, kinds)
        # Mỗi term có đúng 1 dòng cho mỗi ngôn ngữ quét.
        terms = self.Term.search([('module', '=', MOD)])
        self.assertEqual(self.Value.search_count([('term_id', 'in', terms.ids), ('lang', '=', LANG)]), len(terms))

    def test_scan_js_terms(self):
        self.Term._wj_scan(['web'], [LANG])
        self.assertTrue(self.Term.search_count([('module', '=', 'web'), ('kind', '=', 'code_js')]))

    def test_rescan_is_idempotent_and_keeps_edits(self):
        val = self._value([('kind', '=', 'model'), ('name', '=', 'ir.ui.menu,name')])
        val.value = 'EDITED MENU'
        before = (self.Term.search_count([]), self.Value.search_count([]))
        stats = self.Term._wj_scan([MOD], [LANG])
        self.assertEqual(stats['new_terms'], 0)
        self.assertEqual((self.Term.search_count([]), self.Value.search_count([])), before)
        self.assertEqual((val.value, val.state, val.pending), ('EDITED MENU', 'override', True))

    def test_rescan_archives_vanished_terms(self):
        ghost = self.Term.create({'module': MOD, 'kind': 'code_python', 'src': 'ghost', 'key_hash': 'x' * 32})
        self.Term._wj_scan([MOD], [LANG])
        self.assertFalse(ghost.active)

    def test_rescan_refreshes_synced_value_from_db(self):
        menu = self.env.ref('wujia_i18n.menu_wujia_i18n_coverage')
        menu.update_field_translations('name', {LANG: 'Coverage ZH'})
        self.Term._wj_scan([MOD], [LANG])
        val = self._value([('res_id', '=', 'wujia_i18n.menu_wujia_i18n_coverage')])
        self.assertEqual((val.value, val.state), ('Coverage ZH', 'synced'))

    def test_apply_menu_translation(self):
        menu = self.env.ref('wujia_i18n.menu_wujia_i18n_term')
        val = self._value([('res_id', '=', 'wujia_i18n.menu_wujia_i18n_term'), ('name', '=', 'ir.ui.menu,name')])
        val.value = 'TERMS ZH'
        val.action_apply()
        self.assertEqual(menu.with_context(lang=LANG).name, 'TERMS ZH')
        self.assertFalse(val.pending)

    def test_apply_view_term_and_field_label_without_restart(self):
        view = self.env.ref('wujia_i18n.view_wujia_i18n_value_search')
        val = self._value([('res_id', '=', 'wujia_i18n.view_wujia_i18n_value_search'), ('src', '=', 'Not translated')])
        label = self._value([('res_id', '=', 'wujia_i18n.field_wujia_i18n_value__pending'),
                             ('name', '=', 'ir.model.fields,field_description')])
        ValueZh = self.Value.with_context(lang=LANG)
        # Nạp cache 'stable' (nhãn field) + 'templates' (view) trước khi áp.
        ValueZh.fields_get(['pending'])
        ValueZh.get_views([(view.id, 'search')])
        val.value, label.value = 'CHUA DICH ZH', 'CHO AP ZH'
        (val | label).action_apply()
        self.assertIn('CHUA DICH ZH', ValueZh.get_views([(view.id, 'search')])['views']['search']['arch'])
        self.assertEqual(ValueZh.fields_get(['pending'])['pending']['string'], 'CHO AP ZH')

    def test_edit_survives_module_translation_reload(self):
        menu = self.env.ref('wujia_i18n.menu_wujia_i18n_term')
        val = self._value([('res_id', '=', 'wujia_i18n.menu_wujia_i18n_term'), ('name', '=', 'ir.ui.menu,name')])
        val.value = 'TERMS ZH'
        val.action_apply()
        # Giả lập .po của module đè lên (như -u với overwrite).
        menu.update_field_translations('name', {LANG: 'FROM PO'})
        self.assertEqual(menu.with_context(lang=LANG).name, 'FROM PO')
        self.env['ir.module.module'].search([('name', '=', MOD)])._update_translations([LANG], overwrite=True)
        self.assertEqual(menu.with_context(lang=LANG).name, 'TERMS ZH')

    def test_code_string_is_not_applied_to_db(self):
        val = self._value([('kind', '=', 'code_python')])
        val.value = 'CODE ZH'
        val.action_apply()
        self.assertTrue(val.pending)

    def test_clearing_value_marks_missing(self):
        val = self._value([('kind', '=', 'model')])
        val.value = False
        self.assertEqual((val.state, val.pending), ('missing', False))

    def test_coverage_counts(self):
        self.env.flush_all()
        row = self.env['wujia.i18n.coverage'].search([('module', '=', MOD), ('lang', '=', LANG)])
        self.assertEqual(row.total, self.Value.search_count([('module', '=', MOD), ('lang', '=', LANG), ('term_active', '=', True)]))
        self.assertEqual(row.translated + row.missing, row.total)

    def test_access_rights(self):
        user = new_test_user(self.env, login='wj_i18n_user', groups='base.group_user')
        with self.assertRaises(AccessError):
            self.Value.with_user(user).search([])
        translator = new_test_user(self.env, login='wj_i18n_tr', groups='base.group_user,wujia_i18n.group_wujia_translator')
        val = self._value([('kind', '=', 'model')]).with_user(translator)
        val.value = 'BY TRANSLATOR'
        val.action_apply()
        self.assertEqual(val.state, 'override')
        with self.assertRaises(AccessError):
            val.term_id.write({'src': 'hack'})


@tagged('post_install', '-at_install', 'wujia_i18n')
class TestEnableLanguages(TransactionCase):

    def test_default_languages_active(self):
        from odoo.addons.wujia_i18n.models.res_lang import WJ_LANGS
        active = self.env['res.lang']._get_active_by('code')
        for code in WJ_LANGS:
            self.assertIn(code, active)

    def test_enable_is_idempotent(self):
        self.assertEqual(self.env['res.lang']._wj_enable_languages(), [])

    def test_enable_loads_translations(self):
        Lang = self.env['res.lang']
        Lang._wj_enable_languages(('ja_JP',))
        self.assertIn('ja_JP', Lang._get_active_by('code'))
        menu = self.env.ref('base.menu_administration').with_context(lang='ja_JP')
        self.assertNotEqual(menu.name, 'Settings')

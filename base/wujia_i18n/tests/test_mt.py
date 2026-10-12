import io
import zipfile
from contextlib import contextmanager
from unittest.mock import patch

from babel.messages.pofile import read_po

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.wujia_i18n.models.i18n_mt import PARAM_CAPS, PARAM_ERROR, PARAM_KEY
from odoo.addons.wujia_i18n.tools import mt_deepl
from odoo.addons.wujia_i18n.tools.mt_deepl import DeepLClient, MTError

MOD = 'wujia_i18n'
TH = 'th_TH'
ZH = 'zh_CN'


class FakeDeepL:
    """Giả lập API DeepL: dịch = thêm tiền tố mã đích, giữ nguyên thẻ/token như DeepL thật."""

    def __init__(self, targets=('TH', 'ZH-HANS', 'JA'), pairs=(('en', 'zh'),)):
        self.targets, self.pairs = targets, pairs
        self.calls, self.glossaries, self.created = [], {}, 0
        self.translate_hook = None

    def __call__(self, client, method, path, params=None, json=None):
        self.calls.append((method, path, json))
        if path == '/v2/languages':
            return [{'language': t, 'name': t} for t in self.targets]
        if path == '/v2/glossary-language-pairs':
            return {'supported_languages': [{'source_lang': s, 'target_lang': t} for s, t in self.pairs]}
        if path == '/v2/usage':
            return {'character_count': 1200, 'character_limit': 500000}
        if path == '/v2/glossaries':
            self.created += 1
            gid = f'g{self.created}'
            self.glossaries[gid] = json
            return {'glossary_id': gid}
        if method == 'DELETE':
            self.glossaries.pop(path.rsplit('/', 1)[1], None)
            return None
        if path == '/v2/translate':
            if self.translate_hook:
                out = self.translate_hook(json)
                if out is not None:
                    return out
            return {'translations': [{'text': f"[{json['target_lang']}] {t}"} for t in json['text']]}
        raise AssertionError(path)

    def translate_calls(self):
        return [body for method, path, body in self.calls if path == '/v2/translate']


@tagged('post_install', '-at_install', 'wujia_i18n')
class TestMtHelpers(TransactionCase):

    def test_protect_restore_keeps_placeholders_tags_spaces(self):
        cases = [
            ('  %(n)s orders & {count} items  ', False),
            ('100%% done %s', False),
            ('<i class="fa fa-arrow-left"/> Back to&nbsp;list', True),
            ('Total ${amount} <b>now</b>', True),
        ]
        for src, markup in cases:
            text, meta = mt_deepl.protect(src, markup)
            self.assertNotIn('%(n)s', text)
            self.assertNotIn('{count}', text)
            out = mt_deepl.restore('[TH] ' + text, meta)
            self.assertEqual(out, src[:len(src) - len(src.lstrip())] + '[TH] ' + src.strip()
                             + src[len(src.rstrip()):], src)
            self.assertEqual(mt_deepl.check(src, out, markup), '', src)

    def test_code_string_is_escaped_for_xml(self):
        text, meta = mt_deepl.protect('A < B & C', markup=False)
        self.assertEqual(text, 'A &lt; B &amp; C')
        self.assertEqual(mt_deepl.restore('X &lt; Y &amp; Z', meta), 'X < Y & Z')

    def test_check_rejects_lost_placeholder_or_tag(self):
        self.assertTrue(mt_deepl.check('Pay %s now', 'Payer maintenant'))
        self.assertTrue(mt_deepl.check('<b>Hi</b> there', 'Salut', markup=True))
        self.assertTrue(mt_deepl.check('Hi', '  '))

    def test_keep_and_replace_terms(self):
        text, meta = mt_deepl.protect('Order at Ngô Gia', keep_terms=['Ngô Gia'])
        self.assertNotIn('Ngô Gia', text)
        self.assertEqual(mt_deepl.restore(text.replace('Order at', 'สั่งที่'), meta), 'สั่งที่ Ngô Gia')
        text, meta = mt_deepl.protect('Franchise fee', replace_terms={'franchise': 'แฟรนไชส์'})
        self.assertIn('แฟรนไชส์', mt_deepl.restore(text, meta))

    def test_language_codes_and_vietnamese_detection(self):
        self.assertEqual(mt_deepl.deepl_target('zh_CN'), 'ZH-HANS')
        self.assertEqual(mt_deepl.deepl_target('th_TH'), 'TH')
        self.assertEqual(mt_deepl.deepl_glossary_lang('zh_CN'), 'zh')
        self.assertTrue(mt_deepl.is_vietnamese('Đơn hàng'))
        self.assertFalse(mt_deepl.is_vietnamese('Order list'))

    def test_free_key_uses_free_endpoint(self):
        self.assertEqual(DeepLClient('abc:fx').base_url, mt_deepl.DEEPL_FREE_URL)
        self.assertEqual(DeepLClient('abc').base_url, mt_deepl.DEEPL_PRO_URL)


@tagged('post_install', '-at_install', 'wujia_i18n')
class TestMachineTranslation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for code in (TH, ZH):
            cls.env['res.lang']._activate_lang(code)
        cls.Term = cls.env['wujia.i18n.term']
        cls.Value = cls.env['wujia.i18n.value']
        # Cô lập catalog về MOD (DB đo có thể còn catalog module khác).
        cls.Term.with_context(active_test=False).search([('module', '!=', MOD)]).unlink()
        cls.Value.search([('mt_queued', '=', True)]).write({'mt_queued': False})
        cls.Term._wj_scan([MOD], [TH, ZH])
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_param(PARAM_KEY, 'test-key:fx')
        ICP.set_param(PARAM_CAPS, '')
        ICP.set_param(PARAM_ERROR, '')
        cls.menu = cls.env.ref('wujia_i18n.menu_wujia_i18n_term')

    def setUp(self):
        super().setUp()
        self.fake = FakeDeepL()
        patcher = patch.object(DeepLClient, '_request', autospec=True, side_effect=self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _value(self, domain, lang=TH):
        val = self.Value.search([('module', '=', MOD), ('lang', '=', lang)] + domain, limit=1)
        self.assertTrue(val, domain)
        return val

    def _menu_value(self, lang=TH):
        return self._value([('res_id', '=', 'wujia_i18n.menu_wujia_i18n_term'), ('name', '=', 'ir.ui.menu,name')], lang)

    def _translate(self, lang=TH, scope='missing'):
        queued = self.Value._wj_mt_enqueue(lang, [MOD], scope)
        self.Value._wj_mt_run_queue()
        return queued

    @contextmanager
    def _translate_raises(self, kind):
        def hook(body):
            raise MTError(kind, kind)
        self.fake.translate_hook = hook
        yield

    # ------------------------------------------------------------------ luồng chính
    def test_fills_missing_applies_now_and_keeps_others(self):
        menu_val = self._menu_value()
        self.assertEqual(menu_val.state, 'missing')
        edited = self._value([('kind', '=', 'model'), ('id', '!=', menu_val.id)])
        edited.value = 'NGUOI SUA'
        coverage_menu = self.env.ref('wujia_i18n.menu_wujia_i18n_coverage')
        coverage_menu.update_field_translations('name', {TH: 'TH FROM PO'})
        self.Term._wj_scan([MOD], [TH])
        synced = self._value([('res_id', '=', 'wujia_i18n.menu_wujia_i18n_coverage'), ('name', '=', 'ir.ui.menu,name')])
        self.assertEqual(synced.state, 'synced')

        self._translate()

        self.assertEqual((menu_val.value, menu_val.state, menu_val.pending, menu_val.mt_queued),
                         ('[TH] Terms', 'machine', False, False))
        self.assertEqual(self.menu.with_context(lang=TH).name, '[TH] Terms')  # áp ngay, không restart
        self.assertEqual((edited.value, edited.state), ('NGUOI SUA', 'override'))
        self.assertEqual((synced.value, synced.state), ('TH FROM PO', 'synced'))
        code = self._value([('kind', '=', 'code_python'), ('state', '=', 'machine')])
        self.assertTrue(code.pending, 'chuỗi code chờ xuất .po + restart')
        self.assertEqual(self.Value.search_count([('mt_queued', '=', True)]), 0)
        body = self.fake.translate_calls()[0]
        self.assertEqual((body['target_lang'], body['source_lang'], body['tag_handling']), ('TH', 'EN', 'xml'))

    def test_refresh_scope_replaces_synced_but_never_edited(self):
        coverage_menu = self.env.ref('wujia_i18n.menu_wujia_i18n_coverage')
        coverage_menu.update_field_translations('name', {TH: 'TH FROM PO'})
        self.Term._wj_scan([MOD], [TH])
        synced = self._value([('res_id', '=', 'wujia_i18n.menu_wujia_i18n_coverage'), ('name', '=', 'ir.ui.menu,name')])
        edited = self._menu_value()
        edited.value = 'NGUOI SUA'
        queued = self._translate(scope='refresh')
        self.assertIn(synced, queued)
        self.assertNotIn(edited, queued)
        self.assertEqual((synced.value, synced.state), ('[TH] Coverage', 'machine'))
        self.assertEqual(edited.value, 'NGUOI SUA')

    def test_rescan_and_module_reload_keep_machine_translation(self):
        menu_val = self._menu_value()
        self._translate()
        code = self._value([('kind', '=', 'code_python'), ('state', '=', 'machine')])
        code_text = code.value
        self.Term._wj_scan([MOD], [TH])
        self.assertEqual((menu_val.value, menu_val.state), ('[TH] Terms', 'machine'))
        # Chuỗi code chưa có trong .po (DB không lưu) ⇒ quét lại không được xoá bản máy.
        self.assertEqual((code.value, code.state), (code_text, 'machine'))
        self.menu.update_field_translations('name', {TH: 'FROM PO'})
        self.env['ir.module.module'].search([('name', '=', MOD)])._update_translations([TH], overwrite=True)
        self.assertEqual(self.menu.with_context(lang=TH).name, '[TH] Terms')

    def test_review_and_manual_edit(self):
        menu_val = self._menu_value()
        self._translate()
        menu_val.action_mark_reviewed()
        self.assertEqual((menu_val.value, menu_val.state), ('[TH] Terms', 'override'))
        other = self._value([('state', '=', 'machine'), ('kind', '=', 'model')])
        other.value = 'SUA TAY'
        self.assertEqual((other.state, other.pending), ('override', True))
        # Đã duyệt / sửa tay ⇒ dịch lại (cả phạm vi refresh) không đụng tới.
        self._translate(scope='refresh')
        self.assertEqual((menu_val.value, other.value), ('[TH] Terms', 'SUA TAY'))

    def test_edit_while_waiting_for_deepl_wins(self):
        # Dòng có câu nguồn duy nhất, chữ thường ⇒ nhận ra đúng lô chứa nó trong request.
        candidates = self.Value.search([('module', '=', MOD), ('lang', '=', TH), ('state', '=', 'missing'),
                                        ('kind', '=', 'model')])
        counts = {}
        for v in candidates:
            counts[v.src] = counts.get(v.src, 0) + 1
        val = candidates.filtered(lambda v: counts[v.src] == 1 and v.src.replace(' ', '').isalpha())[-1:]
        self.assertTrue(val)

        def hook(body):
            # Người sửa tay đúng lúc request DeepL của lô chứa dòng này đang chạy.
            if val.src in body['text']:
                val.value = 'NGUOI SUA GIUA CHUNG'
        self.fake.translate_hook = hook
        self._translate()
        self.assertEqual(val.value, 'NGUOI SUA GIUA CHUNG', 'hook phải chạy đúng lô chứa dòng này')
        self.assertEqual((val.state, val.mt_queued), ('override', False))

    def test_lost_placeholder_is_rejected(self):
        val = self._value([('kind', '=', 'code_python'), ('src', 'like', '%(n)s')])

        def hook(body):
            # DeepL "nuốt" token placeholder
            return {'translations': [{'text': mt_deepl.TOKEN.sub('', t)} for t in body['text']]}
        self.fake.translate_hook = hook
        self._translate()
        self.assertEqual((val.state, val.value or '', val.mt_queued), ('missing', '', False))
        self.assertIn('placeholders', val.mt_error)

    # ------------------------------------------------------------------ thuật ngữ
    def test_glossary_sent_to_deepl_and_reused(self):
        Glossary = self.env['wujia.i18n.glossary']
        Glossary.create({'src': 'Coverage', 'lang': ZH, 'value': '覆盖率'})
        self._translate(ZH)
        bodies = self.fake.translate_calls()
        self.assertEqual({b.get('glossary_id') for b in bodies}, {'g1'})
        self.assertEqual(self.fake.glossaries['g1']['entries'], 'Coverage\t覆盖率')
        self.assertEqual(self.fake.glossaries['g1']['target_lang'], 'zh')
        # Nội dung không đổi ⇒ dùng lại; đổi ⇒ xoá bản cũ, tạo bản mới.
        self.assertEqual(Glossary._wj_deepl_glossary_id(DeepLClient('k'), ZH, {'Coverage': '覆盖率'}), 'g1')
        Glossary.create({'src': 'Terms', 'lang': ZH, 'value': '术语'})
        self.assertEqual(Glossary._wj_deepl_glossary_id(DeepLClient('k'), ZH, Glossary._wj_terms(ZH)[1]), 'g2')
        self.assertNotIn('g1', self.fake.glossaries)

    def test_glossary_fallback_when_pair_not_supported(self):
        # th không có glossary DeepL (FakeDeepL chỉ en→zh) ⇒ thay thẳng bản dịch đã chốt.
        self.env['wujia.i18n.glossary'].create({'src': 'Coverage', 'lang': TH, 'value': 'ความครอบคลุม'})
        val = self._value([('res_id', '=', 'wujia_i18n.menu_wujia_i18n_coverage'), ('name', '=', 'ir.ui.menu,name')])
        self._translate()
        self.assertEqual(val.value, '[TH] ความครอบคลุม')
        self.assertFalse(self.fake.glossaries)
        self.assertFalse(any(b.get('glossary_id') for b in self.fake.translate_calls()))

    def test_keep_as_is_term_not_sent_as_text(self):
        self.env['wujia.i18n.glossary'].create({'src': 'Coverage', 'no_translate': True})
        val = self._value([('res_id', '=', 'wujia_i18n.menu_wujia_i18n_coverage'), ('name', '=', 'ir.ui.menu,name')])
        self._translate()
        self.assertEqual(val.value, '[TH] Coverage')
        sent = [t for b in self.fake.translate_calls() for t in b['text']]
        self.assertNotIn('Coverage', sent)

    def test_vietnamese_source_lets_deepl_detect_language(self):
        term = self.Term.create({'module': MOD, 'kind': 'code_python', 'src': 'Đơn hàng %s của Ngô Gia', 'key_hash': 'v' * 32})
        val = self.Value.create({'term_id': term.id, 'lang': TH})
        en_term = self.Term.create({'module': MOD, 'kind': 'code_python', 'src': 'Order of Ngô Gia', 'key_hash': 'e' * 32})
        en_val = self.Value.create({'term_id': en_term.id, 'lang': TH})
        self._translate()
        self.assertEqual(val.state, 'machine')
        auto = [b for b in self.fake.translate_calls() if 'source_lang' not in b]
        self.assertEqual(len(auto), 1)
        self.assertEqual(len(auto[0]['text']), 1, 'chỉ câu tiếng Việt đi nhánh tự nhận ngôn ngữ')
        self.assertEqual(en_val.value, '[TH] Order of Ngô Gia', '"Ngô Gia" là thuật ngữ giữ nguyên, không làm câu EN thành VN')

    # ------------------------------------------------------------------ lỗi DeepL
    def test_quota_exceeded_stops_and_keeps_queue(self):
        with self._translate_raises('quota'):
            queued = self._translate()
        self.assertTrue(queued)
        self.assertTrue(all(queued.mapped('mt_queued')))
        self.assertTrue(all(v.state == 'missing' for v in queued))
        self.assertIn('quota', self.env['ir.config_parameter'].sudo().get_param(PARAM_ERROR))

    def test_rate_limit_retries_later(self):
        cron = self.env.ref('wujia_i18n.ir_cron_wujia_i18n_mt')
        Trigger = self.env['ir.cron.trigger']
        with self._translate_raises('rate'):
            queued = self.Value._wj_mt_enqueue(TH, [MOD])
            before = Trigger.search_count([('cron_id', '=', cron.id)])
            self.Value._wj_mt_run_queue()
        self.assertTrue(all(queued.mapped('mt_queued')))
        self.assertEqual(Trigger.search_count([('cron_id', '=', cron.id)]), before + 1)

    def test_other_error_marks_batch_and_continues(self):
        with self._translate_raises('other'):
            queued = self._translate()
        self.assertFalse(any(queued.mapped('mt_queued')))
        self.assertTrue(all(queued.mapped('mt_error')))

    def test_no_key_is_reported(self):
        self.env['ir.config_parameter'].sudo().set_param(PARAM_KEY, '')
        wiz = self.env['wujia.i18n.mt.wizard'].create({'lang_id': self.env.ref('base.lang_th').id})
        self.assertIn('API key', wiz.warning)
        with self.assertRaises(UserError):
            wiz.action_translate()

    # ------------------------------------------------------------------ wizard
    def test_wizard_estimate_and_translate(self):
        wiz = self.env['wujia.i18n.mt.wizard'].create({'lang_id': self.env.ref('base.lang_th').id})
        self.assertIn(MOD, wiz.module_ids.mapped('name'))
        self.assertFalse(any(m.startswith('wujia_franchise') for m in wiz.module_ids.mapped('name')))
        expected = self.Value.search(self.Value._wj_mt_domain(TH, wiz.module_ids.mapped('name')))
        self.assertEqual(wiz.count, len(expected))
        self.assertEqual(wiz.chars, sum(len(s) for s in expected.mapped('src')))
        wiz.module_ids = self.env['ir.module.module'].search([('name', '=', MOD)])
        wiz.action_translate()
        self.assertTrue(self._menu_value().mt_queued)
        wiz.action_check()
        self.assertIn('500,000', wiz.quota_info)

    def test_wizard_enables_inactive_language(self):
        ja = self.env['res.lang'].with_context(active_test=False).search([('code', '=', 'ja_JP')])
        self.assertFalse(ja.active)
        wiz = self.env['wujia.i18n.mt.wizard'].create({
            'lang_id': ja.id, 'module_ids': [(6, 0, self.env['ir.module.module'].search([('name', '=', MOD)]).ids)]})
        self.assertIn('not active', wiz.warning)
        wiz.action_translate()
        self.assertTrue(ja.active)
        self.assertTrue(self.Value.search_count([('module', '=', MOD), ('lang', '=', 'ja_JP'), ('mt_queued', '=', True)]))

    def test_unsupported_language(self):
        self.fake.targets = ('ZH-HANS',)
        wiz = self.env['wujia.i18n.mt.wizard'].create({
            'lang_id': self.env.ref('base.lang_th').id,
            'module_ids': [(6, 0, self.env['ir.module.module'].search([('name', '=', MOD)]).ids)]})
        with self.assertRaises(UserError):
            wiz.action_translate()
        # Hàng đợi cũ của ngôn ngữ không hỗ trợ ⇒ báo lỗi, rời hàng đợi.
        queued = self.Value._wj_mt_enqueue(TH, [MOD])
        self.Value._wj_mt_run_queue()
        self.assertFalse(any(queued.mapped('mt_queued')))
        self.assertTrue(all(queued.mapped('mt_error')))

    def test_access_rights(self):
        translator = new_test_user(self.env, login='wj_mt_tr', groups='base.group_user,wujia_i18n.group_wujia_translator')
        with self.assertRaises(AccessError):
            self.env['ir.config_parameter'].with_user(translator).get_param(PARAM_KEY)
        self.env['wujia.i18n.glossary'].with_user(translator).create({'src': 'Milk tea', 'lang': TH, 'value': 'ชานม'})
        wiz = self.env['wujia.i18n.mt.wizard'].with_user(translator).create({
            'lang_id': self.env.ref('base.lang_th').id,
            'module_ids': [(6, 0, self.env['ir.module.module'].search([('name', '=', MOD)]).ids)]})
        wiz.action_translate()
        self.assertTrue(self._menu_value().mt_queued)
        user = new_test_user(self.env, login='wj_mt_user', groups='base.group_user')
        with self.assertRaises(AccessError):
            self.env['wujia.i18n.mt.wizard'].with_user(user).create({'lang_id': self.env.ref('base.lang_th').id})

    # ------------------------------------------------------------------ độ phủ + nhập/xuất
    def test_coverage_counts_machine(self):
        self._translate()
        self.env.flush_all()
        row = self.env['wujia.i18n.coverage'].search([('module', '=', MOD), ('lang', '=', TH)])
        machine = self.Value.search_count([('module', '=', MOD), ('lang', '=', TH), ('state', '=', 'machine'),
                                           ('term_active', '=', True)])
        self.assertEqual(row.machine, machine)
        self.assertGreater(row.percent, row.percent_reviewed)

    def test_human_glossary_import_replaces_machine(self):
        menu_val = self._menu_value()
        self._translate()
        data = f'key,VN,CN,TH\n{menu_val.src},,,คำศัพท์\n'.encode()
        self.env['wujia.i18n.transfer']._wj_import_csv(data)
        self.assertEqual((menu_val.value, menu_val.state), ('คำศัพท์', 'override'))

    def test_po_export_carries_machine_translation(self):
        self._translate()
        code = self._value([('kind', '=', 'code_python'), ('state', '=', 'machine')])
        content, _notes = self.env['wujia.i18n.transfer']._wj_export_po_zip([MOD], [TH])
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            catalog = read_po(io.BytesIO(zf.read(f'{MOD}/i18n/{TH}.po')))
        self.assertEqual(catalog[code.src].string, code.value)
        self.assertFalse(code.pending, 'đã nằm trong .po ⇒ hết chờ')

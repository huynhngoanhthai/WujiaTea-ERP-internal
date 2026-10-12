"""WJ-LANG-001 — bộ chọn ngôn ngữ portal lấy động, đổi được cả khi chưa đăng nhập."""
from odoo.tests import HttpCase, TransactionCase, tagged


@tagged('post_install', '-at_install', 'wujia_lang_c10')
class TestPortalLangs(TransactionCase):

    def _codes(self):
        return [l['code'] for l in self.env['ir.http']._wj_portal_langs()]

    def test_list_follows_active_langs(self):
        self.assertIn('en_US', self._codes())
        before = self._codes()
        self.env['res.lang']._activate_lang('th_TH')
        self.assertIn('th_TH', self._codes())
        self.assertEqual(len(self._codes()), len(before) + 1 if 'th_TH' not in before
                         else len(before))

    def test_label_and_flag(self):
        self.env['res.lang']._activate_lang('th_TH')
        by_code = {l['code']: l for l in self.env['ir.http']._wj_portal_langs()}
        # Tên bản địa, không phải 'Thai / ...'
        self.assertEqual(by_code['th_TH']['label'], 'ภาษาไทย')
        self.assertEqual(by_code['th_TH']['flag'], 'flag-icon-th')
        self.assertEqual(by_code['en_US']['flag'], 'flag-icon-us')

    def test_current_flag_marks_env_lang(self):
        langs = self.env['ir.http'].with_context(lang='en_US')._wj_portal_langs()
        current = [l['code'] for l in langs if l['current']]
        self.assertEqual(current, ['en_US'])

    def test_inactive_lang_absent(self):
        self.assertNotIn('ja_JP', self._codes())


@tagged('post_install', '-at_install', 'wujia_lang_c10')
class TestSetLangRoute(HttpCase):

    def setUp(self):
        super().setUp()
        # Tự bật ngôn ngữ mình kiểm: DB chỉ cài khung không có sẵn vi_VN.
        self.env['res.lang']._activate_lang('th_TH')
        self.env['res.lang']._activate_lang('vi_VN')
        self.env.cr.flush()

    def test_guest_can_switch_without_account_write(self):
        public = self.env.ref('base.public_user')
        before = public.lang
        res = self.url_open('/portal/set-lang/th_TH', allow_redirects=False)
        self.assertIn(res.status_code, (302, 303))
        self.assertEqual(public.lang, before, "khách đổi lang không được ghi vào user")

    def test_inactive_code_ignored(self):
        res = self.url_open('/portal/set-lang/ja_JP', allow_redirects=False)
        self.assertIn(res.status_code, (302, 303))

    def test_logged_in_switch_writes_user_lang(self):
        user = self.env['res.users'].create({
            'name': 'C10 Lang', 'login': 'c10.lang@wujia.test', 'lang': 'en_US',
            'password': 'c10-lang-pw',
        })
        self.authenticate('c10.lang@wujia.test', 'c10-lang-pw')
        self.url_open('/portal/set-lang/th_TH', allow_redirects=False)
        self.assertEqual(user.lang, 'th_TH')

    def test_selector_renders_every_active_lang(self):
        user = self.env['res.users'].create({
            'name': 'C10 Sel', 'login': 'c10.sel@wujia.test', 'lang': 'vi_VN',
            'password': 'c10-sel-pw',
        })
        self.authenticate('c10.sel@wujia.test', 'c10-sel-pw')
        body = self.url_open('/portal/profile').text
        for code in ('en_US', 'vi_VN', 'th_TH'):
            self.assertIn('/portal/set-lang/%s' % code, body)
        self.assertIn('flag-icon-th', body)
        self.assertTrue(user.lang)  # sanity: user vẫn hợp lệ sau render


@tagged('post_install', '-at_install', 'wujia_lang_c10')
class TestGuestDefaultLang(HttpCase):
    """J-V0: khách chưa đăng nhập ở /portal mặc định tiếng Việt, không theo trình duyệt."""

    def setUp(self):
        super().setUp()
        self.env['res.lang']._activate_lang('vi_VN')
        self.env['res.lang']._activate_lang('th_TH')
        self.env.cr.flush()

    def _html_lang(self, url, accept='en-US,en;q=0.9'):
        body = self.url_open(url, headers={'Accept-Language': accept}).text
        return body.split('<html', 1)[1].split('>', 1)[0]

    def test_english_browser_gets_vietnamese_login(self):
        self.assertIn('lang="vi-VN"', self._html_lang('/portal/login'))

    def test_guest_choice_wins(self):
        self.url_open('/portal/set-lang/th_TH', allow_redirects=False)
        self.assertIn('lang="th-TH"', self._html_lang('/portal/login'))

    def test_logged_in_user_keeps_own_lang(self):
        self.env['res.users'].create({
            'name': 'V0 En', 'login': 'v0.en@wujia.test', 'lang': 'en_US', 'password': 'v0-en-pw',
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        self.authenticate('v0.en@wujia.test', 'v0-en-pw')
        self.assertIn('lang="en-US"', self._html_lang('/portal/profile', accept='vi-VN'))

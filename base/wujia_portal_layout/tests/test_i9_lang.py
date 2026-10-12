"""I9 — WJ-INSPECT-001 ngôn ngữ header trên route `website=True` · WJ-LANG-002 cờ ngôn ngữ PC không co."""
import os
import re

from odoo.tests import HttpCase, tagged

SELECTED = re.compile(r'id="dropdown-flag".*?flag-icon (flag-icon-\w+).*?class="selected-language">([^<]*)<', re.S)


@tagged('post_install', '-at_install', 'wujia_lang_i9')
class TestPortalFrontendRouteLang(HttpCase):
    """Route khai `website=True` (Khảo sát của nhóm khác) theo ngôn ngữ tài khoản như mọi route portal."""

    ROUTE = '/portal/inspection'

    def setUp(self):
        super().setUp()
        if 'wujia.franchise.inspection' not in self.env:
            self.skipTest('wujia_portal_inspection chưa cài — không có route website=True dưới /portal')
        for code in ('vi_VN', 'th_TH'):
            self.env['res.lang']._activate_lang(code)
        self.user = self.env['res.users'].create({
            'name': 'I9 Lang', 'login': 'i9.lang@wujia.test', 'lang': 'vi_VN', 'password': 'i9-lang-pw',
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        self.env.cr.flush()
        self.authenticate('i9.lang@wujia.test', 'i9-lang-pw')

    def _get(self, url, cookie=None):
        if cookie:
            self.opener.cookies.set('frontend_lang', cookie)
        else:
            self.opener.cookies.pop('frontend_lang', None)
        return self.url_open(url, allow_redirects=False)

    def _header(self, res):
        html_lang = res.text.split('<html', 1)[1].split('>', 1)[0]
        m = SELECTED.search(res.text)
        self.assertTrue(m, 'không thấy cờ đang chọn trên header PC')
        return html_lang, m.group(1), m.group(2).strip()

    def test_stale_english_cookie_does_not_override_user_lang(self):
        res = self._get(self.ROUTE, cookie='en_US')
        self.assertEqual(res.status_code, 200)
        html_lang, flag, label = self._header(res)
        self.assertIn('lang="vi-VN"', html_lang)
        self.assertEqual((flag, label), ('flag-icon-vn', 'Tiếng Việt'))

    def test_no_cookie_no_lang_prefix_redirect(self):
        res = self._get(self.ROUTE)
        self.assertEqual(res.status_code, 200, 'không được redirect sang /vi/portal/inspection')
        self.assertEqual(self._header(res)[1], 'flag-icon-vn')

    def test_same_header_as_portal_home(self):
        home = self._header(self._get('/portal/profile', cookie='en_US'))
        insp = self._header(self._get(self.ROUTE, cookie='en_US'))
        self.assertEqual(home, insp)

    def test_other_locale_follows_selection(self):
        self.url_open('/portal/set-lang/th_TH', allow_redirects=False)
        self.assertEqual(self.user.lang, 'th_TH')
        html_lang, flag, _label = self._header(self._get(self.ROUTE, cookie='vi_VN'))
        self.assertIn('lang="th-TH"', html_lang)
        self.assertEqual(flag, 'flag-icon-th')

    def test_unknown_record_redirects_without_prefix(self):
        res = self._get('/portal/inspection/detail/99999999', cookie='en_US')
        self.assertIn(res.status_code, (302, 303))
        self.assertNotIn('/vi/', res.headers.get('Location', ''))
        self.assertNotIn('/en/', res.headers.get('Location', ''))

    def test_guest_still_sent_to_login(self):
        self.logout()
        res = self.url_open(self.ROUTE, allow_redirects=False)
        self.assertIn(res.status_code, (302, 303))
        self.assertIn('login', res.headers.get('Location', ''))


@tagged('post_install', '-at_install', 'wujia_lang_i9')
class TestPcLangFlagCss(HttpCase):
    """WJ-LANG-002: cờ đang chọn trong pill PC giữ ô 20×15, pill nới theo nhãn (tối thiểu 118)."""

    CSS = os.path.join(os.path.dirname(__file__), '..', 'static', 'assets', 'css', '_pc_account.css')

    def setUp(self):
        super().setUp()
        with open(self.CSS, encoding='utf-8') as f:
            self.css = re.sub(r'/\*.*?\*/', '', f.read(), flags=re.S)

    def _rule(self, selector):
        m = re.search(re.escape(selector) + r'\s*\{([^}]*)\}', self.css)
        self.assertTrue(m, 'thiếu rule %s' % selector)
        return re.sub(r'\s+', ' ', m.group(1))

    def test_flag_fixed_box(self):
        body = self._rule('.wujia-navbar .navbar-container ul.nav li.dropdown-language > a.nav-link i.flag-icon')
        for decl in ('flex: 0 0 20px', 'width: 20px', 'height: 15px'):
            self.assertIn(decl, body)

    def test_pill_grows_with_label(self):
        body = self._rule('.wujia-navbar .dropdown-language > .nav-link')
        self.assertIn('width: auto !important', body)
        self.assertIn('min-width: 118px', body)
        self.assertNotRegex(body, r'(^|[;{ ])width: 118px')
        self.assertIn('white-space: nowrap',
                      self._rule('.wujia-navbar .dropdown-language > .nav-link .selected-language'))

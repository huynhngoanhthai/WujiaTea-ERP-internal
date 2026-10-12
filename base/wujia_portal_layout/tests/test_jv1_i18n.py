"""J-V1 — Việt hoá source của khung: câu gốc tiếng Anh, tiếng Việt qua `i18n/vi_VN.po`.

User en_US thấy tiếng Anh, user vi_VN thấy y như trước; chuỗi JS đi qua `data-wj-msg-*`
(khối `#wj-msgs`, đọc bằng `wjMsg()`); viền đỏ form đổi mật khẩu theo `error_field`,
không dò chữ trong câu lỗi (câu lỗi đã dịch thì dò chữ hỏng ở mọi ngôn ngữ khác).
"""
import re

from lxml import etree, html

from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase

from .common import load_vi
from .test_e3_pagination import _pgn


def _text(el):
    return re.sub(r'\s+', ' ', ''.join(el.itertext())).strip()


@tagged('post_install', '-at_install', 'wujia_jv1')
class TestDefaultLabelsFollowLang(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env_vi = load_vi(cls.env)
        cls.env_en = cls.env(context=dict(cls.env.context, lang='en_US'))

    def _render(self, env, tmpl, values):
        return html.fromstring(str(env['ir.qweb']._render(tmpl, values)))

    def test_section_header_view_all(self):
        values = {'sh_title': 'T', 'sh_action_url': '/x'}
        self.assertEqual(
            self._render(self.env_en, 'wujia_portal_layout.wj_section_header', values)
            .xpath('.//a/span')[0].text, 'View all')
        self.assertEqual(
            self._render(self.env_vi, 'wujia_portal_layout.wj_section_header', values)
            .xpath('.//a/span')[0].text, 'Xem tất cả')

    def test_filter_bar_defaults(self):
        values = {'fb_platform': 'pc', 'fb_action': '/x', 'fb_reset_url': '/x',
                  'fb_search': {'name': 'q'}, 'fb_dates': {'from': '', 'to': ''},
                  'fb_selects': [{'name': 's', 'options': []}]}
        for env, words in ((self.env_en, ['Search', 'Clear filters', 'All', 'From', 'To']),
                           (self.env_vi, ['Tìm kiếm', 'Xóa lọc', 'Tất cả', 'Từ', 'Đến'])):
            root = self._render(env, 'wujia_portal_layout.wj_filter_bar', values)
            text = _text(root)
            for word in words:
                self.assertIn(word, text, env.lang)
            dates = [i.get('aria-label') for i in root.xpath('.//input[@type="date"]')]
            self.assertEqual(dates, ['From date', 'To date'] if env.lang == 'en_US'
                             else ['Từ ngày', 'Đến ngày'])

    def test_pagination_next_and_page_size(self):
        """`Trang sau` / `/ trang` / `Trang x / y` từng là tiếng Việt KHÔNG dấu ⇒ máy quét bỏ sót."""
        pgn = _pgn(30, 2, 10, item_label='x', page_size_options=(10, 20))
        arch = ('<t t-name="wujia_portal_layout.wj_jv1_pgn">'
                '<t t-call="wujia_portal_layout.wj_pagination"/></t>')
        view = self.env['ir.ui.view'].create({
            'name': 'jv1 pgn', 'type': 'qweb', 'key': 'wujia_portal_layout.wj_jv1_pgn', 'arch_db': arch})
        en = _text(html.fromstring(str(self.env_en['ir.qweb']._render(view.id, {'pgn': pgn}))))
        vi = _text(html.fromstring(str(self.env_vi['ir.qweb']._render(view.id, {'pgn': pgn}))))
        self.assertIn('Next page', en)
        self.assertIn('Page 2 / 3', en)
        self.assertIn('10 / page', en)
        self.assertNotIn('Trang', en)
        self.assertIn('Trang sau', vi)
        self.assertIn('Trang 2 / 3', vi)
        self.assertIn('10 / trang', vi)


@tagged('post_install', '-at_install', 'wujia_jv1')
class TestPortalPagesByLang(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_vi(cls.env)
        for lang in ('en_US', 'vi_VN'):
            cls.env['res.users'].create({
                'name': 'JV1 %s' % lang, 'login': 'jv1.%s@wujia.test' % lang,
                'password': 'jv1-pw-123', 'lang': lang})

    def _open(self, lang, url):
        self.authenticate('jv1.%s@wujia.test' % lang, 'jv1-pw-123')
        res = self.url_open(url, timeout=30)
        self.assertEqual(res.status_code, 200, url)
        return etree.HTML(res.text)

    def test_wj_msgs_block_follows_lang(self):
        expect = {
            'en_US': ('You have unsaved changes. Leave this page?', 'Show', 'Hide'),
            'vi_VN': ('Bạn có thay đổi chưa lưu. Rời khỏi trang?', 'Hiện', 'Ẩn'),
        }
        for lang, (unsaved, show, hide) in expect.items():
            block = self._open(lang, '/portal/profile').xpath("//div[@id='wj-msgs']")
            self.assertEqual(len(block), 1, lang)
            self.assertEqual(block[0].get('data-wj-msg-unsaved-changes'), unsaved)
            self.assertEqual(block[0].get('data-wj-msg-show'), show)
            self.assertEqual(block[0].get('data-wj-msg-hide'), hide)
            self.assertIsNotNone(block[0].get('hidden'))

    def test_wj_msgs_on_login_page(self):
        """Layout đăng nhập không nạp bundle web.assets_frontend ⇒ khối + wj_msg.js phải có riêng."""
        res = self.url_open('/portal/login', timeout=30)
        doc = etree.HTML(res.text)
        self.assertEqual(len(doc.xpath("//div[@id='wj-msgs']")), 1)
        self.assertTrue(doc.xpath("//script[contains(@src, '/static/assets/js/wj_msg.js')]"))

    def test_profile_labels_follow_lang(self):
        for lang, label in (('en_US', 'Personal information'), ('vi_VN', 'Thông tin cá nhân')):
            self.assertIn(label, _text(self._open(lang, '/portal/profile')), lang)

    def _change_password(self, lang, old, new, confirm):
        login = 'jv1.%s@wujia.test' % lang
        doc = self._open(lang, '/portal/change-password')
        token = doc.xpath("//input[@name='csrf_token']/@value")[0]
        res = self.url_open('/portal/change-password', data={
            'csrf_token': token, 'old-password': old, 'new-password': new, 'con-password': confirm,
        }, timeout=30)
        self.assertEqual(res.status_code, 200, login)
        doc = etree.HTML(res.text)
        boxes = doc.xpath("//div[contains(concat(' ', @class, ' '), ' wj-pc-acct-pw-input ')]")
        self.assertEqual(len(boxes), 3)
        return ['is-error' in (b.get('class') or '').split() for b in boxes]

    def test_error_field_marks_right_box_in_every_lang(self):
        for lang in ('en_US', 'vi_VN'):
            self.assertEqual(self._change_password(lang, 'jv1-pw-123', 'abcdefgh1', 'zzzzzzzz9'),
                             [False, False, True], '%s: confirm' % lang)
            self.assertEqual(self._change_password(lang, 'jv1-pw-123', 'short', 'short'),
                             [False, True, False], '%s: new' % lang)
            self.assertEqual(self._change_password(lang, 'wrong-old-pw', 'abcdefgh1', 'abcdefgh1'),
                             [True, False, False], '%s: old' % lang)

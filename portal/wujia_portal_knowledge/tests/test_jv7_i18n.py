"""J-V7 — câu gốc của màn Kiến thức là tiếng Anh; user vi_VN phải thấy y chữ trước phiên.

Bảng VN chép nguyên từ source TRƯỚC J-V7 (HEAD 8a0d5df6).
"""

import re

from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase

from odoo.addons.wujia_knowledge.tests.common import load_vi
from odoo.addons.wujia_knowledge.tests.test_knowledge import KnowledgeCommon

KNOWLEDGE_MODULES = ('wujia_portal_layout', 'wujia_portal_base', 'wujia_knowledge', 'wujia_portal_knowledge')

# Badge bài viết (dict viết cứng trong QWeb trước J-V7) — PC list + mobile list + mobile detail.
BADGE_VI = {'mandatory': 'Bắt buộc', 'important': 'Quan trọng', 'new': 'Mới'}
BADGE_EN = {'mandatory': 'Mandatory', 'important': 'Important', 'new': 'New'}


def _text(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))


@tagged('post_install', '-at_install', 'wujia_knowledge', 'wujia_jv7')
class TestJv7Labels(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env_vi = load_vi(cls.env, KNOWLEDGE_MODULES)
        cls.env_en = cls.env(context=dict(cls.env.context, lang='en_US'))

    def test_pager_label(self):
        from odoo.addons.wujia_portal_knowledge.controllers import portal as ctrl
        src = open(ctrl.__file__, encoding='utf-8').read()
        self.assertIn("item_label=_lt('articles')", src)
        self.assertEqual(self.env_vi._(ctrl._lt('articles')), 'bài viết')

    def test_view_labels_in_arch(self):
        cases = {
            'wujia_portal_knowledge.portal_knowledge_list': (
                'Tìm bài viết...', 'Tìm kiếm bài viết...', 'Tài liệu mới cập nhật', 'bài viết',
                *BADGE_VI.values()),
            'wujia_portal_knowledge.portal_knowledge_detail': ('lượt xem', *BADGE_VI.values()),
        }
        for xmlid, words in cases.items():
            view = self.env.ref(xmlid)
            arch_vi = re.sub(r'<!--.*?-->', '', view.with_env(self.env_vi).arch, flags=re.S)
            arch_en = re.sub(r'<!--.*?-->', '', view.with_env(self.env_en).arch, flags=re.S)
            for word in words:
                with self.subTest(view=xmlid, word=word):
                    self.assertIn(word, arch_vi)
                    self.assertNotIn(word, arch_en)
        # Badge: 3 bộ nhãn (PC list, mobile list, mobile detail) đều là biến t-set, không còn dict chữ.
        arch_en = self.env.ref('wujia_portal_knowledge.portal_knowledge_list').with_env(self.env_en).arch
        self.assertEqual(arch_en.count('<t t-set="_kn_t_mandatory">Mandatory</t>'), 2)


@tagged('post_install', '-at_install', 'wujia_knowledge', 'wujia_jv7')
class TestJv7PortalByLang(KnowledgeCommon, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_knowledge()
        load_vi(cls.env, KNOWLEDGE_MODULES)
        portal = cls.env.ref('base.group_portal')
        for login, lang in (('jv7_knw_vi', 'vi_VN'), ('jv7_knw_en', 'en_US')):
            cls.env['res.users'].create({
                'name': login, 'login': login, 'password': login, 'lang': lang,
                'group_ids': [(6, 0, [portal.id])]})
        # Danh mục riêng có đúng MỘT bài ⇒ kiểm số ít EN ("1 article").
        cls.cat = cls.env['wujia.knowledge.category'].create({'name': 'JV7 Category', 'sequence': 99})
        cls.art = cls._article('JV7 bài bắt buộc', 'jv7-bat-buoc', category_id=cls.cat.id,
                               portal_badge='mandatory')

    def _get(self, login, url):
        self.authenticate(login, login)
        res = self.url_open(url, timeout=30)
        self.assertEqual(res.status_code, 200)
        return res.text

    def test_list_vi_and_en(self):
        url = '/portal/knowledge?category_id=%s' % self.cat.id
        vi = self._get('jv7_knw_vi', url)
        en = self._get('jv7_knw_en', url)
        self.assertIn('JV7 bài bắt buộc', vi)
        for word in ('Tìm bài viết...', 'Tìm kiếm bài viết...', BADGE_VI['mandatory']):
            self.assertIn(word, vi)
            self.assertNotIn(word, en)
        for word in ('Search articles...', 'Search for articles...', BADGE_EN['mandatory']):
            self.assertIn(word, en)
        self.assertIn('1 bài viết', _text(vi))
        self.assertRegex(_text(en), r'\b1 article\b')
        self.assertNotRegex(_text(en), r'\b1 articles\b')

    def test_recent_title_without_category(self):
        vi = self._get('jv7_knw_vi', '/portal/knowledge')
        en = self._get('jv7_knw_en', '/portal/knowledge')
        self.assertIn('Tài liệu mới cập nhật', vi)
        self.assertIn('Recently updated documents', en)
        self.assertNotIn('Tài liệu mới cập nhật', en)

    def test_detail_view_count_singular(self):
        url = '/portal/knowledge/%s' % self.art.slug
        for login, expect, wrong in (('jv7_knw_vi', r'\b1 lượt xem\b', None),
                                     ('jv7_knw_en', r'\b1 view\b', r'\b1 views\b')):
            with self.subTest(login=login):
                # Mở trang tăng lượt xem trước khi render ⇒ đặt 0 để trang hiện đúng 1.
                self.env.cr.execute(
                    "UPDATE wujia_knowledge_article SET view_count = 0 WHERE id = %s", (self.art.id,))
                self.art.invalidate_recordset(['view_count'])
                html = _text(self._get(login, url))
                self.assertRegex(html, expect)
                if wrong:
                    self.assertNotRegex(html, wrong)
                    self.assertIn(BADGE_EN['mandatory'], html)
                else:
                    self.assertIn(BADGE_VI['mandatory'], html)

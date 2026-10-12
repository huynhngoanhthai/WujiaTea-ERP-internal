"""C8 — CMP-SH-001 SectionHeader: hợp đồng render của component wj_section_header.

Bám từng gạch đầu dòng cột `Kết quả mong muốn` của issue UI-SECTIONHEADER-001 (STT 83):
title là heading THẬT theo level từng màn, TỐI ĐA một right slot, count hiện cả khi = 0
và dùng từ đầy đủ, meta ra markup thô để `wj_ajax_list` swap được.

Call site của 8 module đã dời sang `wujia_portal_base/tests/test_scan_c8_section_header.py`
ở F5b.
"""
from lxml import html
from markupsafe import Markup

from odoo.tests import TransactionCase, tagged

from .common import load_vi

TMPL = 'wujia_portal_layout.wj_section_header'


@tagged('post_install', '-at_install', 'wujia_section_header_c8')
class TestSectionHeaderComponent(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = load_vi(cls.env)

    def _root(self, **values):
        values.setdefault('sh_title', 'Tiêu đề')
        out = self.env['ir.qweb']._render(TMPL, values)
        return html.fragment_fromstring(str(out).strip())

    # --- title là heading thật, đúng level từng màn -----------------------

    def test_default_level_is_h3(self):
        self.assertEqual(self._root()[0].tag, 'h3')

    def test_level_follows_caller(self):
        for lvl, tag in ((2, 'h2'), (3, 'h3'), (4, 'h4')):
            with self.subTest(level=lvl):
                self.assertEqual(self._root(sh_level=lvl)[0].tag, tag)

    def test_title_never_span(self):
        # Spec cấm bọc title bằng <span>; và chỉ có ĐÚNG MỘT heading trong header.
        root = self._root(sh_level=2, sh_meta=Markup('<span>3 mục</span>'))
        heads = root.xpath('.//h1|.//h2|.//h3|.//h4|.//h5|.//h6')
        self.assertEqual(len(heads), 1)
        self.assertEqual(heads[0].get('class'), 'wj-section-header__title')
        self.assertEqual(heads[0].text, 'Tiêu đề')

    def test_unknown_level_falls_back_to_h3(self):
        self.assertEqual(self._root(sh_level=6)[0].tag, 'h3')

    # --- TỐI ĐA một right slot -------------------------------------------

    def test_action_wins_over_control_and_meta(self):
        root = self._root(sh_action_url='/portal/delivery',
                          sh_control=Markup('<select id="c"/>'),
                          sh_meta=Markup('<span id="m">3 mục</span>'))
        self.assertTrue(root.xpath('.//a[@class="wj-section-header__action"]'))
        self.assertFalse(root.xpath('.//*[@id="c"]'))
        self.assertFalse(root.xpath('.//*[@id="m"]'))
        self.assertIn('wj-section-header--action', root.get('class'))

    def test_control_wins_over_meta(self):
        root = self._root(sh_control=Markup('<select id="c"/>'),
                          sh_meta=Markup('<span id="m">3 mục</span>'))
        self.assertTrue(root.xpath('.//*[@id="c"]'))
        self.assertFalse(root.xpath('.//*[@id="m"]'))
        self.assertIn('wj-section-header--control', root.get('class'))

    def test_default_variant_has_no_right_slot(self):
        root = self._root()
        self.assertEqual(len(root), 1)
        self.assertIn('wj-section-header--none', root.get('class'))

    def test_action_label_default_and_override(self):
        self.assertEqual(
            self._root(sh_action_url='/x').xpath('.//a/span')[0].text, 'Xem tất cả')
        self.assertEqual(
            self._root(sh_action_url='/x', sh_action_label='Xem thêm')
            .xpath('.//a/span')[0].text, 'Xem thêm')

    # --- meta là markup THÔ, không bị bọc thêm element ---------------------

    def test_meta_is_direct_child_not_wrapped(self):
        # `wj_ajax_list` swap theo id: meta bị bọc thêm 1 lớp là hỏng slot (bài học B3a).
        root = self._root(sh_meta=Markup('<span id="m" class="wj-section-header__meta">'
                                         '0 sản phẩm</span>'))
        self.assertEqual([c.get('id') for c in root][1:], ['m'])

    def test_meta_keeps_multiple_top_level_nodes(self):
        root = self._root(sh_meta=Markup('<span id="a"/><span id="b"/>'))
        self.assertEqual([c.get('id') for c in root][1:], ['a', 'b'])

    # --- visibility / id / class truyền qua --------------------------------

    def test_platform_bakes_visibility(self):
        self.assertIn('d-flex d-lg-none', self._root(sh_platform='m').get('class'))
        self.assertIn('d-none d-lg-flex', self._root(sh_platform='pc').get('class'))
        self.assertIn('d-flex', self._root().get('class'))

    def test_id_and_extra_class(self):
        root = self._root(sh_id='wj-hist-head', sh_class='wj-section-header--inline')
        self.assertEqual(root.get('id'), 'wj-hist-head')
        self.assertIn('wj-section-header--inline', root.get('class'))

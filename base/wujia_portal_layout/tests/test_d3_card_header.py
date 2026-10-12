"""D3 — CMP-CH-001 CardHeader: hợp đồng render của component wj_card_header.

Bám từng gạch đầu dòng cột `Kết quả mong muốn` của issue UI-CARDHEADER-001 (STT 125):
title là heading THẬT theo level từng màn, TỐI ĐA một trailing, count 0 vẫn hiện,
trailing ra markup thô để `wj_ajax_list` swap được, icon trang trí có aria-hidden,
compact là mặc định và migrate KHÔNG được cộng chồng margin header với body.

F5b: call site của 12 module nghiệp vụ đã dời sang
`wujia_portal_base/tests/test_scan_d3_card_header.py` (quét nhiều màn),
`wujia_portal_debt` · `wujia_portal_exam` (màn của riêng module) và
`wujia_portal_base/tests/test_handover_inspection.py` (bàn giao nhóm Khảo sát).
"""
import os

from lxml import html
from markupsafe import Markup

from odoo.tests import TransactionCase, tagged

from .common import load_vi

TMPL = 'wujia_portal_layout.wj_card_header'
CSS_DIR = os.path.join(os.path.dirname(__file__), '..', 'static', 'assets', 'css')


@tagged('post_install', '-at_install', 'wujia_card_header_d3')
class TestCardHeaderComponent(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = load_vi(cls.env)

    def _root(self, **values):
        values.setdefault('ch_title', 'Tiêu đề')
        out = self.env['ir.qweb']._render(TMPL, values)
        return html.fragment_fromstring(str(out).strip())

    def _title(self, root):
        heads = root.xpath('.//h1|.//h2|.//h3|.//h4|.//h5|.//h6')
        self.assertEqual(len(heads), 1, 'phải có ĐÚNG một heading trong CardHeader')
        return heads[0]

    # --- title là heading thật, đúng level từng màn -----------------------

    def test_default_level_is_h3(self):
        self.assertEqual(self._title(self._root()).tag, 'h3')

    def test_level_follows_caller(self):
        for lvl, tag in ((2, 'h2'), (3, 'h3'), (4, 'h4')):
            with self.subTest(level=lvl):
                self.assertEqual(self._title(self._root(ch_level=lvl)).tag, tag)

    def test_unknown_level_falls_back_to_h3(self):
        self.assertEqual(self._title(self._root(ch_level=6)).tag, 'h3')

    def test_title_is_never_p_or_span(self):
        # Đúng ca BA than: `<p class="wujia-mdash-title">` giả heading.
        root = self._root(ch_subtitle='phụ', ch_meta=Markup('<span>3 mục</span>'))
        title = self._title(root)
        self.assertEqual(title.get('class'), 'wj-card-header__title')
        self.assertEqual(title.text, 'Tiêu đề')

    # --- TỐI ĐA một trailing ---------------------------------------------

    def test_action_wins_over_control_and_meta(self):
        root = self._root(ch_action_url='/portal/support',
                          ch_control=Markup('<select id="c"/>'),
                          ch_meta=Markup('<span id="m">3 mục</span>'))
        self.assertTrue(root.xpath('.//a[@class="wj-card-header__action"]'))
        self.assertFalse(root.xpath('.//*[@id="c"]'))
        self.assertFalse(root.xpath('.//*[@id="m"]'))
        self.assertIn('wj-card-header--action', root.get('class'))

    def test_control_wins_over_meta(self):
        root = self._root(ch_control=Markup('<select id="c"/>'),
                          ch_meta=Markup('<span id="m">3 mục</span>'))
        self.assertTrue(root.xpath('.//*[@id="c"]'))
        self.assertFalse(root.xpath('.//*[@id="m"]'))
        self.assertIn('wj-card-header--control', root.get('class'))

    def test_no_trailing_by_default(self):
        root = self._root()
        self.assertEqual(len(root), 1)          # chỉ có __lead
        self.assertIn('wj-card-header--none', root.get('class'))

    def test_action_label_default_and_override(self):
        self.assertEqual(
            self._root(ch_action_url='/x').xpath('.//a/span')[0].text, 'Xem tất cả')
        self.assertEqual(
            self._root(ch_action_url='/x', ch_action_label='Xem thêm')
            .xpath('.//a/span')[0].text, 'Xem thêm')

    # --- trailing là markup THÔ, không bị bọc thêm element -----------------

    def test_trailing_is_direct_child_not_wrapped(self):
        # `wj_ajax_list` swap theo id: bọc thêm 1 lớp là hỏng slot (bài học B3a).
        root = self._root(ch_meta=Markup('<span id="m" class="wj-card-header__meta">'
                                         '0 ticket</span>'))
        self.assertEqual([c.get('id') for c in root][1:], ['m'])

    def test_trailing_keeps_multiple_top_level_nodes(self):
        root = self._root(ch_meta=Markup('<span id="a"/><span id="b"/>'))
        self.assertEqual([c.get('id') for c in root][1:], ['a', 'b'])

    # --- variant: compact là MẶC ĐỊNH (BA chốt compact-first) --------------

    def test_compact_is_default(self):
        self.assertIn('wj-card-header--compact', self._root().get('class'))

    def test_regular_only_when_asked(self):
        cls = self._root(ch_variant='regular').get('class')
        self.assertIn('wj-card-header--regular', cls)
        self.assertNotIn('wj-card-header--compact', cls)

    def test_unknown_variant_falls_back_to_compact(self):
        self.assertIn('wj-card-header--compact',
                      self._root(ch_variant='cozy').get('class'))

    # --- icon / subtitle ---------------------------------------------------

    def test_decorative_icon_is_aria_hidden(self):
        icon = self._root(ch_icon='life-buoy').xpath('.//*[@class="wj-card-header__icon"]')
        self.assertEqual(len(icon), 1)
        self.assertEqual(icon[0].get('aria-hidden'), 'true')
        self.assertIsNone(icon[0].get('role'))

    def test_meaningful_icon_gets_accessible_name(self):
        icon = self._root(ch_icon='alert-triangle', ch_icon_label='Cảnh báo') \
            .xpath('.//*[@class="wj-card-header__icon"]')[0]
        self.assertEqual(icon.get('role'), 'img')
        self.assertEqual(icon.get('aria-label'), 'Cảnh báo')
        self.assertIsNone(icon.get('aria-hidden'))

    def test_no_icon_node_when_not_asked(self):
        self.assertFalse(self._root().xpath('.//*[@class="wj-card-header__icon"]'))

    def test_subtitle_sits_under_title_inside_lead(self):
        root = self._root(ch_subtitle='Thông tin chính của cửa hàng')
        sub = root.xpath('.//p[@class="wj-card-header__subtitle"]')
        self.assertEqual(len(sub), 1)
        self.assertEqual(sub[0].text, 'Thông tin chính của cửa hàng')
        # subtitle phải là em của title trong cùng __text, không nằm ở trailing
        self.assertEqual(sub[0].getparent().get('class'), 'wj-card-header__text')

    def test_no_subtitle_node_when_not_asked(self):
        self.assertFalse(self._root().xpath('.//p[@class="wj-card-header__subtitle"]'))

    # --- divider mặc định TẮT ---------------------------------------------

    def test_divider_off_by_default(self):
        self.assertNotIn('wj-card-header--divider', self._root().get('class'))

    def test_divider_opt_in(self):
        self.assertIn('wj-card-header--divider',
                      self._root(ch_divider=True).get('class'))

    # --- visibility / id / class truyền qua --------------------------------

    def test_platform_bakes_visibility(self):
        self.assertIn('d-flex d-lg-none', self._root(ch_platform='m').get('class'))
        self.assertIn('d-none d-lg-flex', self._root(ch_platform='pc').get('class'))
        self.assertIn('d-flex', self._root().get('class'))

    def test_id_and_extra_class(self):
        root = self._root(ch_id='wj-sup-head', ch_class='wj-card-header--flush')
        self.assertEqual(root.get('id'), 'wj-sup-head')
        self.assertIn('wj-card-header--flush', root.get('class'))


@tagged('post_install', '-at_install', 'wujia_card_header_d3')
class TestCardHeaderCss(TransactionCase):
    """Rule dáng của component nằm ở CSS của chính khung."""

    def _css(self, name='_components.css'):
        with open(os.path.join(CSS_DIR, name), encoding='utf-8') as fh:
            return fh.read()

    def test_title_colour_beats_theme_card_body_rule(self):
        # Theme Vuexy có `:where(.card…) .card-body:not(…) h4 { color: inherit }` = (0,4,1);
        # bỏ `!important` là title trong `.card > .card-body` rơi về màu body — đo được ở
        # D3b trên /portal/order/product/<id> (UAT #212529, local đen).
        css = self._css()
        # cắt ở `\n}` chứ không phải `}`: trong block có comment chứa `{ … !important }`
        block = css.split('.wj-card-header__title {', 1)[1].split('\n}', 1)[0]
        self.assertIn('color: var(--wujia-text-primary) !important', block)

    def test_sublabel_size_lives_in_one_shared_rule(self):
        # Trước phiên này `portal_return.css` và `portal_inspection.css` có HAI bản
        # trùng tuyệt đối cho cùng vai trò "nhãn phụ giữa thân card". Gộp về một
        # modifier ở component: sửa một chỗ là sửa hết (đồng bộ ở tầng code).
        css = self._css()
        self.assertRegex(
            css,
            r'\.wj-card-header\.wj-card-header--any\.wj-card-header--sublabel'
            r'\s+\.wj-card-header__title,[^{]*\{[^}]*font-size:\s*\.875rem\s*!important')
        # Đủ ba nền tảng, không thì bản mobile/pc rơi về 18px của component.
        for plat in ('any', 'm', 'pc'):
            self.assertIn('.wj-card-header.wj-card-header--%s.wj-card-header--sublabel'
                          % plat, css)

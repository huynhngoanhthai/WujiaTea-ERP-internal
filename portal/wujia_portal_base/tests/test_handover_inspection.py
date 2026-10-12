"""BÀN GIAO — guard giao diện của màn Khảo sát (`wujia_portal_inspection`).

Các guard dưới đây kiểm CHÍNH màn Khảo sát, tức là việc của module đó. F5b gỡ chúng
khỏi `wujia_portal_layout` (khung không được biết màn nào) nhưng KHÔNG ghi vào module
của nhóm Khảo sát theo luật cụm F §0 — nên chúng tạm trú ở đây.

⇒ Anh Thái dời trọn file này về `wujia_portal_inspection/tests/` khi tiện; nội dung
assert giữ nguyên, không sửa gì thêm.
"""
import os
import re

from odoo.tests import TransactionCase, tagged

from .common import find_view, need

INSP = 'wujia_portal_inspection/static/src/css/portal_inspection.css'


def _contrast_hex(fg, bg):
    """Tỉ số tương phản WCAG 2.1 giữa hai màu hex."""
    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    a, b = sorted((lum(fg), lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


@tagged('post_install', '-at_install', 'wujia_card_header_d3')
class TestInspectionCardHeader(TransactionCase):

    INSP = INSP

    CALL_SITES = {
        'wujia_portal_inspection.portal_inspection_detail': 4,
        'wujia_portal_inspection.portal_inspection_remediation_form': 2,
    }

    def _arch(self, xmlid):
        need(self, xmlid)
        return self.env.ref(xmlid).arch_db

    def _css(self, module, name):
        path = os.path.join(os.path.dirname(__file__), '..', '..', module,
                            'static', 'src', 'css', name)
        with open(path, encoding='utf-8') as fh:
            return fh.read()

    def _read(self, rel):
        path = os.path.join(os.path.dirname(__file__), '..', '..', rel)
        with open(path, encoding='utf-8') as fh:
            return fh.read()

    def test_call_sites_use_component(self):
        for xmlid, count in self.CALL_SITES.items():
            with self.subTest(view=xmlid):
                self.assertEqual(
                    self._arch(xmlid).count('wujia_portal_layout.wj_card_header'), count)

    def test_inspection_tab_buttons_keep_their_ids(self):
        # `portal_inspection_detail.js` lấy 2 nút này bằng getElementById; bọc vào
        # ch_control mà đổi id thì tab chết im lặng, không có lỗi JS.
        arch = self._arch('wujia_portal_inspection.portal_inspection_detail')
        for btn_id in ('pc_tab_btn_checklist', 'pc_tab_btn_exam'):
            self.assertIn(btn_id, arch)
        js_path = os.path.join(os.path.dirname(__file__), '..', '..',
                               'wujia_portal_inspection', 'static', 'src', 'js',
                               'portal_inspection_detail.js')
        with open(js_path, encoding='utf-8') as fh:
            js = fh.read()
        for btn_id in ('pc_tab_btn_checklist', 'pc_tab_btn_exam'):
            self.assertIn(btn_id, js)

    def test_section_head_severe_branch_repaints_the_title(self):
        # Nền đỏ đặt bằng inline style nên màu trắng KHÔNG thừa kế xuống được:
        # component khai color ngay trên `.wj-card-header__title`.
        css = self._css('wujia_portal_inspection', 'portal_inspection.css')
        self.assertRegex(
            css,
            r'\.wj-insp-sechead--severe \.wj-card-header__title\s*\{'
            r'[^}]*color:\s*#ffffff\s*!important')
        self.assertRegex(
            css,
            r'\.wj-insp-sechead--severe \.wj-card-header__subtitle\s*\{'
            r'[^}]*color:\s*rgba\(255, 255, 255, \.8\)\s*!important')
        # Bản mobile: rule màu xanh của nó đã là (0,4,0)!important nên rule severe
        # phải bám đủ `.wj-card-header.wj-insp-sechead__hb` mới thắng.
        self.assertRegex(
            css,
            r'\.wj-insp-sechead--m\.wj-insp-sechead--severe\s+'
            r'\.wj-card-header\.wj-insp-sechead__hb \.wj-card-header__title\s*\{'
            r'[^}]*color:\s*#ffffff\s*!important')

    def test_section_head_keeps_its_15px(self):
        self.assertRegex(
            self._css('wujia_portal_inspection', 'portal_inspection.css'),
            r'\.wj-insp-sechead \.wj-card-header\.wj-insp-sechead__hb'
            r'\s+\.wj-card-header__title\s*\{[^}]*font-size:\s*15px\s*!important')

    def test_inspection_sublabels_keep_their_own_shape(self):
        # Nhãn phụ giữa thân card (`Phân bổ kết quả`) và tiêu đề tiêu chí trong hộp
        # `Tiêu chí vi phạm` — mỗi cái một cỡ THIẾT KẾ, đều nhỏ hơn tiêu đề card.
        css = self._css('wujia_portal_inspection', 'portal_inspection.css')
        # `wj-insp-sublabel` nay lấy cỡ từ modifier chung `wj-card-header--sublabel`
        # (D3 REVIEW 2026-09-04) — call site phải mang kèm modifier đó.
        self.assertIn('wj-card-header--sublabel wj-insp-sublabel',
                      self._arch('wujia_portal_inspection.portal_inspection_detail'))
        self.assertRegex(
            css,
            r'\.wj-pc-card \.wj-card-header\.wj-insp-critlabel'
            r'\s+\.wj-card-header__title\s*\{[^}]*font-size:\s*14px\s*!important')

    def test_severe_flag_computed_once(self):
        # Ba chỗ (nền, màu chữ, badge) phải dùng CHUNG một điều kiện, không chép tay.
        arch = self._arch('wujia_portal_inspection.portal_inspection_detail')
        # 2 vòng lặp (PC + mobile), mỗi vòng đúng MỘT lần tính cờ.
        self.assertEqual(arch.count('_sec_sev'), 6)
        self.assertEqual(arch.count("sec.get('is_severe') and sec.get('total_deducted') &gt; 0"), 2)

    def test_mobile_category_head_meets_wcag_aa(self):
        # #0284c7 trên #f1f5f9 chỉ được 3.74. Guard tính THẬT tỉ số tương phản
        # chứ không chỉ so chuỗi màu — đổi màu khác mà vẫn tối là vẫn đỏ.
        css = self._read(self.INSP)
        m = re.search(
            r'\.wj-insp-sechead--m \.wj-card-header\.wj-insp-sechead__hb'
            r'\s+\.wj-card-header__title\s*\{[^}]*color:\s*(#[0-9a-fA-F]{6})',
            css)
        self.assertTrue(m, 'mất rule màu head danh mục bản mobile')
        self.assertGreaterEqual(round(_contrast_hex(m.group(1), '#f1f5f9'), 2), 4.5)

    def test_category_severe_flag_computed_once_per_loop(self):
        # Bài học `_sec_sev` của D3f, áp cho vòng lặp thẻ phân bổ: 2 vòng (PC +
        # mobile), mỗi vòng đúng MỘT lần tính cờ, hai chỗ dùng lại.
        arch = self._arch('wujia_portal_inspection.portal_inspection_detail')
        self.assertEqual(arch.count('_cs_sev'), 6)
        self.assertEqual(arch.count("c_sum.get('is_severe')"), 2)


D4H_CSS = ('wujia_portal_inspection', 'portal_inspection.css')
D4H_SHAPE = ('background', 'background-color', 'border', 'border-radius',
             'box-shadow', 'padding', 'overflow')
D4H_SHELL = 'wj-surface-card wj-surface-card--%s wj-surface-card--compact wj-surface-card--padded '

# `(?:^|\s)card`: token đứng ĐẦU thuộc tính (`class="card wj-…"`) không có ký
# tự trắng đứng trước và `^` chỉ khớp đầu chuỗi ⇒ lọt. Đột biến D4f #1 bắt được.
_CLS_ATTR = re.compile(
    r'(?:class|t-attf-class)="([^"]*)"'
    r'|t-value="\'([^\']*)\'"'
)


def _has_card_token(arch):
    for a, b in _CLS_ATTR.findall(arch or ''):
        if 'card' in (a or b).split():
            return True
    return False


MOD_DIR = os.path.join(os.path.dirname(__file__), '..', '..')


def _mod_css(module, name):
    with open(os.path.join(MOD_DIR, module, 'static', 'src', 'css', name),
              encoding='utf-8') as fh:
        return fh.read()


def _strip_comments(css):
    return re.sub(r'/\*.*?\*/', '', css, flags=re.S)


PROP = r'(?:^|;)\s*%s\s*:'


def _declares(body, prop):
    return re.search(PROP % re.escape(prop), body) is not None


def _rules_anywhere(css, selector):
    css = _strip_comments(css)
    out = []
    for m in re.finditer(re.escape(selector) + r'\s*(?=[,{])', css):
        j = css.find('{', m.end())
        head = css[m.end():j]
        if head.strip() not in ('', ','):
            continue
        out.append(css[j + 1:css.index('}', j)])
    return out

@tagged('post_install', '-at_install', 'wujia_surface_card_d4')
class TestSurfaceCardD4h(TransactionCase):
    """D4h — nhóm Khảo sát (wujia_portal_inspection), lượt đầu tiên đo được vì
    module này vốn uninstalled trên mọi DB copy trước.

    Đếm token lúc chạy (bài học D4f #2) cho ra 3 họ khung thật + 4 hộp inline:
    `.inspection-card-item` (list mobile, wholeCard <a>), `.detail-card-box`
    (hộp mobile duy nhất của chi tiết), `.summary-2x2-card` (ô tổng PC, <a>) và
    4 `.form-card-box` khai dáng bằng style="" ngay tại call site. Hai hộp thoại
    nổi (`.wj-success-card`, `.wj-warning-card`) và ô chỉ báo 60×60
    (`.wj-dist-card`) KHÔNG phải SurfaceCard — ghim lại để đổi phải qua test.
    """

    def _arch(self, key):
        view = find_view(self, key)
        self.assertTrue(view, f'không thấy view {key}')
        return view.arch_db

    # --- A · CSS module không còn khai dáng khung ------------------------

    def test_inspection_families_no_longer_declare_shape(self):
        css = _mod_css(*D4H_CSS)
        for sel in ('.inspection-card-item', '.summary-2x2-card'):
            bodies = _rules_anywhere(css, sel)
            self.assertTrue(bodies, f'rule {sel} biến mất — lớp con/hover cần nó')
            for body in bodies:
                for prop in D4H_SHAPE:
                    with self.subTest(sel=sel, prop=prop):
                        self.assertFalse(_declares(body, prop))
        # Rule chỉ có dáng ⇒ gỡ hẳn, không để rule rỗng.
        self.assertEqual(_rules_anywhere(css, '.detail-card-box'), [])

    def test_hover_no_longer_adds_a_shadow(self):
        # Cùng chốt D4b: wholeCard hover nâng 2px nhưng KHÔNG thêm bóng.
        css = _mod_css(*D4H_CSS)
        for sel in ('.inspection-card-item:hover', '.summary-2x2-card:hover'):
            bodies = _rules_anywhere(css, sel)
            self.assertTrue(bodies)
            for body in bodies:
                with self.subTest(sel=sel):
                    self.assertFalse(_declares(body, 'box-shadow'))
                    self.assertTrue(_declares(body, 'transform'))

    def test_summary_tile_keeps_its_accent_border_as_a_token(self):
        # border-color là TÔNG (điểm nhấn xanh), không phải dáng ⇒ được giữ,
        # nhưng phải là token, hết hex #38bdf8.
        bodies = _rules_anywhere(_mod_css(*D4H_CSS), '.summary-2x2-card')
        self.assertEqual(len(bodies), 1)
        self.assertTrue(_declares(bodies[0], 'border-color'))
        self.assertIn('--wujia-primary', bodies[0])
        self.assertNotIn('#38bdf8', bodies[0].lower())

    def test_severe_modifier_is_tone_only(self):
        bodies = _rules_anywhere(_mod_css(*D4H_CSS), '.summary-2x2-card.severe-card')
        self.assertEqual(len(bodies), 1)
        self.assertTrue(_declares(bodies[0], 'border-color'))
        self.assertTrue(_declares(bodies[0], 'background'))
        for prop in ('border-radius', 'padding', 'box-shadow', 'border'):
            self.assertFalse(_declares(bodies[0], prop))

    # --- B · call site nướng shell, giữ lớp riêng ------------------------

    def test_list_item_is_a_whole_card_link(self):
        arch = self._arch('wujia_portal_inspection.portal_inspection_list_content')
        self.assertEqual(arch.count('wj-surface-card-link'), 1)
        self.assertEqual(arch.count(D4H_SHELL % 'record' + 'inspection-card-item'), 1)

    def test_detail_call_sites_bake_the_shell(self):
        arch = self._arch('wujia_portal_inspection.portal_inspection_detail')
        self.assertEqual(arch.count(D4H_SHELL % 'summary' + 'summary-2x2-card'), 1)
        self.assertEqual(arch.count(D4H_SHELL % 'section' + 'detail-card-box'), 1)

    def test_remediation_boxes_dropped_the_inline_shape(self):
        # 4 hộp từng khai bg/radius/viền/bóng bằng style="" — chỗ rò mà grep CSS
        # không thấy, chỉ đếm lúc chạy mới lộ. ĐẾM đủ 4, không `in`.
        arch = self._arch('wujia_portal_inspection.portal_inspection_remediation_form')
        self.assertEqual(arch.count(D4H_SHELL % 'section' + 'form-card-box'), 4)
        self.assertEqual(arch.count('form-card-box'), 4)
        self.assertNotIn('box-shadow', arch)

    def test_no_card_token_leaks_into_inspection_views(self):
        need(self, 'wujia_portal_inspection')
        views = self.env['ir.ui.view'].search(
            [('key', '=like', 'wujia_portal_inspection.%')])
        self.assertTrue(views)
        self.assertEqual([v.key for v in views if _has_card_token(v.arch_db)], [])

    # --- C · phân loại đã chốt: KHÔNG phải SurfaceCard ---------------------

    def test_dialogs_and_dist_tile_are_pinned_out_of_scope(self):
        css = _mod_css(*D4H_CSS)
        for sel, prop in (('.wj-success-card', 'box-shadow'),
                          ('.wj-warning-card', 'box-shadow'),
                          ('.wj-dist-card', 'width')):
            with self.subTest(sel=sel):
                self.assertTrue(any(_declares(b, prop) for b in _rules_anywhere(css, sel)))
        for key in ('wujia_portal_inspection.portal_inspection_success_popup',
                    'wujia_portal_inspection.portal_inspection_warning_popup'):
            with self.subTest(key=key):
                self.assertNotIn('wj-surface-card', self._arch(key))

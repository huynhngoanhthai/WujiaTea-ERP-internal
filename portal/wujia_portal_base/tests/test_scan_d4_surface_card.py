"""D4 (quét nhiều module) — call site SurfaceCard CMP-SC-001.

F5b dời khỏi `wujia_portal_layout`: khung không được biết màn nào. Hợp đồng render
của component vẫn ở layout.
"""
import os
import re

from lxml import html

from odoo.tests import TransactionCase, tagged

from .common import find_view, need

TMPL = 'wujia_portal_layout.wj_surface_card'
MOD_DIR = os.path.join(os.path.dirname(__file__), '..', '..')
CSS_DIR = os.path.join(MOD_DIR, 'wujia_portal_layout', 'static', 'assets', 'css')


def _css(name):
    with open(os.path.join(CSS_DIR, name), encoding='utf-8') as fh:
        return fh.read()


def _strip_comments(css):
    return re.sub(r'/\*.*?\*/', '', css, flags=re.S)


def _rule(css, selector):
    """Thân của rule ở TẦNG GỐC (ngoài mọi @media). Gộp @media vào là bẫy đã trả
    giá ở D4a — wj-auth-card từng bị đọc ra số của bản mobile."""
    css = _strip_comments(css)
    depth, i, out = 0, 0, None
    while i < len(css):
        c = css[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        elif depth == 0 and css.startswith(selector, i):
            after = css[i + len(selector)]
            if after in ' ,{\n':
                j = css.index('{', i)
                if css[i:j].strip() == selector:
                    out = css[j + 1:css.index('}', j)]
                    break
        i += 1
    return out


@tagged('post_install', '-at_install', 'wujia_surface_card_d4')
class TestSurfaceCardLegacyFamilies(TransactionCase):

    def test_legacy_families_no_longer_declare_surface_shape(self):
        # Hai rule cùng đặc hiệu cùng khai padding thì thắng thua do thứ tự
        # nguồn — chủ sở hữu phải là DUY NHẤT.
        css = _css('_components.css') + _mod_css('wujia_portal_base', 'portal_dashboard.css')
        for sel in ('.wujia-kpi-card', '.wujia-content-card'):
            with self.subTest(sel=sel):
                body = _rule(css, sel)
                for prop in ('padding', 'border-radius', 'box-shadow'):
                    self.assertNotIn(prop, body,
                                     '%s không được khai %s nữa' % (sel, prop))

    def test_kpi_card_no_longer_locks_height(self):
        # F3: CSS Home dời về wujia_portal_base.
        body = _rule(_mod_css('wujia_portal_base', 'portal_dashboard.css'), '.wujia-kpi-card')
        self.assertIsNotNone(body)
        self.assertNotIn('min-height', body)

    def test_hover_of_whole_card_drops_the_shadow_too(self):
        # wholeCard: bỏ shadow mặc định mà giữ shadow hover là vẫn còn shadow.
        css = _mod_css('wujia_portal_base', 'portal_dashboard.css')
        i = css.index('.wujia-kpi-card-link:hover .wujia-kpi-card')
        self.assertNotIn('box-shadow', css[i:css.index('}', i)])


def _mod_css(module, name):
    with open(os.path.join(MOD_DIR, module, 'static', 'src', 'css', name),
              encoding='utf-8') as fh:
        return fh.read()


PROP = r'(?:^|;)\s*%s\s*:'


def _declares(body, prop):
    """Có khai THUỘC TÍNH prop không. Dò chuỗi con là bẫy: `top: var(--wj-pc-
    content-padding)` chứa chữ "padding" mà không hề khai padding."""
    return re.search(PROP % re.escape(prop), body) is not None


def _rules_anywhere(css, selector):
    """Mọi thân rule của selector, KỂ CẢ trong @media. `_rule` cố ý bỏ @media;
    các modifier của exam nằm trọn trong @media nên phải có bản quét này."""
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
class TestSurfaceCardD4c(TransactionCase):
    """D4c — họ shell PC: wj-pc-card + 8 modifier + wj-pc-acct-headcard."""

    def _root(self, **values):
        out = self.env['ir.qweb']._render(TMPL, values)
        return html.fragment_fromstring(str(out).strip())

    # --- chủ sở hữu DUY NHẤT của dáng khung -------------------------------

    def test_pc_card_no_longer_declares_surface_shape(self):
        body = _rule(_css('_pc_components.css'), '.wj-pc-card')
        self.assertIsNone(body, '.wj-pc-card không được khai dáng khung nữa')

    def test_acct_headcard_keeps_layout_but_drops_shape(self):
        body = _rule(_css('_pc_account.css'), '.wj-pc-acct-headcard')
        self.assertIsNotNone(body)
        for prop in ('background', 'border', 'border-radius', 'padding'):
            with self.subTest(prop=prop):
                self.assertFalse(_declares(body, prop))
        self.assertIn('display: flex', body, 'phần bố cục phải giữ nguyên')

    def test_modifiers_no_longer_declare_padding(self):
        # Chúng nằm ở CSS module khác, nạp SAU _pc_components.css ⇒ cùng đặc hiệu
        # (0,1,0) mà thắng theo thứ tự nguồn. Đây là chỗ "sửa xong vẫn y như cũ".
        for module, css_name, sel in (
                ('wujia_portal_debt', 'portal_debt.css', '.wj-debt-pc-card'),
                ('wujia_portal_exam', 'portal_exam.css', '.wj-exam-pc-card'),
                ('wujia_portal_exam', 'portal_exam.css', '.wj-exam-pc-fcard'),
                ('wujia_portal_exam', 'portal_exam.css', '.wj-exam-pc-sumcard'),
                ('wujia_portal_exam', 'portal_exam.css', '.wj-exam-pc-dcard'),
                ('wujia_portal_sale', 'portal_order.css', '.wj-pc-order-card'),
                ('wujia_portal_report', 'portal_report.css', '.wj-rep-pccard')):
            with self.subTest(sel=sel):
                for body in _rules_anywhere(_mod_css(module, css_name), sel):
                    self.assertFalse(_declares(body, 'padding'),
                                     '%s vẫn đè padding lên SurfaceCard' % sel)

    def test_paycard_keeps_its_non_shape_rule(self):
        # max-width KHÔNG phải dáng khung ⇒ modifier được giữ.
        bodies = _rules_anywhere(_mod_css('wujia_portal_debt', 'portal_debt.css'),
                                 '.wj-debt-pc-paycard')
        self.assertTrue(any('max-width' in b for b in bodies))

    # --- token ------------------------------------------------------------

    def test_pc_card_radius_token_converged_to_sixteen(self):
        # DRIFT: --wj-pc-card-radius 18 vs --wujia-card-radius 16, cùng vai trò.
        css = _strip_comments(_css('_variables.css'))
        self.assertTrue(re.search(r'--wj-pc-card-radius:\s*16px', css))

    def test_tonal_tokens_exist(self):
        css = _strip_comments(_css('_variables.css'))
        self.assertTrue(re.search(r'--wujia-surface-tonal:\s*#F8FAFC', css, re.I))
        self.assertTrue(re.search(r'--wujia-surface-tonal-radius:\s*12px', css))

    # --- biến thể tonal ---------------------------------------------------

    def test_tone_tonal_adds_the_modifier(self):
        self.assertIn('wj-surface-card--tonal',
                      self._root(sc_tone='tonal').get('class'))

    def test_tone_defaults_to_none(self):
        self.assertNotIn('wj-surface-card--tonal', self._root().get('class'))

    def test_tonal_variant_has_no_border_and_no_shadow(self):
        body = _rule(_css('_components.css'), '.wj-surface-card--tonal')
        self.assertIsNotNone(body)
        self.assertIn('var(--wujia-surface-tonal)', body)
        self.assertIn('var(--wujia-surface-tonal-radius)', body)
        self.assertTrue(re.search(r'border:\s*0', body))
        self.assertTrue(re.search(r'box-shadow:\s*none', body))

    def test_nested_exam_panels_no_longer_paint_white(self):
        # BA cấm thẻ trắng lồng thẻ trắng — 2 vi phạm ở /portal/exam/register.
        css = _mod_css('wujia_portal_exam', 'portal_exam.css')
        for sel in ('.wj-exam-pc-cal', '.wj-exam-pc-slots'):
            with self.subTest(sel=sel):
                for body in _rules_anywhere(css, sel):
                    self.assertFalse(_declares(body, 'background'))
                    self.assertFalse(_declares(body, 'border'))

    # --- call site không phải <div> ---------------------------------------

    def test_non_div_call_sites_carry_the_owner_class(self):
        # <form> POST, <aside>, <section> không đi qua t-call được (component
        # luôn sinh <div>) ⇒ mang thẳng class chủ sở hữu, không mất landmark.
        need(self, 'wujia_portal_support', 'wujia_portal_exam', 'wujia_portal_report')
        views = self.env['ir.ui.view'].search([
            ('key', 'in', ['wujia_portal_support.portal_support_form',
                           'wujia_portal_exam.portal_exam_register',
                           'wujia_portal_report.portal_report_orders'])])
        self.assertEqual(len(views), 3)
        for v in views:
            with self.subTest(key=v.key):
                self.assertIn('wj-surface-card', v.arch_db)


@tagged('post_install', '-at_install', 'wujia_surface_card_d4')
class TestSurfaceCardD4d(TransactionCase):
    """D4d — 10 họ MOBILE + wj-filter-card. Lượt đầu tiên dùng cột mobile của
    component, nên guard cả token @media lẫn từng rule cũ."""

    # Rule gốc nằm ở _components.css; 5 họ bị module riêng đè, nạp SAU nên
    # thắng theo thứ tự nguồn dù cùng đặc hiệu (0,1,0).
    SHARED = ('.wj-filter-card', '.wujia-mres-card', '.wujia-mhist-card',
              '.wujia-mknow-card', '.wujia-mdash-card')
    OWNED = ('background', 'border', 'border-radius', 'padding', 'box-shadow', 'gap')

    # --- chủ sở hữu DUY NHẤT của dáng khung -------------------------------

    def test_shared_mobile_families_no_longer_declare_shape(self):
        # F2: rule mhist/mknow dời về module chủ ⇒ đọc cả hai file.
        css = (_css('_components.css')
               + _mod_css('wujia_portal_purchase_history', 'portal_history.css')
               + _mod_css('wujia_portal_knowledge', 'portal_knowledge.css')
               + _mod_css('wujia_portal_sale', 'portal_order.css')
               + _mod_css('wujia_portal_base', 'portal_dashboard.css'))
        for sel in self.SHARED:
            for body in _rules_anywhere(css, sel):
                for prop in self.OWNED:
                    with self.subTest(sel=sel, prop=prop):
                        self.assertFalse(
                            _declares(body, prop),
                            f'{sel} vẫn khai {prop} — dáng khung phải nằm ở .wj-surface-card')

    def test_module_owned_families_no_longer_declare_shape(self):
        for module, name, sels in (
                ('wujia_portal_exam', 'portal_exam.css',
                 ('.wujia-mexam-cfcard',)),
                ('wujia_portal_notification', 'portal_notification.css',
                 ('.wujia-mnoti-detail-card',)),
                ('wujia_portal_delivery', 'portal_delivery.css',
                 ('.wujia-mdelivery-prodcard',))):
            css = _mod_css(module, name)
            for sel in sels:
                for body in _rules_anywhere(css, sel):
                    for prop in self.OWNED:
                        with self.subTest(sel=sel, prop=prop):
                            self.assertFalse(_declares(body, prop))

    def test_selcard_keeps_only_its_tonal_fill(self):
        # Nền tonal là sắc thái BA duyệt cho thẻ "đang chọn"; KHÔNG dùng biến thể
        # --tonal vì biến thể đó bỏ hẳn viền, còn BA vẫn đòi viền 1px.
        bodies = _rules_anywhere(_mod_css('wujia_portal_exam', 'portal_exam.css'),
                                 '.wujia-mexam-selcard')
        self.assertTrue(bodies)
        joined = ''.join(bodies)
        self.assertIn('var(--wujia-surface-tonal)', joined)
        for prop in ('border', 'border-radius', 'padding', 'gap'):
            with self.subTest(prop=prop):
                self.assertFalse(_declares(joined, prop))

    # --- bẫy đã trả giá ---------------------------------------------------

    def test_filter_chips_compensation_is_gone(self):
        # gap 10 của wj-filter-card là số BÙ: có .wj-filter-chips{margin-top:-2px}
        # kèm. Kéo gap về 8 mà giữ -2px thì khoảng hở thật thành 6px — RULE 1/2
        # mù trước lỗi này vì nó đều tay mọi card.
        css = _strip_comments(_css('_components.css'))
        self.assertNotRegex(css, r'\.wj-filter-card\s*>\s*\.wj-filter-chips\s*\{[^}]*margin-top')

    def test_notification_no_longer_overrides_knowledge_card(self):
        # Rule liên module .wujia-mnoti .wujia-mknow-card{padding:9px 12px} đo lúc
        # chạy ra 0 phần tử khớp ⇒ rule chết, giữ lại chỉ để lệch hai màn.
        css = _strip_comments(_mod_css('wujia_portal_notification',
                                       'portal_notification.css'))
        self.assertNotIn('.wujia-mnoti .wujia-mknow-card', css)

    def test_knowledge_article_no_longer_overrides_padding(self):
        # .wujia-mknow-article{padding:16px} từng ĐÈ compact 14 của card — đo được
        # 16 ở /portal/knowledge/<slug>. Kiểm kê D4a ghi p14, đó là số của rule gốc.
        bodies = _rules_anywhere(_css('_components.css')
                                 + _mod_css('wujia_portal_knowledge', 'portal_knowledge.css'),
                                 '.wujia-mknow-article')
        for body in bodies:
            self.assertFalse(_declares(body, 'padding'))

    # --- những thứ CỐ Ý giữ lại -------------------------------------------

    def test_non_shape_rules_survive(self):
        keep = (
            (_mod_css('wujia_portal_sale', 'portal_order.css'), '.wujia-mres-card', 'max-width'),
            # .wujia-mhist-card KHÔNG còn trong danh sách này: nhịp giữa các thẻ nay do
            # gap chung của trang mobile cấp (một nguồn duy nhất cho mọi trang), nên
            # margin-bottom riêng của nó bị gỡ — cộng dồn với gap là lỗi, không phải nhịp.
            (_css('_components.css'), '.wujia-mdash-card', 'display'),
            (_mod_css('wujia_portal_delivery', 'portal_delivery.css'),
             '.wujia-mdelivery-prodcard', 'overflow'),
        )
        for css, sel, prop in keep:
            with self.subTest(sel=sel, prop=prop):
                self.assertTrue(any(_declares(b, prop)
                                    for b in _rules_anywhere(css, sel)),
                                f'{sel} mất {prop} — đó không phải dáng khung')

    def test_mdash_list_keeps_its_own_inset(self):
        # 9 call site "gộp" dùng sc_body="flush": card không khai đệm, phần đệm
        # là của chính danh sách (4/14) + nhịp dọc 12 của .wujia-mdash-row.
        self.assertTrue(any(_declares(b, 'padding')
                            for b in _rules_anywhere(_css('_components.css'),
                                                     '.wujia-mdash-list')))

    # --- token cột mobile --------------------------------------------------

    def test_mobile_tokens_match_ba(self):
        css = _strip_comments(_css('_variables.css'))
        block = css[css.index('@media (max-width: 991.98px)'):]
        for token, value in (('--wujia-surface-radius', '14px'),
                             ('--wujia-surface-pad-compact', '12px'),
                             ('--wujia-surface-pad-regular', '14px'),
                             ('--wujia-surface-gap', '8px')):
            with self.subTest(token=token):
                self.assertRegex(block, re.escape(token) + r':\s*' + re.escape(value))

    def test_mobile_border_tone_is_the_stronger_one(self):
        # BA: mobile viền #E5E7EB (--wujia-border), desktop #EEF2F5 (--wujia-border-soft).
        css = _strip_comments(_css('_components.css'))
        m = re.search(r'@media \(max-width: 991\.98px\) \{\s*'
                      r'\.wj-surface-card \{([^}]*)\}', css)
        self.assertIsNotNone(m, 'mất nhánh @media của .wj-surface-card')
        self.assertIn('var(--wujia-border)', m.group(1))

    # --- call site ---------------------------------------------------------

    def test_mobile_non_div_call_sites_carry_the_owner_class(self):
        # 6 <form method="get"> lọc, 1 <article> landmark, 1 <a> wholeCard và 1
        # <div role="status"> — t-call sinh <div> trơn nên sẽ nuốt mất tag/thuộc
        # tính. Giữ tag, thêm thẳng class (cách D4c đã chốt).
        # E5b2: card lịch thi rời khỏi SurfaceCard — dáng ngoài nay do D5
        # (.wj-data-list--detail-card .wj-data-item) lo, nên bỏ khỏi bảng này.
        for key, tag in (('wujia_portal_knowledge.portal_knowledge_detail', '<article'),
                         ('wujia_portal_sale.mres_shell', 'role="status"')):
            view = find_view(self, key)
            with self.subTest(key=key):
                self.assertTrue(view, f'không thấy view {key}')
                self.assertIn('wj-surface-card', view.arch_db)
                self.assertIn(tag, view.arch_db)

    def test_no_inline_padding_left_on_migrated_cards(self):
        # Bẫy #5: style inline thắng mọi CSS. Đã chuyển sang sc_body="flush",
        # để cả hai cùng tồn tại là mâu thuẫn im lặng.
        need(self, 'wujia_portal_support')
        views = self.env['ir.ui.view'].search(
            [('key', 'in', ['wujia_portal_base.portal_franchise_information',
                            'wujia_portal_support.portal_support_detail'])])
        self.assertEqual(len(views), 2)
        for v in views:
            with self.subTest(key=v.key):
                self.assertNotIn('padding:0', v.arch_db.replace(' ', ''))


@tagged('post_install', '-at_install', 'wujia_surface_card_d4')
class TestSurfaceCardD4e1(TransactionCase):
    """D4e1 — họ wj-pc-metric-card: 12 shell / 3 file (báo cáo · gallery · khảo sát).

    Hai thứ CỐ Ý ở lại rule họ, chủ dự án chốt sau khi đo: đệm dọc của họ này
    bằng 0 nên `min-height` là SÀN chiều cao thiết kế — bỏ đi thì thẻ cao lên
    96→121..126 (đo thật) ⇒ *thưa hơn* sau migration, chỏi đúng câu BA viết
    trong `Kết quả mong muốn`. Đệm ngang 22→16 hội tụ hai họ về một số.
    """

    OWNED_HERE = ('background', 'border', 'border-radius', 'box-shadow', 'gap')
    CALL_SITES = ('wujia_portal_report.portal_report_orders',
                  'wujia_portal_layout.pc_preview_page',
                  'wujia_portal_inspection.portal_inspection_detail')

    # --- chủ sở hữu dáng khung -------------------------------------------

    def test_metric_card_no_longer_declares_surface_shape(self):
        for body in _rules_anywhere(_css('_pc_components.css'), '.wj-pc-metric-card'):
            for prop in self.OWNED_HERE:
                with self.subTest(prop=prop):
                    self.assertFalse(
                        _declares(body, prop),
                        f'.wj-pc-metric-card vẫn khai {prop} — phải ở .wj-surface-card')

    def test_report_cross_module_override_is_gone(self):
        # Rule này SỐNG (đo lúc chạy: khớp đúng 4 phần tử ở cả 5 khổ) và đặc hiệu
        # (0,2,0) thắng chủ sở hữu (0,1,0) ⇒ giữ lại là đẻ variant theo route.
        css = _strip_comments(_mod_css('wujia_portal_report', 'portal_report.css'))
        self.assertNotRegex(css, r'\.wj-rep-pcmetrics\s+\.wj-pc-metric-card\s*\{')

    def test_report_keeps_its_non_shape_overrides(self):
        # Cỡ chữ và gap của LƯỚI không phải dáng khung — cố ý giữ.
        css = _strip_comments(_mod_css('wujia_portal_report', 'portal_report.css'))
        self.assertIn('.wj-rep-pcmetrics .wj-pc-metric-card__value', css)
        self.assertIsNotNone(_rule(css, '.wj-rep-pcmetrics'))

    # --- hai thứ cố ý ở lại ----------------------------------------------

    def test_metric_card_keeps_flex_and_height_floor(self):
        body = _rule(_css('_pc_components.css'), '.wj-pc-metric-card')
        self.assertIsNotNone(body)
        # --summary chỉ khai gap, KHÔNG khai display ⇒ bỏ flex là gap vô tác dụng.
        self.assertTrue(_declares(body, 'display'))
        self.assertTrue(_declares(body, 'align-items'))
        self.assertTrue(_declares(body, 'min-height'))
        self.assertIn('--wj-pc-metric-h', body)

    def test_horizontal_inset_converged_to_16(self):
        body = _rule(_css('_pc_components.css'), '.wj-pc-metric-card')
        self.assertRegex(body, r'padding:\s*0\s+16px')

    # --- call site --------------------------------------------------------

    def test_all_metric_call_sites_use_the_component(self):
        for key in self.CALL_SITES:
            view = find_view(self, key)
            with self.subTest(key=key):
                self.assertTrue(view, f'không thấy view {key}')
                arch = view.arch_db
                self.assertNotIn('<div class="wj-pc-metric-card">', arch)
                self.assertIn('wujia_portal_layout.wj_surface_card', arch)
                # Luật #1: lớp cũ phải còn, nếu không CSS con __icon/__body đứt.
                self.assertIn('wj-pc-metric-card', arch)

    def test_call_sites_bake_summary_and_flush(self):
        # summary = biến thể DUY NHẤT khai gap (Luật #8); flush vì đệm dọc = 0.
        for key in self.CALL_SITES:
            view = find_view(self, key)
            with self.subTest(key=key):
                arch = view.arch_db
                self.assertIn("'summary'", arch)
                self.assertIn("'flush'", arch)


@tagged('post_install', '-at_install', 'wujia_surface_card_d4')
class TestSurfaceCardD4e2(TransactionCase):
    """D4e2 — wj-rep-mcard (3 shell mobile) + 2 món nợ D4d: inline padding và
    nhịp header→body 18/23/25 → 12."""

    # --- A · wj-rep-mcard -------------------------------------------------

    def test_rep_mcard_no_longer_declares_surface_shape(self):
        # Rule nằm TRONG @media ⇒ phải dùng _rules_anywhere, _rule sẽ trượt.
        css = _mod_css('wujia_portal_report', 'portal_report.css')
        for body in _rules_anywhere(css, '.wj-rep-mcard'):
            for prop in ('background', 'border', 'border-radius', 'box-shadow', 'padding'):
                with self.subTest(prop=prop):
                    self.assertFalse(_declares(body, prop))

    def test_rep_mcard_content_rules_survive(self):
        # __head/__body là NỘI DUNG, không phải khung — rút nhầm là mất đệm.
        css = _mod_css('wujia_portal_report', 'portal_report.css')
        head = _rules_anywhere(css, '.wj-rep-mcard__head')
        body = _rules_anywhere(css, '.wj-rep-mcard__body')
        self.assertTrue(head and _declares(head[0], 'padding'))
        self.assertTrue(head and _declares(head[0], 'min-height'))
        self.assertTrue(body and _declares(body[0], 'padding'))

    def test_rep_mcard_call_sites_carry_the_component(self):
        view = find_view(self, 'wujia_portal_report.portal_report_orders')
        self.assertTrue(view)
        arch = view.arch_db
        self.assertEqual(arch.count('wj-surface-card--flush wj-rep-mcard'), 3)
        # Luật #1: lớp cũ ở lại, nếu không CSS con __head/__body và :is() hover đứt.
        self.assertIn('wj-rep-mcard--chart', arch)
        self.assertNotIn('"wj-rep-mcard"', arch)

    # --- B · 2 inline padding --------------------------------------------

    def test_headpad_class_uses_the_token(self):
        body = _rule(_css('_components.css'), '.wj-surface-headpad')
        self.assertTrue(body)
        self.assertIn('--wujia-surface-pad-regular', body)
        self.assertNotIn('14px', body)

    def test_inline_padding_gone_from_both_views(self):
        for key in ('wujia_portal_base.portal_franchise_information',
                    'wujia_portal_support.portal_support_detail'):
            view = find_view(self, key)
            with self.subTest(key=key):
                self.assertTrue(view, f'không thấy view {key}')
                self.assertNotIn('padding:14px 14px 0', view.arch_db)
                self.assertIn('wj-surface-headpad', view.arch_db)

    # --- C · nhịp header→body → 12 ---------------------------------------

    def test_pc_card_head_rhythm_is_12(self):
        body = _rule(_css('_pc_components.css'), '.wj-pc-card__head')
        self.assertTrue(body)
        self.assertRegex(body, r'margin-bottom:\s*12px')

    def test_exam_no_longer_overrides_the_rhythm(self):
        css = _mod_css('wujia_portal_exam', 'portal_exam.css')
        for sel in ('.wj-exam-pc-card__head', '.wj-exam-pc-dhead',
                    '.wj-exam-pc-fcard .wj-exam-pc-field'):
            with self.subTest(sel=sel):
                for body in _rules_anywhere(css, sel):
                    self.assertFalse(_declares(body, 'margin-bottom'))
                    self.assertFalse(_declares(body, 'margin-top'))

    def test_exam_sumlist_drops_margin_top_but_keeps_gap(self):
        bodies = _rules_anywhere(_mod_css('wujia_portal_exam', 'portal_exam.css'),
                                 '.wj-exam-pc-sumlist')
        self.assertTrue(bodies)
        self.assertFalse(_declares(bodies[0], 'margin-top'))
        self.assertTrue(_declares(bodies[0], 'gap'))


_CLS_ATTR = re.compile(
    r'(?:class|t-attf-class)="([^"]*)"'
    r'|t-value="\'([^\']*)\'"'
)


def _has_card_token(arch):
    for a, b in _CLS_ATTR.findall(arch or ''):
        if 'card' in (a or b).split():
            return True
    return False


D4F_VIEWS = (
    'wujia_portal_base.portal_franchise_profile_full',
    'wujia_portal_base.portal_franchise_information_locked',
    'wujia_portal_base.portal_franchises_list',
    'wujia_portal_base.portal_franchise_detail',
    'wujia_portal_info_request.portal_info_request_list',
    'wujia_portal_info_request.portal_info_request_form',
    'wujia_portal_info_request.portal_info_request_detail',
    'wujia_portal_knowledge.portal_knowledge_list',
    'wujia_portal_knowledge.portal_knowledge_detail',
    'wujia_portal_return.portal_return_detail',
    'wujia_portal_return.portal_return_form',
    'wujia_portal_return.portal_return_list',
    'wujia_portal_sale.portal_order_product_detail',
    'wujia_portal_support.portal_support_list',
    'wujia_portal_support.portal_support_detail',
    'wujia_portal_layout.forgot_pass_back',
    'wujia_portal_layout.signup_form',
)


SHELL = ('wj-surface-card', 'wj-surface-card--section',
         'wj-surface-card--compact', 'wj-surface-card--flush')


@tagged('post_install', '-at_install', 'wujia_surface_card_d4')
class TestSurfaceCardD4f(TransactionCase):
    """D4f — nhóm cuối: gỡ hẳn `.card` của Bootstrap khỏi Portal.

    Khác mọi lượt trước ở một điểm: `.card` KHÔNG phải lớp của Wujia. Bundle
    `web.assets_frontend` của Odoo nạp SAU mọi <link> của Wujia ở cùng đặc hiệu
    (0,1,0) nên nền + viền thẻ do Odoo quyết, radius chỉ đứng nhờ !important.
    Vì thế Luật #1 (giữ lớp cũ qua sc_class) KHÔNG áp dụng: giữ chữ `card` là
    để Odoo tiếp tục thắng. Test dưới đây khoá cả hai đầu — call site sạch
    token `card`, và dáng khung chỉ còn một chủ.
    """

    # --- A · call site không còn token `card` -----------------------------

    def _arch(self, key):
        view = find_view(self, key)
        self.assertTrue(view, f'không thấy view {key}')
        return view.arch_db

    def test_no_d4f_view_keeps_the_bootstrap_card_class(self):
        for key in D4F_VIEWS:
            with self.subTest(key=key):
                self.assertFalse(_has_card_token(self._arch(key)))

    def test_no_portal_view_at_all_keeps_the_card_class(self):
        # Đếm trên TOÀN BỘ view đã cài, không chỉ 17 view trên: lượt sau thêm
        # call site mới mà quên là test này đỏ ngay.
        views = self.env['ir.ui.view'].search(
            [('key', '=like', 'wujia_portal_%')])
        leaks = [v.key for v in views if _has_card_token(v.arch_db)]
        # NGOẠI LỆ ghi rõ: /my/franchises/<id> chạy trên bundle
        # `portal.portal_layout` của Odoo, KHÔNG nạp một dòng CSS Wujia nào
        # (đo lúc chạy D4f: radius 6px, shadow none). Đổi lớp ở đó là sửa dáng
        # màn không thuộc shell Vuexy ⇒ để nguyên, ghi LIMIT.
        self.assertEqual(leaks, ['wujia_portal_base.portal_my_franchise_detail'])

    def test_children_migrated_to_the_bem_names(self):
        for key in D4F_VIEWS:
            arch = self._arch(key)
            for old in ('"card-header', '"card-body', '"card-footer',
                        '"card-img-top', "'card-header"):
                with self.subTest(key=key, old=old):
                    self.assertNotIn(old, arch)

    # E4b1: thanh lọc PC của 3 màn này vốn là vỏ --section dựng tay, nay gọi
    # component CMP-FB-001 ⇒ view không còn vỏ nào. Ghi tên ra đây để hướng
    # ngược lại (ai dựng tay trở lại) vẫn đỏ.
    NO_SECTION_SHELL = {
        'wujia_portal_support.portal_support_list',
        'wujia_portal_return.portal_return_list',
        'wujia_portal_info_request.portal_info_request_list',
    }

    def test_call_sites_bake_all_four_shell_classes(self):
        # ĐẾM chứ không `in`: một call site rơi mất --flush mà call site khác
        # cùng view còn giữ thì phép `in` vẫn xanh — đột biến D4f #3 đã lọt.
        full = ' '.join(SHELL)
        for key in D4F_VIEWS:
            arch = self._arch(key)
            with self.subTest(key=key):
                n = arch.count('wj-surface-card wj-surface-card--section')
                if key in self.NO_SECTION_SHELL:
                    self.assertEqual(n, 0)
                else:
                    self.assertGreaterEqual(n, 1)
                self.assertEqual(arch.count(full), n)

    def test_module_own_classes_survive_next_to_the_shell(self):
        # Luật #1 phần CÒN áp dụng được: lớp riêng của module nuôi CSS con và
        # 3 danh sách :is() hover của _interaction.css — rút là đứt.
        for key, cls in (('wujia_portal_knowledge.portal_knowledge_detail',
                          'knowledge-detail'),
                         ('wujia_portal_support.portal_support_detail',
                          'support-chatter'),
                         ('wujia_portal_return.portal_return_form',
                          'wujia-return-form')):
            with self.subTest(key=key):
                self.assertIn('wj-surface-card--flush ' + cls, self._arch(key))

    # --- B · con BEM khai đúng dáng --------------------------------------

    def test_bem_children_declare_their_own_frame(self):
        css = _css('_components.css')
        head = _rule(css, '.wj-surface-card__head')
        body = _rule(css, '.wj-surface-card__body')
        foot = _rule(css, '.wj-surface-card__foot')
        flush = _rule(css, '.wj-surface-card__body--flush')
        for name, got in (('head', head), ('body', body),
                          ('foot', foot), ('flush', flush)):
            self.assertTrue(got, f'thiếu rule {name}')
        self.assertTrue(_declares(head, 'padding'))
        self.assertTrue(_declares(head, 'border-bottom'))
        self.assertIn('transparent', head)
        self.assertTrue(_declares(body, 'padding'))
        self.assertTrue(_declares(foot, 'border-top'))
        self.assertIn('transparent', foot)
        self.assertRegex(flush, r'padding:\s*0')

    def test_bem_children_use_the_tokens_not_raw_px(self):
        css = _css('_components.css')
        for sel in ('.wj-surface-card__head', '.wj-surface-card__body',
                    '.wj-surface-card__foot'):
            with self.subTest(sel=sel):
                self.assertIn('--wujia-surface-pad-', _rule(css, sel))

    def test_card_title_font_size_retargeted_to_the_head(self):
        # Cỡ chữ tiêu đề là địa hạt D3 — chỉ trỏ lại tên, KHÔNG đổi giá trị.
        css = _strip_comments(_css('_components.css'))
        self.assertIn('.wj-surface-card__head .card-title', css)
        self.assertIn('--wujia-font-size-card-title', css)

    # --- C · dáng khung chỉ còn MỘT chủ -----------------------------------

    def test_global_card_shape_rules_are_gone(self):
        # Chốt #2 của chủ dự án: gỡ vì đếm lúc chạy ra 0 thẻ `.card` còn hiện.
        for name in ('_wujia_theme.css', '_components.css'):
            with self.subTest(css=name):
                self.assertEqual(_rules_anywhere(_css(name), '.card'), [])

    def test_theme_no_longer_shapes_card_children(self):
        css = _css('_wujia_theme.css')
        for sel in ('.card > .card-header', '.card-footer',
                    '.card-body .wujia-section-header'):
            with self.subTest(sel=sel):
                self.assertEqual(_rules_anywhere(css, sel), [])

    def test_module_css_retargeted_off_card_body(self):
        ret = _mod_css('wujia_portal_return', 'portal_return.css')
        sup = _mod_css('wujia_portal_support', 'portal_support.css')
        self.assertIn('.wj-surface-card__body > .wj-card-header', ret)
        self.assertNotIn('.card-body >', ret)
        self.assertIn('.support-chatter .wj-surface-card__body', sup)
        self.assertNotIn('.support-chatter .card-body', sup)

    def test_surface_card_still_has_no_shadow(self):
        body = _rule(_css('_components.css'), '.wj-surface-card')
        self.assertTrue(body)
        self.assertFalse(_declares(body, 'box-shadow'))

    # --- D · ảnh bìa: bo góc thay cho overflow:hidden đã gỡ ---------------

    def test_media_class_carries_the_radius_itself(self):
        # `.card` cũ bo góc ảnh bìa NHỜ overflow:hidden của cha. Gỡ .card là
        # mất cái đó, nên radius phải nằm thẳng trên ảnh.
        css = _css('_components.css')
        media = _rule(css, '.wj-surface-card__media')
        self.assertTrue(media)
        self.assertTrue(_declares(media, 'border-radius'))
        self.assertIn('--wujia-surface-radius', media)
        # Và KHÔNG được thêm overflow vào shell: 113 thẻ D4b–D4e chạy không có
        # nó, thêm là đổi hành vi cả cụm. Quét MỌI rule của selector — `_rule`
        # chỉ trả rule ĐẦU TIÊN nên một rule thêm sau nó sẽ lọt (đột biến #11).
        for body in _rules_anywhere(css, '.wj-surface-card'):
            self.assertFalse(_declares(body, 'overflow'))

    def test_cover_images_use_the_media_class(self):
        for key in ('wujia_portal_knowledge.portal_knowledge_detail',
                    'wujia_portal_sale.portal_order_product_detail'):
            with self.subTest(key=key):
                self.assertIn('wj-surface-card__media', self._arch(key))


D4H_CSS = ('wujia_portal_inspection', 'portal_inspection.css')


D4H_SHAPE = ('background', 'background-color', 'border', 'border-radius',
             'box-shadow', 'padding', 'overflow')


D4H_SHELL = 'wj-surface-card wj-surface-card--%s wj-surface-card--compact wj-surface-card--padded '

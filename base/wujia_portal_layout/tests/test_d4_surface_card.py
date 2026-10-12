"""D4 — CMP-SC-001 SurfaceCard: hợp đồng render của component wj_surface_card.

Bám cột `Kết quả mong muốn` của issue UI-SURFACECARD-001 (STT 127) cho phần lượt
D4b phủ: 4 biến thể, 2 mức mật độ, bodyMode padded/flush, interactive wholeCard,
BỎ shadow mặc định, CÓ viền 1px, và KHÔNG khoá cứng chiều cao.

F5b: call site của 12 module nghiệp vụ đã dời sang
`wujia_portal_base/tests/test_scan_d4_surface_card.py`; nhóm Khảo sát (D4h) sang
`wujia_portal_base/tests/test_handover_inspection.py` để bàn giao.
"""
import os
import re

from lxml import html

from odoo.tests import TransactionCase, tagged

TMPL = 'wujia_portal_layout.wj_surface_card'
CSS_DIR = os.path.join(os.path.dirname(__file__), '..', 'static', 'assets', 'css')


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
class TestSurfaceCardComponent(TransactionCase):

    def _root(self, **values):
        out = self.env['ir.qweb']._render(TMPL, values)
        return html.fragment_fromstring(str(out).strip())

    def test_default_variant_is_section(self):
        self.assertIn('wj-surface-card--section', self._root().get('class'))

    def test_each_variant_gets_its_modifier(self):
        for v in ('record', 'summary', 'transactional'):
            with self.subTest(variant=v):
                self.assertIn('wj-surface-card--%s' % v,
                              self._root(sc_variant=v).get('class'))

    def test_unknown_variant_falls_back_to_section(self):
        cls = self._root(sc_variant='bogus').get('class')
        self.assertIn('wj-surface-card--section', cls)
        self.assertNotIn('bogus', cls)

    def test_density_defaults_to_compact(self):
        self.assertIn('wj-surface-card--compact', self._root().get('class'))

    def test_density_regular_replaces_compact(self):
        cls = self._root(sc_density='regular').get('class')
        self.assertIn('wj-surface-card--regular', cls)
        self.assertNotIn('wj-surface-card--compact', cls)

    def test_body_defaults_to_padded(self):
        self.assertIn('wj-surface-card--padded', self._root().get('class'))

    def test_body_flush(self):
        self.assertIn('wj-surface-card--flush',
                      self._root(sc_body='flush').get('class'))

    def test_href_wraps_the_card_in_an_anchor(self):
        root = self._root(sc_href='/portal/notification')
        self.assertEqual(root.tag, 'a')
        self.assertEqual(root.get('href'), '/portal/notification')
        self.assertIn('wj-surface-card-link', root.get('class'))
        self.assertIn('wj-surface-card', root[0].get('class'))

    def test_no_href_means_no_anchor_wrapper(self):
        self.assertEqual(self._root().tag, 'div')

    def test_link_keeps_caller_class(self):
        # Lớp cũ phải sống sót, nếu không ba danh sách :is() hover ở
        # _interaction.css mất đối tượng và thẻ KPI hết phản hồi.
        root = self._root(sc_href='/x', sc_link_class='wujia-kpi-card-link')
        self.assertIn('wujia-kpi-card-link', root.get('class'))

    def test_card_keeps_caller_class(self):
        self.assertIn('wujia-content-card',
                      self._root(sc_class='wujia-content-card').get('class'))

    def _via_call(self, sets='', body='<p id="inner">nội dung</p>'):
        # _render() xoá values['0'] (ir_qweb.py:712) — slot CHỈ đến được qua
        # t-call thật, nên test phải dựng một view gọi component.
        view = self.env['ir.ui.view'].create({
            'name': 'wj surface card probe',
            'type': 'qweb',
            'arch_db': '<t t-name="wj_sc_probe">'
                       '<t t-call="%s">%s%s</t></t>' % (TMPL, sets, body),
        })
        out = self.env['ir.qweb']._render(view.id)
        return html.fragment_fromstring(str(out).strip())

    def test_body_passes_through_untouched(self):
        root = self._via_call()
        self.assertEqual(len(root), 1)          # KHÔNG bọc thêm tầng nào
        self.assertEqual(root[0].get('id'), 'inner')
        self.assertIn('wj-surface-card', root.get('class'))

    def test_body_passes_through_under_anchor_too(self):
        root = self._via_call(
            sets='<t t-set="sc_href" t-value="\'/portal\'"/>')
        self.assertEqual(root.tag, 'a')
        self.assertEqual(root[0][0].get('id'), 'inner')

    def test_component_never_emits_inline_height(self):
        for kw in ({}, {'sc_href': '/x'}, {'sc_density': 'regular'}):
            with self.subTest(**kw):
                self.assertNotIn('height', str(self._root(**kw).get('style') or ''))

    def test_no_kpi_min_height_token_left(self):
        self.assertNotIn('--wujia-kpi-card-min-height', _css('_variables.css'))

    def test_surface_card_has_no_default_shadow(self):
        self.assertNotIn('box-shadow', _rule(_css('_components.css'), '.wj-surface-card'))

    def test_surface_card_has_one_pixel_border(self):
        body = _rule(_css('_components.css'), '.wj-surface-card')
        self.assertTrue(re.search(r'border:\s*1px solid var\(--wujia-border-soft\)', body),
                        'viền PC phải là 1px --wujia-border-soft (#EEF2F5)')

    def test_base_card_declares_no_gap(self):
        # Card xếp dọc đã có nhịp header→body 12px do margin của wj_card_header.
        # Thêm gap ở base là 12+12=24px — đo được, mà RULE 1/2 không thấy vì nó
        # đều tay trên mọi card.
        self.assertNotIn('gap', _rule(_css('_components.css'), '.wj-surface-card'))

    def test_summary_variant_owns_the_gap(self):
        body = _rule(_css('_components.css'), '.wj-surface-card--summary')
        self.assertIsNotNone(body)
        self.assertIn('gap: var(--wujia-surface-gap)', body)

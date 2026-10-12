"""I10 — UI-LISTCARD-002 (STT 168): một bộ token chữ cho ListCard + căn badge hai họ.

Bám cột `Kết quả mong muốn`: (2) label 12/500/18 · value 13/500/18 · strong 13/600/18 ·
title 15/600/20; (3) StatusBadge compact 12/600, CategoryBadge cùng line-height, căn giữa;
(4) không làm card cao lên; (6) bảng desktop không đổi — `.wujia-badge`/`.wj-status-badge`
gốc giữ nguyên, rule mới chỉ sống trong `.wj-lc`. Không style theo route.
"""
import os
import re

from odoo.tests import TransactionCase, tagged

from .test_e5_list_card import _block, _css, _resolved

CUSTOM = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))


def _decl(block, prop):
    m = re.search(r'(?<![\w-])%s\s*:\s*([^;]+);' % re.escape(prop), block)
    return m.group(1).strip() if m else None


@tagged('post_install', '-at_install', 'wujia_listcard_i10')
class TestListCardTypographyI10(TransactionCase):

    def setUp(self):
        super().setUp()
        self.css = _css('_components.css')

    def _rule(self, selector):
        return _resolved(_block(self.css, selector))

    def test_token_chu_dung_so_ba(self):
        expect = {
            '.wj-lc__name': {'font-size': '15px', 'font-weight': '600', 'line-height': '20px'},
            '.wj-lc__label': {'font-size': '12px', 'font-weight': '500', 'line-height': '18px'},
            '.wj-lc__row': {'font-size': '13px', 'line-height': '18px'},
            '.wj-lc__value': {'font-weight': '500'},
            '.wj-lc__value--strong': {'font-weight': '600'},
        }
        for selector, props in expect.items():
            blk = self._rule(selector)
            for prop, val in props.items():
                self.assertEqual(_decl(blk, prop), val, '%s %s' % (selector, prop))

    def test_so_nam_o_token_khong_viet_cung(self):
        """Tiêu chí 1: cùng token cho title/label/value/strong — rule đọc var, không số cứng."""
        for selector, prop in (('.wj-lc__name', 'font-size'), ('.wj-lc__label', 'font-size'),
                               ('.wj-lc__label', 'font-weight'), ('.wj-lc__value', 'font-weight'),
                               ('.wj-lc__value--strong', 'font-weight'), ('.wj-lc__row', 'line-height')):
            self.assertRegex(_decl(_block(self.css, selector), prop) or '', r'^var\(--wj-lc-',
                             '%s %s phải lấy từ token --wj-lc-*' % (selector, prop))

    def test_hang_nhan_gia_tri_giu_dung_18(self):
        """Tiêu chí 4 (đo I10): căn baseline label 12 với value 13 ⇒ hàng 19, card +1–2px;
        icon 16 trong label căn baseline cũng đội hộp lên 19."""
        self.assertEqual(_decl(self._rule('.wj-lc__row'), 'align-items'), 'flex-start')
        label = self._rule('.wj-lc__label')
        self.assertEqual(_decl(label, 'display'), 'inline-flex')
        self.assertEqual(_decl(label, 'align-items'), 'center')

    def test_badge_hai_ho_cung_line_height_trong_card(self):
        compact = self._rule('.wj-status-badge--compact')
        self.assertEqual(_decl(compact, 'font-size'), '12px')
        cat = self._rule('.wj-lc .wujia-badge')
        self.assertEqual(_decl(cat, 'line-height'), _decl(compact, 'line-height'))
        self.assertEqual(_decl(cat, 'display'), 'inline-flex')
        self.assertEqual(_decl(cat, 'align-items'), 'center')
        # semantic riêng của họ tag: không đổi cỡ chữ, màu, nền, cao cứng
        for cam in ('font-size', 'color', 'background', 'background-color', 'height'):
            self.assertIsNone(_decl(cat, cam), 'CategoryBadge trong card không được đổi %s' % cam)

    def test_badge_trong_card_khong_cao_hon_cu(self):
        """Tiêu chí 4: cao = line-height + đệm dọc + viền 2 ≤ cao cũ (26,8 · --sm 23,4)."""
        lh = float(_decl(self._rule('.wj-lc .wujia-badge'), 'line-height').rstrip('px'))
        self.assertLessEqual(lh + 2 * 4 + 2, 26.8)
        sm = self._rule('.wj-lc .wujia-badge--sm')
        pad = float(_decl(sm, 'padding-top').rstrip('px')) + float(_decl(sm, 'padding-bottom').rstrip('px'))
        self.assertLessEqual(lh + pad + 2, 23.4)

    def test_badge_goc_ngoai_card_giu_nguyen(self):
        """Tiêu chí 6: bảng desktop / Home dùng rule gốc — I10 không được chạm."""
        base = _block(self.css, '.wujia-badge')
        self.assertEqual(_decl(base, 'display'), 'inline-block')
        self.assertEqual(_decl(base, 'line-height'), '1.4')
        self.assertEqual(_decl(base, 'padding'), '4px 10px')
        sb = _block(self.css, '.wj-status-badge')
        self.assertEqual(_decl(sb, 'font-size'), '13px')
        self.assertEqual(_decl(sb, 'line-height'), '1')

    def test_khong_module_nao_de_chu_listcard_theo_route(self):
        """'Không tạo style riêng theo route': module màn chỉ được tô MÀU ruột ListCard."""
        typo = re.compile(r'\b(font-size|font-weight|line-height|font-family)\s*:')
        offenders = []
        for mod in sorted(os.listdir(CUSTOM)):
            if not mod.startswith('wujia_portal_') or mod in ('wujia_portal_layout', 'wujia_portal_inspection'):
                continue
            for root, _dirs, files in os.walk(os.path.join(CUSTOM, mod, 'static')):
                for fn in files:
                    if not fn.endswith('.css'):
                        continue
                    with open(os.path.join(root, fn), encoding='utf-8') as fh:
                        text = re.sub(r'/\*.*?\*/', '', fh.read(), flags=re.S)
                    for selector, body in re.findall(r'([^{}]+)\{([^}]*)\}', text):
                        if re.search(r'wj-lc__(name|label|value)', selector) and typo.search(body):
                            offenders.append('%s → %s' % (fn, selector.strip()))
        self.assertEqual(offenders, [], 'chữ ListCard bị đè theo route')

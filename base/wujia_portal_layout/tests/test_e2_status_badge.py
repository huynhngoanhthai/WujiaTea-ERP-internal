"""E2 / UI-STATUSBADGE-001 — StatusBadge CMP-SB-001 là MỘT component.

Phần dáng của component (nằm ở khung). Bảng trạng thái → badge, call site và phép quét
CSS toàn hệ đã dời sang `wujia_portal_base/tests/test_scan_e2_status_badge.py` ở F5b.
"""

import colorsys
import os
import re

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

CSS_DIR = os.path.join(os.path.dirname(__file__), '..', 'static', 'assets', 'css')
# Hex BA chốt ở tab UI Component dòng 37. NỀN giữ nguyên; CHỮ 5/7 mã của BA đo
# dưới AA 4.5 nên đã làm đậm tối thiểu — test dưới khoá nền + ngưỡng AA + tông.
BA_TOKENS = {
    'neutral': ('#F3F4F6', '#6B7280'), 'info': ('#EAF7FD', '#168FC2'),
    'pending': ('#FFF7E6', '#D97706'), 'processing': ('#FEF3C7', '#B45309'),
    'success': ('#EAF8EF', '#16A34A'), 'danger': ('#FEECEC', '#DC2626'),
    'feedback': ('#F3E8FF', '#7C3AED'),
}


def _rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def _contrast(fg, bg):
    def lum(h):
        out = 0
        for c, w in zip(_rgb(h), (0.2126, 0.7152, 0.0722)):
            c /= 255.0
            out += w * (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
        return out
    a, b = sorted((lum(fg), lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def _hue_gap(a, b):
    ha, hb = (colorsys.rgb_to_hls(*[c / 255.0 for c in _rgb(x)])[0] * 360 for x in (a, b))
    d = abs(ha - hb) % 360
    return min(d, 360 - d)


@tagged('post_install', '-at_install', 'wujia_status_badge_e2')
class TestStatusBadgeIsOneComponent(TransactionCase):

    def _read(self, name):
        with open(os.path.join(CSS_DIR, name), encoding='utf-8') as fh:
            return fh.read()

    def _rule(self, css, selector):
        m = re.search(r'(?<![\w.-])' + re.escape(selector) + r'\s*\{([^}]*)\}', css)
        self.assertTrue(m, 'không tìm thấy rule %s' % selector)
        return m.group(1)

    # --- 1. hình học -------------------------------------------------------
    def test_base_class_carries_the_whole_geometry(self):
        body = self._rule(self._read('_components.css'), '.wj-status-badge')
        self.assertRegex(body, r'height:\s*var\(--wj-sb-h\)')
        self.assertRegex(body, r'min-width:\s*var\(--wj-sb-min-w\)')
        self.assertRegex(body, r'padding:\s*0 14px')
        self.assertRegex(body, r'border-radius:\s*var\(--wj-sb-radius\)')
        self.assertRegex(body, r'font-size:\s*13px')
        self.assertRegex(body, r'font-weight:\s*600')
        self.assertRegex(body, r'line-height:\s*1\s*;')
        self.assertRegex(body, r'white-space:\s*nowrap')
        self.assertRegex(body, r'border:\s*0')
        self.assertRegex(body, r'box-shadow:\s*none')

    def test_tokens_keep_ba_background_and_reach_wcag_aa(self):
        """Nền = hex BA. Chữ: AA 4.5 (13px không phải chữ lớn) + giữ tông của BA."""
        css = self._read('_variables.css')
        for variant, (bg, ba_fg) in BA_TOKENS.items():
            self.assertRegex(css, r'--wj-sb-%s-bg:\s*%s;' % (variant, bg))
            m = re.search(r'--wj-sb-%s-fg:\s*(#[0-9A-Fa-f]{6});' % variant, css)
            self.assertTrue(m, 'thiếu token chữ %s' % variant)
            fg = m.group(1)
            self.assertGreaterEqual(
                round(_contrast(fg, bg), 2), 4.5,
                '%s: %s trên %s chỉ %.2f — dưới WCAG AA' % (variant, fg, bg, _contrast(fg, bg)))
            self.assertLessEqual(
                _hue_gap(fg, ba_fg), 12,
                '%s: %s lệch tông khỏi hex BA %s — chỉ được làm đậm, không đổi màu'
                % (variant, fg, ba_fg))
        for name, value in (('h', '28px'), ('min-w', '84px'), ('radius', '14px')):
            self.assertRegex(css, r'--wj-sb-%s:\s*%s;' % (name, value))

    def test_badge_row_does_not_stretch_the_excluded_chip(self):
        # `align-items` mặc định là stretch ⇒ chip mã cửa hàng 26,8px bị kéo lên 28px
        # theo StatusBadge. Kiểm chéo E2 đã bắt đúng lỗi này.
        self.assertRegex(self._rule(self._read('_components.css'), '.wujia-maccount-badgerow'),
                         r'align-items:\s*center')

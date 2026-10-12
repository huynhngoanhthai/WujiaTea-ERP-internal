"""I13 / WJ-PORTAL-UI-006 — tương phản chữ dùng chung ≥ WCAG AA 4.5:1.

Khoá ở TOKEN (`_variables.css`), không theo màn: mọi token chữ × mọi nền sáng ≥ 4.5,
mọi nền đặc mang chữ trắng ≥ 4.5, vòng focus trên topbar xanh ≥ 3. Màu thương
hiệu #28A9DF vẫn là nền/viền/icon — chỉ thôi làm màu chữ. Phép quét `color:` toàn
module ở `wujia_portal_base/tests/test_scan_i13_contrast.py` (tầng ghép).
Đo trên trang thật: `scripts/qa/wj_contrast.py`.
"""
import os
import re

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from .test_e2_status_badge import _contrast

CSS = os.path.join(os.path.dirname(__file__), '..', 'static', 'assets', 'css', '_variables.css')

# Nền sáng mà chữ thường nằm trên (đo bằng máy 56 trang × 2 khổ): thẻ, trang, hàng đang
# chọn, ô xám vô hiệu, header bảng.
LIGHT_SURFACES = ('--wujia-bg-card', '--wujia-bg-page', '--wujia-primary-soft',
                  '--wujia-primary-light', '--wj-disabled-bg', '#F8FAFC')
TEXT_TOKENS = ('--wujia-brand-text', '--wujia-brand-text-hover', '--wujia-active-text',
               '--wujia-text-primary', '--wujia-text-secondary', '--wujia-text-muted',
               '--wujia-text-subtitle', '--wj-pc-subtle', '--wj-disabled-fg',
               '--wj-pgn-disabled-fg', '--wujia-danger-text', '--wujia-success-text',
               '--wujia-warning-text', '--wujia-mnav-active', '--wujia-mnav-inactive',
               '--wujia-mhome-nav-inactive', '--wujia-mobile-strip-label-color',
               '--wujia-content-card-link-color')
# Chữ trạng thái còn nằm trên nền nhạt cùng tông.
TONE_PAIRS = (('--wujia-danger-text', '--wujia-danger-bg'),
              ('--wujia-success-text', '--wujia-success-bg'),
              ('--wujia-warning-text', '--wujia-warning-bg'))
WHITE_FILLS = ('--wujia-brand-fill', '--wujia-brand-fill-hover', '--wujia-danger-fill',
               '--wujia-success-fill', '--wujia-warning-fill', '--wujia-mnav-badge')


@tagged('post_install', '-at_install', 'wujia_i13')
class TestSharedTokensReachAA(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(CSS, encoding='utf-8') as fh:
            cls.tokens = dict(re.findall(r'(--[\w-]+)\s*:\s*([^;]+);', fh.read()))

    def _hex(self, name):
        """Lần chuỗi var() tới hex cuối. Token khai trùng thì lấy khai báo SAU (như CSS)."""
        value, seen = name, set()
        while value.startswith('--'):
            self.assertNotIn(value, seen, 'vòng var() ở %s' % name)
            seen.add(value)
            self.assertIn(value, self.tokens, 'thiếu token %s' % value)
            raw = self.tokens[value].split('/*')[0].strip()
            m = re.fullmatch(r'var\((--[\w-]+)(?:\s*,[^)]*)?\)', raw)
            value = m.group(1) if m else raw
        self.assertRegex(value, r'^#[0-9A-Fa-f]{6}$', '%s không ra hex 6 số: %s' % (name, value))
        return value.upper()

    def test_every_text_token_on_every_light_surface(self):
        bad = []
        for fg in TEXT_TOKENS:
            for bg in LIGHT_SURFACES:
                bgh = bg if bg.startswith('#') else self._hex(bg)
                ratio = _contrast(self._hex(fg), bgh)
                if ratio < 4.5:
                    bad.append('%s/%s %.2f' % (fg, bg, ratio))
        for fg, bg in TONE_PAIRS:
            ratio = _contrast(self._hex(fg), self._hex(bg))
            if ratio < 4.5:
                bad.append('%s/%s %.2f' % (fg, bg, ratio))
        self.assertFalse(bad, 'cặp chữ/nền dưới AA 4.5: %s' % bad)

    def test_white_text_fills(self):
        bad = ['%s %.2f' % (t, _contrast('#FFFFFF', self._hex(t))) for t in WHITE_FILLS
               if _contrast('#FFFFFF', self._hex(t)) < 4.5]
        self.assertFalse(bad, 'nền đặc mang chữ trắng dưới 4.5: %s' % bad)

    def test_topbar_keeps_cyan_with_glass_pills(self):
        """Topbar giữ nền #28A9DF; pill PC là kính mờ + chữ trắng theo Figma — ngoại lệ AA do chủ dự án
        chốt 10/10/2026, nên chỉ khoá đúng giá trị Figma chứ không khoá tỉ lệ."""
        cyan = self._hex('--wujia-primary')
        self.assertEqual(cyan, '#28A9DF', 'màu thương hiệu không được đổi')
        self.assertGreaterEqual(_contrast(self._hex('--wujia-topbar-fg'), cyan), 4.5)
        for t in ('--wujia-navbar-pill-text', '--wujia-navbar-pill-icon'):
            self.assertEqual(self._hex(t), '#FFFFFF', t)
        for t, alpha in (('--wujia-navbar-pill-bg', '.18'), ('--wujia-navbar-chip-bg', '.26'),
                         ('--wujia-navbar-pill-label-color', '.82')):
            self.assertEqual(self.tokens[t].split('/*')[0].strip(), 'rgb(255 255 255 / %s)' % alpha, t)
        # Vòng focus mặc định (xanh CTA) ≥ 3 trên mọi nền sáng.
        ring = re.search(r'(var\((--[\w-]+)\)|#[0-9A-Fa-f]{6})\s*$', self.tokens['--wujia-focus-ring'].strip())
        ring_hex = self._hex(ring.group(2)) if ring.group(2) else ring.group(1).upper()
        for bg in LIGHT_SURFACES:
            bgh = bg if bg.startswith('#') else self._hex(bg)
            self.assertGreaterEqual(_contrast(ring_hex, bgh), 3.0, 'focus ring trên %s' % bg)

    def test_brand_is_no_longer_a_text_token(self):
        """#28A9DF chỉ 2.68 trên trắng — không token CHỮ nào được trỏ về nó."""
        cyan = self._hex('--wujia-primary')
        for t in TEXT_TOKENS + ('--wujia-topbar-fg',):
            self.assertNotEqual(self._hex(t), cyan, '%s vẫn là màu brand' % t)

    def test_topbar_overrides_focus_ring_locally(self):
        """Vòng focus CTA trên nền cyan chỉ ~1.6 ⇒ topbar PC + header mobile đổi ring sang navy."""
        here = os.path.dirname(CSS)
        with open(os.path.join(here, '_pc_account.css'), encoding='utf-8') as fh:
            self.assertRegex(fh.read(), r'\.wujia-navbar\s*\{\s*--wujia-focus-ring:\s*2px solid var\(--wujia-topbar-fg\)')
        with open(os.path.join(here, '_components.css'), encoding='utf-8') as fh:
            self.assertRegex(fh.read(), r'--wujia-focus-ring:\s*2px solid var\(--wujia-topbar-fg\)')

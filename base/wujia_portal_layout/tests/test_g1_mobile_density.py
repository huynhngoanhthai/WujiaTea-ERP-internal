# -*- coding: utf-8 -*-
"""G1 — mật độ khung mobile: PageHeader · SectionHeader · BottomNav.

Hai issue BA (21/09/2026), cả hai là component dùng chung nên sửa ở token/component,
không override từng trang:
- UI-MOB-HEADER-DENSITY-001: PageHeader mobile pad dọc 8 (từ 12) — chủ dự án chốt cả ba
  biến thể title/back/create cùng cao 44; SectionHeader mobile 18/24 (từ 20/28). PC giữ.
- UI-MOB-BOTTOMNAV-DENSITY-001: thanh dưới 72 + safe area thực tế (từ 83), mục chạm 50,
  icon 22, nhãn 12 (từ 11).

Guard quét CSS nguồn; số đo trình duyệt ở `scripts/qa/wj_density.py`.
"""
import os
import re

from odoo.tests import TransactionCase, tagged

CSS_DIR = os.path.join(os.path.dirname(__file__), '..', 'static', 'assets', 'css')
MOBILE_MQ = '@media (max-width: 991.98px)'


def _css(name):
    with open(os.path.join(CSS_DIR, name), encoding='utf-8') as fh:
        return re.sub(r'/\*.*?\*/', '', fh.read(), flags=re.S)


def _rules(css):
    return [(m.group(1).strip(), m.group(2))
            for m in re.finditer(r'([^{}]+)\{([^{}]*)\}', css)]


def _body(css, selector):
    """Thân của rule có selector ĐÚNG bằng `selector` (ngoài @media)."""
    hits = [b for s, b in _rules(css) if s == selector]
    assert hits, 'không tìm thấy rule %s' % selector
    return hits[0]


def _media_blocks(css, header=MOBILE_MQ):
    out, i = [], css.find(header)
    while i >= 0:
        j = css.index('{', i)
        depth = 0
        for k in range(j, len(css)):
            depth += {'{': 1, '}': -1}.get(css[k], 0)
            if depth == 0:
                out.append(css[j + 1:k])
                break
        i = css.find(header, k)
    return out


def _outside_media(css):
    """CSS đã cắt bỏ mọi khối @media."""
    out, i = [], 0
    for m in re.finditer(r'@media[^{]*\{', css):
        if m.start() < i:
            continue
        out.append(css[i:m.start()])
        depth = 0
        for k in range(m.end() - 1, len(css)):
            depth += {'{': 1, '}': -1}.get(css[k], 0)
            if depth == 0:
                i = k + 1
                break
    out.append(css[i:])
    return ''.join(out)


@tagged('post_install', '-at_install', 'wujia_mobile_density_g1')
class TestMobileDensityTokens(TransactionCase):

    def test_token_gia_tri_ba(self):
        css = _css('_variables.css')
        self.assertRegex(css, r'--wujia-m-pagehead-py:\s*8px;')
        self.assertRegex(css, r'--wujia-m-sechead-fs:\s*18px;')
        self.assertRegex(css, r'--wujia-m-sechead-lh:\s*24px;')
        self.assertRegex(css, r'--wujia-mnav-height:\s*72px;')

    def test_mnav_total_bang_72_cong_safe_area(self):
        """Công thức cũ `83 + max(0, safe - 6)` lệch cao thật của nav (91 vs 111)."""
        css = _css('_variables.css')
        self.assertRegex(css, r'--wujia-mnav-total:\s*calc\(var\(--wujia-mnav-height\)\s*\+\s*'
                              r'env\(safe-area-inset-bottom,\s*0px\)\);')

    def test_chua_day_noi_dung_bam_token_nav(self):
        css = _css('_variables.css')
        self.assertRegex(css, r'--wujia-mshell-content-pad-bottom:\s*calc\(var\(--wujia-mnav-height\)')


@tagged('post_install', '-at_install', 'wujia_mobile_density_g1')
class TestMobilePageHeader(TransactionCase):

    def test_pad_doc_tu_token_va_cao_44(self):
        body = _body(_css('_components.css'), '.wj-page-header--m')
        self.assertIn('padding: var(--wujia-m-pagehead-py) 0', body)
        self.assertIn('min-height: calc(28px + 2 * var(--wujia-m-pagehead-py))', body)

    def test_bien_the_back_create_cung_cao_44(self):
        """back 42 + 2×1 = 44, create 44 + 0 = 44 — cùng hàng với title 28 + 2×8."""
        css = _css('_components.css')
        self.assertRegex(_body(css, '.wj-page-header--m.wj-page-header--back'), r'padding:\s*1px 0')
        self.assertRegex(_body(css, '.wj-page-header--m.wj-page-header--create'), r'padding:\s*0\s*;')

    def test_khong_cong_them_padding_ngang(self):
        """Gutter ngang của PageContainer (UI-PAGECONTAINER-001) — component chỉ lo dọc."""
        body = _body(_css('_components.css'), '.wj-page-header--m')
        self.assertRegex(body, r'padding:\s*var\(--wujia-m-pagehead-py\)\s+0\s*;')


@tagged('post_install', '-at_install', 'wujia_mobile_density_g1')
class TestMobileSectionHeader(TransactionCase):

    TITLE_M = '.wj-section-header--m .wj-section-header__title'
    TITLE_ANY = '.wj-section-header--any .wj-section-header__title'

    def test_m_dung_token_18_24(self):
        body = _body(_css('_components.css'), self.TITLE_M)
        self.assertIn('font-size: var(--wujia-m-sechead-fs) !important', body)
        self.assertIn('line-height: var(--wujia-m-sechead-lh)', body)

    def test_any_chi_nhan_co_mobile_duoi_992(self):
        """--any hiện ở MỌI khổ ⇒ cỡ 18/24 ra ngoài @media là đổi PC (BA cấm)."""
        css = _css('_components.css')
        outside = [b for s, b in _rules(_outside_media(css)) if self.TITLE_ANY in s]
        self.assertTrue(outside)
        for b in outside:
            self.assertNotIn('--wujia-m-sechead-fs', b)
            self.assertRegex(b, r'font-size:\s*20px !important')
        inside = [b for blk in _media_blocks(css) for s, b in _rules(blk) if self.TITLE_ANY in s]
        self.assertTrue(any('var(--wujia-m-sechead-fs)' in b for b in inside))


@tagged('post_install', '-at_install', 'wujia_mobile_density_g1')
class TestMobileBottomNav(TransactionCase):

    def test_vo_cao_dung_chieu_cao_thuc(self):
        body = _body(_css('_components.css'), '.wujia-mhome-bottomnav')
        self.assertIn('height: var(--wujia-mnav-total)', body)
        self.assertRegex(body, r'padding:\s*0 0 env\(safe-area-inset-bottom,\s*0px\)')
        self.assertNotIn('min-height', body)

    def test_muc_cham_50_nhan_12_icon_22(self):
        css = _css('_components.css')
        self.assertRegex(_body(css, '.wujia-mhome-nav-item'), r'min-height:\s*50px')
        self.assertRegex(_body(css, '.wujia-mhome-nav-label'), r'font-size:\s*12px')
        self.assertRegex(_body(css, '.wujia-mhome-nav-item i'), r'font-size:\s*22px')

    def test_khoi_co_dinh_tren_nav_bam_total(self):
        """Sheet Thêm + backdrop bám `-height` thì chồng lên nav trên máy có safe area."""
        blk = ''.join(_media_blocks(_css('_components.css')))
        for sel in ('.wujia-msheet-backdrop', '.wujia-msheet'):
            bodies = [b for s, b in _rules(blk) if s == sel and 'bottom:' in b]
            self.assertTrue(bodies, sel)
            self.assertIn('bottom: var(--wujia-mnav-total)', bodies[0], sel)

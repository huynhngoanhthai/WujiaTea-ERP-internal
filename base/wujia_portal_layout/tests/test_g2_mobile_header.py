# -*- coding: utf-8 -*-
"""G2 — chiều cao header mobile do MỘT token cấp, và không ai neo cứng theo nó.

Chủ dự án: *"cái navigation này phải hẹp cái height lại"*. Khung cố định của mobile
chiếm 235px trên màn 900 (header + dải cửa hàng + thanh dưới); header là phần lấy lại
được mà không đụng nội dung.

Cái dễ hỏng không phải con số 72, mà là những giá trị neo TUYỆT ĐỐI theo con số cũ:
cụm nút trước đây `margin-top: 39px` để khớp Blank Shell của header 104 — hạ header mà
quên gỡ thì cụm nút tràn ra ngoài. Guard ở đây khoá đúng lớp đó, quét CSS nguồn.
"""
import os
import re

from odoo.tests import TransactionCase, tagged

CSS_DIR = os.path.join(os.path.dirname(__file__), '..', 'static', 'assets', 'css')
MOBILE_MQ = '@media (max-width: 991.98px)'


def _css(name):
    with open(os.path.join(CSS_DIR, name), encoding='utf-8') as fh:
        return re.sub(r'/\*.*?\*/', '', fh.read(), flags=re.S)


def _rule(css, selector):
    """Thân rule đầu tiên của selector — đủ dùng vì mỗi selector chỉ khai một lần."""
    head = selector + ' {'
    assert head in css, 'không tìm thấy rule %s' % selector
    return css.split(head, 1)[1].split('}', 1)[0]


def _mobile_block(css):
    """Nội dung khối @media mobile (cắt theo dấu ngoặc, không dựa vào thụt lề)."""
    start = css.index(MOBILE_MQ)
    depth, i = 0, css.index('{', start)
    for j in range(i, len(css)):
        if css[j] == '{':
            depth += 1
        elif css[j] == '}':
            depth -= 1
            if depth == 0:
                return css[i:j]
    raise AssertionError('khối @media mobile không đóng ngoặc')


@tagged('post_install', '-at_install', 'wujia_mobile_header_g2')
class TestMobileHeaderHeight(TransactionCase):

    def test_chieu_cao_72_khai_trong_khoi_mobile(self):
        """Khai trong @media mobile ⇒ PC không đọc tới, khỏi phải chứng minh bằng đo."""
        css = _css('_variables.css')
        self.assertRegex(_mobile_block(css), r'--wujia-mheader-height:\s*72px;')

    def test_header_lay_chieu_cao_tu_token(self):
        body = _rule(_css('_components.css'), '.wujia-mheader')
        self.assertIn('height: var(--wujia-mheader-height);', body)
        self.assertNotRegex(body, r'height:\s*\d')

    def test_khong_trang_nao_tu_khai_lai_chieu_cao_header(self):
        """Một nguồn duy nhất: sửa token là mọi trang ăn theo."""
        root = os.path.normpath(os.path.join(CSS_DIR, '..', '..', '..', '..'))
        thua = []
        for mod in sorted(os.listdir(root)):
            if not mod.startswith('wujia_'):
                continue
            for base, _dirs, files in os.walk(os.path.join(root, mod)):
                for fn in files:
                    if not fn.endswith('.css'):
                        continue
                    path = os.path.join(base, fn)
                    if os.path.normpath(path) == os.path.normpath(
                            os.path.join(CSS_DIR, '_components.css')):
                        continue
                    with open(path, encoding='utf-8') as fh:
                        body = re.sub(r'/\*.*?\*/', '', fh.read(), flags=re.S)
                    for chunk in re.findall(r'\.wujia-mheader\s*\{([^}]*)\}', body):
                        if re.search(r'(?<!min-)(?<!max-)height:', chunk):
                            thua.append(os.path.relpath(path, root))
        self.assertEqual(thua, [], 'chiều cao header phải do token cấp, không khai lại')


@tagged('post_install', '-at_install', 'wujia_mobile_header_g2')
class TestMobileHeaderLayout(TransactionCase):

    def test_cum_nut_khong_neo_cung_theo_chieu_cao_cu(self):
        """`margin-top: 39px` chỉ đúng với header 104 — neo tuyệt đối là mìn hẹn giờ."""
        body = _rule(_css('_components.css'), '.wujia-mheader-actions')
        self.assertNotIn('align-self: flex-start;', body)
        self.assertNotRegex(body, r'margin-top:')

    def test_logo_van_lot_trong_header(self):
        css = _css('_variables.css')
        logo_h = int(re.search(r'--wujia-mheader-logo-h:\s*(\d+)px', css).group(1))
        header_h = int(re.search(r'--wujia-mheader-height:\s*(\d+)px',
                                 _mobile_block(css)).group(1))
        self.assertLessEqual(logo_h + 8, header_h,
                             'logo phải còn chỗ thở trong header')

    def test_vung_cham_44_ma_hop_nhin_thay_van_38(self):
        """BA chốt nút 38; ngưỡng chạm 44 nới bằng pseudo nên không nở header."""
        css = _css('_components.css')
        self.assertRegex(css, r'--wujia-mheader-action-size:|width: var\(--wujia-mheader-action-size\)')
        before = _rule(css, '.wujia-mheader-action::before')
        self.assertIn('position: absolute;', before)
        self.assertIn('width: 44px;', before)
        self.assertIn('height: 44px;', before)
        self.assertRegex(_css('_variables.css'), r'--wujia-mheader-action-size:\s*38px;')

    def test_vung_cham_khong_dung_after_vi_after_da_bi_dung(self):
        """::after của nút đang để tắt caret Bootstrap — dùng lại là mất vùng chạm."""
        css = _css('_components.css')
        self.assertIn('.wujia-mheader-action.dropdown-toggle::after { display: none; }', css)
        self.assertNotIn('.wujia-mheader-action::after {', css)

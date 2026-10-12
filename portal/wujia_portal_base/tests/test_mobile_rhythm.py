# -*- coding: utf-8 -*-
"""Nhịp dọc mobile có ĐÚNG MỘT nguồn.

BA yêu cầu một màn hình điện thoại chứa được nhiều thông tin hơn. Hạ khoảng cách
là việc dễ; giữ cho nó đừng trôi lại mới khó — trước đợt này mỗi trang tự đặt một
giá trị (mpage 14 · Home 18 · Công nợ 12 · Báo cáo 12, còn Đặt hàng/Giỏ/Lịch sử
dàn con bằng margin-bottom 10..16), nên sửa token ở một chỗ thì 6 trang không đổi.

Quét CSS thay vì đo trình duyệt: lỗi kiểu này là lỗi QUYỀN SỞ HỮU (ai được quyền
khai khoảng cách), đọc nguồn bắt được ngay, mà không cần dựng server.
"""
import os
import re

from odoo.tests import TransactionCase, tagged

CUSTOM = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))

# Wrapper trang mobile — mọi lớp ở đây ăn nhịp từ rule chung trong _components.css.
PAGE_WRAPPERS = (
    'wujia-mpage', 'wujia-mhome', 'wujia-morder', 'wujia-mcart',
    'wujia-mhist', 'wujia-mhist-detail', 'wujia-mreport', 'wj-debt',
)


def _read(*parts):
    with open(os.path.join(CUSTOM, *parts), encoding='utf-8') as fh:
        return fh.read()


def _nocomment(css):
    """Bỏ chú thích TRƯỚC khi quét.

    Bài học F5b: câu văn trong chú thích ("gap 12 cũ") bị đếm như khai báo thật,
    làm guard báo đỏ ở chỗ đã dọn xong.
    """
    return re.sub(r'/\*.*?\*/', '', css, flags=re.S)


def _rules(css):
    """Trả về [(selector, thân rule)] — đủ dùng cho CSS phẳng của portal."""
    return [(m.group(1).strip(), m.group(2))
            for m in re.finditer(r'([^{}]+)\{([^{}]*)\}', _nocomment(css))]


def _declares(body, prop):
    return re.search(r'(^|;)\s*%s\s*:' % re.escape(prop), body) is not None


def _media_block(css, header):
    """Thân của một @media, cắt bằng ĐẾM NGOẶC. Cắt bằng regex `\n}` thì dừng ở
    rule đầu tiên khép ở đầu dòng, nên bỏ sót phần còn lại của khối."""
    i = css.find(header)
    if i < 0:
        return ''
    j = css.index('{', i)
    depth, k = 0, j
    while k < len(css):
        if css[k] == '{':
            depth += 1
        elif css[k] == '}':
            depth -= 1
            if depth == 0:
                return css[j + 1:k]
        k += 1
    return ''


def _module_css():
    """Mọi file CSS của portal, TRỪ phần của anh Thái (không đụng code nhóm Khảo sát)."""
    out = []
    for mod in sorted(os.listdir(CUSTOM)):
        if not mod.startswith('wujia_portal_') or 'inspection' in mod:
            continue
        root = os.path.join(CUSTOM, mod, 'static')
        for dirpath, _dirs, files in os.walk(root):
            for f in files:
                if f.endswith('.css'):
                    path = os.path.join(dirpath, f)
                    with open(path, encoding='utf-8') as fh:
                        out.append((os.path.relpath(path, CUSTOM), fh.read()))
    return out


@tagged('post_install', '-at_install', 'wujia_mobile_rhythm')
class TestMobileRhythmSingleSource(TransactionCase):

    def test_tokens_khai_o_khoi_mobile(self):
        """4 giá trị nhịp dọc mobile nằm trong khối @media mobile của _variables.css."""
        css = _nocomment(_read('wujia_portal_layout', 'static', 'assets', 'css', '_variables.css'))
        block = re.search(r'@media \(max-width: 991\.98px\)\s*\{\s*:root\s*\{(.*?)\}', css, re.S)
        self.assertTrue(block, 'không tìm thấy khối :root mobile')
        for token in ('--wujia-mshell-content-gap', '--wujia-mcontent-top',
                      '--wujia-m-sechead-mt', '--wujia-m-sechead-mb'):
            self.assertIn(token, block.group(1),
                          '%s phải khai trong khối mobile, không rải ra ngoài' % token)

    def test_pc_van_giu_16_8_cho_tieu_de_nhom(self):
        """Rule .wj-section-header--m/--any nằm NGOÀI @media nên PC cũng đọc token này.

        Không có giá trị nền ở :root gốc thì PC mất margin — đúng bẫy đã suýt dính.
        """
        css = _nocomment(_read('wujia_portal_layout', 'static', 'assets', 'css', '_variables.css'))
        root = css.split('@media')[0]
        self.assertRegex(root, r'--wujia-m-sechead-mt:\s*16px')
        self.assertRegex(root, r'--wujia-m-sechead-mb:\s*8px')

    def test_mot_rule_duy_nhat_cap_gap_cho_moi_trang(self):
        comp = _read('wujia_portal_layout', 'static', 'assets', 'css', '_components.css')
        owner = [(sel, body) for sel, body in _rules(comp)
                 if '.wujia-mpage' in sel and _declares(body, 'gap')]
        self.assertEqual(len(owner), 1, 'gap trang mobile phải do ĐÚNG MỘT rule cấp')
        sel, body = owner[0]
        self.assertIn('var(--wujia-mshell-content-gap)', body, 'gap phải lấy từ token')
        for cls in PAGE_WRAPPERS:
            self.assertIn('.%s' % cls, sel, '%s chưa nằm trong rule nhịp chung' % cls)

    def test_khong_trang_nao_tu_dat_gap_rieng(self):
        """Đây là cái giữ cho 'sửa một nơi, cả portal đổi' còn đúng sau nhiều phiên."""
        hits = []
        for path, css in _module_css():
            if path.endswith('_components.css'):
                continue                      # chính là rule chung, đã kiểm ở test trên
            for sel, body in _rules(css):
                for cls in PAGE_WRAPPERS:
                    # chỉ bắt rule đặt TRÊN CHÍNH wrapper, không bắt con cháu
                    if not re.search(r'\.%s\s*(,|\{|$)' % re.escape(cls), sel.strip() + '{'):
                        continue
                    for prop in ('gap', 'row-gap'):
                        if _declares(body, prop):
                            hits.append('%s: %s { %s }' % (path, sel.strip()[:48], prop))
        self.assertFalse(hits, 'trang mobile tự khai khoảng cách riêng:\n  ' + '\n  '.join(hits))

    def test_khong_con_rule_bu_tru_header(self):
        """Gap chung nay đúng 8 của CMP-PG-001 ⇒ mọi rule bù âm phải biến mất."""
        hits = []
        for path, css in _module_css() + [
            ('wujia_portal_layout/_components.css',
             _read('wujia_portal_layout', 'static', 'assets', 'css', '_components.css'))]:
            for sel, body in _rules(css):
                if 'wj-page-header--m' not in sel:
                    continue
                if re.search(r'margin-bottom:\s*-\d', body):
                    hits.append('%s: %s' % (path, sel.strip()[:56]))
        self.assertFalse(hits, 'còn rule bù trừ âm cho PageHeader:\n  ' + '\n  '.join(hits))

    # ------------------------------------------------------------------
    # E5c — gutter NGANG cũng phải một nguồn (LC-08). Trước phiên này nhịp dọc đã
    # về token còn lề ngang thì không: trang BlankShell ăn token (16), còn Đặt
    # hàng/Lịch sử ăn 16,8px của Vuexy qua .content-wrapper ⇒ lệch 5px giữa các màn.
    # ------------------------------------------------------------------
    def test_token_gutter_khai_o_khoi_mobile(self):
        css = _nocomment(_read('wujia_portal_layout', 'static', 'assets', 'css', '_variables.css'))
        block = re.search(r'@media \(max-width: 991\.98px\)\s*\{\s*:root\s*\{(.*?)\}', css, re.S)
        self.assertTrue(block, 'không tìm thấy khối :root mobile')
        self.assertRegex(css, r'--wujia-mshell-content-pad-x:\s*12px',
                         'gutter danh sách mobile phải là 12 (LC-08, BA Q2)')

    def test_wrapper_khong_con_giu_gutter(self):
        """E7a: lề ngang thuộc PageContainer — khối mobile không trả lề cho `.content-wrapper`.

        Trước E7a guard này đòi wrapper LẤY token (E5c); nay token vẫn là nguồn của lề
        danh sách nhưng qua `--wj-page-gutter-m-list` của container."""
        css = _nocomment(_read('wujia_portal_layout', 'static', 'assets', 'css', '_wujia_theme.css'))
        block = _media_block(css, '@media (max-width: 991.98px)')
        self.assertTrue(block, 'không tìm thấy khối mobile của _wujia_theme.css')
        hits = [sel for sel, body in _rules(block)
                if 'content-wrapper' in sel and _declares(body, 'padding-left')]
        self.assertFalse(hits, 'khối mobile còn trả lề ngang cho content-wrapper: %s' % hits)
        self.assertIn('var(--wj-page-gutter-m-list)', block,
                      'lề danh sách mobile phải về container qua token')

    def test_khong_trang_nao_go_so_gutter_rieng(self):
        """Wrapper trang mobile không được tự gõ số lề ngang — phải qua token."""
        hits = []
        for path, css in _module_css():
            for sel, body in _rules(css):
                for cls in PAGE_WRAPPERS:
                    if not re.search(r'\.%s\s*(,|\{|$)' % re.escape(cls), sel.strip() + '{'):
                        continue
                    for prop in ('padding', 'padding-left', 'padding-right', 'padding-inline'):
                        m = re.search(r'(?<![-\w])%s:\s*([^;]+);' % prop, body)
                        if m and re.search(r'\d+px', m.group(1)) \
                                and 'var(--wujia-mshell-content-pad-x)' not in m.group(1):
                            hits.append('%s: %s { %s: %s }'
                                        % (path, sel.strip()[:40], prop, m.group(1).strip()))
        self.assertFalse(hits, 'trang mobile tự gõ số lề ngang:\n  ' + '\n  '.join(hits))

"""E7a — CMP-PC-001 PageContainer: hợp đồng khung `app_layout` + CSS của chính nó.

Bám dòng 38 tab `UI Component` (BA Confirmed 26/08/2026): PageContainer là nơi DUY
NHẤT giữ lề ngang, lề trên/dưới và khoảng tránh top bar; gutter 24 (≥992) / 16
(<992); đáy mobile 96 + safe area; nền trong suốt; không overflow-x:hidden.
Lề mobile màn danh sách = 12 (LC-08, BA Q2) qua biến thể `wj-page-container--list`.
E7b: bề rộng `standard` 1440 / `narrow` 960 (fluid = mặc định) và đáy `sticky` cho
thanh hành động cố định trên bottom-nav.

Call site (route nào bật `list`, vỏ route không tự đặt lề) nằm ở sổ quét nhiều
module `wujia_portal_base/tests/test_scan_e7_page_container.py` (luật F5b).
"""
import os
import re

from lxml import etree

from odoo.tests import TransactionCase, tagged

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, '..')
CSS_DIR = os.path.join(ROOT, 'static', 'assets', 'css')


def _css(name):
    with open(os.path.join(CSS_DIR, name), encoding='utf-8') as fh:
        return re.sub(r'/\*.*?\*/', '', fh.read(), flags=re.S)


def _rules(css):
    """[(media, selector, thân)] — `media` là tiêu đề @media bao ngoài ('' = tầng gốc).

    Đếm ngoặc thay vì regex phẳng: cùng một selector có ba bản (gốc · ≥992 · <992),
    gộp lẫn là đọc nhầm số của khổ khác (bẫy D4a)."""
    out, media, depth, start = [], '', 0, 0
    i = 0
    while i < len(css):
        c = css[i]
        if c == '{':
            head = css[start:i].strip()
            if depth == 0 and head.startswith('@media'):
                media = head
                depth = 1
            else:
                j = css.index('}', i)
                out.append((media if depth else '', head, css[i + 1:j]))
                i = j
            start = i + 1
        elif c == '}':
            depth = 0
            media = ''
            start = i + 1
        i += 1
    return out


def _body(css, selector, media=''):
    than = [b for m, s, b in _rules(css)
            if m == media and selector in [p.strip() for p in s.split(',')]]
    return '\n'.join(than)


def _co_padding(body):
    """True nếu thân rule khai padding (bất kỳ phía nào) khác 0."""
    for _prop, val in re.findall(r'(?<![-\w])(padding(?:-[a-z]+)?)\s*:\s*([^;]+)', body):
        if any(v not in ('0', '0px') for v in val.replace('!important', '').split()):
            return True
    return False


MOBILE = '@media (max-width: 991.98px)'
PC = '@media (min-width: 992px)'


@tagged('post_install', '-at_install', 'wujia_page_container_e7')
class TestPageContainerFrame(TransactionCase):

    # ---------------------------------------------------------------- template
    def _app_layout_file(self):
        tree = etree.parse(os.path.join(ROOT, 'views', 'layouts.xml'))
        tpl = tree.xpath('//template[@id="wujia_portal_layout.app_layout"]')
        self.assertEqual(len(tpl), 1, 'không thấy template app_layout')
        return tpl[0]

    def test_mot_container_boc_noi_dung_route(self):
        """PC-1: đúng MỘT <main.wj-page-container> và nó bọc chính `t-out="0"`."""
        tpl = self._app_layout_file()
        mains = tpl.xpath('.//main[contains(@t-attf-class, "wj-page-container")]')
        self.assertEqual(len(mains), 1, 'app_layout phải có đúng một PageContainer')
        self.assertEqual(len(mains[0].xpath('./t[@t-out="0"]')), 1,
                         'nội dung route (t-out="0") phải là con trực tiếp của PageContainer')
        self.assertEqual(len(tpl.xpath('.//t[@t-out="0"]')), 1,
                         'còn nội dung route nằm ngoài PageContainer')

    def test_shell_nam_ngoai_container(self):
        """Header mobile, dải bóng navbar, bottom-nav là Global Shell — không nằm trong container."""
        main = self._app_layout_file().xpath('.//main')[0]
        inner = etree.tostring(main, encoding='unicode')
        for shell in ('mobile_header', 'mobile_bottomnav', 'header-navbar-shadow', 'layout_sidenav'):
            self.assertNotIn(shell, inner, '%s lọt vào trong PageContainer' % shell)

    def test_arch_ghep_van_mot_container(self):
        """Sau khi ghép mọi view kế thừa (store picker của portal_base…) vẫn đúng một container."""
        view = self.env.ref('wujia_portal_layout.app_layout')
        arch = view.get_combined_arch()
        self.assertEqual(arch.count('wj-page-container '), 1, arch[:200])

    def test_bien_the_list_qua_co(self):
        """`pc_gutter='list'` là công tắc duy nhất; route không đặt thì về mặc định."""
        main = self._app_layout_file().xpath('.//main')[0]
        cls = main.get('t-attf-class')
        self.assertIn("wj-page-container--list", cls)
        self.assertIn("pc_gutter == 'list'", cls)

    # ------------------------------------------------------------------- token
    def test_token_gutter(self):
        css = _css('_variables.css')
        root = _body(css, ':root')
        self.assertRegex(root, r'--wj-page-gutter:\s*24px')
        self.assertRegex(root, r'--wj-page-gutter-m:\s*16px')
        self.assertRegex(root, r'--wj-page-gutter-m-list:\s*var\(--wujia-mshell-content-pad-x\)')
        self.assertRegex(root, r'--wj-page-pad-bottom:\s*32px')

    # --------------------------------------------------------------------- CSS
    def test_container_tang_goc(self):
        body = _body(_css('_wujia_theme.css'), '.wj-page-container')
        self.assertIn('var(--wj-page-gutter)', body, 'gutter PC phải lấy từ token')
        self.assertIn('var(--wj-page-pad-bottom)', body)
        self.assertRegex(body, r'background:\s*transparent', 'PageContainer trong suốt (tiêu chí 8)')
        self.assertNotRegex(body, r'overflow(-x)?\s*:\s*hidden', 'không che lỗi tràn bằng overflow')

    def test_container_pc_tranh_top_bar(self):
        """992–1199 và ≥1200 cùng MỘT rule (trước E7a: 1200 riêng, tablet rơi về Vuexy 30,8)."""
        body = _body(_css('_wujia_theme.css'), '.wj-page-container', PC)
        self.assertIn('var(--wujia-header-height)', body)

    def test_container_mobile(self):
        css = _css('_wujia_theme.css')
        body = _body(css, '.wj-page-container', MOBILE)
        self.assertIn('var(--wj-page-gutter-m)', body)
        self.assertIn('env(safe-area-inset-bottom', body, 'đáy mobile phải cộng safe area')
        self.assertIn('var(--wujia-mshell-content-pad-bottom)', body)
        lst = _body(css, '.wj-page-container--list', MOBILE)
        self.assertIn('var(--wj-page-gutter-m-list)', lst)

    def test_content_wrapper_khong_giu_le(self):
        """Vỏ Vuexy `.content-wrapper` về 0 ở MỌI khổ — không rule nào của khung trả lề cho nó."""
        rules = _rules(_css('_wujia_theme.css'))
        goc = [b for m, s, b in rules if not m and s.strip() == 'html body .content .content-wrapper']
        self.assertTrue(goc, 'thiếu rule đưa content-wrapper về 0')
        self.assertTrue(any(re.search(r'padding:\s*0\s*!important', b) for b in goc))
        self.assertTrue(any(re.search(r'margin-top:\s*0\s*!important', b) for b in goc))
        tra_le = [(m, s) for m, s, b in rules
                  if any(p.strip().endswith('.content-wrapper') for p in s.split(','))
                  and _co_padding(b)]
        self.assertFalse(tra_le, 'còn rule trả lề cho content-wrapper: %s' % tra_le)

    def test_app_content_khong_giu_day(self):
        """Khoảng chừa bottom-nav nay là padding-bottom của container, không phải .app-content."""
        for name in ('_components.css', '_wujia_theme.css'):
            for m, s, b in _rules(_css(name)):
                if any(p.strip().endswith('.app-content') or p.strip().endswith('.app-content.content')
                       for p in s.split(',')):
                    self.assertNotRegex(b, r'padding-bottom', '%s: %s' % (name, s))

    def test_mpage_khong_giu_le(self):
        """`.wujia-mpage` (BlankShell mobile) chỉ còn bố cục — không padding."""
        for m, s, b in _rules(_css('_components.css')):
            if '.wujia-mpage' in [p.strip() for p in s.split(',')]:
                self.assertNotRegex(b, r'(^|;)\s*padding', s)

    # ------------------------------------------------------------- E7b width
    def test_bien_the_width_va_day_qua_co(self):
        """`pc_width` chỉ nhận standard|narrow (fluid = không class); `pc_bottom='sticky'`."""
        cls = self._app_layout_file().xpath('.//main')[0].get('t-attf-class')
        self.assertIn("pc_width in ('standard', 'narrow')", cls)
        self.assertIn("'wj-page-container--' + pc_width", cls)
        self.assertIn("wj-page-container--sticky", cls)
        self.assertIn("pc_bottom == 'sticky'", cls)

    def test_token_width(self):
        root = _body(_css('_variables.css'), ':root')
        self.assertRegex(root, r'--wj-page-width-standard:\s*1440px')
        self.assertRegex(root, r'--wj-page-width-narrow:\s*960px')
        self.assertRegex(root, r'--wj-sticky-action-h:\s*\d+px')
        self.assertRegex(root, r'--wj-sticky-action-gap:\s*\d+px')

    def test_width_tren_chinh_container(self):
        """Max-width nằm trên container (bề rộng trong + 2 gutter), căn giữa — PageHeader
        nằm trong container nên cùng bề rộng với nội dung."""
        css = _css('_wujia_theme.css')
        for variant in ('standard', 'narrow'):
            body = _body(css, '.wj-page-container--%s' % variant)
            self.assertRegex(body, r'max-width:\s*calc\(var\(--wj-page-width-%s\)\s*\+\s*2\s*\*\s*'
                                   r'var\(--wj-page-gutter\)\)' % variant, variant)
            self.assertRegex(body, r'margin-left:\s*auto', variant)
            self.assertRegex(body, r'margin-right:\s*auto', variant)
            self.assertNotRegex(body, r'overflow', variant)
        self.assertFalse(_body(css, '.wj-page-container--fluid'), 'fluid là mặc định, không có class riêng')

    def test_day_sticky_mobile(self):
        body = _body(_css('_wujia_theme.css'), '.wj-page-container--sticky', MOBILE)
        for token in ('--wujia-mnav-total', '--wj-sticky-action-h', '--wj-sticky-action-gap'):
            self.assertIn('var(%s)' % token, body)

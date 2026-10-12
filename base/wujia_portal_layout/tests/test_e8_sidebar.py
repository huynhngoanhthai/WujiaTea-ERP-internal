"""E8b — CMP-SN-001 SidebarNavigation (UI-SIDEBAR-001): hợp đồng khung + CSS/JS của nó.

BA: sidebar 264 cố định ≥1200 · drawer đóng mặc định ở 992–1199 (hamburger, nút Đóng,
Escape, backdrop, trả focus) · ẩn <992 (mobile dùng bottom-nav) · brand 88, logo ≤160×64 ·
mục cao 44, bo 10 mọi state, icon 20, chữ 15/22/500, active 700 + nền #EAF7FD + chữ
#168FC2 + rail trái 3px.

Danh sách mục/nhóm/quyền nằm ở `wujia_portal_base/tests/test_f5_menu_ownership.py`
(đụng nhiều module). File này chỉ đo phần của khung, chạy được trên DB chỉ cài khung.
"""
import os
import re

from lxml import etree

from odoo.tests import HttpCase, TransactionCase, tagged

from .common import load_vi

from .test_e7_page_container import _body

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, '..')
STATIC = os.path.join(ROOT, 'static', 'assets')
DRAWER = '@media (min-width: 992px) and (max-width: 1199.98px)'


def _read(*parts, strip_comments=True):
    with open(os.path.join(STATIC, *parts), encoding='utf-8') as fh:
        text = fh.read()
    if strip_comments:
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return text


def _token(name):
    m = re.search(r'--%s\s*:\s*([^;]+);' % re.escape(name), _read('css', '_variables.css'))
    return m and m.group(1).strip()


@tagged('post_install', '-at_install', 'wujia_e8')
class TestSidebarCss(TransactionCase):

    def test_token_kich_thuoc(self):
        self.assertEqual(_token('wujia-sidebar-width'), '264px')
        self.assertEqual(_token('wujia-sidebar-brand-h'), '88px')
        self.assertEqual(_token('wujia-menu-item-height'), '44px')
        self.assertEqual(_token('wujia-menu-icon-size'), '20px')
        self.assertEqual(_token('wujia-menu-text-size'), '15px')
        self.assertEqual(_token('wujia-menu-text-lh'), '22px')

    def test_brand_88_logo_toi_da_160x64(self):
        css = _read('css', '_sidebar.css')
        brand = _body(css, '#wj-main-menu .wj-sidebar__brand')
        self.assertIn('height: var(--wujia-sidebar-brand-h)', brand)
        logo = _body(css, '#wj-main-menu .wj-sidebar__logo img')
        self.assertIn('max-width: 160px', logo)
        self.assertIn('max-height: 64px', logo)
        self.assertIn('object-fit: contain', logo)

    def test_dang_muc(self):
        css = _read('css', '_sidebar.css')
        item = _body(css, '#wj-main-menu .navigation > li > a')
        for decl in ('height: var(--wujia-menu-item-height)', 'padding: 10px 12px',
                     'gap: 12px', 'border-radius: 10px !important',
                     'font-size: var(--wujia-menu-text-size)',
                     'line-height: var(--wujia-menu-text-lh)', 'font-weight: 500'):
            self.assertIn(decl, item)
        icon = _body(css, '#wj-main-menu .navigation > li > a > i')
        self.assertIn('font-size: var(--wujia-menu-icon-size)', icon)

    def test_hover_khong_truot(self):
        """Vuexy đẩy mục 25px khi hover — state chỉ đổi màu."""
        css = _read('css', '_sidebar.css')
        self.assertIn('transform: none !important',
                      _body(css, '#wj-main-menu .navigation > li > a:hover'))

    def test_active_nen_chu_rail(self):
        css = _read('css', '_sidebar.css')
        active = _body(css, '#wj-main-menu .navigation > li.active > a')
        self.assertIn('background: var(--wujia-primary-soft)', active)
        self.assertIn('color: var(--wujia-brand-text-hover)', active)   # WJ-PORTAL-UI-006: #168FC2 chỉ 3.66
        self.assertIn('font-weight: 700', active)
        rail = _body(css, '#wj-main-menu .navigation > li.active > a::before')
        self.assertIn('width: 3px', rail)
        self.assertIn('position: absolute', rail)   # rail không đẩy layout
        self.assertEqual(_token('wujia-primary-soft'), '#EAF7FD')
        self.assertEqual(_token('wujia-brand-text-hover'), '#125C7B')

    def test_drawer_992_1199(self):
        css = _read('css', '_sidebar.css')
        closed = _body(css, 'body.vertical-layout #wj-main-menu', DRAWER)
        self.assertIn('left: calc(-1 * var(--wujia-sidebar-width))', closed)
        # style.css:96 đặt .main-menu 1040 !important — drawer phải nằm trên backdrop.
        self.assertIn('z-index: 1041 !important', closed)
        opened = _body(css, 'body.vertical-layout.menu-open #wj-main-menu', DRAWER)
        self.assertIn('translate3d(var(--wujia-sidebar-width), 0, 0)', opened)
        self.assertIn('display: block', _body(css, 'body.menu-open .sidenav-overlay', DRAWER))
        self.assertIn('display: inline-flex', _body(css, '#wj-main-menu .wj-sidebar__close', DRAWER))
        self.assertIn('display: none', _body(css, '#wj-main-menu .wj-sidebar__close'))

    def test_an_duoi_992(self):
        css = _read('css', '_sidebar.css')
        self.assertIn('display: none !important',
                      _body(css, '#wj-main-menu', '@media (max-width: 991.98px)'))
        self.assertIn('display: none !important',
                      _body(css, '.sidenav-overlay', '@media (max-width: 991.98px), (min-width: 1200px)'))

    def test_nhom_rong_an_tieu_de(self):
        """Render theo quyền: nhóm hết mục thì không chừa tiêu đề trơ trọi."""
        css = _read('css', '_sidebar.css')
        body = _body(css, '#wj-main-menu .navigation > li.wujia-nav-header:has(+ li.wujia-nav-header)')
        self.assertIn('display: none', body)
        self.assertIn('display: none', _body(css, '#wj-main-menu .navigation > #nav_end'))

    def test_brand_cu_da_go(self):
        """Khối brand/mục cũ ở _wujia_theme.css đã dời hết sang _sidebar.css."""
        theme = _read('css', '_wujia_theme.css')
        self.assertNotIn('wujia-sidebar-logo-h', theme)
        self.assertNotIn('wujia-sidebar-header-gap', theme)
        self.assertNotIn('wujia-sidebar-logo-h', _read('css', '_variables.css'))


@tagged('post_install', '-at_install', 'wujia_e8')
class TestSidebarJs(TransactionCase):

    def test_chi_ep_mo_tu_1200(self):
        js = _read('js', 'my_js.js', strip_comments=False)
        m = re.search(r'function _wujiaForceMenuExpanded\(\)\s*\{(.*?)\n\}', js, re.S)
        self.assertTrue(m, 'mất _wujiaForceMenuExpanded')
        self.assertIn("matchMedia('(min-width: 1200px)')", m.group(1))

    def test_drawer_js(self):
        js = _read('js', 'wujia_sidebar.js')
        self.assertIn("'(min-width: 992px) and (max-width: 1199.98px)'", js)
        self.assertIn("ev.key === 'Escape'", js)
        self.assertIn('.sidenav-overlay', js)
        self.assertIn('.wj-sidebar__close', js)
        self.assertIn("setAttribute('aria-expanded'", js)
        self.assertIn('lastToggle.focus()', js)          # đóng xong trả focus về hamburger
        self.assertIn('stopImmediatePropagation', js)    # chặn handler ủy quyền của Vuexy
        self.assertRegex(js, r"addEventListener\('click',[\s\S]*?\}, true\);")  # pha capture


@tagged('post_install', '-at_install', 'wujia_e8')
class TestSidebarShell(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = load_vi(cls.env)

    def _arch(self, key):
        return self.env.ref(key).arch

    def test_brand_khong_con_kich_thuoc_cung(self):
        arch = self._arch('wujia_portal_layout.layout_sidenav')
        self.assertNotIn('mb-5', arch)
        self.assertNotIn('width="200"', arch)
        self.assertNotIn('height="100"', arch)
        self.assertIn('id="wj-main-menu"', arch)
        self.assertIn('aria-label="Điều hướng chính"', arch)
        self.assertIn('class="wj-sidebar__close"', arch)

    def test_nav_item_co_aria_current(self):
        arch = self._arch('wujia_portal_layout.wj_nav_item')
        self.assertIn('t-att-aria-current="\'page\' if ni_active else None"', arch)

    def test_asset_nap_css_js_sidebar(self):
        with open(os.path.join(ROOT, 'views', 'assets.xml'), encoding='utf-8') as fh:
            xml = fh.read()
        self.assertRegex(xml, r'_sidebar\.css\?v=\d+')
        self.assertRegex(xml, r'wujia_sidebar\.js\?v=\d+')
        self.assertRegex(xml, r'my_js\.js\?v=\d+')


@tagged('post_install', '-at_install', 'wujia_e8')
class TestSidebarRendered(HttpCase):
    """Trang thật của khung (`/portal/profile`) — chạy được cả trên DB chỉ cài khung."""

    def setUp(self):
        super().setUp()
        self.env['res.users'].create({
            'name': 'E8 Sidebar', 'login': 'e8.sidebar@wujia.test', 'password': 'e8-sidebar-pw'})
        self.authenticate('e8.sidebar@wujia.test', 'e8-sidebar-pw')
        res = self.url_open('/portal/profile', timeout=30)
        self.assertEqual(res.status_code, 200)
        self.html = etree.HTML(res.text)

    def test_mot_backdrop(self):
        self.assertEqual(len(self.html.xpath("//*[contains(concat(' ', @class, ' '), ' sidenav-overlay ')]")), 1)

    def test_hamburger_la_button(self):
        toggles = self.html.xpath("//*[contains(concat(' ', @class, ' '), ' wj-menu-toggle ')]")
        self.assertEqual(len(toggles), 1)
        btn = toggles[0]
        self.assertEqual(btn.tag, 'button')
        self.assertEqual(btn.get('type'), 'button')
        self.assertTrue(btn.get('aria-label'))
        self.assertEqual(btn.get('aria-controls'), 'wj-main-menu')
        self.assertEqual(btn.get('aria-expanded'), 'false')
        self.assertIsNone(btn.get('style'))
        self.assertTrue(self.html.xpath("//*[@id='wj-main-menu']"), 'aria-controls trỏ vào id không có')

    def test_neo_nhom_co_mat_khi_render(self):
        ids = [li.get('id') for li in self.html.xpath("//ul[@id='main-menu-navigation']/li")]
        for anchor in ('nav_header_main', 'nav_header_finance', 'nav_header_ops', 'nav_end'):
            self.assertIn(anchor, ids)
        self.assertNotIn('nav_item_account', ids)
        # Trang của khung không thuộc mục sidebar nào ⇒ không mục nào sáng / aria-current.
        self.assertFalse(self.html.xpath("//ul[@id='main-menu-navigation']//a[@aria-current]"))

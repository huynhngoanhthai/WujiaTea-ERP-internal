"""CMP-SN-001 (UI-SIDEBAR-001) — nhóm cửa hàng trong avatar + sheet "Thêm" mobile theo quyền.

Guard nhiều module (sheet gom dòng của 6–7 module) ⇒ nằm ở L3a như test_f5_menu_ownership.
BA: "Hồ sơ cửa hàng" + "Tài khoản/Cài đặt" chuyển vào avatar, không trùng trong "Thêm";
thứ tự, tên gọi, route, quyền nhất quán PC/mobile.
"""
import re

from lxml import etree

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from .common import need_suite

# Sheet "Thêm" (mobile) — cùng thứ tự các mục ngoài bottom-nav trên sidebar PC.
GOLDEN_SHEET = [
    ('/portal/debt', 'Công nợ & thanh toán'),
    ('/portal/return', 'Đổi trả / Bù hàng'),
    ('/portal/exam', 'Đăng ký thi'),
    ('/portal/knowledge', 'Kiến thức'),
    ('/portal/support', 'Hỗ trợ'),
    ('/portal/reports/orders', 'Báo cáo'),
]
INSPECTION = '/portal/inspection'
MENUS = ('wj-pc-acct-menu', 'wujia-mheader-menu')


def _text(el):
    return re.sub(r'\s+', ' ', ''.join(el.itertext())).strip()


@tagged('post_install', '-at_install', 'wujia_e8')
class TestAccountMenuStore(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        mk = lambda code: env['wujia.franchise.management'].create({  # noqa: E731
            'code': code, 'name': f'E8c store {code}', 'franchise_end_date': '2030-01-01',
            'partner_id': env['res.partner'].create({'name': f'E8c partner {code}'}).id})
        cls.store, cls.store2 = mk('E8C1'), mk('E8C2')
        for login, rows in (('e8c_owner', [(cls.store, 'owner')]),
                            ('e8c_staff', [(cls.store, 'staff')]),
                            ('e8c_mixed', [(cls.store, 'staff'), (cls.store2, 'manager')])):
            user = env['res.users'].create({
                'name': login, 'login': login, 'password': login,
                'group_ids': [(6, 0, [env.ref('base.group_portal').id])]})
            for franchise, role in rows:
                env['wujia.franchise.member'].create({
                    'user_id': user.id, 'franchise_id': franchise.id, 'role': role})

    def _page(self, login, route='/portal', store=None):
        self.authenticate(login, login)
        if store:
            self.opener.cookies.set('wujia_active_franchise_id', str(store.id))
        res = self.url_open(route, timeout=30)
        self.assertEqual(res.status_code, 200, route)
        return etree.HTML(res.text)

    def _menu(self, html, cls):
        menus = html.xpath(f"//div[contains(concat(' ', @class, ' '), ' {cls} ')]")
        self.assertEqual(len(menus), 1, cls)
        return menus[0]

    def _keys(self, menu):
        out = []
        for el in menu:
            cls = el.get('class') or ''
            if 'wj-acct-menu__group' in cls:
                out.append('LANG')
            elif 'wj-acct-menu__store' in cls:
                out.append('STORE')
            elif el.tag == 'a':
                out.append(el.get('data-action') or el.get('href'))
        return out

    def _sheet(self, html):
        return [(a.get('href'), _text(a.xpath(".//*[contains(@class, 'wujia-msheet-item-title')]")[0]))
                for a in html.xpath("//div[contains(@class, 'wujia-msheet-list')]/a")]

    # ── Avatar ────────────────────────────────────────────────────────────
    def test_thu_tu_avatar_theo_ba_ca_pc_lan_mobile(self):
        html = self._page('e8c_owner')
        for cls in MENUS:
            self.assertEqual(self._keys(self._menu(html, cls)), [
                '/portal/profile', '/portal/change-password', 'LANG', 'STORE',
                '/portal/franchise-information', '/portal/logout'], cls)

    def test_khoi_cua_hang_co_ma_ten_vai_tro(self):
        html = self._page('e8c_owner')
        for cls in MENUS:
            block = self._menu(html, cls).xpath(".//div[contains(@class, 'wj-acct-menu__store')]")[0]
            self.assertIn('E8C1', _text(block))
            self.assertIn('E8c store E8C1', _text(block))
            chip = block.xpath(".//span[contains(@class, 'wj-acct-menu__role')]")[0]
            self.assertIn('wujia-store-role-badge-owner', chip.get('class'))
            self.assertEqual(_text(chip), 'Chủ tiệm')

    def test_doi_cua_hang_chi_khi_nhieu_cua_hang(self):
        single = self._page('e8c_owner')
        multi = self._page('e8c_mixed', store=self.store2)
        for cls in MENUS:
            self.assertFalse(self._menu(single, cls).xpath(".//a[@data-action='open-store-picker']"), cls)
            btn = self._menu(multi, cls).xpath(".//a[@data-action='open-store-picker']")
            self.assertEqual(len(btn), 1, cls)
            self.assertEqual(_text(btn[0]), 'Đổi cửa hàng')
            self.assertEqual(btn[0].get('role'), 'button')
        # modal mà nút mở phải có trên trang
        self.assertTrue(multi.xpath("//*[contains(@class, 'wujia-store-overlay')]"))
        self.assertEqual(self._keys(self._menu(multi, 'wj-pc-acct-menu'))[3:6],
                         ['STORE', 'open-store-picker', '/portal/franchise-information'])

    def test_ho_so_cua_hang_sang_o_ho_so_va_info_request(self):
        routes = ['/portal/franchise-information']
        if self.env['ir.module.module']._get('wujia_portal_info_request').state == 'installed':
            routes.append('/portal/info-request')
        for route in routes:
            html = self._page('e8c_owner', route)
            for cls in MENUS:
                cur = self._menu(html, cls).xpath(".//a[@aria-current='page']")
                self.assertEqual([a.get('href') for a in cur], ['/portal/franchise-information'],
                                 f'{route} {cls}')
                self.assertIn('is-active', cur[0].get('class'))

    def test_ten_ho_so_cua_hang_o_menu_va_tieu_de(self):
        html = self._page('e8c_owner', '/portal/franchise-information')
        for cls in MENUS:
            link = self._menu(html, cls).xpath(".//a[@href='/portal/franchise-information']")[0]
            self.assertEqual(_text(link), 'Hồ sơ cửa hàng')
        # PC (acct_title) và mobile (ph_title) cùng đổ vào WjPageHeader
        heads = [_text(h) for h in html.xpath("//h1[contains(@class, 'wj-page-header__title')]")]
        self.assertTrue(heads)
        self.assertEqual(set(heads), {'Hồ sơ cửa hàng'})
        nav = html.xpath("//nav[contains(@class, 'wj-pc-acct-nav__list')]"
                         "/a[@href='/portal/franchise-information']")
        self.assertEqual(_text(nav[0]), 'Hồ sơ cửa hàng')

    # ── Sheet "Thêm" ──────────────────────────────────────────────────────
    def _golden(self, html, drop=()):
        rows = self._sheet(html)
        exp = [g for g in GOLDEN_SHEET if g[0] not in drop]
        if rows and rows[-1][0] == INSPECTION:   # Khảo sát (anh Thái) luôn cuối nếu cài
            exp = exp + [rows[-1]]
        return rows, exp

    def test_sheet_khong_trung_voi_avatar(self):
        html = self._page('e8c_owner')
        hrefs = [h for h, _ in self._sheet(html)]
        for gone in ('/portal/profile', '/portal/franchise-information', '/portal/change-password'):
            self.assertNotIn(gone, hrefs)

    def test_sheet_owner_du_muc_dung_thu_tu(self):
        need_suite(self)
        rows, exp = self._golden(self._page('e8c_owner'))
        self.assertEqual(rows, exp)

    def test_sheet_theo_quyen(self):
        need_suite(self)
        rows, exp = self._golden(self._page('e8c_staff'),
                                 drop=('/portal/debt', '/portal/reports/orders'))
        self.assertEqual(rows, exp)
        # staff ở cửa hàng đang chọn, manager nơi khác: quyền theo cửa hàng đang chọn (như sidebar)
        rows, exp = self._golden(self._page('e8c_mixed', store=self.store),
                                 drop=('/portal/debt', '/portal/reports/orders'))
        self.assertEqual(rows, exp)
        rows, exp = self._golden(self._page('e8c_mixed', store=self.store2))
        self.assertEqual(rows, exp)

    def test_sheet_cung_quyen_voi_sidebar(self):
        for login, store in (('e8c_owner', None), ('e8c_staff', None),
                             ('e8c_mixed', self.store), ('e8c_mixed', self.store2)):
            html = self._page(login, store=store)
            side = set(html.xpath("//ul[@id='main-menu-navigation']/li/a/@href"))
            for href in ('/portal/debt', '/portal/reports/orders'):
                self.assertEqual(href in side, href in [h for h, _ in self._sheet(html)],
                                 f'{login} {store and store.code} {href}')

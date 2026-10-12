"""CMP-SN-001 (UI-SIDEBAR-001) — menu avatar dùng chung PC + mobile, sheet "Thêm" mobile.

Phần khung: thân menu chỉ chứa route của chính khung + neo trung tính cho nhóm cửa hàng;
ngôn ngữ vừa ở header (CMP-GH-001) vừa ở avatar; nút avatar đủ aria. Nhóm cửa hàng và
quyền sheet kiểm ở wujia_portal_base (cần franchise).
"""
import re

from lxml import etree

from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase

from .common import load_vi

FRAME_HREFS = ['/portal/profile', '/portal/change-password', '/portal/set-lang/', '/portal/logout']


def _text(el):
    return re.sub(r'\s+', ' ', ''.join(el.itertext())).strip()


def _arch(env, xmlid):
    return etree.fromstring(env.ref(xmlid).arch_db)


@tagged('post_install', '-at_install', 'wujia_e8')
class TestAccountMenuArch(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = load_vi(cls.env)

    def test_than_menu_chi_co_route_khung_dung_thu_tu(self):
        root = _arch(self.env, 'wujia_portal_layout.wj_acct_menu_items')
        hrefs = [a.get('href') or a.get('t-attf-href') for a in root.iter('a')]
        self.assertEqual([h.split('{{')[0] for h in hrefs], FRAME_HREFS)

    def test_neo_nhom_cua_hang_nam_truoc_dang_xuat(self):
        root = _arch(self.env, 'wujia_portal_layout.wj_acct_menu_items')
        kids = [el for el in root if el.tag is not etree.Comment]
        anchor = [i for i, el in enumerate(kids) if el.get('data-wj-anchor') == 'acct_store_end']
        self.assertEqual(len(anchor), 1)
        # neo là data-attribute: partial render 2 lần/trang (PC + mobile) ⇒ id sẽ trùng
        self.assertIsNone(kids[anchor[0]].get('id'))
        self.assertEqual(kids[anchor[0] + 1].get('href'), '/portal/logout')

    def test_nhom_ngon_ngu_co_nhan_va_aria_current(self):
        root = _arch(self.env, 'wujia_portal_layout.wj_acct_menu_items')
        group = root.xpath("//div[contains(@class, 'wj-acct-menu__group')]")
        self.assertEqual(len(group), 1)
        self.assertEqual(group[0].get('role'), 'group')
        self.assertEqual(group[0].get('aria-label'), 'Ngôn ngữ')
        link = group[0].xpath('.//a')[0]
        self.assertIn('_wj_portal_langs', link.get('t-foreach'))
        self.assertIn('aria-current', ' '.join(link.attrib))

    def test_pc_va_mobile_cung_goi_than_chung(self):
        for xmlid in ('wujia_portal_layout.layout_top_navbar', 'wujia_portal_layout.mobile_header'):
            arch = self.env.ref(xmlid).arch_db
            self.assertEqual(arch.count('t-call="wujia_portal_layout.wj_acct_menu_items"'), 1, xmlid)
            for href in ('/portal/profile', '/portal/change-password', '/portal/logout'):
                self.assertNotIn(f'href="{href}"', arch, f'{xmlid} còn mục riêng {href}')

    def test_header_van_giu_nut_ngon_ngu(self):
        """CMP-GH-001: header = logo/ngôn ngữ/cart/avatar — cả PC lẫn mobile."""
        pc = _arch(self.env, 'wujia_portal_layout.layout_top_navbar')
        self.assertTrue(pc.xpath("//li[contains(@class, 'dropdown-language')]"))
        mobile = _arch(self.env, 'wujia_portal_layout.mobile_header')
        self.assertTrue(mobile.xpath("//*[contains(@class, 'dropdown-language')]"))

    def test_sheet_them_khong_con_tai_khoan(self):
        root = _arch(self.env, 'wujia_portal_layout.mobile_bottomnav')
        sheet = root.xpath("//div[contains(@class, 'wujia-msheet-list')]")[0]
        self.assertFalse(sheet.xpath(".//a[@href='/portal/profile']"))
        end = sheet.xpath(".//span[@id='msheet_end']")
        self.assertEqual(len(end), 1)
        self.assertEqual(end[0].get('hidden'), 'hidden')


@tagged('post_install', '-at_install', 'wujia_e8')
class TestAccountMenuRendered(HttpCase):
    """Trang thật của khung — chạy được cả trên DB chỉ cài khung."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = load_vi(cls.env)

    def setUp(self):
        super().setUp()
        self.env['res.users'].create({
            'name': 'E8c Acct', 'login': 'e8c.acct@wujia.test', 'password': 'e8c-acct-pw',
            'lang': 'vi_VN'})
        self.authenticate('e8c.acct@wujia.test', 'e8c-acct-pw')
        res = self.url_open('/portal/profile', timeout=30)
        self.assertEqual(res.status_code, 200)
        self.html = etree.HTML(res.text)

    def _menu(self, cls):
        menus = self.html.xpath(f"//div[contains(concat(' ', @class, ' '), ' {cls} ')]")
        self.assertEqual(len(menus), 1, cls)
        return menus[0]

    def _links(self, menu):
        return [(a.get('href') or '').split('/portal/set-lang/')[0] or 'LANG'
                for a in menu.xpath('.//a')]

    def test_pc_va_mobile_cung_thu_tu(self):
        pc = self._links(self._menu('wj-pc-acct-menu'))
        mobile = self._links(self._menu('wujia-mheader-menu'))
        self.assertEqual(pc, mobile)
        head = [h for h in pc if h != 'LANG']
        self.assertEqual(head[:2], ['/portal/profile', '/portal/change-password'])
        self.assertEqual(head[-1], '/portal/logout')
        self.assertLess(pc.index('/portal/change-password'), pc.index('LANG'))

    def test_muc_hien_tai_sang(self):
        for cls in ('wj-pc-acct-menu', 'wujia-mheader-menu'):
            menu = self._menu(cls)
            cur = menu.xpath(".//a[@aria-current='page']")
            self.assertEqual([a.get('href') for a in cur], ['/portal/profile'], cls)
            self.assertIn('is-active', cur[0].get('class'))
            langs = menu.xpath(".//a[starts-with(@href, '/portal/set-lang/')][@aria-current='true']")
            self.assertEqual(len(langs), 1, cls)

    def test_khong_co_cua_hang_thi_khong_hai_divider_lien(self):
        for cls in ('wj-pc-acct-menu', 'wujia-mheader-menu'):
            kids = [el.get('class') or '' for el in self._menu(cls)]
            pairs = [a for a, b in zip(kids, kids[1:]) if 'dropdown-divider' in a and 'dropdown-divider' in b]
            self.assertFalse(pairs, cls)

    def test_nut_avatar_du_aria(self):
        toggles = self.html.xpath(
            "//a[contains(@class, 'dropdown-user-link')] | //a[contains(@class, 'wujia-mheader-avatar')]")
        self.assertEqual(len(toggles), 2)
        for a in toggles:
            self.assertEqual(a.get('aria-label'), 'Tài khoản')
            self.assertEqual(a.get('aria-haspopup'), 'true')
            self.assertEqual(a.get('aria-expanded'), 'false')

    def test_nhan_muc_menu(self):
        pc = self._menu('wj-pc-acct-menu')
        labels = [_text(a) for a in pc.xpath('./a')]
        self.assertEqual(labels[:2], ['Thông tin tài khoản', 'Đổi mật khẩu'])
        self.assertEqual(labels[-1], 'Đăng xuất')
        self.assertEqual(_text(pc.xpath(".//span[@class='wj-acct-menu__label']")[0]), 'Ngôn ngữ')

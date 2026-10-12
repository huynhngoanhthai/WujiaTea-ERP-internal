"""G2 — Current Store Switcher mobile (UI-MOB-STORE-SWITCHER-001) + khối Cửa hàng hiện tại PC
(UI-PC-TOPBAR-REG-001).

Chủ dự án chốt 29/09: chevron chỉ khi đổi được cửa hàng (>1); nhãn vai trò một nguồn tiếng Việt
(`ROLE_LABELS`) ở mọi chỗ in vai trò; dải hiện cả trên Home; chip vai trò nằm trong khối PC.
"""
import re

from lxml import etree

from odoo.tests import TransactionCase, tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_portal_base.tests.css_probe import _mod_css, _rule, _strip_comments

STRIP = "//*[contains(concat(' ', @class, ' '), ' wujia-store-mobile-strip ')]"
CHEVRON = ".//i[contains(@class, 'wujia-store-strip-chevron')]"


def _text(el):
    return re.sub(r'\s+', ' ', ''.join(el.itertext())).strip()


@tagged('post_install', '-at_install', 'wujia_store_switcher_g2')
class TestStoreSwitcherG2(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        mk = lambda code: env['wujia.franchise.management'].create({  # noqa: E731
            'code': code, 'name': f'G2 store {code}', 'franchise_end_date': '2030-01-01',
            'partner_id': env['res.partner'].create({'name': f'G2 partner {code}'}).id})
        cls.store, cls.store2 = mk('G2S1'), mk('G2S2')
        for login, rows in (('g2_owner', [(cls.store, 'owner')]),
                            ('g2_mixed', [(cls.store, 'staff'), (cls.store2, 'manager')])):
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

    def _strip(self, html):
        strips = html.xpath(STRIP)
        self.assertEqual(len(strips), 1)
        return strips[0]

    def test_chevron_chi_khi_doi_duoc_cua_hang(self):
        single = self._strip(self._page('g2_owner'))
        self.assertEqual(single.tag, 'div')
        self.assertFalse(single.xpath(CHEVRON))
        multi = self._strip(self._page('g2_mixed', store=self.store2))
        self.assertEqual(multi.tag, 'a')
        self.assertEqual(multi.get('data-action'), 'open-store-picker')
        # chevron nằm TRONG thẻ bấm, sau chip vai trò
        self.assertEqual(len(multi.xpath(CHEVRON)), 1)
        self.assertEqual([c.get('class').split()[0] for c in multi][-2:],
                         ['wujia-store-strip-role', 'feather'])

    def test_dai_hien_tren_home_va_trang_khac(self):
        for route in ('/portal', '/portal/profile'):
            self._strip(self._page('g2_owner', route))

    def test_nhan_vai_tro_mot_nguon_tieng_viet(self):
        for login, store, label in (('g2_owner', None, 'Chủ tiệm'),
                                    ('g2_mixed', self.store2, 'Quản lý'),
                                    ('g2_mixed', self.store, 'Nhân viên')):
            html = self._page(login, store=store)
            spots = {
                'strip': html.xpath("//span[contains(@class, 'wujia-store-strip-role')]"),
                'pc_block': html.xpath("//div[contains(@class, 'wujia-store-current-block')]"
                                       "//span[contains(@class, 'wujia-store-role-badge')]"),
                'avatar': html.xpath("//span[contains(@class, 'wj-pc-user-nav__role')]"),
                'acct_menu': html.xpath("//span[contains(@class, 'wj-acct-menu__role')]"),
                'home_hero': html.xpath("//span[contains(@class, 'wujia-mhome-role-badge')]"),
            }
            for spot, els in spots.items():
                self.assertTrue(els, f'{login}/{spot}: không có chỗ in vai trò')
                self.assertEqual({_text(e) for e in els}, {label}, f'{login}/{spot}')

    def test_chip_vai_tro_nam_trong_khoi_pc(self):
        html = self._page('g2_owner')
        block = html.xpath("//div[contains(@class, 'wujia-store-current-block')]")[0]
        self.assertEqual(len(block.xpath(".//a[@data-action='open-store-picker']")), 1)
        self.assertEqual(len(block.xpath(".//span[contains(@class, 'wujia-store-role-badge')]")), 1)


@tagged('post_install', '-at_install', 'wujia_store_switcher_g2')
class TestStoreBlockCssG2(TransactionCase):

    def setUp(self):
        super().setUp()
        self.css = _mod_css('wujia_portal_base', 'store_picker.css')

    def test_nen_thuoc_ve_ca_khoi(self):
        self.assertIn('background-color: var(--wujia-navbar-pill-bg)',
                      _rule(self.css, '.wujia-store-current-block'))
        # pill trong suốt cả lúc hover — nếu không, hover vẽ lại "pill trong pill"
        bodies = [b for s, b in re.findall(r'([^{}]+)\{([^{}]*)\}', _strip_comments(self.css))
                  if '.wujia-store-current-block .wujia-active-store-badge:hover' in s]
        self.assertTrue(bodies and 'transparent' in bodies[0])

    def test_khoi_co_duoc_o_992_1199(self):
        """992–1199 hàng trái không xuống dòng ⇒ khối co được khi thiếu chỗ (tên ellipsis), không rớt dòng."""
        css = _strip_comments(self.css)
        mq = '@media (min-width: 992px) and (max-width: 1199.98px)'
        i = css.find(mq)
        self.assertGreaterEqual(i, 0)
        blk = css[css.index('{', i):]
        body = re.search(r'\.wujia-store-current-block\s*\{([^{}]*)\}', blk).group(1)
        self.assertIn('min-width: 0', body)
        self.assertRegex(blk, r'li:has\(> \.wujia-store-current-block\)\s*\{\s*min-width: 0')
        # khối ôm nội dung ở mọi khổ PC, trần 430 của Figma
        self.assertIn('max-width: 430px', _rule(self.css, '.wujia-store-current-block'))

    def test_nhan_viet_khong_bi_viet_hoa_tung_chu(self):
        self.assertNotIn('capitalize', _rule(self.css, '.wujia-store-role-badge'))

    def test_chevron_mau_chinh_khong_co_lai(self):
        body = _rule(self.css, '.wujia-store-strip-chevron')
        self.assertIn('flex: 0 0 auto', body)
        self.assertIn('var(--wujia-brand-text)', body)   # WJ-PORTAL-UI-006: chữ/icon brand đậm ≥4.5

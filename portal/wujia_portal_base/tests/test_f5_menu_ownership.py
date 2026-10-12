"""F5a/E8b — danh sách vàng của menu + QUYỀN SỞ HỮU từng mục (guard nhiều module ⇒ L3a).

Vì sao ở `wujia_portal_base`: mỗi phép kiểm ở đây đụng 9–11 module cùng lúc; cắt nhỏ
về từng module thì không còn chỗ nào đo được THỨ TỰ và tính TOÀN VẸN của menu.
Mỗi module vẫn có test riêng cho mục của mình (`test_f5_nav_item.py`).

Ý nghĩa: gỡ một module portal ⇒ mục của nó biến mất, khung không gãy. Bằng chứng là
mỗi <li> mục menu thuộc `ir.model.data` của MODULE SỞ HỮU, không phải của khung.
"""
import re

from lxml import etree

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from .common import need_suite

# (id của <li>, module sở hữu, href, icon, nhãn) — thứ tự đúng như sidebar PC hiển thị.
# E8b (CMP-SN-001): 3 nhóm theo BA; Thông báo (chuông) và Tài khoản (avatar) không nằm ở sidebar.
GOLDEN_SIDENAV = [
    ('nav_item_home', 'wujia_portal_base', '/portal', 'feather icon-home', 'Trang chủ'),
    ('nav_item_order', 'wujia_portal_sale', '/portal/order', 'feather icon-shopping-cart', 'Đặt hàng'),
    ('nav_item_delivery', 'wujia_portal_delivery', '/portal/delivery', 'feather icon-truck', 'Giao hàng'),
    ('nav_item_history', 'wujia_portal_purchase_history', '/portal/purchase-history', 'feather icon-clock', 'Lịch sử đặt hàng'),
    ('nav_item_debt', 'wujia_portal_debt', '/portal/debt', 'feather icon-credit-card', 'Công nợ & thanh toán'),
    ('nav_item_return', 'wujia_portal_return', '/portal/return', 'feather icon-corner-up-left', 'Đổi trả / Bù hàng'),
    ('nav_item_exam', 'wujia_portal_exam', '/portal/exam', 'feather icon-edit', 'Đăng ký thi'),
    ('nav_item_knowledge', 'wujia_portal_knowledge', '/portal/knowledge', 'feather icon-book', 'Kiến thức'),
    ('nav_item_support', 'wujia_portal_support', '/portal/support', 'feather icon-life-buoy', 'Hỗ trợ'),
    ('nav_item_report', 'wujia_portal_report', '/portal/reports/orders', 'feather icon-bar-chart-2', 'Báo cáo'),
    # Khảo sát: view của anh Thái (priority 101), neo cuối nhóm "Hỗ trợ vận hành".
    ('nav_item_inspection', 'wujia_portal_inspection', '/portal/inspection', 'feather icon-clipboard', 'Khảo sát'),
]
# Thứ tự đầy đủ kèm tiêu đề nhóm.
GOLDEN_WITH_GROUPS = [
    'nav_header_main', 'nav_item_home', 'nav_item_order', 'nav_item_delivery', 'nav_item_history',
    'nav_header_finance', 'nav_item_debt', 'nav_item_return',
    'nav_header_ops', 'nav_item_exam', 'nav_item_knowledge', 'nav_item_support', 'nav_item_report',
    'nav_item_inspection', 'nav_end',
]

# Đường dẫn ⇒ mục phải sáng (None = không mục nào sáng).
ACTIVE_CASES = [
    ('/portal', 'nav_item_home'),
    ('/portal/order', 'nav_item_order'),
    ('/portal/purchase-history', 'nav_item_history'),
    ('/portal/return', 'nav_item_return'),
    ('/portal/return/new', 'nav_item_return'),
    ('/portal/reports/orders', 'nav_item_report'),
    # Không có mục sidebar: Tài khoản/Hồ sơ cửa hàng ở avatar, Thông báo ở chuông,
    # info-request thuộc Hồ sơ cửa hàng (avatar).
    ('/portal/profile', None),
    ('/portal/franchise-information', None),
    ('/portal/notification', None),
    ('/portal/info-request', None),
]


@tagged('post_install', '-at_install', 'wujia_f5')
class TestMenuOwnership(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.franchise = env['wujia.franchise.management'].create({
            'code': 'F5MN', 'name': 'F5 menu store', 'franchise_end_date': '2030-01-01',
            'partner_id': env['res.partner'].create({'name': 'F5 menu partner'}).id})
        cls.user = env['res.users'].create({
            'name': 'f5_menu', 'login': 'f5_menu', 'password': 'f5_menu',
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])]})
        env['wujia.franchise.member'].create({
            'user_id': cls.user.id, 'franchise_id': cls.franchise.id, 'role': 'owner'})
        # Quyền: staff một cửa hàng; "mixed" = staff ở cửa hàng đang chọn, manager nơi khác.
        cls.franchise2 = env['wujia.franchise.management'].create({
            'code': 'F5MN2', 'name': 'F5 menu store 2', 'franchise_end_date': '2030-01-01',
            'partner_id': env['res.partner'].create({'name': 'F5 menu partner 2'}).id})
        for login, rows in (('f5_staff', [(cls.franchise, 'staff')]),
                            ('f5_mixed', [(cls.franchise, 'staff'), (cls.franchise2, 'manager')])):
            user = env['res.users'].create({
                'name': login, 'login': login, 'password': login,
                'group_ids': [(6, 0, [env.ref('base.group_portal').id])]})
            for franchise, role in rows:
                env['wujia.franchise.member'].create({
                    'user_id': user.id, 'franchise_id': franchise.id, 'role': role})

    def _ids(self, login, store=None):
        self.authenticate(login, login)
        if store:
            self.opener.cookies.set('wujia_active_franchise_id', str(store.id))
        html = etree.HTML(self.url_open('/portal', timeout=30).text)
        return [li.get('id') for li in html.xpath("//ul[@id='main-menu-navigation']/li")]

    def _sidenav(self, route='/portal'):
        self.authenticate('f5_menu', 'f5_menu')
        res = self.url_open(route, timeout=30)
        self.assertEqual(res.status_code, 200, route)
        html = etree.HTML(res.text)
        ul = html.xpath("//ul[@id='main-menu-navigation']")
        self.assertTrue(ul, f'không thấy sidebar ở {route}')
        return ul[0]

    def test_sidenav_groups_in_ba_order(self):
        """3 nhóm BA (Chức năng chính / Tài chính & xử lý / Hỗ trợ vận hành), mục đúng nhóm."""
        need_suite(self)
        ul = self._sidenav()
        self.assertEqual([li.get('id') for li in ul.xpath('./li')], GOLDEN_WITH_GROUPS)
        heads = [re.sub(r'\s+', ' ', ''.join(li.itertext())).strip()
                 for li in ul.xpath("./li[contains(@class, 'navigation-header')]")]
        self.assertEqual(heads, ['Chức năng chính', 'Tài chính & xử lý', 'Hỗ trợ vận hành'])

    def test_sidenav_golden_list(self):
        """11 mục, đúng thứ tự, đúng href + icon + nhãn."""
        need_suite(self)
        items = [li for li in self._sidenav().xpath('./li')
                 if 'navigation-header' not in (li.get('class') or '') and li.get('id') != 'nav_end']
        self.assertEqual([li.get('id') for li in items],
                         [g[0] for g in GOLDEN_SIDENAV])
        for li, (nid, _mod, href, icon, label) in zip(items, GOLDEN_SIDENAV):
            link = li.xpath('./a')[0]
            self.assertEqual(link.get('href'), href, nid)
            text = re.sub(r'\s+', ' ', ''.join(link.itertext())).strip()
            self.assertEqual(text, label, nid)   # khớp TUYỆT ĐỐI: đổi nhãn là đỏ
            if icon:
                self.assertIn(icon, etree.tostring(link, encoding='unicode'), nid)

    def test_every_item_belongs_to_the_module_owning_the_route(self):
        """Mục menu nằm trong view của MODULE SỞ HỮU ⇒ gỡ module là mất mục."""
        need_suite(self)
        for nid, module, *_rest in GOLDEN_SIDENAV:
            shell = self.env.ref('wujia_portal_layout.layout_sidenav')
            views = shell + self.env['ir.ui.view'].search([('inherit_id', '=', shell.id)])
            owners = set()
            for view in views:
                # Chỉ tính view TẠO ra mục; view chỉ NHẮC id trong xpath neo không phải
                # chủ sở hữu.
                if not re.search(rf'<li[^>]*id="{nid}"', (view.arch or '').replace("'", '"')):
                    continue
                data = self.env['ir.model.data'].search(
                    [('model', '=', 'ir.ui.view'), ('res_id', '=', view.id)], limit=1)
                owners.add(data.module)
            self.assertEqual(owners, {module},
                             f'{nid} phải do {module} khai, đang thấy {owners}')

    def test_active_item_follows_the_route(self):
        need_suite(self)
        for route, nid in ACTIVE_CASES:
            ul = self._sidenav(route)
            active = [li.get('id') for li in ul.xpath('./li')
                      if 'active' in (li.get('class') or '')]
            self.assertEqual(active, [nid] if nid else [], route)
            # aria-current="page" đúng trên mục sáng, không mục nào khác.
            current = [a.getparent().get('id') for a in ul.xpath("./li/a[@aria-current='page']")]
            self.assertEqual(current, [nid] if nid else [], route)

    def test_items_render_by_permission(self):
        """Mục hiện theo quyền vào route (điều kiện controller), không chừa khoảng trống."""
        need_suite(self)
        owner = self._ids('f5_menu')
        self.assertIn('nav_item_debt', owner)
        self.assertIn('nav_item_report', owner)
        staff = self._ids('f5_staff')
        self.assertNotIn('nav_item_debt', staff)      # _debt_access: staff → không quyền
        self.assertNotIn('nav_item_report', staff)
        self.assertIn('nav_item_return', staff)
        mixed = self._ids('f5_mixed', store=self.franchise)
        self.assertNotIn('nav_item_debt', mixed)      # staff ở cửa hàng đang chọn
        self.assertNotIn('nav_item_report', mixed)    # manager ở cửa hàng khác không cấp quyền ở đây
        mixed2 = self._ids('f5_mixed', store=self.franchise2)
        self.assertIn('nav_item_debt', mixed2)
        self.assertIn('nav_item_report', mixed2)

    def test_bottomnav_more_button_is_active_when_no_tab_matches(self):
        """Nút "Thêm" sáng khi không tab nào sáng (hành vi Sprint 11)."""
        need_suite(self)
        self.authenticate('f5_menu', 'f5_menu')
        for route, more_active in (('/portal', False), ('/portal/order', False),
                                   ('/portal/support', True)):
            html = etree.HTML(self.url_open(route, timeout=30).text)
            more = html.xpath("//button[@data-wujia-more='toggle']")[0]
            self.assertEqual('is-active' in (more.get('class') or ''), more_active, route)
